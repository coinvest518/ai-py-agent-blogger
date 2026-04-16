from dotenv import load_dotenv
from pathlib import Path
ROOT = Path(r'C:/Users/mildh/ai-py-agent-blogger')
load_dotenv(ROOT / '.env')
from src.agent.memory_store import ASTRA_COLLECTION, ASTRA_COLLECTIONS, ASTRA_VECTOR_COLLECTIONS, _astra_env
print('ASTRA_COLLECTION=', ASTRA_COLLECTION)
print('ASTRA_COLLECTIONS=', ASTRA_COLLECTIONS)
print('ASTRA_VECTOR_COLLECTIONS=', ASTRA_VECTOR_COLLECTIONS)
print('_astra_env=', _astra_env())
