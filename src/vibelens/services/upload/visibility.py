"""Upload visibility state and filtering.

Owns the mapping of browser session tokens to their last upload.
The storage layer tags metadata with _upload_id; this module provides
filter_visible() and is_session_visible() for service-layer callers
to enforce visibility without circular imports.

After a user uploads, only sessions from that last upload are shown;
example sessions are hidden. Tokens without uploads see examples only.
"""

from vibelens.utils import get_logger

logger = get_logger(__name__)

# Maps browser session token -> last upload_id
_token_last_upload: dict[str, str] = {}


def register_upload(session_token: str, upload_id: str) -> None:
    """Record the last upload for a browser session token.

    Replaces any previously tracked upload so the user only sees
    sessions from their most recent upload.

    Args:
        session_token: Browser tab UUID from X-Session-Token header.
        upload_id: Upload subdirectory name.
    """
    logger.info(
        "register_upload: token=%s upload_id=%s (prev=%s)",
        session_token[:8],
        upload_id,
        _token_last_upload.get(session_token, "none"),
    )
    _token_last_upload[session_token] = upload_id


def filter_visible(summaries: list[dict], session_token: str | None) -> list[dict]:
    """Filter metadata summaries to those visible to the given token.

    When the token has uploaded, only sessions from the last upload
    are returned; example sessions are hidden. Tokens without uploads
    see only example (root-level) sessions.

    Args:
        summaries: List of trajectory summary dicts.
        session_token: Browser tab token, or None.

    Returns:
        Filtered list of visible summaries.
    """
    token_short = session_token[:8] if session_token else "none"
    last_id = _token_last_upload.get(session_token) if session_token else None

    # Log upload_id distribution for debugging
    upload_ids = {}
    no_upload_count = 0
    for s in summaries:
        uid = s.get("_upload_id")
        if uid:
            upload_ids[uid] = upload_ids.get(uid, 0) + 1
        else:
            no_upload_count += 1

    logger.info(
        "filter_visible: token=%s last_upload=%s total=%d "
        "no_upload_id=%d upload_ids=%s",
        token_short,
        last_id or "none",
        len(summaries),
        no_upload_count,
        upload_ids,
    )

    if last_id:
        result = [s for s in summaries if s.get("_upload_id") == last_id]
    else:
        result = [s for s in summaries if not s.get("_upload_id")]

    logger.info("filter_visible: returning %d sessions", len(result))
    return result


def is_session_visible(meta: dict | None, session_token: str | None) -> bool:
    """Check if a single session is visible to the given token.

    When the token has uploaded, only the last upload's sessions are
    visible; example sessions are hidden. Tokens without uploads see
    only example sessions.

    Args:
        meta: Session metadata dict (may contain _upload_id).
        session_token: Browser tab token, or None.

    Returns:
        True if the session is visible.
    """
    if not meta:
        return False
    upload_id = meta.get("_upload_id")
    last_id = _token_last_upload.get(session_token) if session_token else None
    if last_id:
        return upload_id == last_id
    return not upload_id
