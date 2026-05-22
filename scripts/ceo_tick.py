"""Run the Autonomous CEO strategy loop."""
import sys
from pathlib import Path

# Add root to sys.path
root = Path(__file__).parent.parent
sys.path.append(str(root))

from features.autonomous_ceo import get_ceo
from loguru import logger

def main():
    logger.info("CEO Tick Starting...")
    ceo = get_ceo()
    decision = ceo.execute_strategy()
    
    print("\n--- CEO DECISION MATRIX ---")
    print(f"Total Projects Evaluated: {len(decision.get('decisions', []))}")
    for d in decision.get('decisions', []):
        print(f"  [{d['project']}] -> {d['action']} : {d['reason']}")
    
    marketing = decision.get('marketing_sync', {})
    actions = marketing.get('actions', [])
    print(f"\nMarketing Sync Actions: {len(actions)}")
    for a in actions:
        print(f"  [Calendar] Generated content for: {a['event']}")
        
    print("\nCEO Tick Complete.")

if __name__ == "__main__":
    main()
