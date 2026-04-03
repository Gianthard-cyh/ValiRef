"""Custom exceptions for ValiRef."""
from typing import Optional


class ValirefError(Exception):
    """Base exception for ValiRef with error_code for frontend."""
    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class ErrorCode:
    """Error codes for structured error handling."""
    # Extraction errors
    PDF_CORRUPTED = "pdf_corrupted"
    PDF_NO_TEXT = "pdf_no_text"
    PDF_TOO_SHORT = "pdf_too_short"
    EXTRACTION_FAILED = "extraction_failed"
    NO_REFERENCES_FOUND = "no_references_found"

    # Validation errors
    VALIDATION_TIMEOUT = "validation_timeout"
    SEARCH_FAILED = "search_failed"
    AGENT_PARSE_ERROR = "agent_parse_error"


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
