import importlib.util
import os

# Load module directly to avoid importing package-level modules with heavy deps
mod_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'agent', 'telegram_agent.py'))
spec = importlib.util.spec_from_file_location('tg_local', mod_path)
tg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tg)

print('COMPOSIO_API_KEY set?', bool(os.getenv('COMPOSIO_API_KEY')))
print('TELEGRAM_ENTITY_ID set?', bool(os.getenv('TELEGRAM_ENTITY_ID')))

print('\n== GET ME ==')
info = tg.get_bot_info()
print(info)

print('\n== GET UPDATES ==')
updates = tg.get_updates(limit=10, timeout=0)
print(updates)

print('\n== SEND TO GROUP (username fallback) ==')
res = tg.send_to_group('Automated test message from repo (Composio v3).')
print(res)
