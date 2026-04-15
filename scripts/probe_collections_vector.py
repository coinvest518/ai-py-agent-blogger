#!/usr/bin/env python3
from dotenv import load_dotenv
import os
load_dotenv()
from astrapy import DataAPIClient

endpoint=os.getenv('ASTRA_DB_API_ENDPOINT') or os.getenv('ASTRA_DB_ENDPOINT')
token=os.getenv('ASTRA_DB_API_KEY') or os.getenv('ASTRA_DB_APPLICATION_TOKEN') or os.getenv('ASTRA_APPLICATION_TOKEN')
if not endpoint or not token:
    print('Missing endpoint/token')
    raise SystemExit(2)

client=DataAPIClient()
db=client.get_database(endpoint, token=token)

names = db.list_collection_names()
print('Collections count:', len(names))
vector_enabled = []
for n in names:
    try:
        coll = db.get_collection(n)
        try:
            list(coll.find({}, sort={'$vectorize': 'probe'}, limit=1))
            print(n, '=> VECTOR_ENABLED')
            vector_enabled.append(n)
        except Exception as e:
            print(n, '=> no vector (probe error)')
    except Exception as e:
        print(n, '=> get_collection failed:', e)

print('\nVector-enabled collections found:', vector_enabled)
