#!/usr/bin/env python3
"""Migrate documents from the `fdwa_general_memory` collection into the
existing vector-enabled `law_cases` collection using server-side embeddings.

This script will not delete source docs. It upserts documents into `law_cases`
with new '_id' values prefixed to avoid collisions.
"""
import os, sys, json, time
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from astrapy import DataAPIClient

endpoint = os.getenv("ASTRA_DB_API_ENDPOINT") or os.getenv("ASTRA_DB_ENDPOINT")
token = (
    os.getenv("ASTRA_DB_API_KEY")
    or os.getenv("ASTRA_DB_APPLICATION_TOKEN")
    or os.getenv("ASTRA_APPLICATION_TOKEN")
)
src_name = os.getenv("ASTRA_COLL_GENERAL") or "fdwa_general_memory"
target_name = os.getenv("ASTRA_COLL_FALLBACK") or "law_cases"

if not endpoint or not token:
    print("Missing Astra endpoint/token in env; aborting.")
    sys.exit(2)

print("Connecting to Astra at:", endpoint)
client = DataAPIClient()
try:
    db = client.get_database(endpoint, token=token)
except Exception as e:
    print("Failed to get Astra database:", e)
    sys.exit(3)

names = db.list_collection_names()
print("Collections in DB:", len(names))
if src_name not in names:
    print("Source collection not found:", src_name)
    sys.exit(4)
if target_name not in names:
    print("Target collection not found:", target_name)
    sys.exit(5)

source_coll = db.get_collection(src_name)
target_coll = db.get_collection(target_name)

# helper to pick text for vectorization
def pick_text_for_vector(doc: dict) -> str:
    for key in ("value", "text", "content", "summary", "body", "note", "title"):
        v = doc.get(key)
        if v:
            if isinstance(v, dict):
                return json.dumps(v, ensure_ascii=False)[:4000]
            return str(v)[:4000]
    strs = []
    for k, v in doc.items():
        if isinstance(v, str) and len(v) > 20:
            strs.append(v)
            if len(strs) >= 3:
                break
    if strs:
        return (" ").join(strs)[:4000]
    return json.dumps(doc, default=str)[:4000]

processed = 0
migrated = 0
failed = 0
failed_path = os.path.join(os.path.dirname(__file__), "..", "data", "astra_failed_migrate_to_law_cases.jsonl")
os.makedirs(os.path.dirname(failed_path), exist_ok=True)

print("Starting migration from", src_name, "to", target_name)
try:
    cursor = source_coll.find({})
except Exception as e:
    print("Failed to read source collection:", e)
    sys.exit(6)

for doc in cursor:
    processed += 1
    try:
        if hasattr(doc, "to_dict"):
            doc = doc.to_dict()
        elif not isinstance(doc, dict):
            doc = dict(doc)

        orig_id = doc.get("_id") or doc.get("id") or str(processed)
        new_id = f"fdwa_mem_{orig_id}"

        # remove any embeddings fields and set $vectorize
        doc.pop("$vector", None)
        doc.pop("$vectorize", None)

        # add metadata
        doc["_id"] = new_id
        doc["migrated_from"] = src_name
        doc["migrated_at"] = datetime.utcnow().isoformat()

        vector_text = pick_text_for_vector(doc)
        doc["$vectorize"] = vector_text

        # upsert into target
        try:
            target_coll.replace_one({"_id": new_id}, doc, upsert=True)
        except Exception:
            target_coll.insert_one(doc)
        migrated += 1

    except Exception as e:
        failed += 1
        with open(failed_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"error": str(e), "doc_id": doc.get("_id"), "doc": doc}, default=str) + "\n")

print(f"Processed: {processed}, Migrated: {migrated}, Failed: {failed}")
print("Failures (if any) logged to:", failed_path)
print("Migration complete. Update .env: ASTRA_COLL_GENERAL=", target_name)
print("Restart web/worker to pick up new collection.")
