"""Domain errors for authentication."""


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AuthUnavailableError(AuthError):
    def __init__(self, message: str = "Authentication service temporarily unavailable."):
        super().__init__(message, status_code=503)


class AuthConflictError(AuthError):
    def __init__(self, message: str):
        super().__init__(message, status_code=409)


class AuthForbiddenError(AuthError):
    def __init__(
        self, message: str = "You don't have permission to perform this action."
    ):
        super().__init__(message, status_code=403)


class AuthUnauthorizedError(AuthError):
    def __init__(self, message: str = "Authentication required."):
        super().__init__(message, status_code=401)


class AuthRateLimitError(AuthError):
    def __init__(self, message: str = "Too many login attempts. Please try again later."):
        super().__init__(message, status_code=429)
