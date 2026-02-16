import os
import logging
import json

os.chdir(r"C:\Users\mildh\Downloads\ai-studio\ai-agent")
import sys
# ensure project root (ai-agent) is on sys.path so `src` imports work
sys.path.insert(0, os.getcwd())
logging.basicConfig(level=logging.INFO)
from src.agent.graph import graph

print('--- START: graph.invoke() ---')
final = graph.invoke({})
print('\n--- AGENT FINAL STATE (partial) ---')
print(json.dumps({'ai_strategy': final.get('ai_strategy'), 'memory_status': final.get('memory_status')}, default=str, indent=2)[:4000])
print('--- END ---')
