class LibreLeafError(Exception):
    """Base exception that can be shown to a command-line user."""


class ApiError(LibreLeafError):
    """An upstream API failed after the configured retry policy."""


class ConfigurationError(LibreLeafError):
    """Required provider credentials or configuration are missing."""


class InvalidIsbnError(LibreLeafError):
    """An ISBN is malformed or fails its checksum."""
