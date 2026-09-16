"""Tools available to the agent."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import tool


@tool
def get_current_time(timezone_name: str = "UTC") -> str:
    """Return the current time as an ISO-8601 string.

    Args:
        timezone_name: IANA timezone name (e.g. ``"UTC"``,
            ``"America/New_York"``). Defaults to ``"UTC"``. Empty strings
            are coerced to ``"UTC"``.

    Returns:
        str: ISO-8601 formatted timestamp in the requested timezone.

    Raises:
        ValueError: If ``timezone_name`` is not a valid IANA timezone name.
    """
    tz_name = timezone_name or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {timezone_name!r}") from exc
    return datetime.now(tz).isoformat()


def default_tools() -> list:
    """Return the default tool set exposed to the agent.

    Returns:
        list: Tools the agent may call. Currently a single-element list
        containing :func:`get_current_time`.
    """
    return [get_current_time]
