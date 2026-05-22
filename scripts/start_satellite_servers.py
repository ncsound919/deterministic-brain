
import subprocess
import sys
from pathlib import Path

def start_servers():
    import os
    skilltech_dir = Path(os.getenv("SKILLTECH_ROOT", Path.home() / "Downloads" / "Skilltech"))
    
    # 1. BookBridge (Port 8778 MCP)
    bookbridge_path = skilltech_dir / "BookBridge--main"
    print(f"Starting BookBridge at {bookbridge_path}...")
    subprocess.Popen([sys.executable, "main.py"], cwd=str(bookbridge_path))
    
    # 2. VibeServe (Port based on implementation, usually stdio or custom port)
    # Based on SUMMARY.md, it's python mcp_ui_optimizer_v4.py or main.py update
    vibeserve_path = skilltech_dir / "VibeServe-MCP"
    print(f"Starting VibeServe at {vibeserve_path}...")
    subprocess.Popen([sys.executable, "vibeserve.py"], cwd=str(vibeserve_path))
    
    # 3. Business Logic MCP (Node.js stdio)
    # This one we will likely run via stdio when called, or start as a long-running process if it supports HTTP
    # The file is 'Business logic mcp' (no extension, but it's a node script)
    biz_logic_path = skilltech_dir / "Business-Logic-MCP-main"
    print(f"Business Logic MCP found at {biz_logic_path}. Will be invoked via stdio.")

if __name__ == "__main__":
    start_servers()
    print("Satellite servers initiated.")
