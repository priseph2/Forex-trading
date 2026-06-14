import logging
import os
from datetime import datetime, timezone

from apscheduler.events import EVENT_JOB_ERROR
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from bot import risk
from bot.broker.base import BrokerError
from bot.scanner import get_top_candidates

logger = logging.getLogger(__name__)

MAX_OPEN_TRADES = int(os.getenv("BOT_MAX_OPEN_TRADES", "2"))


# ── Jobs ─────────────────────────────────────────────────────────────────────

def scan_and_trade(brokers: dict, state, reporter) -> None:
    logger.info("scan_and_trade: starting")

    open_count = state.get_open_trade_count()
    if open_count >= MAX_OPEN_TRADES:
        logger.info("scan_and_trade: max open trades reached (%d), skipping", open_count)
        return

    open_trades = state.get_open_trades()
    exclude = {t["pair"] for t in open_trades}

    slots = MAX_OPEN_TRADES - open_count
    candidates = get_top_candidates(max_candidates=slots, exclude_pairs=exclude)

    if not candidates:
        logger.info("scan_and_trade: no qualifying signals today")
        return

    for candidate in candidates:
        broker = brokers.get(candidate.broker)
        if broker is None:
            logger.warning("No broker instance for %s, skipping %s", candidate.broker, candidate.pair)
            continue

        try:
            balance = broker.get_balance()
            entry_price = broker.get_price(candidate.pair)
            params = risk.calculate_position(
                direction=candidate.direction,
                entry_price=entry_price,
                account_balance=balance,
                broker=broker.name,
            )
            if not risk.validate_position(params):
                logger.warning("Position too small for %s (balance=%.2f)", candidate.pair, balance)
                reporter.send_error_alert(
                    f"Insufficient balance for {candidate.pair}",
                    Exception(f"units={params.units}, balance={balance:.2f}")
                )
                continue

            broker_trade_id = broker.place_order(
                pair=candidate.pair,
                direction=candidate.direction,
                units=params.units,
                stop_loss=params.stop_loss,
                take_profit=params.take_profit,
            )
            state.insert_trade(
                pair=candidate.pair,
                broker=broker.name,
                direction=candidate.direction,
                entry_price=params.entry_price,
                stop_loss=params.stop_loss,
                take_profit=params.take_profit,
                units=params.units,
                broker_trade_id=broker_trade_id,
            )
            reporter.send_trade_alert(
                pair=candidate.pair,
                broker=broker.name,
                direction=candidate.direction,
                entry=params.entry_price,
                sl=params.stop_loss,
                tp=params.take_profit,
                confidence=candidate.confidence,
            )
        except BrokerError as e:
            logger.error("Order failed for %s: %s", candidate.pair, e)
            reporter.send_error_alert(f"Order failed for {candidate.pair}", e)
        except Exception as e:
            logger.error("Unexpected error for %s: %s", candidate.pair, e)
            reporter.send_error_alert(f"Unexpected error for {candidate.pair}", e)


def monitor_positions(brokers: dict, state, reporter) -> None:
    open_trades = state.get_open_trades()
    if not open_trades:
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for trade in open_trades:
        broker = brokers.get(trade["broker"])
        if broker is None:
            continue
        try:
            live_ids = {t["trade_id"] for t in broker.get_open_trades()}
            if trade["broker_trade_id"] in live_ids:
                continue  # still open, nothing to do

            # Trade was auto-closed by broker (SL or TP hit)
            closed = broker.close_trade(trade["broker_trade_id"])
            pnl = closed.get("realised_pnl", 0.0)
            state.close_trade(
                trade_id=trade["id"],
                exit_price=closed["exit_price"],
                pnl=pnl,
                closed_at=closed["closed_at"],
            )
            state.upsert_daily_summary(today)
            reporter.send_trade_closed_alert(
                pair=trade["pair"],
                direction=trade["direction"],
                exit_price=closed["exit_price"],
                pnl=pnl,
            )
        except BrokerError as e:
            logger.error("Monitor failed for trade %d: %s", trade["id"], e)
            reporter.send_error_alert(f"Monitor failed for trade {trade['id']}", e)
        except Exception as e:
            logger.error("Unexpected monitor error for trade %d: %s", trade["id"], e)


def send_daily_report(state, reporter) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state.upsert_daily_summary(today)
    summary = state.get_daily_summary(today) or {"date": today, "total_trades": 0,
                                                   "wins": 0, "losses": 0, "gross_pnl": 0.0}
    trades = state.get_all_trades_for_date(today)
    reporter.send_daily_report(summary, trades)


# ── Scheduler factory ─────────────────────────────────────────────────────────

def build_scheduler(brokers: dict, state, reporter) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")

    scheduler.add_job(
        func=scan_and_trade,
        trigger=CronTrigger(hour=0, minute=5, timezone="UTC"),
        id="scan_and_trade",
        kwargs={"brokers": brokers, "state": state, "reporter": reporter},
        max_instances=1,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        func=monitor_positions,
        trigger=CronTrigger(minute="*/30", timezone="UTC"),
        id="monitor_positions",
        kwargs={"brokers": brokers, "state": state, "reporter": reporter},
        max_instances=1,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        func=send_daily_report,
        trigger=CronTrigger(hour=22, minute=0, timezone="UTC"),
        id="daily_report",
        kwargs={"state": state, "reporter": reporter},
        max_instances=1,
    )

    def _on_job_error(event):
        logger.error("Scheduler job %s crashed: %s", event.job_id, event.exception)
        reporter.send_error_alert(f"Job '{event.job_id}' crashed", event.exception)

    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
    return scheduler
