import os
import json
import time
from mcp.server.fastmcp import FastMCP
from pathlib import Path

mcp = FastMCP("Superalgos")

SUPERALGOS_PATH = Path("Superalgos-master")
SIGNAL_DIR = SUPERALGOS_PATH / "Signals"

@mcp.tool()
def send_trade_signal(symbol: str, action: str, price: float, confidence: float, reason: str = "") -> str:
    """Send a deterministic trade signal directly to the Superalgos workspace."""
    os.makedirs(SIGNAL_DIR, exist_ok=True)
    
    signal = {
        "symbol": symbol,
        "action": action,
        "price": price,
        "confidence": confidence,
        "reason": reason,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "AetherOS_MCP"
    }
    
    signal_file = SIGNAL_DIR / f"signal_{symbol}_{int(time.time())}.json"
    with open(signal_file, 'w') as f:
        json.dump(signal, f, indent=2)
        
    return f"Signal successfully deposited at {signal_file}. Superalgos will ingest on next tick."

@mcp.tool()
def check_superalgos_status() -> str:
    """Check if the Superalgos trading engine is actively running and logging."""
    log_dir = SUPERALGOS_PATH / "Log-Files"
    if log_dir.exists() and any(log_dir.iterdir()):
        return "Superalgos Core is ONLINE and processing log files."
    return "Superalgos Core is OFFLINE or idle. No active log files detected."

if __name__ == "__main__":
    mcp.run()
