#!/usr/bin/env python3
"""Attempt to create a vector-enabled collection with minimal indexing to
avoid hitting the 'Cannot have more than 100 indexes' limit.
"""
import os, sys, time, traceback
from dotenv import load_dotenv
load_dotenv()

endpoint = os.getenv("ASTRA_DB_API_ENDPOINT") or os.getenv("ASTRA_DB_ENDPOINT")
token = (
    os.getenv("ASTRA_DB_API_KEY")
    or os.getenv("ASTRA_DB_APPLICATION_TOKEN")
    or os.getenv("ASTRA_APPLICATION_TOKEN")
)

if not endpoint or not token:
    print("Missing Astra endpoint/token in env; aborting.")
    sys.exit(2)

from astrapy import DataAPIClient
from astrapy.info import CollectionDefinition, CollectionVectorOptions, VectorServiceOptions

client = DataAPIClient()
try:
    db = client.get_database(endpoint, token=token)
except Exception as e:
    print("Failed to get database:", e)
    sys.exit(3)

src = os.getenv("ASTRA_COLL_GENERAL") or "fdwa_general_memory"
base_target = os.getenv("ASTRA_COLL_GENERAL_V2") or (src + "_v2_minindex")
# Timestamp suffix to avoid collisions
target = f"{base_target}_{int(time.time())}"
print("Attempting to create collection:", target)

definition = CollectionDefinition(
    vector=CollectionVectorOptions(
        service=VectorServiceOptions(
            provider="nvidia",
            model_name="NV-Embed-QA",
        )
    )
)

try:
    db.create_collection(target, definition=definition)
    print("Create request submitted for:", target)
    # brief pause
    time.sleep(2)
    try:
        coll = db.get_collection(target)
        # probe vector
        try:
            list(coll.find({}, sort={"$vectorize": "probe"}, limit=1))
            print("Target appears vector-enabled:", target)
        except Exception as e:
            print("Vector probe failed (may still be pending):", e)
    except Exception as e:
        print("Could not get target collection after create:", e)
except Exception as e:
    print("Create collection failed:", repr(e))
    traceback.print_exc()
    sys.exit(4)

print("Done.")
