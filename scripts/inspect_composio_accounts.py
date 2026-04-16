#!/usr/bin/env python3
import os
import sys
import json

# Ensure repo root is on sys.path so `src` imports work
sys.path.insert(0, os.getcwd())

import importlib.util
from pathlib import Path

# Load composio_tools directly to avoid heavy package imports
mod_path = Path(os.getcwd()) / "src" / "agent" / "tools" / "composio_tools.py"
spec = importlib.util.spec_from_file_location("composio_tools", str(mod_path))
composio_tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(composio_tools)
get_composio_client = composio_tools.get_composio_client
_execute_with_fallback = getattr(composio_tools, "_execute_with_fallback", None)

entity = os.getenv('COMPOSIO_ENTITY_ID') or os.getenv('COMPOSIO_USER_ID')
print(json.dumps({'COMPOSIO_ENTITY_ID': entity}, indent=2))

client = get_composio_client()
try:
    resp = client.connected_accounts.list(user_ids=[entity], statuses=["ACTIVE"]) if entity else client.connected_accounts.list(statuses=["ACTIVE"])
    items = getattr(resp, 'items', None) or resp or []
    out = []
    for it in (items or []):
        try:
            if isinstance(it, dict):
                out.append({
                    'slug': it.get('slug'),
                    'alias': it.get('alias'),
                    'word_id': it.get('word_id'),
                    'state': it.get('state'),
                })
            else:
                out.append({
                    'slug': getattr(it, 'slug', None),
                    'alias': getattr(it, 'alias', None),
                    'word_id': getattr(it, 'word_id', None),
                    'state': getattr(it, 'state', None),
                })
        except Exception as e:
            out.append({'error': str(e)})
    print(json.dumps(out, indent=2, default=str)[:8000])
except Exception as e:
    print('ERROR listing connected accounts:', str(e))
