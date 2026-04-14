#!/usr/bin/env python3
"""Run the main graph.invoke() using the repository .env and print a short summary.

This is a lightweight runner created for local verification.
"""
from dotenv import load_dotenv
import os, sys, json

# ensure repo root on path
ROOT = os.getcwd()
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from src.agent.graph import graph

print('--- START: graph.invoke() ---')
final = graph.invoke({})
print('\n--- AGENT FINAL STATE (partial) ---')
print(json.dumps({'ai_strategy': final.get('ai_strategy'), 'memory_status': final.get('memory_status')}, default=str, indent=2)[:4000])
print('--- END ---')
