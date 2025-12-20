"""Authentication configuration for fastapi-users with email/password and JWT."""

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Literal, Optional, overload

import jwt
from beanie import PydanticObjectId
from dotenv import load_dotenv
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)

from advanced_omi_backend.users import User, UserCreate, get_user_db

logger = logging.getLogger(__name__)

load_dotenv()

# JWT configuration
JWT_LIFETIME_SECONDS = int(os.getenv("JWT_LIFETIME_SECONDS", "86400"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

# Cached config values (lazy-loaded from config.yaml/secrets.yaml)
_secret_key: Optional[str] = None
_admin_password: Optional[str] = None
_admin_email: Optional[str] = None


def get_secret_key() -> str:
    """Get AUTH_SECRET_KEY from secrets.yaml (lazy-loaded)."""
    global _secret_key
    if _secret_key is None:
        # Try environment variable first (for backward compatibility)
        _secret_key = os.getenv("AUTH_SECRET_KEY")
        if not _secret_key:
            # Load from config
            try:
                from advanced_omi_backend.config import get_config_parser
                import asyncio

                config_parser = get_config_parser()
                config = asyncio.run(config_parser.load())
                _secret_key = config.auth.secret_key

                if not _secret_key:
                    raise ValueError("AUTH_SECRET_KEY not found in secrets.yaml or environment")
            except Exception as e:
                logger.error(f"Failed to load AUTH_SECRET_KEY from config: {e}")
                raise ValueError("AUTH_SECRET_KEY not configured") from e
    return _secret_key


def get_admin_password() -> str:
    """Get ADMIN_PASSWORD from environment (used for initial setup only)."""
    global _admin_password
    if _admin_password is None:
        _admin_password = os.getenv("ADMIN_PASSWORD")
        if not _admin_password:
            raise ValueError("ADMIN_PASSWORD not set - required for admin user creation")
    return _admin_password


def get_admin_email() -> str:
    """Get admin email from config (lazy-loaded)."""
    global _admin_email
    if _admin_email is None:
        # Try environment variable first
        _admin_email = os.getenv("ADMIN_EMAIL")
        if not _admin_email:
            # Load from config
            try:
                from advanced_omi_backend.config import get_config_parser
                import asyncio

                config_parser = get_config_parser()
                config = asyncio.run(config_parser.load())
                _admin_email = config.auth.admin_email or "admin@example.com"
            except Exception:
                _admin_email = "admin@example.com"
    return _admin_email


class UserManager(BaseUserManager[User, PydanticObjectId]):
    """User manager with minimal customization for fastapi-users."""

    @property
    def reset_password_token_secret(self) -> str:
        return get_secret_key()

    @property
    def verification_token_secret(self) -> str:
        return get_secret_key()

    def parse_id(self, value: str) -> PydanticObjectId:
        """Parse string ID to PydanticObjectId for MongoDB compatibility."""
        try:
            return PydanticObjectId(value)
        except Exception as e:
            raise ValueError(f"Invalid ObjectId format: {value}") from e

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        """Called after a user registers."""
        logger.info(f"User {user.user_id} ({user.email}) has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """Called after a user requests password reset."""
        logger.info(f"User {user.user_id} ({user.email}) has requested password reset")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """Called after a user requests verification."""
        logger.info(f"Verification requested for user {user.user_id} ({user.email})")


async def get_user_manager(user_db=Depends(get_user_db)):
    """Get user manager instance for dependency injection."""
    yield UserManager(user_db)


# Transport configurations
cookie_transport = CookieTransport(
    cookie_max_age=JWT_LIFETIME_SECONDS,  # Matches JWT lifetime
    cookie_secure=COOKIE_SECURE,  # Set to False in development if not using HTTPS
    cookie_httponly=True,
    cookie_samesite="lax",
)

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    """Get JWT strategy for token generation and validation."""
    return JWTStrategy(
        secret=get_secret_key(), lifetime_seconds=JWT_LIFETIME_SECONDS
    )


def generate_jwt_for_user(user_id: str, user_email: str) -> str:
    """Generate a JWT token for a user to authenticate with external services.

    This function creates a JWT token that can be used to authenticate with
    services that share the same AUTH_SECRET_KEY, such as Mycelia.

    Args:
        user_id: User's unique identifier (MongoDB ObjectId as string)
        user_email: User's email address

    Returns:
        JWT token string valid for JWT_LIFETIME_SECONDS (default: 24 hours)

    Example:
        >>> token = generate_jwt_for_user("507f1f77bcf86cd799439011", "user@example.com")
        >>> # Use token to call Mycelia API
    """
    # Create JWT payload matching Chronicle's standard format
    payload = {
        "sub": user_id,  # Subject = user ID
        "email": user_email,
        "iss": "chronicle",  # Issuer
        "aud": "chronicle",  # Audience
        "exp": datetime.utcnow() + timedelta(seconds=JWT_LIFETIME_SECONDS),
        "iat": datetime.utcnow(),  # Issued at
    }

    # Sign the token with the same secret key
    token = jwt.encode(payload, get_secret_key(), algorithm="HS256")
    return token


# Authentication backends
cookie_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

bearer_backend = AuthenticationBackend(
    name="bearer",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# FastAPI Users instance
fastapi_users = FastAPIUsers[User, PydanticObjectId](
    get_user_manager,
    [cookie_backend, bearer_backend],
)

# User dependencies for protecting endpoints
current_active_user = fastapi_users.current_user(active=True)
current_active_user_optional = fastapi_users.current_user(active=True, optional=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)


async def get_user_from_token_param(token: str) -> Optional[User]:
    """
    Get user from JWT token string (for query parameter authentication).

    This is useful for endpoints that need to support token-based auth via query params,
    such as HTML audio elements that can't set custom headers.

    Args:
        token: JWT token string

    Returns:
        User object if token is valid and user is active, None otherwise
    """
    if not token:
        return None
    try:
        strategy = get_jwt_strategy()
        user_db_gen = get_user_db()
        user_db = await user_db_gen.__anext__()
        user_manager = UserManager(user_db)
        user = await strategy.read_token(token, user_manager)
        if user and user.is_active:
            return user
    except Exception:
        pass
    return None


def get_accessible_user_ids(user: User) -> list[str] | None:
    """
    Get list of user IDs that the current user can access data for.
    Returns None for superusers (can access all), or [user.id] for regular users.
    """
    if user.is_superuser:
        return None  # Can access all data
    else:
        return [str(user.id)]  # Can only access own data


async def create_admin_user_if_needed():
    """Create admin user during startup if it doesn't exist and credentials are provided."""
    try:
        admin_password = get_admin_password()
    except ValueError:
        logger.warning("Skipping admin user creation - ADMIN_PASSWORD not set")
        return

    try:
        admin_email = get_admin_email()

        # Get user database
        user_db_gen = get_user_db()
        user_db = await user_db_gen.__anext__()

        # Check if admin user already exists by email
        existing_admin = await user_db.get_by_email(admin_email)

        if existing_admin:
            logger.info(
                f"✅ Admin user already exists: {existing_admin.user_id} ({existing_admin.email})"
            )
            return

        # Create admin user
        user_manager_gen = get_user_manager(user_db)
        user_manager = await user_manager_gen.__anext__()

        admin_create = UserCreate(
            email=admin_email,
            password=admin_password,
            is_superuser=True,
            is_verified=True,
            display_name="Administrator",
        )

        admin_user = await user_manager.create(admin_create)
        logger.info(
            f"✅ Created admin user: {admin_user.user_id} ({admin_user.email}) (ID: {admin_user.id})"
        )

    except Exception as e:
        logger.error(f"Failed to create admin user: {e}", exc_info=True)


async def websocket_auth(websocket, token: Optional[str] = None) -> Optional[User]:
    """
    WebSocket authentication that supports both cookie and token-based auth.
    Returns None if authentication fails (allowing graceful handling).
    """
    strategy = get_jwt_strategy()

    # Try JWT token from query parameter first
    if token:
        logger.info(f"Attempting WebSocket auth with query token (first 20 chars): {token[:20]}...")
        try:
            user_db_gen = get_user_db()
            user_db = await user_db_gen.__anext__()
            user_manager = UserManager(user_db)
            user = await strategy.read_token(token, user_manager)
            if user and user.is_active:
                logger.info(f"WebSocket auth successful for user {user.user_id} using query token.")
                return user
            else:
                logger.warning(f"Token validated but user inactive or not found: user={user}")
        except Exception as e:
            logger.error(f"WebSocket auth with query token failed: {type(e).__name__}: {e}", exc_info=True)

    # Try cookie authentication
    logger.debug("Attempting WebSocket auth with cookie.")
    try:
        cookie_header = next(
            (v.decode() for k, v in websocket.headers.items() if k.lower() == b"cookie"), None
        )
        if cookie_header:
            match = re.search(r"fastapiusersauth=([^;]+)", cookie_header)
            if match:
                user_db_gen = get_user_db()
                user_db = await user_db_gen.__anext__()
                user_manager = UserManager(user_db)
                user = await strategy.read_token(match.group(1), user_manager)
                if user and user.is_active:
                    logger.info(f"WebSocket auth successful for user {user.user_id} using cookie.")
                    return user
    except Exception as e:
        logger.warning(f"WebSocket auth with cookie failed: {e}")

    logger.warning("WebSocket authentication failed.")
    return None
