#!/usr/bin/env python3
from pathlib import Path
from dotenv import load_dotenv
import os

repo_root = Path(__file__).resolve().parents[1]
load_dotenv(repo_root / ".env")

print("cwd:", Path.cwd())
print("env_path:", repo_root / ".env")
print("COMPOSIO_API_KEY set:", bool(os.getenv("COMPOSIO_API_KEY")))
print("COMPOSIO_ENTITY_ID:", os.getenv("COMPOSIO_ENTITY_ID"))
print("COMPOSIO_TOOLKIT_VERSION_LINKEDIN:", os.getenv("COMPOSIO_TOOLKIT_VERSION_LINKEDIN"))
print("COMPOSIO_DANGEROUSLY_SKIP_VERSION_CHECK:", os.getenv("COMPOSIO_DANGEROUSLY_SKIP_VERSION_CHECK"))
print("LANGSMITH_PROJECT:", os.getenv("LANGSMITH_PROJECT"))
print("LANGSMITH_API_KEY set:", bool(os.getenv("LANGSMITH_API_KEY")))

try:
    from src.agent.tools.composio_tools import _env_toolkit_versions, get_composio_client
    versions = _env_toolkit_versions()
    print("parsed COMPOSIO_TOOLKIT_VERSION_*:", versions)
    client = get_composio_client()
    print("Composio client type:", type(client).__name__)
except Exception as e:
    print("ERROR loading Composio client:", e)
