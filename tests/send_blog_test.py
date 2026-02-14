import runpy
import json
import pathlib

# Execute blog_email_agent.py in isolation and get its namespace
ns = runpy.run_path('src/agent/blog_email_agent.py')
update_profile = ns.get('update_business_profile_from_shop')
generate_and_send = ns.get('generate_and_send_blog')
_load_profile = ns.get('_load_business_profile')

print('Loaded blog_email_agent helpers')

profile = _load_profile()
shop = profile.get('shop_page') or profile.get('buymeacoffee')
if shop:
    print('Refreshing business profile from', shop)
    updated = update_profile([shop])
    print('Profile products count:', len(updated.get('products', [])))
else:
    print('No shop URL found in business_profile.json')

# Use README.md as trend_data seed (if exists)
readme_path = pathlib.Path('README.md')
if readme_path.exists():
    trend_data = readme_path.read_text(encoding='utf-8')[:2000]
    print('Using README.md as trend_data (first 2000 chars)')
else:
    trend_data = 'Business automation and AI trends for small businesses.'
    print('README.md not found; using fallback trend data')

print('Generating and sending blog...')
result = generate_and_send(trend_data)
print('\n=== generate_and_send_blog result ===')
print(json.dumps(result, indent=2, ensure_ascii=False))
