"""Panel-specific exceptions for clean error handling upstream."""


class PanelError(Exception):
    """Base error for any 3X-UI panel interaction."""


class PanelAuthError(PanelError):
    """Login failed / session expired."""


class PanelRequestError(PanelError):
    """A request to the panel returned a non-success result."""


class PanelUnavailableError(PanelError):
    """Panel is unreachable (network/timeout) — treat server as down."""
