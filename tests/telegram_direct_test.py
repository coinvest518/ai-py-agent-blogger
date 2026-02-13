import os
import sys
import importlib.util

# Load telegram_agent.py directly to avoid importing package-level side-effects
mod_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'agent', 'telegram_agent.py'))
spec = importlib.util.spec_from_file_location('telegram_agent_local', mod_path)
tg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tg)

print('BOT_TOKEN set?', bool(getattr(tg, 'TELEGRAM_BOT_TOKEN', None)))
res = tg.send_to_group('Test message — direct BOT API test (from repo).', use_direct=True)
print('RESULT:', res)
