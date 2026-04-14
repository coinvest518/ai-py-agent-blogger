#!/usr/bin/env python3
from dotenv import load_dotenv
import os, sys, json
ROOT = os.getcwd()
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, '.env'))
from src.agent.tools.composio_tools import get_composio_client

c = get_composio_client()

print('--- TOOLKITS ---')
try:
    kits = c.toolkits.list()
    items = getattr(kits, 'items', None) or kits
    out = []
    for k in (items or []):
        if isinstance(k, dict):
            out.append({
                'slug': k.get('slug'),
                'name': k.get('name'),
                'version': k.get('version') or k.get('latest') or k.get('latest_version') or k.get('current_version')
            })
        else:
            out.append({'slug': getattr(k, 'slug', None), 'name': getattr(k, 'name', None), 'version': getattr(k, 'version', None)})
    print(json.dumps(out, indent=2))
except Exception as e:
    print('toolkits list failed:', e)

print('\n--- TOOLS (sample) ---')
try:
    tools = c.tools.get_raw_composio_tools()
    sample = []
    for t in (tools or [])[:40]:
        if isinstance(t, dict):
            tkit = t.get('toolkit') or {}
            sample.append({'slug': t.get('slug'), 'name': t.get('name'), 'toolkit': (tkit.get('slug') if isinstance(tkit, dict) else tkit)})
        else:
            sample.append({'slug': getattr(t, 'slug', None), 'name': getattr(t, 'name', None), 'toolkit': getattr(getattr(t, 'toolkit', None), 'slug', None)})
    print(json.dumps(sample, indent=2))
except Exception as e:
    print('tools list failed:', e)
