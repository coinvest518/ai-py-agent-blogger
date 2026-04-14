"""Auto-resolve LinkedIn author URN, Instagram Business ID, Facebook Page ID via Composio.

Uses the already-connected Composio entity (COMPOSIO_ENTITY_ID) to call each platform's
"get my profile" / "get pages" / "get accounts" endpoint — no manual dev-portal clicks.

Writes results back to .env automatically (appending if missing, updating if present).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from composio import Composio
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent.parent
ENV_FILE = REPO / ".env"
load_dotenv(ENV_FILE)

ENTITY = os.getenv("COMPOSIO_ENTITY_ID") or os.getenv("COMPOSIO_USER_ID")
API_KEY = os.getenv("COMPOSIO_API_KEY")


def upsert_env(key: str, value: str) -> None:
    """Add or update KEY=VALUE in .env. Idempotent."""
    text = ENV_FILE.read_text(encoding="utf-8")
    line = f"{key}={value}"
    pattern = rf"^{re.escape(key)}=.*$"
    if re.search(pattern, text, flags=re.MULTILINE):
        text = re.sub(pattern, line, text, flags=re.MULTILINE)
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += line + "\n"
    ENV_FILE.write_text(text, encoding="utf-8")
    print(f"  [ok] wrote {key}={value}")


def try_tool(client: Composio, slug: str, args: dict) -> dict:
    try:
        resp = client.tools.execute(slug, arguments=args, user_id=ENTITY)
        return resp if isinstance(resp, dict) else {}
    except Exception as e:
        return {"successful": False, "error": str(e)}


def resolve_linkedin(client: Composio) -> None:
    print("\n[LinkedIn] fetching profile ...")
    for slug in (
        "LINKEDIN_GET_MY_INFO",
        "LINKEDIN_GET_CURRENT_USER",
        "LINKEDIN_GET_USER_INFO",
        "LINKEDIN_GET_USER_PROFILE",
    ):
        resp = try_tool(client, slug, {})
        if not resp.get("successful"):
            continue
        data = resp.get("data", {})
        # search every nested str for a person URN or "sub"
        payload = str(data)
        m = re.search(r"urn:li:person:([A-Za-z0-9_-]+)", payload)
        if m:
            urn = f"urn:li:person:{m.group(1)}"
            print(f"  found URN via {slug}: {urn}")
            upsert_env("LINKEDIN_AUTHOR_URN", urn)
            return
        # try "sub" field
        sub = None
        if isinstance(data, dict):
            sub = data.get("sub") or (data.get("data") or {}).get("sub") or (data.get("response_data") or {}).get("sub")
        if sub:
            urn = f"urn:li:person:{sub}"
            print(f"  found sub via {slug}: {urn}")
            upsert_env("LINKEDIN_AUTHOR_URN", urn)
            return
    print("  [fail] could not resolve LinkedIn URN - no matching tool returned profile")


def resolve_facebook_pages(client: Composio) -> None:
    print("\n[Facebook] fetching pages ...")
    existing_page_id = os.getenv("FACEBOOK_PAGE_ID")
    for slug in ("FACEBOOK_GET_PAGES", "FACEBOOK_LIST_PAGES", "FACEBOOK_GET_USER_PAGES"):
        resp = try_tool(client, slug, {})
        if not resp.get("successful"):
            continue
        data = resp.get("data", {})
        pages = []
        if isinstance(data, dict):
            pages = data.get("data") or data.get("pages") or data.get("response_data", {}).get("data") or []
        if not pages:
            continue
        print(f"  via {slug}: {len(pages)} page(s)")
        for p in pages:
            pid = p.get("id")
            name = p.get("name", "?")
            token = p.get("access_token")
            print(f"    - {name} (id={pid})")
            if existing_page_id and str(pid) == str(existing_page_id) and token:
                upsert_env("FACEBOOK_PAGE_ACCESS_TOKEN", token)
                return
        # if no match, write first page
        first = pages[0]
        if first.get("id"):
            upsert_env("FACEBOOK_PAGE_ID", str(first["id"]))
        if first.get("access_token"):
            upsert_env("FACEBOOK_PAGE_ACCESS_TOKEN", first["access_token"])
        return
    print("  [fail] could not fetch Facebook pages")


def resolve_instagram(client: Composio) -> None:
    print("\n[Instagram] resolving business account id ...")
    # IG business account is attached to a FB page — query page for instagram_business_account
    import requests as _rq

    # Reload env in case FB token was just written
    load_dotenv(ENV_FILE, override=True)
    page_id = os.getenv("FACEBOOK_PAGE_ID")
    page_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")

    if page_id and page_token:
        try:
            url = f"https://graph.facebook.com/v20.0/{page_id}"
            r = _rq.get(url, params={"fields": "instagram_business_account", "access_token": page_token}, timeout=15)
            if r.ok:
                data = r.json()
                iba = data.get("instagram_business_account")
                if iba and iba.get("id"):
                    ig_id = iba["id"]
                    print(f"  found IG business account via FB page: {ig_id}")
                    upsert_env("INSTAGRAM_USER_ID", ig_id)
                    return
                print(f"  FB page has no linked Instagram business account: {data}")
            else:
                print(f"  FB graph error: {r.status_code} {r.text[:200]}")
        except Exception as e:
            print(f"  FB graph request failed: {e}")

    # Fallback to Composio IG tools
    for slug in ("INSTAGRAM_GET_USER_INFO", "INSTAGRAM_GET_ACCOUNT", "INSTAGRAM_GET_PROFILE"):
        resp = try_tool(client, slug, {})
        if resp.get("successful"):
            data = resp.get("data", {})
            payload = str(data)
            m = re.search(r'"id"\s*:\s*"?(\d{10,20})"?', payload)
            if m:
                print(f"  found IG id via {slug}: {m.group(1)}")
                upsert_env("INSTAGRAM_USER_ID", m.group(1))
                return
    print("  [fail] could not resolve IG user id - link an Instagram Business account to your FB page")


def main() -> int:
    if not API_KEY:
        print("ERROR: COMPOSIO_API_KEY missing"); return 1
    if not ENTITY:
        print("ERROR: COMPOSIO_ENTITY_ID missing"); return 1

    print(f"Entity: {ENTITY}")
    client = Composio(api_key=API_KEY)

    resolve_linkedin(client)
    resolve_facebook_pages(client)
    resolve_instagram(client)

    print("\nDone. Reload .env and re-run the graph.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
