"""
Backup PnL database to external storage.

Supports:
- S3 (AWS, MinIO, etc.)
- Local file system
- Webhook/API endpoint
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

LOG = logging.getLogger("pnl_backup")


class PnLBackup:
    """Backup PnL database to external storage."""

    def __init__(self, db_path: str, backup_config: Optional[Dict[str, Any]] = None):
        self.db_path = db_path
        self.config = backup_config or {}
        self.enabled = self.config.get("enabled", False)
        self.backup_interval_seconds = self.config.get("interval_seconds", 3600)  # 1 hour default
        self._last_backup_time = 0.0

    async def backup(self) -> bool:
        """Perform backup if enabled and interval has passed."""
        if not self.enabled:
            return False

        now = time.time()
        if now - self._last_backup_time < self.backup_interval_seconds:
            return False

        try:
            # Try S3 backup first
            if self.config.get("s3"):
                success = await self._backup_to_s3()
                if success:
                    self._last_backup_time = now
                    return True

            # Try local backup
            if self.config.get("local_path"):
                success = await self._backup_to_local()
                if success:
                    self._last_backup_time = now
                    return True

            # Try webhook backup
            if self.config.get("webhook_url"):
                success = await self._backup_to_webhook()
                if success:
                    self._last_backup_time = now
                    return True

            return False
        except Exception as e:
            LOG.exception(f"[pnl_backup] Error during backup: {e}")
            return False

    async def _backup_to_s3(self) -> bool:
        """Backup to S3-compatible storage."""
        try:
            import boto3
            from botocore.exceptions import ClientError

            s3_config = self.config["s3"]
            bucket = s3_config["bucket"]
            key_prefix = s3_config.get("key_prefix", "pnl_backups/")

            # Create S3 client
            s3_client = boto3.client(
                "s3",
                endpoint_url=s3_config.get("endpoint_url"),  # For MinIO
                aws_access_key_id=s3_config.get("access_key_id") or os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=s3_config.get("secret_access_key") or os.environ.get("AWS_SECRET_ACCESS_KEY"),
                region_name=s3_config.get("region", "us-east-1"),
            )

            # Create backup filename with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            key = f"{key_prefix}pnl_trades_{timestamp}.db"

            # Upload database file
            s3_client.upload_file(self.db_path, bucket, key)

            LOG.info(f"[pnl_backup] Backed up to S3: s3://{bucket}/{key}")
            return True
        except ImportError:
            LOG.warning("[pnl_backup] boto3 not installed, skipping S3 backup")
            return False
        except Exception as e:
            LOG.exception(f"[pnl_backup] S3 backup failed: {e}")
            return False

    async def _backup_to_local(self) -> bool:
        """Backup to local file system."""
        try:
            local_path = Path(self.config["local_path"])
            local_path.mkdir(parents=True, exist_ok=True)

            # Create backup filename with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_file = local_path / f"pnl_trades_{timestamp}.db"

            # Copy database file
            shutil.copy2(self.db_path, backup_file)

            # Keep only last N backups
            max_backups = self.config.get("max_backups", 10)
            backups = sorted(local_path.glob("pnl_trades_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old_backup in backups[max_backups:]:
                old_backup.unlink()
                LOG.debug(f"[pnl_backup] Removed old backup: {old_backup}")

            LOG.info(f"[pnl_backup] Backed up to local: {backup_file}")
            return True
        except Exception as e:
            LOG.exception(f"[pnl_backup] Local backup failed: {e}")
            return False

    async def _backup_to_webhook(self) -> bool:
        """Backup to webhook/API endpoint."""
        try:
            import aiohttp

            webhook_url = self.config["webhook_url"]

            # Read database and convert to JSON
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades ORDER BY exit_time DESC")

            columns = [desc[0] for desc in cursor.execute("PRAGMA table_info(trades)").fetchall()]
            trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
            conn.close()

            # Send to webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json={
                        "timestamp": datetime.utcnow().isoformat(),
                        "trade_count": len(trades),
                        "trades": trades,
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        LOG.info(f"[pnl_backup] Backed up {len(trades)} trades to webhook")
                        return True
                    else:
                        LOG.warning(f"[pnl_backup] Webhook returned status {resp.status}")
                        return False
        except ImportError:
            LOG.warning("[pnl_backup] aiohttp not installed, skipping webhook backup")
            return False
        except Exception as e:
            LOG.exception(f"[pnl_backup] Webhook backup failed: {e}")
            return False

