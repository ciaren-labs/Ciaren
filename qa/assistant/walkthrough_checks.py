"""Sanitized acceptance checks shared by the live and recorded editor scenarios."""

from playwright.sync_api import Error as BrowserError


class Failed(Exception):
    """A fixed diagnostic suitable for printing; never embed request or exception contents."""


# Match only fixed Ciaren diagnostics. Never echo arbitrary server detail, nested validation input or provider text.
TURN_ERRORS = {
    "The provider returned an unsupported regression plan.": "REGRESSION_PLAN_SCHEMA",
    "The provider returned an unsupported Join proposal.": "JOIN_PLAN_SCHEMA",
    "The repair references an unavailable Join.": "JOIN_REFERENCE_MISMATCH",
    "The provider returned an incomplete structured answer.": "PROVIDER_OUTPUT_INVALID",
    "The provider request timed out.": "PROVIDER_TIMEOUT",
    "The provider request or response transfer failed.": "PROVIDER_TRANSPORT",
    "Provider request failed or returned an incomplete structured answer.": "PROVIDER_TRANSPORT_OR_OUTPUT",
    "Assistant hourly turn budget reached.": "LOCAL_TURN_BUDGET",
    "Choose an available dataset in this flow's project.": "INPUT_UNAVAILABLE",
    "Invalid input version.": "INPUT_VERSION",
    "Assistant request cancelled.": "TURN_CANCELLED",
    "Too many open proposals. Retry after existing proposals expire.": "PROPOSAL_CAPACITY",
}


def turn_error_code(response):
    try:
        body = response.json()
    except (ValueError, BrowserError):
        return "UNCLASSIFIED"
    detail = body.get("detail") if isinstance(body, dict) else None
    if not isinstance(detail, str):
        return "UNCLASSIFIED"
    if detail in TURN_ERRORS:
        return TURN_ERRORS[detail]
    for status in (400, 401, 402, 403, 404, 422, 429, 500, 502, 503, 504):
        if detail == f"Provider returned HTTP {status}. Check credentials, model and quota.":
            return f"UPSTREAM_HTTP_{status}"
    return "UNCLASSIFIED"


def check_turn(response, before, snapshot):
    failure = "" if response.ok else f"HTTP {response.status} [{turn_error_code(response)}]. "
    try:
        after = snapshot()
    except Exception:
        raise Failed(failure + "Saved state could not be verified.") from None
    if after != before:
        raise Failed(failure + "A proposal changed server state before approval.")
    if failure:
        raise Failed(failure.rstrip(". "))


def require(condition, message):
    if not condition:
        raise Failed(message)


def check_profile(get, provider, model):
    status = get("/assistant/status")
    require(
        (status.get("provider"), status.get("model"), status.get("state"), status.get("source"))
        == (provider, model, "configured", "env"),
        "Configured adapter, model or credential source did not match.",
    )
