"""Exceptions used across the crawler modules."""


class ApiError(RuntimeError):
    """Raised when a Bilibili API call does not return usable data."""


class RiskControlError(ApiError):
    """Raised when Bilibili blocks an unauthenticated or unsigned request."""
