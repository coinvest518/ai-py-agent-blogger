import os
import logging
import json
from pathlib import Path
import sys

# Ensure we're running from the repository root and load envs if present
REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))
logging.basicConfig(level=logging.INFO)
from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

from src.agent.graph import execute

print('--- START: graph.execute() ---')
final = execute({})
print('\n--- AGENT FINAL STATE (partial) ---')
print(json.dumps({'ai_strategy': final.get('ai_strategy'), 'memory_status': final.get('memory_status')}, default=str, indent=2)[:4000])
print('--- END ---')
