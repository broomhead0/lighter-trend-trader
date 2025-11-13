# core/state_store.py
"""Simplified state store for trend trader."""
from __future__ import annotations

import time
from typing import Dict, Optional


class StateStore:
    """Tracks live mid prices for markets."""

    def __init__(self):
        self._mids: Dict[str, float] = {}

    def set_mid(self, market_id: str, price: float) -> None:
        """Set mid price for a market."""
        self._mids[market_id] = float(price)

    def update_mid(self, market_id: str, price: float) -> None:
        """Update mid price, accepting float."""
        self._mids[market_id] = float(price)

    def get_mid(self, market_id: str) -> Optional[float]:
        """Get mid price for a market."""
        return self._mids.get(market_id)

    def now(self) -> float:
        """Get current time."""
        return time.time()

