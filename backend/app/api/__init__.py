"""CareerMail AI — API routers."""

from app.api.auth import router as auth_router
from app.api.accounts import router as accounts_router
from app.api.emails import router as emails_router

__all__ = ["auth_router", "accounts_router", "emails_router"]
