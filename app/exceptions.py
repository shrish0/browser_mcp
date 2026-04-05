from __future__ import annotations

from typing import Any, Dict, Optional


class AppException(Exception):
    def __init__(
        self,
        error_message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.error_message = error_message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(error_message)


class ScraperError(AppException):
    pass


class LoginRequiredError(ScraperError):
    def __init__(
        self,
        error_message: str = "Login required",
        status_code: int = 401,
        is_redirect: bool = False,
        requires_login: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = {
            "is_redirect": is_redirect,
            "requires_login": requires_login,
        }
        if details:
            payload.update(details)
        super().__init__(error_message, status_code, payload)


class NotFoundError(ScraperError):
    def __init__(
        self,
        error_message: str = "Page not found",
        status_code: int = 404,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(error_message, status_code, details)


class RedirectError(LoginRequiredError):
    def __init__(
        self,
        error_message: str = "Redirected to login or authentication page",
        status_code: int = 302,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(error_message, status_code, is_redirect=True, details=details)
