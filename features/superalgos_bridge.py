"""Superalgos Bridge — Connecting Aether OS to the Trading Engine.

Allows Draymond to pipe market opportunities directly into Superalgos
for deterministic execution and backtesting.
"""
import os
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
from config import cfg

logger = logging.getLogger("AetherOS.Superalgos")

class SuperalgosBridge:
    def __init__(self):
        self.superalgos_path = Path("Superalgos-master")
        self.signal_dir = self.superalgos_path / "Signals"
        os.makedirs(self.signal_dir, exist_ok=True)

    def send_trade_signal(self, symbol: str, action: str, price: float, confidence: float) -> Dict:
        """Send a signal to the Superalgos task server."""
        signal = {
            "symbol": symbol,
            "action": action,
            "price": price,
            "confidence": confidence,
            "timestamp": os.getenv("CURRENT_TIME", "2026-05-10T00:00:00"),
            "source": "AetherOS_OpportunityScout"
        }
        
        # Save signal to Superalgos signaling directory
        signal_file = self.signal_dir / f"signal_{symbol}_{int(time.time())}.json"
        try:
            import time
            with open(signal_file, 'w') as f:
                json.dump(signal, f, indent=2)
            
            logger.info(f"Signal sent to Superalgos: {action} {symbol} @ {price}")
            return {"status": "success", "file": str(signal_file)}
        except Exception as e:
            logger.error(f"Failed to send signal to Superalgos: {e}")
            return {"status": "error", "message": str(e)}

    def check_engine_status(self) -> Dict:
        """Check if Superalgos is actually running."""
        # Check for active logs or lock files
        log_dir = self.superalgos_path / "Log-Files"
        if log_dir.exists() and any(log_dir.iterdir()):
            return {"status": "running", "engine": "Superalgos Core"}
        return {"status": "stopped", "reason": "No active log files found"}

_BRIDGE: Optional[SuperalgosBridge] = None

def get_superalgos_bridge() -> SuperalgosBridge:
    global _BRIDGE
    if _BRIDGE is None: _BRIDGE = SuperalgosBridge()
    return _BRIDGE
