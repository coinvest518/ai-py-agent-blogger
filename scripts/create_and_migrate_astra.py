#!/usr/bin/env python3
"""Create a vector-enabled Astra collection and migrate documents from the
existing `fdwa_general_memory` collection into it using server-side embeddings.

Usage: python scripts/create_and_migrate_astra.py

This script reads Astra endpoint/token from the environment (or .env).
It will not delete the source collection. If a target collection already exists
but is not vector-enabled, a timestamped new collection name will be used.
"""

import os
import sys
import time
import json
import traceback
from dotenv import load_dotenv

load_dotenv()

endpoint = os.getenv("ASTRA_DB_API_ENDPOINT") or os.getenv("ASTRA_DB_ENDPOINT")
token = (
    os.getenv("ASTRA_DB_API_KEY")
    or os.getenv("ASTRA_DB_APPLICATION_TOKEN")
    or os.getenv("ASTRA_APPLICATION_TOKEN")
)

src_name = os.getenv("ASTRA_COLL_GENERAL") or "fdwa_general_memory"
preferred_target = os.getenv("ASTRA_COLL_GENERAL_V2") or (src_name + "_v2")

def abort(msg, code=1):
    print(msg)
    sys.exit(code)

if not endpoint or not token:
    abort("Missing ASTRA_DB_API_ENDPOINT or ASTRA_DB_API_KEY in environment.")

print("Connecting to Astra at:", endpoint)

try:
    from astrapy import DataAPIClient
    from astrapy.info import (
        CollectionDefinition,
        CollectionVectorOptions,
        VectorServiceOptions,
    )
except Exception as e:
    abort(f"astrapy import failed: {e}. Install requirements and retry.")

client = DataAPIClient()
try:
    db = client.get_database(endpoint, token=token)
except Exception as e:
    abort(f"Failed to get Astra database: {e}")

try:
    names = db.list_collection_names()
except Exception as e:
    abort(f"Failed to list collections: {e}")

print("Collections count:", len(names))
print("Source collection:", src_name)
if src_name not in names:
    abort(f"Source collection '{src_name}' not found in DB. Aborting.")

# Decide on target name: prefer preferred_target, but if exists and not vector-enabled,
# create timestamped variant.
target = preferred_target

if target in names:
    print(f"Target collection '{target}' already exists — checking vector config...")
    coll = db.get_collection(target)
    try:
        # Try a vector probe (will raise if vector service not configured)
        list(coll.find({}, sort={"$vectorize": "probe"}, limit=1))
        print("Existing target is vector-enabled — will use it for migration.")
    except Exception as e:
        print("Existing target not vector-enabled or probe failed:", repr(e))
        timestamp = int(time.time())
        target = f"{target}_{timestamp}"
        print("Will create new collection:", target)

# Create target collection if missing
if target not in names:
    print("Creating vector-enabled collection:", target)
    definition = CollectionDefinition(
        vector=CollectionVectorOptions(
            service=VectorServiceOptions(
                provider="nvidia",
                model_name="NV-Embed-QA",
            )
        ),
        indexing={"allow": ["_type", "topic", "platform", "timestamp", "token_symbol"]},
    )
    try:
        db.create_collection(target, definition=definition)
        print("Create collection request submitted — waiting briefly for readiness...")
        time.sleep(3)
    except Exception as e:
        abort(f"Failed to create collection '{target}': {e}\n{traceback.format_exc()}")

# Verify target vectorization
try:
    target_coll = db.get_collection(target)
    try:
        list(target_coll.find({}, sort={"$vectorize": "probe"}, limit=1))
        print("Target collection verified vector-enabled.")
    except Exception as e:
        # Try an insert test (best-effort) then delete
        print("Vector probe failed after create — attempting test insert:", e)
        try:
            test_id = f"__vector_test__{int(time.time())}"
            target_coll.insert_one({"_id": test_id, "$vectorize": "test embedding text"})
            target_coll.delete_one({"_id": test_id})
            print("Test insert succeeded — vectorization appears configured.")
        except Exception as e2:
            abort(f"Vectorization not available for '{target}': {e2}")
except Exception as e:
    abort(f"Failed to access target collection '{target}': {e}")

# Begin migration
print(f"Migrating documents from '{src_name}' -> '{target}'")
source_coll = db.get_collection(src_name)

def pick_text_for_vector(doc: dict) -> str:
    # Prefer known text-like fields
    for key in ("value", "text", "content", "summary", "body", "note", "title"):
        v = doc.get(key)
        if v:
            if isinstance(v, dict):
                return json.dumps(v)[:4000]
            return str(v)[:4000]
    # Otherwise, try joining string fields
    strs = []
    for k, v in doc.items():
        if isinstance(v, str) and len(v) > 20:
            strs.append(v)
            if len(strs) >= 3:
                break
    if strs:
        return (" ").join(strs)[:4000]
    # Fallback to JSON of doc (truncated)
    return json.dumps(doc, default=str)[:4000]

migrated = 0
failed = 0
processed = 0
failed_path = os.path.join(os.path.dirname(__file__), "..", "data", "astra_failed_migrate.jsonl")
os.makedirs(os.path.dirname(failed_path), exist_ok=True)

try:
    cursor = source_coll.find({})
except Exception as e:
    abort(f"Source collection read failed: {e}")

print("Starting iteration over source collection (this may take a while)...")
for doc in cursor:
    processed += 1
    try:
        # Ensure it's a plain dict
        if hasattr(doc, "to_dict"):
            doc = doc.to_dict()
        elif not isinstance(doc, dict):
            doc = dict(doc)

        # Remove any existing vector fields
        doc.pop("$vector", None)
        doc.pop("$vectorize", None)

        # Choose text for server-side embedding
        vector_text = pick_text_for_vector(doc)
        if not vector_text.strip():
            vector_text = "[no_text]"

        doc["$vectorize"] = vector_text

        # Upsert into target
        key_filter = {"_id": doc.get("_id")}
        try:
            target_coll.replace_one(key_filter, doc, upsert=True)
            migrated += 1
        except Exception as e:
            # Try insert fallback
            target_coll.insert_one(doc)
            migrated += 1

    except Exception as e:
        failed += 1
        with open(failed_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"error": str(e), "doc_id": doc.get("_id"), "doc": doc}, default=str) + "\n")

print(f"Processed: {processed}, Migrated: {migrated}, Failed: {failed}")
print("Migration complete — review any failures in:", failed_path)

# Print final status and suggest updating .env
print('\nNext step: update your .env to point ASTRA_COLL_GENERAL to the new collection:')
print(f"ASTRA_COLL_GENERAL={target}")
print("You can set this in .env or set environment variable before restarting the app.")
