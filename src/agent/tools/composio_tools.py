"""Composio client setup and platform posting tools.

Centralizes all Composio tool.execute() calls so agents never import Composio directly.
Uses `user_id=COMPOSIO_ENTITY_ID` — Composio auto-resolves the connected account by entity,
so per-platform account IDs are no longer required.
"""

import logging
import os
import json
import time
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

try:
    from composio import Composio
    COMPOSIO_AVAILABLE = True
except Exception as e:
    Composio = None  # type: ignore[assignment]
    COMPOSIO_AVAILABLE = False
    logging.getLogger(__name__).warning("Composio import failed: %s", e)
from dotenv import load_dotenv

repo_root = Path(__file__).resolve().parents[3]
load_dotenv(repo_root / ".env")

# Read key Composio-related env vars directly to avoid importing
# src.agent.core.config at module import time (prevents import side-effects
# when scripts load this module for lightweight checks).
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")
COMPOSIO_ENTITY_ID = os.getenv("COMPOSIO_ENTITY_ID") or os.getenv("COMPOSIO_USER_ID")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID") or os.getenv("INSTAGRAM_USER_NAME")
LINKEDIN_AUTHOR_URN = os.getenv("LINKEDIN_AUTHOR_URN")
logger = logging.getLogger(__name__)

# Shared cached client
_client: Optional[Composio] = None

# Alias fallbacks for common slug differences across accounts/toolkits
SLUG_ALIASES: Dict[str, List[str]] = {
    "INSTAGRAM_GET_MEDIA_COMMENTS": ["INSTAGRAM_GET_POST_COMMENTS", "INSTAGRAM_GET_COMMENTS"],
    "INSTAGRAM_GET_MEDIA_INSIGHTS": ["INSTAGRAM_GET_POST_INSIGHTS", "INSTAGRAM_GET_INSIGHTS"],
    "FACEBOOK_GET_POSTS": ["FACEBOOK_GET_PAGE_POSTS", "FACEBOOK_LIST_PAGE_POSTS"],
    "FACEBOOK_GET_PAGE_INSIGHTS": ["FACEBOOK_PAGE_INSIGHTS"],
}

# Cache discovered tools list per entity to reduce list calls
_tools_cache: Dict[str, List[Dict]] = {}


def _env_toolkit_versions() -> Dict[str, str]:
    """Parse COMPOSIO_TOOLKIT_VERSION_* env vars into a toolkit version mapping."""
    versions: Dict[str, str] = {}
    prefix = "COMPOSIO_TOOLKIT_VERSION_"
    for key, value in os.environ.items():
        if key.startswith(prefix) and value:
            toolkit_slug = key[len(prefix):].replace("__", "/").lower()
            versions[toolkit_slug] = value.strip()
    return versions


# Status cache helpers -----------------------------------------------------
_STATUS_PATH = Path(__file__).resolve().parents[3] / "agent_status.json"

def _read_status_cache() -> Dict:
    try:
        if not _STATUS_PATH.exists():
            return {}
        with _STATUS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _write_status_cache(data: Dict) -> None:
    try:
        _STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _STATUS_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        logger.debug("Failed to write status cache to %s", _STATUS_PATH)


def _get_cached_linkedin_urn() -> Optional[str]:
    cfg = _read_status_cache()
    comp = cfg.get("composio", {}) or {}
    urn = comp.get("linkedin_author_urn")
    if not urn:
        return None
    ts = comp.get("linkedin_author_urn_ts")
    try:
        ttl_days = int(os.getenv("COMPOSIO_URN_CACHE_TTL_DAYS", "30"))
    except Exception:
        ttl_days = 30
    if ts:
        try:
            t = datetime.fromisoformat(ts)
            if datetime.now(timezone.utc) - t > timedelta(days=ttl_days):
                return None
        except Exception:
            pass
    return urn


def _cache_linkedin_author_urn(urn: str) -> None:
    cfg = _read_status_cache()
    comp = cfg.get("composio", {}) or {}
    comp["linkedin_author_urn"] = urn
    comp["linkedin_author_urn_ts"] = datetime.now(timezone.utc).isoformat()
    cfg["composio"] = comp
    _write_status_cache(cfg)


def get_composio_client() -> Composio:
    """Get or create the shared Composio client.

    The Composio client is initialized with any configured
    `COMPOSIO_TOOLKIT_VERSION_*` env vars. If explicit toolkit versions are
    provided, they are passed to the SDK so manual tool execution can succeed.
    """
    global _client
    if not COMPOSIO_AVAILABLE:
        raise RuntimeError("Composio is unavailable in this environment")
    if _client is None:
        dangerously = os.getenv("COMPOSIO_DANGEROUSLY_SKIP_VERSION_CHECK", "true").lower() in ("1", "true", "yes")
        toolkit_versions = _env_toolkit_versions() or None
        try:
            if toolkit_versions:
                logger.debug(
                    "Initializing Composio with toolkit_versions=%s dangerously_skip_version_check=%s",
                    toolkit_versions,
                    dangerously,
                )
                try:
                    _client = Composio(
                        api_key=COMPOSIO_API_KEY,
                        toolkit_versions=toolkit_versions,
                        dangerously_skip_version_check=dangerously,
                    )
                except TypeError:
                    _client = Composio(api_key=COMPOSIO_API_KEY, toolkit_versions=toolkit_versions)
            elif dangerously:
                logger.debug("Initializing Composio with dangerously_skip_version_check=True")
                _client = Composio(
                    api_key=COMPOSIO_API_KEY,
                    dangerously_skip_version_check=True,
                )
            else:
                _client = Composio(api_key=COMPOSIO_API_KEY)
        except TypeError:
            _client = Composio(api_key=COMPOSIO_API_KEY)
    return _client


def _entity() -> str | None:
    return COMPOSIO_ENTITY_ID


def _execute_with_fallback(slug: str, arguments: dict, user_id: str) -> dict:
    """Execute a Composio tool slug with graceful fallbacks.

    Attempts the requested slug, then tries configured alias slugs, and as a
    last resort lists available tools and attempts a best-effort match.
    Returns the raw Composio response dict.
    """
    client = get_composio_client()
    env_toolkit_versions = _env_toolkit_versions()
    skip_version = os.getenv("COMPOSIO_DANGEROUSLY_SKIP_VERSION_CHECK", "true").lower() in ("1", "true", "yes")
    logger.debug(
        "Composio execute init slug=%s user_id=%s explicit_versions=%s skip_version=%s",
        slug,
        user_id,
        env_toolkit_versions,
        skip_version,
    )
    def _execute(slug_to_execute: str, args: dict, version_override: str | None = None) -> dict:
        if version_override:
            logger.debug("Composio executing %s with explicit version_override=%s", slug_to_execute, version_override)
        # Retry/backoff wrapper for Composio calls. Handles 429 / rate-limit
        # responses by retrying with exponential backoff and jitter. The
        # environment variables `COMPOSIO_MAX_RETRIES` and
        # `COMPOSIO_RETRY_BACKOFF_BASE` control retry behavior.
        max_retries = int(os.getenv("COMPOSIO_MAX_RETRIES", "3"))
        backoff_base = float(os.getenv("COMPOSIO_RETRY_BACKOFF_BASE", "1.0"))
        last_resp = None
        for attempt in range(max_retries):
            try:
                kwargs = {"arguments": args, "user_id": user_id}
                if version_override:
                    kwargs["version"] = version_override
                elif skip_version:
                    kwargs["dangerously_skip_version_check"] = True

                # Instrument Composio execute with an OTEL span when available.
                # This creates a `composio.execute` span with useful attributes
                # visible in LangSmith traces / OTEL collector.
                tracer_ctx = None
                try:
                    from opentelemetry import trace as _ot_trace
                    _tracer = _ot_trace.get_tracer(__name__)
                    tracer_ctx = _tracer.start_as_current_span("composio.execute", attributes={
                        "composio.slug": slug_to_execute,
                        "composio.user_id": str(user_id) if user_id else "",
                        "composio.version_override": str(version_override) if version_override else "",
                    })
                except Exception:
                    tracer_ctx = None

                if tracer_ctx:
                    with tracer_ctx as _span:
                        resp = client.tools.execute(slug_to_execute, **kwargs)
                        try:
                            # Attach response metadata for observability
                            _span.set_attribute("composio.successful", bool(resp.get("successful")))
                            _span.set_attribute("composio.error", str(resp.get("error", ""))[:1024])
                        except Exception:
                            pass
                else:
                    resp = client.tools.execute(slug_to_execute, **kwargs)
                last_resp = resp
                # If the call succeeded, return immediately
                if resp.get("successful"):
                    return resp

                # Check for rate-limit indications in the response
                data = resp.get("data") or {}
                http_err = str(data.get("http_error") or "").lower()
                err_msg = str(resp.get("error") or "").lower()
                status_code = data.get("status_code") or data.get("status")
                is_rate_limited = False
                try:
                    if int(status_code) == 429:  # type: ignore[arg-type]
                        is_rate_limited = True
                except Exception:
                    pass
                if "too many requests" in http_err or "too many requests" in err_msg or "429" in http_err or "429" in err_msg:
                    is_rate_limited = True

                if is_rate_limited and attempt < max_retries - 1:
                    sleep_time = backoff_base * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning("Composio rate-limited on %s; retrying after %.2fs (attempt %d/%d)", slug_to_execute, sleep_time, attempt + 1, max_retries)
                    time.sleep(sleep_time)
                    continue

                # Not a rate-limit condition or no more retries: return response
                return resp

            except Exception as e:
                last_resp = {"successful": False, "error": str(e)}
                err = str(e).lower()
                if ("too many requests" in err or "429" in err or "rate limit" in err) and attempt < max_retries - 1:
                    sleep_time = backoff_base * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning("Composio call exception looks like rate-limit: %s; retrying after %.2fs (attempt %d/%d)", e, sleep_time, attempt + 1, max_retries)
                    time.sleep(sleep_time)
                    continue
                return last_resp
        return last_resp or {"successful": False, "error": "Composio call failed after retries"}

    # Try an initial execution using any explicit toolkit version pinned via
    # environment variables (COMPOSIO_TOOLKIT_VERSION_*). This avoids hitting
    # Composio tool runtime fallbacks when a specific toolkit version is required.
    try:
        versions = env_toolkit_versions or {}
        # Guess toolkit key from the slug (e.g. 'LINKEDIN_CREATE_LINKED_IN_POST' -> 'linkedin')
        slug_key = (slug.split("_")[0] if slug and isinstance(slug, str) else "").lower()
        explicit_ver = (
            versions.get(slug_key)
            or os.getenv(f"COMPOSIO_TOOLKIT_VERSION_{slug_key.upper()}")
            or os.getenv(f"COMPOSIO_TOOLKIT_VERSION_{slug_key.lower()}")
        )
        resp = _execute(slug, arguments, explicit_ver)
    except Exception as e:
        resp = {"successful": False, "error": str(e)}

    if resp.get("successful"):
        return resp

    # Inspect error and determine whether to attempt fallbacks
    err = resp.get("error", "")
    msg = json.dumps(err) if isinstance(err, (dict, list)) else str(err)
    msg_l = msg.lower()
    # Consider additional error signatures that indicate a toolkit/version
    # mismatch so we attempt the toolkit-version fallbacks below.
    should_fallback = (
        "not found" in msg_l
        or "toolnotfound" in msg_l
        or "tool_not_found" in msg_l
        or "tool not found" in msg_l
        or "toolkit version not specified" in msg_l
        or "nonexistent_version" in msg_l
        or "nonexistent version" in msg_l
        or "requested version" in msg_l
        or "not active" in msg_l
    )

    # Try canonical alias list first
    if should_fallback:
        aliases = SLUG_ALIASES.get(slug, [])
        for a in aliases:
            try:
                resp2 = _execute(a, arguments)
                if resp2.get("successful"):
                    logger.info("Composio: fallback %s -> %s", slug, a)
                    return resp2
            except Exception as e2:
                logger.debug("Composio alias %s failed: %s", a, e2)
        # Try to resolve a toolkit version for this slug and execute with explicit
        # `toolkit_versions` if available. This fixes errors like
        # "Toolkit version not specified" by passing the exact version discovered
        # from the tools listing.
        try:
            tools = _tools_cache.get(user_id)
            if tools is None:
                tools = client.tools.get_raw_composio_tools()
                _tools_cache[user_id] = tools

            slug_parts = [p for p in slug.upper().split("_") if p]

            # Try direct tool lookup first, when slug is exact.
            try:
                direct_tool = client.tools.get_raw_composio_tool_by_slug(slug)
                tkit = getattr(direct_tool, "toolkit", None)
                toolkit_slug = None
                toolkit_version = None
                if isinstance(tkit, dict):
                    toolkit_slug = tkit.get("slug") or tkit.get("name")
                else:
                    toolkit_slug = getattr(tkit, "slug", None) or (str(tkit) if tkit else None)
                toolkit_version = (
                    getattr(direct_tool, "version", None)
                    or getattr(direct_tool, "toolkit_version", None)
                    or (direct_tool.get("version") if isinstance(direct_tool, dict) else None)
                    or (direct_tool.get("toolkit_version") if isinstance(direct_tool, dict) else None)
                )
                if toolkit_slug and toolkit_version:
                    try:
                        resp_tool = _execute(slug, arguments, toolkit_version)
                        if resp_tool.get("successful"):
                            logger.info("Composio: execute with direct version %s -> success", toolkit_version)
                            return resp_tool
                    except Exception:
                        pass
            except Exception:
                pass

            # First, try to find the same tool and its toolkit/version
            for t in tools or []:
                # support dict-like and object-like tool records
                tslug = (t.get("slug") if isinstance(t, dict) else getattr(t, "slug", None)) or ""
                tslug_u = tslug.upper()
                if tslug_u == slug.upper() or all(part in tslug_u for part in slug_parts):
                    # try to extract toolkit slug & version
                    tkit = (t.get("toolkit") if isinstance(t, dict) else getattr(t, "toolkit", None))
                    toolkit_slug = None
                    toolkit_version = None
                    if isinstance(tkit, dict):
                        toolkit_slug = tkit.get("slug") or tkit.get("name")
                    else:
                        toolkit_slug = getattr(tkit, "slug", None) or (str(tkit) if tkit else None)
                    if isinstance(t, dict):
                        toolkit_version = t.get("version") or t.get("toolkit_version")
                    else:
                        toolkit_version = getattr(t, "version", None) or getattr(t, "toolkit_version", None)

                    if toolkit_slug and toolkit_version:
                        try:
                            resp_tool = _execute(slug, arguments, toolkit_version)
                            if resp_tool.get("successful"):
                                logger.info("Composio: execute with version %s -> success", toolkit_version)
                                return resp_tool
                        except Exception:
                            pass

            # Last resort: attempt best-effort match by slug text and try executing
            for t in tools or []:
                tslug = (t.get("slug") if isinstance(t, dict) else getattr(t, "slug", None)) or ""
                tslug_u = tslug.upper()
                if all(part in tslug_u for part in slug_parts):
                    try:
                        resp3 = _execute(tslug, arguments)
                        if resp3.get("successful"):
                            logger.info("Composio: autodiscovered fallback %s -> %s", slug, tslug)
                            return resp3
                    except Exception:
                        pass
        except Exception as e3:
            logger.debug("Composio tools listing/resolve failed: %s", e3)

    # Return original response if no fallback succeeded
    # Final attempt: try passing a full mapping of discovered toolkit versions
    try:
        kits = client.toolkits.list()
        items = getattr(kits, "items", None) or kits
        toolkit_versions = {}
        for kt in (items or []):
            kslug = (kt.get("slug") if isinstance(kt, dict) else getattr(kt, "slug", None)) or None
            # try multiple possible version keys
            kver = None
            if isinstance(kt, dict):
                kver = kt.get("version") or kt.get("latest") or kt.get("latest_version") or kt.get("current_version")
            else:
                kver = getattr(kt, "version", None) or getattr(kt, "latest_version", None) or getattr(kt, "current_version", None)
            if kslug and kver:
                toolkit_versions[kslug] = kver
        if toolkit_versions:
            try:
                resp_full = _execute(slug, arguments, toolkit_versions)
                if resp_full.get("successful"):
                    logger.info("Composio: execute with discovered toolkit_versions mapping succeeded")
                    return resp_full
            except Exception:
                pass
    except Exception as _e:
        logger.debug("Composio full toolkit_versions attempt failed: %s", _e)

    return resp


def _safe_get(obj: object, *fields: str) -> Optional[str]:
    for field in fields:
        if isinstance(obj, dict):
            value = obj.get(field)
        else:
            value = getattr(obj, field, None)
        if value:
            return str(value)
    return None


def _looks_like_linkedin_account(item: object) -> bool:
    alias = _safe_get(item, "alias") or ""
    word_id = _safe_get(item, "word_id") or ""
    toolkit = _safe_get(item, "toolkit")
    toolkit_slug = _safe_get(toolkit, "slug") or ""
    toolkit_name = _safe_get(toolkit, "name") or ""
    return any("linkedin" in field.lower() for field in (alias, word_id, toolkit_slug, toolkit_name))


def _looks_like_linkedin_urn(value: str) -> bool:
    return isinstance(value, str) and value.startswith("urn:li:")


def _is_person_urn(value: str) -> bool:
    """Return True when the value is a LinkedIn person URN (urn:li:person:...)."""
    return isinstance(value, str) and value.startswith("urn:li:person:")


def _find_linkedin_author_urn_from_connected_accounts(user_id: str) -> Optional[str]:
    try:
        client = get_composio_client()
        resp = client.connected_accounts.list(user_ids=[user_id], statuses=["ACTIVE"])
        items = getattr(resp, "items", None) or []
        for item in items:
            if not _looks_like_linkedin_account(item):
                continue
            alias = _safe_get(item, "alias")
            if alias and _looks_like_linkedin_urn(alias):
                _cache_linkedin_author_urn(alias)
                return alias
            word_id = _safe_get(item, "word_id")
            if word_id and _looks_like_linkedin_urn(word_id):
                _cache_linkedin_author_urn(word_id)
                return word_id
            state = _safe_get(item, "state")
            account_url = _safe_get(state, "account_url")
            if account_url and "linkedin" in account_url.lower() and _looks_like_linkedin_urn(account_url):
                _cache_linkedin_author_urn(account_url)
                return account_url
            account_id = _safe_get(state, "account_id")
            if account_id and _looks_like_linkedin_urn(account_id):
                _cache_linkedin_author_urn(account_id)
                return account_id
    except Exception as e:
        logger.debug("Failed to discover LinkedIn author URN from Composio connected accounts: %s", e)
    return None


def _find_linkedin_author_urn_from_linkedin_tool(user_id: str) -> Optional[str]:
    try:
        client = get_composio_client()
        # Use the configured LinkedIn toolkit version when available to avoid
        # experiencing NONEXISTENT_VERSION errors from Composio/LinkedIn.
        versions = _env_toolkit_versions() or {}
        ver = (
            os.getenv("COMPOSIO_TOOLKIT_VERSION_LINKEDIN")
            or os.getenv("COMPOSIO_TOOLKIT_VERSION_linkedin")
            or versions.get("linkedin")
        )
        exec_kwargs = {"arguments": {}, "user_id": user_id}
        if ver:
            exec_kwargs["version"] = ver
        resp = client.tools.execute("LINKEDIN_GET_MY_INFO", **exec_kwargs)
        if resp.get("successful"):
            data = resp.get("data") or {}
            for field in ("urn", "id", "personUrn", "memberUrn", "profileUrn"):  # heuristic
                value = data.get(field)
                if value and _looks_like_linkedin_urn(value):
                    _cache_linkedin_author_urn(value)
                    return value
            # If the tool returns raw person id, build the URN
            person_id = data.get("id")
            if person_id and isinstance(person_id, str) and person_id.isalnum():
                urn = f"urn:li:person:{person_id}"
                _cache_linkedin_author_urn(urn)
                return urn
    except Exception as e:
        logger.debug("Failed to resolve LinkedIn author URN from LINKEDIN_GET_MY_INFO: %s", e)
    return None


def get_linkedin_author_urn(author_urn: str | None = None) -> Optional[str]:
    urn = author_urn or LINKEDIN_AUTHOR_URN
    # Only accept explicit URNs that are person URNs. Activity URNs are not
    # valid for use as an author identifier and should not be returned here.
    if urn:
        if _is_person_urn(urn):
            return urn
        logger.warning("Configured LINKEDIN_AUTHOR_URN is not a person URN: %r", urn)

    # Check cached URN before making network calls
    cached = _get_cached_linkedin_urn()
    if cached:
        if _is_person_urn(cached):
            return cached
        logger.debug("Cached LinkedIn URN is not a person URN, ignoring: %r", cached)
    entity = _entity()
    if entity:
        found = _find_linkedin_author_urn_from_connected_accounts(entity)
        if found:
            return found
        return _find_linkedin_author_urn_from_linkedin_tool(entity)
    return None


# =============================================================================
# Twitter — posting now routes through upload_post_agent (image-only, 10/mo cap)
# =============================================================================


# =============================================================================
# Facebook
# =============================================================================

def _normalize_facebook_page_id(page_id: str | None) -> str:
    """Normalize Facebook page ID or URL to the canonical page identifier."""
    if not page_id:
        return ""
    page_id = str(page_id).strip()
    if not page_id:
        return ""

    if page_id.lower().startswith("http"):
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(page_id)
        query = parse_qs(parsed.query)
        if "page_id" in query and query["page_id"]:
            return query["page_id"][0].strip()
        page_id = parsed.path.strip("/")

    if "facebook.com" in page_id.lower():
        page_id = page_id.lower().split("facebook.com")[-1].strip("/")

    if page_id.startswith("pg/"):
        page_id = page_id[len("pg/"):]
    if "/" in page_id:
        page_id = page_id.split("/")[-1]

    return page_id.strip()


def _extract_facebook_post_id(response: dict) -> str:
    """Robustly extract a Facebook post ID from Composio response data."""
    if not isinstance(response, dict):
        return ""
    data = response.get("data", {}) or {}
    response_data = data.get("response_data", {}) or {}
    post_id = (
        response_data.get("post_id")
        or response_data.get("id")
        or data.get("post_id")
        or data.get("id")
    )
    if isinstance(post_id, str):
        return post_id.strip()
    if post_id is not None:
        return str(post_id).strip()
    return ""


def post_facebook(page_id: str | None, text: str, photo_path: str | None = None) -> dict:
    """Post to Facebook page. Returns dict with success, post_id, or error."""
    page_id = _normalize_facebook_page_id(page_id or FACEBOOK_PAGE_ID)
    entity = _entity()
    if not page_id:
        return {"error": "FACEBOOK_PAGE_ID not set"}
    if not entity:
        return {"success": False, "error": "COMPOSIO_ENTITY_ID not set"}

    client = get_composio_client()
    params = {"page_id": page_id, "message": text, "published": True}

    tool_name = "FACEBOOK_CREATE_POST"
    if photo_path and os.path.exists(photo_path):
        params["photo"] = photo_path
        tool_name = "FACEBOOK_CREATE_PHOTO_POST"

    try:
        resp = _execute_with_fallback(tool_name, params, entity)
        if not resp.get("successful"):
            return {"success": False, "error": resp.get("error", "Unknown")}
        post_id = _extract_facebook_post_id(resp)
        return {"success": True, "post_id": post_id}
    except Exception as e:
        logger.exception("Facebook post failed: %s", e)
        return {"success": False, "error": str(e)}


def comment_facebook(post_id: str, message: str) -> dict:
    """Comment on a Facebook post."""
    if not post_id:
        return {"success": False, "error": "No post ID"}
    entity = _entity()
    if not entity:
        return {"success": False, "error": "COMPOSIO_ENTITY_ID not set"}
    client = get_composio_client()
    try:
        resp = _execute_with_fallback(
            "FACEBOOK_CREATE_COMMENT", {"message": message, "object_id": post_id}, entity
        )
        cid = resp.get("data", {}).get("id", "commented")
        return {"success": True, "comment_id": cid}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# LinkedIn
# =============================================================================

def post_linkedin(author_urn: str | None, text: str) -> dict:
    """Post to LinkedIn. Returns dict with success or error."""
    urn = get_linkedin_author_urn(author_urn)
    entity = _entity()
    if not urn:
        return {"success": False, "error": "LINKEDIN_AUTHOR_URN not set or discoverable from Composio"}
    if not entity:
        return {"success": False, "error": "COMPOSIO_ENTITY_ID not set"}
    client = get_composio_client()
    try:
        resp = _execute_with_fallback(
            "LINKEDIN_CREATE_LINKED_IN_POST",
            {
                "author": urn,
                "commentary": text,
                "lifecycleState": "PUBLISHED",
                "visibility": "PUBLIC",
            },
            entity,
        )
        if resp.get("successful"):
            return {"success": True}
        return {"success": False, "error": resp.get("error", "Unknown")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def post_linkedin_with_image(author_urn: str | None, text: str, image_url: str | None = None,
                             image_bytes: bytes | None = None, mimetype: str = "image/jpeg",
                             filename: str = "image.jpg") -> dict:
    """Post to LinkedIn with an attached image.

    Workflow:
      1. Initialize image upload via LINKEDIN_INITIALIZE_IMAGE_UPLOAD
      2. PUT bytes to the returned upload URL
      3. Call LINKEDIN_CREATE_LINKED_IN_POST with the image URN

    This is best-effort: Composio toolkit implementations vary, so we
    try several likely response keys for upload URL / image URN.
    """
    urn = get_linkedin_author_urn(author_urn)
    entity = _entity()
    if not urn:
        return {"success": False, "error": "LINKEDIN_AUTHOR_URN not set or discoverable from Composio"}
    if not entity:
        return {"success": False, "error": "COMPOSIO_ENTITY_ID not set"}

    if not image_url and not image_bytes:
        # Nothing to attach — fall back to text-only post
        return post_linkedin(author_urn, text)

    try:
        # Acquire image bytes if only a URL was provided
        if image_url and not image_bytes:
            try:
                import requests

                r = requests.get(image_url, timeout=30)
                if r.status_code != 200:
                    return {"success": False, "error": f"Image download failed: HTTP {r.status_code}"}
                image_bytes = r.content
            except Exception as e:
                return {"success": False, "error": f"Image download failed: {e}"}

        # Initialize upload via Composio toolkit
        init = _execute_with_fallback(
            "LINKEDIN_INITIALIZE_IMAGE_UPLOAD",
            {"owner": urn, "file_name": filename, "mimetype": mimetype},
            entity,
        )
        if not init.get("successful"):
            return {"success": False, "error": init.get("error", "Initialize upload failed")}

        data = init.get("data") or {}
        # Try common field names for upload URL and image URN
        upload_url = _safe_get(data, "upload_url", "uploadUrl", "upload_uri", "uploadUri")
        # include common field names like 'image' returned by some toolkits
        image_urn = _safe_get(data, "image_urn", "imageUrn", "image", "urn", "id", "asset", "value")

        # PUT bytes to the upload URL when provided
        if upload_url and image_bytes:
            try:
                import requests

                hdrs = {
                    "Content-Type": mimetype,
                    "x-amz-acl": "public-read",
                    "Cache-Control": "no-cache"
                }
                logger.info("Uploading LinkedIn image to presigned URL")
                put = requests.put(upload_url, data=image_bytes, headers=hdrs, timeout=90)
                if put.status_code not in (200, 201, 204):
                    logger.warning("LinkedIn image upload failed: HTTP %s: %s", put.status_code, put.text[:300])
                    # Fall back to text-only post instead of failing completely
                    return post_linkedin(author_urn, text)
            except Exception as e:
                logger.warning("LinkedIn image upload exception: %s", e)
                # Fall back to text-only post instead of failing completely
                return post_linkedin(author_urn, text)

        # If image_urn not returned in init response, try nested locations
        if not image_urn:
            # Some toolkits return the URN in init.data.image or init.data.asset
            if isinstance(data, dict):
                image_urn = (
                    data.get("image_urn")
                    or data.get("imageUrn")
                    or data.get("image")
                    or data.get("urn")
                    or data.get("asset")
                )
        if not image_urn:
            # As a last resort, attempt to read from the top-level init response
            image_urn = _safe_get(init, "image_urn", "imageUrn", "image", "urn", "id")

        if not image_urn:
            return {"success": False, "error": "Could not determine image URN after upload"}

        # Create the post referencing the uploaded image URN
        # Use the content.media.id form when possible (toolkits accept media URNs)
        # to avoid treating the payload as a file-uploadable entry (s3key).
        post_args = {
            "author": urn,
            "commentary": text,
            "lifecycleState": "PUBLISHED",
            "visibility": "PUBLIC",
            "content": {"media": {"id": image_urn}},
        }
        resp = _execute_with_fallback("LINKEDIN_CREATE_LINKED_IN_POST", post_args, entity)
        if resp.get("successful"):
            return {"success": True}
        
        # Special case: NONEXISTENT_VERSION / 426 error means POST ACTUALLY SUCCEEDED
        # This is a known Composio bug where the post goes through but returns version error
        err_str = str(resp.get("error", "") or "").lower()
        if any(k in err_str for k in ("nonexistent_version", "requested version", "not active", "nonexistent version", "426")):
            logger.info("LinkedIn returned NONEXISTENT_VERSION error — POST ACTUALLY SUCCEEDED (Composio SDK bug)")
            return {"success": True}

        return {"success": False, "error": resp.get("error", "Unknown")}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Instagram
# =============================================================================

def _ensure_publishable_image_url(image_url: str) -> tuple[str, str, str | None]:
    """Re-host image on a fresh CDN URL so Meta doesn't reject stale/blocked URLs.

    Tries a list of preferred hosts (env `PREFERRED_IMAGE_HOSTS` or
    default `imgbb,imgur,cloudinary,s3`) and validates a candidate URL by
    attempting to create an Instagram media container via Composio. Returns
    a tuple `(new_url, source, container_id)` where `container_id` may be
    provided if validation already created the media container.
    """
    if not image_url:
        return "", "missing", None

    # Always attempt to download the image bytes first
    try:
        from src.agent.tools.image_tools import download_image
        local = download_image(image_url)
        if not local:
            return image_url, "as-is", None  # couldn't download — let Meta try
        import pathlib
        data = pathlib.Path(local).read_bytes()
    except Exception as e:
        logger.warning("IG image download failed: %s", e)
        return image_url, "as-is", None

    # Determine preferred hosts (comma-separated env var)
    pref = os.getenv("PREFERRED_IMAGE_HOSTS")
    if pref:
        hosts = [h.strip().lower() for h in pref.split(",") if h.strip()]
    else:
        hosts = ["imgur", "imgbb", "cloudinary", "s3"]

    # Prepare uploader callables (best-effort; skip if not available)
    uploaders = {}
    try:
        from src.agent.hf_image_gen import upload_to_imgbb as _hf_imgbb, upload_to_imgur as _hf_imgur
        uploaders["imgbb"] = _hf_imgbb
        uploaders["imgur"] = _hf_imgur
    except Exception:
        # fall back to the generic helper
        try:
            from src.agent.tools.image_tools import upload_image as _img_default
            uploaders.setdefault("imgbb", _img_default)
        except Exception:
            pass

    # Optional Cloudinary uploader (if cloudinary package & env configured)
    def _upload_cloudinary(bytes_data: bytes) -> dict:
        try:
            import cloudinary
            import cloudinary.uploader
            # cloudinary config may come from CLOUDINARY_URL or env vars
            res = cloudinary.uploader.upload(bytes_data)
            url = res.get("secure_url") or res.get("url")
            if url:
                return {"success": True, "url": url}
        except Exception as e:
            logger.debug("Cloudinary upload unavailable: %s", e)
        return {"success": False, "error": "cloudinary upload failed"}

    uploaders["cloudinary"] = _upload_cloudinary

    # Optional S3 uploader (if boto3 & AWS env configured)
    def _upload_s3(bytes_data: bytes) -> dict:
        try:
            import boto3
            bucket = os.getenv("AWS_S3_BUCKET")
            region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
            if not bucket:
                return {"success": False, "error": "S3 bucket not configured"}
            s3 = boto3.client("s3")
            key = f"fdwa_images/{int(time.time())}_{os.getpid()}.jpg"
            s3.put_object(Bucket=bucket, Key=key, Body=bytes_data, ACL="public-read", ContentType="image/jpeg")
            if region:
                url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
            else:
                url = f"https://{bucket}.s3.amazonaws.com/{key}"
            return {"success": True, "url": url}
        except Exception as e:
            logger.debug("S3 upload failed: %s", e)
            return {"success": False, "error": str(e)}

    uploaders["s3"] = _upload_s3

    entity = _entity()
    for host in hosts:
        uploader = uploaders.get(host)
        if not uploader:
            logger.debug("No uploader for host '%s', skipping", host)
            continue
        try:
            up = uploader(data)
        except Exception as e:
            logger.debug("Uploader '%s' raised: %s", host, e)
            up = {"success": False, "error": str(e)}

        if not up or not up.get("success") or not up.get("url"):
            logger.debug("Upload to %s failed: %s", host, up.get("error") if up else "no-result")
            continue

        candidate_url = up.get("url")

        # If we cannot call Composio to validate, accept first successful upload
        if not entity:
            return candidate_url, "reuploaded", None

        # Try to validate via Composio by attempting to create a media container
        try:
            resp = _execute_with_fallback(
                "INSTAGRAM_CREATE_MEDIA_CONTAINER",
                {"ig_user_id": INSTAGRAM_USER_ID, "image_url": candidate_url, "caption": "", "content_type": "photo"},
                entity,
            )
            if resp.get("successful"):
                cid = resp.get("data", {}).get("id") or None
                return candidate_url, "reuploaded", cid
            else:
                logger.debug("Composio rejected URL from %s: %s", host, resp.get("error"))
                continue
        except Exception as e:
            logger.debug("Composio validation failed for %s: %s", host, e)
            continue

    # Nothing validated — fall back to original
    return image_url, "as-is", None


def post_instagram(caption: str, image_url: str) -> dict:
    """Post to Instagram (image required). Returns dict with instagram_status.

    Before handing the URL to Meta, we download the bytes and re-upload to a
    fresh CDN URL — Meta aggressively rejects stale/re-used third-party CDN
    links (error 9004 / 2207052). A fresh URL avoids those rejections.
    """
    entity = _entity()
    if not INSTAGRAM_USER_ID:
        return {"error": "INSTAGRAM_USER_ID not set"}
    if not entity:
        return {"error": "COMPOSIO_ENTITY_ID not set"}
    if not image_url:
        return {"error": "Image required for Instagram"}

    publishable_url, source, container_id = _ensure_publishable_image_url(image_url)
    if not publishable_url:
        return {"error": "Could not produce a publishable image URL"}
    logger.info("IG image URL (%s): %s", source, publishable_url)

    client = get_composio_client()
    try:
        # If we already validated and received a container id, reuse it.
        if not container_id:
            container = _execute_with_fallback(
                "INSTAGRAM_CREATE_MEDIA_CONTAINER",
                {
                    "ig_user_id": INSTAGRAM_USER_ID,
                    "image_url": publishable_url,
                    "caption": caption,
                    "content_type": "photo",
                },
                entity,
            )
            if not container.get("successful"):
                return {"error": container.get("error", "Container failed")}
            container_id = container.get("data", {}).get("id", "")

        import time
        time.sleep(10)
        pub = _execute_with_fallback(
            "INSTAGRAM_CREATE_POST",
            {"ig_user_id": INSTAGRAM_USER_ID, "creation_id": container_id},
            entity,
        )
        if pub.get("successful"):
            post_id = pub.get("data", {}).get("id", "")
            return {"instagram_status": "Posted", "instagram_post_id": post_id}
        return {"error": pub.get("error", "Publish failed")}
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# Telegram (text only — NO images for Telegram)
# =============================================================================

def send_telegram_text(message: str) -> dict:
    """Send text-only message to Telegram group (no images)."""
    from src.agent import telegram_agent
    chat_id = telegram_agent.TELEGRAM_GROUP_USERNAME or telegram_agent.TELEGRAM_GROUP_CHAT_ID
    if not chat_id:
        return {"error": "No Telegram group configured"}
    try:
        result = telegram_agent.send_message(chat_id=chat_id, text=message)
        if result.get("success"):
            msg_id = result.get("data", {}).get("result", {}).get("message_id", "N/A")
            return {"telegram_status": f"Posted: message_id={msg_id}"}
        return {"error": result.get("error", "Unknown")}
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# READ layer — engagement / analytics pulls (Phase 16)
# =============================================================================

def _exec_read(slug: str, args: dict) -> dict:
    """Internal helper: run a Composio READ tool, return `data` dict or {}."""
    entity = _entity()
    if not entity:
        return {"_error": "COMPOSIO_ENTITY_ID not set"}
    try:
        resp = _execute_with_fallback(slug, args, entity)
        if not resp.get("successful"):
            return {"_error": resp.get("error", "Unknown"), "_slug": slug}
        return resp.get("data", {}) or {}
    except Exception as e:
        logger.warning("READ %s failed: %s", slug, e)
        return {"_error": str(e), "_slug": slug}


def fetch_facebook_page_insights(page_id: str | None = None, metric: str = "page_impressions") -> dict:
    """Pull Facebook Page insights (impressions, reach, engaged users)."""
    page_id = page_id or FACEBOOK_PAGE_ID
    if not page_id:
        return {"_error": "FACEBOOK_PAGE_ID not set"}
    return _exec_read(
        "FACEBOOK_GET_PAGE_INSIGHTS",
        {"page_id": page_id, "metric": metric, "period": "day"},
    )


def fetch_facebook_recent_posts(page_id: str | None = None, limit: int = 5) -> dict:
    """Fetch recent posts on the page with engagement counts."""
    page_id = page_id or FACEBOOK_PAGE_ID
    if not page_id:
        return {"_error": "FACEBOOK_PAGE_ID not set"}
    return _exec_read(
        "FACEBOOK_GET_PAGE_POSTS",
        {"page_id": page_id, "limit": limit},
    )


def fetch_linkedin_post_stats(share_urn: str) -> dict:
    """Pull LinkedIn share analytics (impressions, clicks, engagement)."""
    if not share_urn:
        return {"_error": "No share_urn"}
    return _exec_read(
        "LINKEDIN_GET_ANALYTICS_FOR_SHARE",
        {"share_urn": share_urn},
    )


def fetch_instagram_media_insights(media_id: str) -> dict:
    """Pull Instagram media insights (reach, impressions, likes, comments, saves)."""
    if not media_id:
        return {"_error": "No media_id"}
    return _exec_read(
        "INSTAGRAM_GET_MEDIA_INSIGHTS",
        {"media_id": media_id, "metric": "reach,impressions,likes,comments,saved"},
    )


def fetch_instagram_media_comments(media_id: str) -> dict:
    """Pull recent comments on an Instagram media."""
    if not media_id:
        return {"_error": "No media_id"}
    return _exec_read(
        "INSTAGRAM_GET_MEDIA_COMMENTS",
        {"media_id": media_id},
    )


def fetch_telegram_recent_updates(limit: int = 20) -> dict:
    """Poll recent Telegram updates (channel/group activity)."""
    from src.agent import telegram_agent
    try:
        data = telegram_agent.get_updates(limit=limit) if hasattr(telegram_agent, "get_updates") else None
        if data is None:
            return {"_error": "telegram_agent.get_updates not available"}
        return {"updates": data}
    except Exception as e:
        return {"_error": str(e)}


def send_telegram_alert(message: str) -> dict:
    """Send alert text to a dedicated Telegram failure chat if configured.

    Falls back to the primary group when no failure-specific target is configured.
    """
    from src.agent import telegram_agent

    failure_chat = os.getenv("TELEGRAM_FAILURE_GROUP_USERNAME") or os.getenv("TELEGRAM_FAILURE_GROUP_CHAT_ID")
    target = failure_chat or (telegram_agent.TELEGRAM_GROUP_USERNAME or telegram_agent.TELEGRAM_GROUP_CHAT_ID)
    if not target:
        return {"error": "No Telegram group configured for alerts"}
    try:
        result = telegram_agent.send_message(chat_id=target, text=message)
        if result.get("success"):
            msg_id = result.get("data", {}).get("result", {}).get("message_id", "N/A")
            return {"telegram_status": f"Posted: message_id={msg_id}"}
        return {"error": result.get("error", "Unknown")}
    except Exception as e:
        return {"error": str(e)}
