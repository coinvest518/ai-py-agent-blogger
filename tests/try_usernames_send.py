import importlib.util
import os

# load telegram_agent.py directly (avoid package side-effects)
mod_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'agent', 'telegram_agent.py'))
spec = importlib.util.spec_from_file_location('tg', mod_path)
tg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tg)

usernames = ['@yieldbotdefi', '@yieldbotai', '@ybotai_bot']
print('Using BOT_TOKEN set?', bool(getattr(tg, 'TELEGRAM_BOT_TOKEN', None)))

for u in usernames:
    print('\n--- Attempting send to', u)
    res = tg.send_message(u, f'Test message to {u} (direct Bot API)', use_direct=True)
    print('Result:', res)
    # also try get_chat_info via direct GET (if available)
    try:
        print('Trying getChat via direct Bot API...')
        import requests
        token = getattr(tg, 'TELEGRAM_BOT_TOKEN', None)
        if token:
            r = requests.get(f'https://api.telegram.org/bot{token}/getChat', params={'chat_id': u}, timeout=10)
            print('getChat status:', r.status_code, r.json())
    except Exception as e:
        print('getChat error:', e)
