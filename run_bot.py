"""
Entry point for the automated trading bot.

Usage:
    python run_bot.py

Required environment variables (see .env.example):
    OANDA_ACCOUNT_ID, OANDA_API_KEY
    BINANCE_API_KEY, BINANCE_SECRET_KEY
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import logging
import os
import signal
import sys
import time

from dotenv import load_dotenv

load_dotenv()


def _configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _validate_env() -> None:
    required = {
        "OANDA": ["OANDA_ACCOUNT_ID", "OANDA_API_KEY"],
        "BINANCE": ["BINANCE_API_KEY", "BINANCE_SECRET_KEY"],
        "TELEGRAM": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
    }
    missing = []
    for group, keys in required.items():
        for key in keys:
            if not os.getenv(key):
                missing.append(key)
    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)


def main() -> None:
    _configure_logging()
    logger = logging.getLogger(__name__)

    logger.info("=== Forex/Crypto Trading Bot starting ===")

    _validate_env()

    # Lazy imports after env validation so missing deps give clear messages
    try:
        from bot.broker.binance import BinanceBroker
        from bot.broker.oanda import OANDABroker
        from bot.reporter import TelegramReporter
        from bot.scheduler import build_scheduler
        from bot.state import TradeState
    except ImportError as e:
        logger.error("Missing dependency: %s", e)
        logger.error("Run: pip install -r requirements.txt")
        sys.exit(1)

    try:
        brokers = {
            "OANDA": OANDABroker(),
            "BINANCE": BinanceBroker(),
        }
    except EnvironmentError as e:
        logger.error("Broker init failed: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error initialising brokers: %s", e)
        sys.exit(1)

    state = TradeState()
    reporter = TelegramReporter()
    scheduler = build_scheduler(brokers, state, reporter)

    # Graceful shutdown on SIGTERM / SIGINT
    def _shutdown(signum, frame):
        logger.info("Received signal %d — shutting down scheduler...", signum)
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped. Goodbye.")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    scheduler.start()
    logger.info("Scheduler started. Jobs: %s", [j.id for j in scheduler.get_jobs()])
    reporter.send_error_alert("Bot started", Exception("Bot is online and running in paper-trade mode."))

    # Block main thread indefinitely
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        _shutdown(0, None)


if __name__ == "__main__":
    main()
