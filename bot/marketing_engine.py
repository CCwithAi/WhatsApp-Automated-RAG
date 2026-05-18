"""
Marketing broadcast engine for WhatsApp Bot.
Sends promotional messages to group chats from the marketing queue.
"""

import json
import logging
import requests
from typing import List, Dict

from config import BotConfig
from db import BridgeDB, TrackingDB

logger = logging.getLogger("whatsapp-bot.marketing")


class MarketingEngine:
    """Broadcast marketing messages to WhatsApp group chats."""

    def __init__(self, config: BotConfig, bridge_db: BridgeDB, tracking_db: TrackingDB):
        self.config = config
        self.bridge_db = bridge_db
        self.tracking_db = tracking_db

    def run_broadcast(self):
        """Main marketing loop: called on cron schedule."""
        if not self.config.marketing.enabled:
            logger.debug("Marketing disabled, skipping")
            return

        logger.info("=== Marketing broadcast started ===")

        pending = self.tracking_db.get_pending_marketing()
        if not pending:
            logger.info("No pending marketing messages")
            return

        all_groups = self.bridge_db.get_group_chats()
        logger.info(f"Found {len(pending)} pending messages, {len(all_groups)} group chats")

        for msg in pending:
            marketing_id = msg["id"]
            content = msg["content"]
            target_groups_raw = msg.get("target_groups")

            # Determine target groups
            if target_groups_raw:
                try:
                    target_jids = json.loads(target_groups_raw)
                    groups = [g for g in all_groups if g["jid"] in target_jids]
                except (json.JSONDecodeError, TypeError):
                    groups = all_groups
            else:
                groups = all_groups

            if not groups:
                logger.warning(f"Marketing #{marketing_id}: no target groups found")
                self.tracking_db.mark_marketing_sent(marketing_id)
                continue

            sent_count = 0
            fail_count = 0

            for group in groups:
                group_jid = group["jid"]
                group_name = group.get("name", group_jid)

                success = self._send_message(group_jid, content)
                self.tracking_db.log_marketing_delivery(
                    marketing_id, group_jid, success,
                    None if success else "Send failed"
                )

                if success:
                    sent_count += 1
                    logger.info(f"  ✓ Sent to {group_name}")
                else:
                    fail_count += 1
                    logger.error(f"  ✗ Failed: {group_name}")

            self.tracking_db.mark_marketing_sent(marketing_id)
            logger.info(f"Marketing #{marketing_id}: {sent_count} sent, {fail_count} failed")

        logger.info("=== Marketing broadcast complete ===")

    def _send_message(self, recipient: str, message: str) -> bool:
        """Send a message via the Go bridge REST API."""
        try:
            url = f"{self.config.bridge_api_url}/send"
            payload = {"recipient": recipient, "message": message}
            response = requests.post(url, json=payload, timeout=15)

            if response.status_code == 200:
                result = response.json()
                return result.get("success", False)
            else:
                logger.error(f"Bridge API error: HTTP {response.status_code}")
                return False
        except requests.RequestException as e:
            logger.error(f"Bridge API request error: {e}")
            return False
