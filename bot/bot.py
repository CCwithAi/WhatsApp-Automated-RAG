"""
WhatsApp AI Bot — Entry Point
Loads config, runs DB migrations, starts APScheduler with reply + marketing jobs.
"""

import logging
import signal
import sys
import time

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from config import load_config
from db import BridgeDB, TrackingDB
from reply_engine import ReplyEngine
from marketing_engine import MarketingEngine

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("whatsapp-bot")


def main():
    logger.info("=" * 50)
    logger.info("  WhatsApp AI Bot — Starting up")
    logger.info("=" * 50)

    # ── Load config ──
    config = load_config()
    logger.info(f"Instance: {config.instance_name} ({config.business_name})")
    logger.info(f"Bridge API: {config.bridge_api_url}")
    logger.info(f"Bridge DB: {config.bridge_db_path}")
    logger.info(f"LLM: {config.llm.base_url} (model: {config.llm.model})")
    logger.info(f"Check interval: {config.check_interval_minutes} min")
    logger.info(f"Lookback: {config.lookback_minutes} min")
    logger.info(f"Marketing: {'enabled' if config.marketing.enabled else 'disabled'}")

    # ── Wait for bridge DB to exist ──
    logger.info("Waiting for bridge database...")
    retries = 0
    max_retries = 60  # 5 minutes at 5s intervals
    while retries < max_retries:
        try:
            bridge_db = BridgeDB(config.bridge_db_path)
            bridge_db.get_recent_messages(1)  # Test connection
            logger.info("Bridge database ready")
            break
        except Exception:
            retries += 1
            if retries % 12 == 0:
                logger.info(f"Still waiting for bridge DB... ({retries * 5}s)")
            time.sleep(5)
    else:
        logger.warning("Bridge DB not found after 5 min — starting anyway (will retry on each tick)")
        bridge_db = BridgeDB(config.bridge_db_path)

    # ── SQL Server migrations ──
    logger.info("Running SQL Server migrations...")
    tracking_db = TrackingDB(config)
    try:
        tracking_db.run_migrations()
    except Exception as e:
        logger.error(f"SQL Server migration failed: {e}")
        logger.error("Bot will retry on first tick. Continuing startup...")

    # ── Engines ──
    reply_engine = ReplyEngine(config, bridge_db, tracking_db)
    marketing_engine = MarketingEngine(config, bridge_db, tracking_db)

    # ── Scheduler ──
    scheduler = BlockingScheduler()

    # Reply job: every N minutes
    scheduler.add_job(
        reply_engine.run_check,
        trigger=IntervalTrigger(minutes=config.check_interval_minutes),
        id="reply_check",
        name=f"Reply Check ({config.instance_name})",
        max_instances=1,
        coalesce=True,
    )

    # Marketing job: cron expression from config
    if config.marketing.enabled:
        cron_parts = config.marketing.cron.split()
        if len(cron_parts) == 5:
            scheduler.add_job(
                marketing_engine.run_broadcast,
                trigger=CronTrigger(
                    minute=cron_parts[0],
                    hour=cron_parts[1],
                    day=cron_parts[2],
                    month=cron_parts[3],
                    day_of_week=cron_parts[4],
                ),
                id="marketing_broadcast",
                name=f"Marketing Broadcast ({config.instance_name})",
                max_instances=1,
                coalesce=True,
            )
            logger.info(f"Marketing cron: {config.marketing.cron}")

    # ── Run first check immediately ──
    logger.info("Running initial reply check...")
    try:
        reply_engine.run_check()
    except Exception as e:
        logger.error(f"Initial check failed (non-fatal): {e}")

    # ── Graceful shutdown ──
    def shutdown(signum, frame):
        logger.info("Shutdown signal received...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # ── Start ──
    logger.info("Scheduler started — bot is running")
    scheduler.start()


if __name__ == "__main__":
    main()
