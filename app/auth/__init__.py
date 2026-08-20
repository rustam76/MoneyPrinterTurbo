"""Authentication package for MoneyPrinterTurbo.

When MPT_AUTH_ENABLED is false (default), callers should skip auth gates.
"""

from app.auth.settings import auth_settings, is_auth_enabled

__all__ = ["auth_settings", "is_auth_enabled"]
