"""Enterprise security module for AgentCollab."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum, StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class UserRole(StrEnum):
    """User roles for RBAC."""

    ADMIN = "admin"
    MANAGER = "manager"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class Permission(StrEnum):
    """Permissions for RBAC."""

    # Workflow permissions
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_UPDATE = "workflow:update"
    WORKFLOW_DELETE = "workflow:delete"
    WORKFLOW_EXECUTE = "workflow:execute"

    # Task permissions
    TASK_CREATE = "task:create"
    TASK_READ = "task:read"
    TASK_UPDATE = "task:update"
    TASK_DELETE = "task:delete"
    TASK_EXECUTE = "task:execute"

    # User permissions
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"

    # Tenant permissions
    TENANT_CREATE = "tenant:create"
    TENANT_READ = "tenant:read"
    TENANT_UPDATE = "tenant:update"
    TENANT_DELETE = "tenant:delete"

    # API Key permissions
    API_KEY_CREATE = "api_key:create"
    API_KEY_READ = "api_key:read"
    API_KEY_DELETE = "api_key:delete"

    # Audit permissions
    AUDIT_READ = "audit:read"

    # Admin permissions
    ADMIN_ALL = "admin:all"


# Role-Permission mapping
ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.ADMIN: {Permission.ADMIN_ALL},
    UserRole.MANAGER: {
        Permission.WORKFLOW_CREATE,
        Permission.WORKFLOW_READ,
        Permission.WORKFLOW_UPDATE,
        Permission.WORKFLOW_DELETE,
        Permission.WORKFLOW_EXECUTE,
        Permission.TASK_CREATE,
        Permission.TASK_READ,
        Permission.TASK_UPDATE,
        Permission.TASK_DELETE,
        Permission.TASK_EXECUTE,
        Permission.USER_READ,
        Permission.API_KEY_CREATE,
        Permission.API_KEY_READ,
        Permission.API_KEY_DELETE,
        Permission.AUDIT_READ,
    },
    UserRole.DEVELOPER: {
        Permission.WORKFLOW_CREATE,
        Permission.WORKFLOW_READ,
        Permission.WORKFLOW_UPDATE,
        Permission.WORKFLOW_EXECUTE,
        Permission.TASK_CREATE,
        Permission.TASK_READ,
        Permission.TASK_UPDATE,
        Permission.TASK_EXECUTE,
        Permission.API_KEY_CREATE,
        Permission.API_KEY_READ,
    },
    UserRole.VIEWER: {
        Permission.WORKFLOW_READ,
        Permission.TASK_READ,
        Permission.API_KEY_READ,
    },
}


@dataclass
class User:
    """User model."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    email: str = ""
    hashed_password: str = ""
    role: UserRole = UserRole.DEVELOPER
    tenant_id: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_login: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Tenant:
    """Tenant model for multi-tenancy."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    slug: str = ""
    plan: str = "free"
    max_users: int = 10
    max_workflows: int = 100
    max_tasks_per_day: int = 1000
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class APIKey:
    """API Key model."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    tenant_id: str = ""
    name: str = ""
    key_hash: str = ""
    prefix: str = ""
    permissions: set[Permission] = field(default_factory=set)
    is_active: bool = True
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditLog:
    """Audit log entry."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    user_id: str = ""
    action: str = ""
    resource_type: str = ""
    resource_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    ip_address: str = ""
    user_agent: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Token:
    """JWT token model."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user_id: str = ""
    tenant_id: str = ""
    role: UserRole = UserRole.DEVELOPER


class AuthProvider(ABC):
    """Abstract base class for authentication providers.

    .. note::

        :class:`~agent_collab.security.providers.InMemoryAuthProvider` is
        provided for development.  For production, implement this interface
        backed by a database (e.g. PostgreSQL, MongoDB).
    """

    @abstractmethod
    async def authenticate(self, username: str, password: str) -> User | None:
        """Authenticate a user with username and password.

        Args:
            username: The username.
            password: The password.

        Returns:
            The authenticated user, or None if authentication failed.
        """

    @abstractmethod
    async def get_user(self, user_id: str) -> User | None:
        """Get a user by ID.

        Args:
            user_id: The user ID.

        Returns:
            The user, or None if not found.
        """

    @abstractmethod
    async def create_user(self, user: User) -> User:
        """Create a new user.

        Args:
            user: The user to create.

        Returns:
            The created user.
        """

    @abstractmethod
    async def update_user(self, user: User) -> User:
        """Update a user.

        Args:
            user: The user to update.

        Returns:
            The updated user.
        """

    @abstractmethod
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user.

        Args:
            user_id: The user ID.

        Returns:
            True if the user was deleted.
        """

    @abstractmethod
    async def get_users_by_tenant(self, tenant_id: str) -> list[User]:
        """Get all users for a tenant.

        Args:
            tenant_id: The tenant ID.

        Returns:
            List of users.
        """


class TenantProvider(ABC):
    """Abstract base class for tenant providers."""

    @abstractmethod
    async def get_tenant(self, tenant_id: str) -> Tenant | None:
        """Get a tenant by ID.

        Args:
            tenant_id: The tenant ID.

        Returns:
            The tenant, or None if not found.
        """

    @abstractmethod
    async def create_tenant(self, tenant: Tenant) -> Tenant:
        """Create a new tenant.

        Args:
            tenant: The tenant to create.

        Returns:
            The created tenant.
        """

    @abstractmethod
    async def update_tenant(self, tenant: Tenant) -> Tenant:
        """Update a tenant.

        Args:
            tenant: The tenant to update.

        Returns:
            The updated tenant.
        """

    @abstractmethod
    async def delete_tenant(self, tenant_id: str) -> bool:
        """Delete a tenant.

        Args:
            tenant_id: The tenant ID.

        Returns:
            True if the tenant was deleted.
        """

    @abstractmethod
    async def get_all_tenants(self) -> list[Tenant]:
        """Get all tenants.

        Returns:
            List of tenants.
        """


class APIKeyProvider(ABC):
    """Abstract base class for API key providers."""

    @abstractmethod
    async def create_api_key(self, api_key: APIKey) -> str:
        """Create a new API key.

        Args:
            api_key: The API key to create.

        Returns:
            The raw API key (only shown once).
        """

    @abstractmethod
    async def get_api_key(self, key_id: str) -> APIKey | None:
        """Get an API key by ID.

        Args:
            key_id: The API key ID.

        Returns:
            The API key, or None if not found.
        """

    @abstractmethod
    async def validate_api_key(self, raw_key: str) -> APIKey | None:
        """Validate an API key.

        Args:
            raw_key: The raw API key.

        Returns:
            The API key if valid, or None if invalid.
        """

    @abstractmethod
    async def delete_api_key(self, key_id: str) -> bool:
        """Delete an API key.

        Args:
            key_id: The API key ID.

        Returns:
            True if the API key was deleted.
        """

    @abstractmethod
    async def get_api_keys_by_user(self, user_id: str) -> list[APIKey]:
        """Get all API keys for a user.

        Args:
            user_id: The user ID.

        Returns:
            List of API keys.
        """


class AuditProvider(ABC):
    """Abstract base class for audit providers."""

    @abstractmethod
    async def log(self, entry: AuditLog) -> None:
        """Log an audit entry.

        Args:
            entry: The audit log entry.
        """

    @abstractmethod
    async def get_logs(
        self,
        tenant_id: str,
        user_id: str | None = None,
        action: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        """Get audit logs.

        Args:
            tenant_id: The tenant ID.
            user_id: Optional user ID filter.
            action: Optional action filter.
            start_time: Optional start time filter.
            end_time: Optional end time filter.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            List of audit log entries.
        """


def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt.

    Args:
        password: The password to hash.

    Returns:
        The hashed password.
    """
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a hash.

    Args:
        password: The password to verify.
        hashed_password: The hashed password.

    Returns:
        True if the password matches.
    """
    try:
        salt, expected_hash = hashed_password.split("$", 1)
        actual_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return actual_hash == expected_hash
    except ValueError:
        return False


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (raw_key, key_hash, prefix).
    """
    raw_key = f"ac_{secrets.token_urlsafe(32)}"
    prefix = raw_key[:8]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash, prefix


def has_permission(user_role: UserRole, required_permission: Permission) -> bool:
    """Check if a user role has a permission.

    Args:
        user_role: The user's role.
        required_permission: The required permission.

    Returns:
        True if the role has the permission.
    """
    permissions = ROLE_PERMISSIONS.get(user_role, set())
    return Permission.ADMIN_ALL in permissions or required_permission in permissions


# ── JWT Token helpers (stdlib-only, no PyJWT dependency) ──────────────

import base64
import json as _json


def _b64url_encode(data: bytes) -> str:
    """Base64url-encode *data* without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    """Base64url-decode *s*, re-adding padding as needed."""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


# Module-level secret; override via ``set_token_secret()`` or env var.
_token_secret: str = os.environ.get("AGENT_COLLAB_SECRET", "")


def set_token_secret(secret: str) -> None:
    """Set the HMAC signing secret for JWT tokens.

    Call once at startup (e.g. from CLI or config loader).
    If not called, a random secret is generated per-process.
    """
    global _token_secret
    _token_secret = secret


def _get_secret() -> str:
    global _token_secret
    if not _token_secret:
        _token_secret = secrets.token_hex(32)
    return _token_secret


def generate_token(
    user: User,
    expires_in: int = 3600,
    secret: str | None = None,
) -> Token:
    """Generate a signed JWT-like token for *user*.

    The token is a compact ``header.payload.signature`` string signed
    with HMAC-SHA256.  No external JWT library is required.

    Args:
        user: The authenticated user.
        expires_in: Token lifetime in seconds (default 3600).
        secret: Override signing secret.  Falls back to module secret.

    Returns:
        A :class:`Token` instance with ``access_token`` set.
    """
    secret = secret or _get_secret()
    now = datetime.now(UTC)

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user.id,
        "username": user.username,
        "tenant_id": user.tenant_id,
        "role": user.role.value,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }

    header_b64 = _b64url_encode(_json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(_json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}"

    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)

    access_token = f"{signing_input}.{signature_b64}"

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
    )


def verify_token(
    access_token: str,
    secret: str | None = None,
) -> dict[str, Any] | None:
    """Verify a JWT-like token and return its payload.

    Args:
        access_token: The compact ``header.payload.signature`` string.
        secret: Override signing secret.  Falls back to module secret.

    Returns:
        The decoded payload dict if the signature is valid and the
        token has not expired, or ``None`` on any failure.
    """
    secret = secret or _get_secret()
    try:
        parts = access_token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}"

        expected_sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        actual_sig = _b64url_decode(signature_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload_bytes = _b64url_decode(payload_b64)
        payload: dict[str, Any] = _json.loads(payload_bytes)

        # Check expiration
        if payload.get("exp", 0) < datetime.now(UTC).timestamp():
            return None

        return payload

    except Exception:
        return None
