#!/usr/bin/env python3
import sys, pathlib, json, os
sys.path.insert(0, str(pathlib.Path('.').resolve()))
from src.agent.tools.composio_tools import get_linkedin_author_urn, _execute_with_fallback

auth = get_linkedin_author_urn(None)
print('AUTHOR_URN:', auth)
entity = os.getenv('COMPOSIO_ENTITY_ID') or os.getenv('COMPOSIO_USER_ID')
print('ENTITY:', entity)
init = _execute_with_fallback('LINKEDIN_INITIALIZE_IMAGE_UPLOAD', {'owner': auth, 'file_name': 'test.png', 'mimetype': 'image/png'}, entity)
print(json.dumps(init, indent=2))
