from pathlib import Path
from dotenv import load_dotenv
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.agent.tools.composio_tools import get_composio_client

load_dotenv(dotenv_path=Path('.env'))
client = get_composio_client()
entity = os.getenv('COMPOSIO_ENTITY_ID') or os.getenv('COMPOSIO_USER_ID')
print('entity', entity)
print('has tools execute', hasattr(client.tools, 'execute'))
print('has get_raw_composio_tool_by_slug', hasattr(client.tools, 'get_raw_composio_tool_by_slug'))
print('has get_raw_composio_tools', hasattr(client.tools, 'get_raw_composio_tools'))

try:
    tools = client.tools.get_raw_composio_tools(toolkits=['linkedin'])
    print('linkedin tool count', len(tools))
    for t in tools:
        print('slug=', getattr(t, 'slug', None), 'title=', getattr(t, 'title', None), 'version=', getattr(t, 'version', None), 'toolkit=', getattr(t, 'toolkit', None))
except Exception as e:
    import traceback
    traceback.print_exc()

for slug in ['LINKEDIN_GET_MY_INFO', 'GET_MY_INFO', 'LINKEDIN_CREATE_LINKED_IN_POST']:
    try:
        tool = client.tools.get_raw_composio_tool_by_slug(slug)
        print('direct tool', slug, '->', getattr(tool, 'slug', None), 'version=', getattr(tool, 'version', None), 'toolkit=', getattr(tool, 'toolkit', None))
    except Exception as e:
        print('direct tool', slug, 'failed:', e)
