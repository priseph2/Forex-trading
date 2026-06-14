import asyncio
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class TelegramReporter:
    def __init__(self):
        self._token = os.getenv("TELEGRAM_BOT_TOKEN")
        self._chat_id = os.getenv("TELEGRAM_CHAT_ID")

    def _send(self, text: str) -> None:
        if not self._token or not self._chat_id:
            logger.warning("Telegram not configured — skipping message")
            return

        async def _inner():
            from telegram import Bot
            async with Bot(self._token) as bot:
                await bot.send_message(
                    chat_id=self._chat_id,
                    text=text,
                    parse_mode="HTML",
                )

        try:
            asyncio.run(_inner())
        except Exception as e:
            logger.error("Telegram send failed: %s", e)

    def send_trade_alert(self, pair: str, broker: str, direction: str,
                         entry: float, sl: float, tp: float, confidence: float) -> None:
        icon = "🟢" if direction == "BUY" else "🔴"
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        self._send(
            f"🔔 <b>TRADE OPENED</b>\n"
            f"📈 Pair: {pair} ({broker})\n"
            f"Direction: {direction} {icon}\n"
            f"Entry:       {entry:.5f}\n"
            f"Stop Loss:   {sl:.5f} (-1%)\n"
            f"Take Profit: {tp:.5f} (+1%)\n"
            f"Confidence:  {confidence * 100:.0f}%\n"
            f"⏰ {ts}"
        )

    def send_trade_closed_alert(self, pair: str, direction: str,
                                exit_price: float, pnl: float) -> None:
        won = pnl > 0
        icon = "✅" if won else "❌"
        label = "WIN" if won else "LOSS"
        self._send(
            f"{icon} <b>TRADE CLOSED ({label})</b>\n"
            f"Pair: {pair} {direction}\n"
            f"Exit: {exit_price:.5f}\n"
            f"P&amp;L: {'+'if won else ''}{pnl:.2f} USD"
        )

    def send_daily_report(self, summary: dict, trades: list[dict]) -> None:
        date = summary.get("date", "today")
        total = summary.get("total_trades", 0)
        wins = summary.get("wins", 0)
        losses = summary.get("losses", 0)
        pnl = summary.get("gross_pnl", 0.0)
        sign = "+" if pnl >= 0 else ""

        lines = [
            f"📊 <b>DAILY REPORT — {date}</b>",
            f"Trades: {total} | Wins: {wins} ✅ | Losses: {losses} ❌",
            f"Gross P&amp;L: {sign}${pnl:.2f}",
        ]

        if trades:
            lines.append("────────────────")
            for i, t in enumerate(trades, 1):
                p = t.get("pnl") or 0
                icon = "✅" if p > 0 else "❌"
                lines.append(
                    f"{i}. {t['pair']} {t['direction']} → "
                    f"{'+'if p>=0 else ''}{p:.2f} USD {icon}"
                )
        else:
            lines.append("No trades today — no qualifying signals.")

        self._send("\n".join(lines))

    def send_error_alert(self, context: str, error: Exception) -> None:
        self._send(
            f"🚨 <b>BOT ERROR</b>\n"
            f"Context: {context}\n"
            f"Error: {str(error)[:300]}"
        )
