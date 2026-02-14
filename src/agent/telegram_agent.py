"""Telegram Agent for FDWA AI - Using Composio v3 API directly.

This agent works with the Composio v3 API format that was verified to work.
"""

import logging
import os
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_ENTITY_ID")  # Composio v3 uses `user_id`
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID")  # numeric chat id (optional)
TELEGRAM_GROUP_USERNAME = os.getenv("TELEGRAM_GROUP_USERNAME")  # preferred: username (e.g. @yieldbotdefi)
TELEGRAM_CONNECTED_ACCOUNT_ID = os.getenv("TELEGRAM_ACCOUNT_ID")  # composio connected account id (optional)
BASE_URL = "https://backend.composio.dev/api/v3/tools/execute"

# Configure logging
logger = logging.getLogger(__name__)


def _execute_telegram_tool(tool_slug: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a Telegram tool using Composio v3 API (safe, resilient wrapper).

    - Validates required env vars
    - Normalizes Composio response and surfaces Telegram error messages when present
    - Returns consistent dict: {success: bool, data?:..., error?:..., status_code?: int}
    """
    if not COMPOSIO_API_KEY:
        return {"success": False, "error": "COMPOSIO_API_KEY not set"}
    if not TELEGRAM_USER_ID:
        return {"success": False, "error": "TELEGRAM_ENTITY_ID (user_id) not set"}

    url = f"{BASE_URL}/{tool_slug}"
    headers = {"x-api-key": COMPOSIO_API_KEY, "Content-Type": "application/json"}
    payload = {"user_id": TELEGRAM_USER_ID, "arguments": arguments}

    logger.debug("POST %s %s", url, arguments)

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
    except Exception as e:
        logger.exception("Network error calling Composio: %s", e)
        return {"success": False, "error": f"Network error: {e}"}

    status = resp.status_code

    # Try to parse JSON response from Composio
    try:
        body = resp.json()
    except Exception:
        body = {"raw_text": resp.text}

    # Normal success path
    if status == 200 and body.get("successful"):
        return {"success": True, "data": body.get("data"), "log_id": body.get("log_id"), "status_code": status}

    # If Composio returned structured error, try to surface helpful message
    # Composio often embeds Telegram HTTP error details inside data/http_error or error
    error_detail = None
    if isinstance(body, dict):
        error_detail = body.get("error") or (body.get("data") or {}).get("message") or (body.get("data") or {}).get("http_error")

    err_msg = error_detail or f"Composio HTTP {status}: {resp.text}"
    logger.warning("%s returned error: %s", tool_slug, err_msg)

    return {"success": False, "error": err_msg, "body": body, "status_code": status}



def send_message(
    chat_id: str,
    text: str,
    parse_mode: str | None = None,
    disable_notification: bool = False,
    disable_web_page_preview: bool = False,
    reply_to_message_id: int | None = None,
    reply_markup: str | None = None,
    use_direct: bool = False
) -> Dict[str, Any]:
    """Send a text message to a Telegram chat.

    - By default uses Composio v3 tools (recommended).
    - If `use_direct=True` or Composio fails and `TELEGRAM_BOT_TOKEN` is set,
      falls back to direct Bot API.

    Returns consistent dict {success: bool, data?:..., error?:...}
    """
    # Build Composio arguments
    arguments = {
        "chat_id": chat_id,
        "text": text,
        "disable_notification": disable_notification,
        "disable_web_page_preview": disable_web_page_preview
    }
    if parse_mode:
        arguments["parse_mode"] = parse_mode
    if reply_to_message_id:
        arguments["reply_to_message_id"] = reply_to_message_id
    if reply_markup:
        arguments["reply_markup"] = reply_markup

    # Use Composio v3 API only — follow toolkit docs (accepts `@channelusername`)
    result = _execute_telegram_tool("TELEGRAM_SEND_MESSAGE", arguments)
    
    # Extract and save crypto tokens mentioned in message
    if result.get("success"):
        try:
            from src.agent.sheets_agent import (
                extract_crypto_tokens_from_text,
                save_token_to_sheets,
            )
            tokens = extract_crypto_tokens_from_text(text)
            for token in tokens:
                save_token_to_sheets(
                    symbol=token,
                    source="telegram_outbound",
                    notes=f"Mentioned in bot message to {chat_id}"
                )
                logger.debug(f"Tracked token {token} from Telegram message")
        except Exception as e:
            logger.debug(f"Token extraction error (non-critical): {e}")
    
    return result


# NOTE: direct Bot API fallback removed to strictly follow Composio toolkit docs.
# All sends now go through Composio v3 tools (accepts `chat_id` as username or channel name).


def get_updates(
    offset: int | None = None,
    limit: int = 100,
    timeout: int = 0
) -> Dict[str, Any]:
    """Get incoming updates using long polling.
    
    Args:
        offset: Identifier of first update to return
        limit: Number of updates to retrieve (1-100)
        timeout: Timeout in seconds for long polling
        
    Returns:
        Dict with success status and updates array
    """
    arguments = {"limit": limit}
    
    if offset is not None:
        arguments["offset"] = offset
    if timeout:
        arguments["timeout"] = timeout
    
    return _execute_telegram_tool("TELEGRAM_GET_UPDATES", arguments)


def get_bot_info() -> Dict[str, Any]:
    """Get information about the bot.
    
    Returns:
        Dict with success status and bot info
    """
    return _execute_telegram_tool("TELEGRAM_GET_ME", {})


def send_photo(
    chat_id: str,
    photo: str,
    caption: str | None = None,
    parse_mode: str | None = None,
    disable_notification: bool = False
) -> Dict[str, Any]:
    """Send a photo to a Telegram chat.
    
    Args:
        chat_id: Chat ID or username
        photo: Photo URL or file_id
        caption: Photo caption (0-1024 characters)
        parse_mode: Caption parse mode
        disable_notification: Send silently
        
    Returns:
        Dict with success status and message data
    """
    arguments = {
        "chat_id": chat_id,
        "photo": photo,
        "disable_notification": disable_notification
    }
    
    if caption:
        arguments["caption"] = caption
    if parse_mode:
        arguments["parse_mode"] = parse_mode
    
    result = _execute_telegram_tool("TELEGRAM_SEND_PHOTO", arguments)
    
    # Extract and save crypto tokens from caption
    if result.get("success") and caption:
        try:
            from src.agent.sheets_agent import (
                extract_crypto_tokens_from_text,
                save_token_to_sheets,
            )
            tokens = extract_crypto_tokens_from_text(caption)
            for token in tokens:
                save_token_to_sheets(
                    symbol=token,
                    source="telegram_photo_caption",
                    notes=f"Mentioned in photo caption to {chat_id}"
                )
                logger.debug(f"Tracked token {token} from Telegram photo caption")
        except Exception as e:
            logger.debug(f"Token extraction error (non-critical): {e}")
    
    return result


def send_document(
    chat_id: str,
    document: str,
    caption: str | None = None,
    parse_mode: str | None = None,
    disable_notification: bool = False
) -> Dict[str, Any]:
    """Send a document to a Telegram chat.
    
    Args:
        chat_id: Chat ID or username
        document: Document URL or file_id
        caption: Document caption
        parse_mode: Caption parse mode
        disable_notification: Send silently
        
    Returns:
        Dict with success status
    """
    arguments = {
        "chat_id": chat_id,
        "document": document,
        "disable_notification": disable_notification
    }
    
    if caption:
        arguments["caption"] = caption
    if parse_mode:
        arguments["parse_mode"] = parse_mode
    
    return _execute_telegram_tool("TELEGRAM_SEND_DOCUMENT", arguments)


def send_poll(
    chat_id: str,
    question: str,
    options: List[str],
    is_anonymous: bool = True,
    allows_multiple_answers: bool = False,
    disable_notification: bool = False
) -> Dict[str, Any]:
    """Send a poll to a Telegram chat.
    
    Args:
        chat_id: Chat ID or username
        question: Poll question (1-300 characters)
        options: List of answer options (2-10 items)
        is_anonymous: True if poll is anonymous
        allows_multiple_answers: True if multiple answers allowed
        disable_notification: Send silently
        
    Returns:
        Dict with success status
    """
    arguments = {
        "chat_id": chat_id,
        "question": question,
        "options": options,
        "is_anonymous": is_anonymous,
        "allows_multiple_answers": allows_multiple_answers,
        "disable_notification": disable_notification
    }
    
    return _execute_telegram_tool("TELEGRAM_SEND_POLL", arguments)


def send_location(
    chat_id: str,
    latitude: float,
    longitude: float,
    disable_notification: bool = False
) -> Dict[str, Any]:
    """Send a location to a Telegram chat.
    
    Args:
        chat_id: Chat ID or username
        latitude: Latitude of location
        longitude: Longitude of location
        disable_notification: Send silently
        
    Returns:
        Dict with success status
    """
    arguments = {
        "chat_id": chat_id,
        "latitude": latitude,
        "longitude": longitude,
        "disable_notification": disable_notification
    }
    
    return _execute_telegram_tool("TELEGRAM_SEND_LOCATION", arguments)


def get_chat_info(chat_id: str) -> Dict[str, Any]:
    """Get information about a chat.
    
    Args:
        chat_id: Chat ID or username
        
    Returns:
        Dict with success status and chat info
    """
    return _execute_telegram_tool("TELEGRAM_GET_CHAT", {"chat_id": chat_id})


def edit_message(
    chat_id: str,
    message_id: int,
    text: str,
    parse_mode: str | None = None
) -> Dict[str, Any]:
    """Edit a text message.
    
    Args:
        chat_id: Chat ID or username
        message_id: ID of message to edit
        text: New text content
        parse_mode: Parse mode for new text
        
    Returns:
        Dict with success status
    """
    arguments = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }
    
    if parse_mode:
        arguments["parse_mode"] = parse_mode
    
    return _execute_telegram_tool("TELEGRAM_EDIT_MESSAGE", arguments)


def delete_message(chat_id: str, message_id: int) -> Dict[str, Any]:
    """Delete a message.
    
    Args:
        chat_id: Chat ID or username
        message_id: ID of message to delete
        
    Returns:
        Dict with success status
    """
    arguments = {
        "chat_id": chat_id,
        "message_id": message_id
    }
    
    return _execute_telegram_tool("TELEGRAM_DELETE_MESSAGE", arguments)


# Convenience function for default group
def send_to_group(text: str, **kwargs) -> Dict[str, Any]:
    """Send message to the configured Telegram group.

    Behavior:
    - If `TELEGRAM_GROUP_CHAT_ID` is set, use it.
    - Else, try `TELEGRAM_GROUP_USERNAME` (e.g. @yieldbotdefi).
    - If username send succeeds and returns numeric chat id, recommend setting TELEGRAM_GROUP_CHAT_ID.
    """
    # Preferred: use configured username (per Composio docs)
    if TELEGRAM_GROUP_USERNAME:
        return send_message(TELEGRAM_GROUP_USERNAME, text, **kwargs)

    # Fallback: if numeric chat id is explicitly set, use it
    if TELEGRAM_GROUP_CHAT_ID:
        return send_message(TELEGRAM_GROUP_CHAT_ID, text, **kwargs)

    return {"success": False, "error": "No TELEGRAM_GROUP_USERNAME or TELEGRAM_GROUP_CHAT_ID configured. Set TELEGRAM_GROUP_USERNAME=@yourgroup or add the bot to the group and run get_chat_id_from_updates.py."}
