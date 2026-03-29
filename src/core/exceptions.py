"""Custom exceptions for ValiRef."""


class ValirefError(Exception):
    """Base exception for ValiRef."""
    pass


class ExtractionError(ValirefError):
    """Raised when PDF extraction fails. Causes entire task to fail."""
    pass


class ValidationError(ValirefError):
    """Raised when reference validation fails."""
    pass


class ValidationTimeoutError(ValidationError):
    """Raised when validation timeout."""
    pass


class AgentParseError(ValidationError):
    """Raised when agent output parsing fails."""
    pass


class SearchError(ValirefError):
    """Raised when external search fails."""
    pass
