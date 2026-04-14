from pathlib import Path
from dotenv import load_dotenv
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(dotenv_path=Path('.env'))
from src.agent.tools.composio_tools import get_composio_client

client = get_composio_client()
try:
    tool = client.tools.get_raw_composio_tool_by_slug('LINKEDIN_CREATE_LINKED_IN_POST')
    print('tool type', type(tool))
    print('tool repr', tool)
    toolkit = getattr(tool, 'toolkit', None)
    print('toolkit raw', toolkit)
    if isinstance(toolkit, dict):
        print('toolkit slug', toolkit.get('slug'))
        print('toolkit version', toolkit.get('version') or tool.get('toolkit_version'))
    else:
        print('toolkit slug', getattr(toolkit, 'slug', None))
        print('toolkit version', getattr(toolkit, 'version', None) or getattr(tool, 'toolkit_version', None))
except Exception as e:
    import traceback
    traceback.print_exc()
