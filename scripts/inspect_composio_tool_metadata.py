from pathlib import Path
from dotenv import load_dotenv
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(dotenv_path=Path('.env'))
from src.agent.tools.composio_tools import get_composio_client

client = get_composio_client()
response = client.tools.get_raw_composio_tools()
print('total tools', len(response or []))
for t in response or []:
    slug = t.get('slug') if isinstance(t, dict) else getattr(t, 'slug', None)
    toolkit = t.get('toolkit') if isinstance(t, dict) else getattr(t, 'toolkit', None)
    if toolkit is not None:
        if isinstance(toolkit, dict):
            kslug = toolkit.get('slug')
            kver = toolkit.get('version') or t.get('toolkit_version')
        else:
            kslug = getattr(toolkit, 'slug', None)
            kver = getattr(toolkit, 'version', None) or getattr(t, 'toolkit_version', None)
    else:
        kslug = None
        kver = None
    if 'linkedin' in (slug or '').lower() or 'linkedin' in (kslug or '').lower() or 'LINKEDIN_CREATE_LINKED_IN_POST'.upper() in (slug or '').upper():
        print('MATCH', slug, 'toolkit_slug=', kslug, 'toolkit_ver=', kver)
    elif 'linkedin' in (kslug or '').lower():
        print('TOOLKIT_MATCH', slug, 'toolkit_slug=', kslug, 'toolkit_ver=', kver)
