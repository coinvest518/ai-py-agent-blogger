from pathlib import Path
from dotenv import load_dotenv
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

load_dotenv(dotenv_path=Path('.env'))

def main():
    from src.agent.tools.composio_tools import get_composio_client
    client = get_composio_client()
    print('client tools attr:', hasattr(client, 'tools'))
    print('client toolkits attr:', hasattr(client, 'toolkits'))
    try:
        print('toolkits.list exists:', hasattr(client.toolkits, 'list'))
        kits = client.toolkits.list()
        items = getattr(kits, 'items', None) or kits
        print('toolkits count', len(items) if items else 0)
        for kt in items[:10]:
            print('kit slug', getattr(kt, 'slug', None), 'version', getattr(kt, 'version', None), 'latest', getattr(kt, 'latest', None), 'latest_version', getattr(kt, 'latest_version', None), 'current_version', getattr(kt, 'current_version', None))
    except Exception as e:
        print('toolkits list failed:', e)
    try:
        print('tools.get_raw_composio_tools exists:', hasattr(client.tools, 'get_raw_composio_tools'))
        tools = client.tools.get_raw_composio_tools()
        print('tools count', len(tools) if tools else 0)
        link_tools = [t for t in tools if 'linkedin' in ((t.get('slug') if isinstance(t, dict) else getattr(t,'slug', '')).lower())]
        print('linkedin tool count', len(link_tools))
        for t in link_tools[:10]:
            print('slug=', t.get('slug') if isinstance(t, dict) else getattr(t,'slug', None), 'toolkit', t.get('toolkit') if isinstance(t, dict) else getattr(t,'toolkit', None), 'version', t.get('version') if isinstance(t, dict) else getattr(t,'version', None), 'toolkit_version', t.get('toolkit_version') if isinstance(t, dict) else getattr(t,'toolkit_version', None))
    except Exception as e:
        print('tools get_raw_composio_tools failed:', e)
    try:
        tool = client.tools.get_raw_composio_tool_by_slug('LINKEDIN_CREATE_LINKED_IN_POST')
        print('direct tool slug', getattr(tool,'slug', None) if not isinstance(tool, dict) else tool.get('slug'))
        tkit = getattr(tool,'toolkit', None) if not isinstance(tool, dict) else tool.get('toolkit')
        print('direct tool toolkit', tkit)
        if isinstance(tkit, dict):
            print('toolkit slug', tkit.get('slug'), 'toolkit name', tkit.get('name'), 'toolkit version', tkit.get('version'))
        else:
            print('toolkit slug', getattr(tkit,'slug', None), 'toolkit name', getattr(tkit,'name', None))
        print('tool version', getattr(tool,'version', None) if not isinstance(tool, dict) else tool.get('version'))
        print('tool toolkit_version', getattr(tool,'toolkit_version', None) if not isinstance(tool, dict) else tool.get('toolkit_version'))
    except Exception as e:
        print('direct get tool failed:', e)

if __name__ == '__main__':
    main()
