"""In-memory implementations for security module."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from agent_collab.security import (
    APIKey,
    APIKeyProvider,
    AuditLog,
    AuditProvider,
    AuthProvider,
    Permission,
    Tenant,
    TenantProvider,
    User,
    UserRole,
    generate_api_key,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)


class InMemoryAuthProvider(AuthProvider):
    """In-memory authentication provider."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    async def authenticate(self, username: str, password: str) -> User | None:
        """Authenticate a user with username and password."""
        for user in self._users.values():
            if user.username == username and user.is_active:
                if verify_password(password, user.hashed_password):
                    user.last_login = datetime.now(timezone.utc)
                    return user
        return None

    async def get_user(self, user_id: str) -> User | None:
        """Get a user by ID."""
        return self._users.get(user_id)

    async def create_user(self, user: User) -> User:
        """Create a new user."""
        if not user.hashed_password:
            raise ValueError("Password is required")
        self._users[user.id] = user
        logger.info(f"User {user.id} created: {user.username}")
        return user

    async def update_user(self, user: User) -> User:
        """Update a user."""
        if user.id not in self._users:
            raise ValueError(f"User {user.id} not found")
        user.updated_at = datetime.now(timezone.utc)
        self._users[user.id] = user
        logger.info(f"User {user.id} updated")
        return user

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        if user_id in self._users:
            del self._users[user_id]
            logger.info(f"User {user_id} deleted")
            return True
        return False

    async def get_users_by_tenant(self, tenant_id: str) -> list[User]:
        """Get all users for a tenant."""
        return [u for u in self._users.values() if u.tenant_id == tenant_id]


class InMemoryTenantProvider(TenantProvider):
    """In-memory tenant provider."""

    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}

    async def get_tenant(self, tenant_id: str) -> Tenant | None:
        """Get a tenant by ID."""
        return self._tenants.get(tenant_id)

    async def create_tenant(self, tenant: Tenant) -> Tenant:
        """Create a new tenant."""
        self._tenants[tenant.id] = tenant
        logger.info(f"Tenant {tenant.id} created: {tenant.name}")
        return tenant

    async def update_tenant(self, tenant: Tenant) -> Tenant:
        """Update a tenant."""
        if tenant.id not in self._tenants:
            raise ValueError(f"Tenant {tenant.id} not found")
        tenant.updated_at = datetime.now(timezone.utc)
        self._tenants[tenant.id] = tenant
        logger.info(f"Tenant {tenant.id} updated")
        return tenant

    async def delete_tenant(self, tenant_id: str) -> bool:
        """Delete a tenant."""
        if tenant_id in self._tenants:
            del self._tenants[tenant_id]
            logger.info(f"Tenant {tenant_id} deleted")
            return True
        return False

    async def get_all_tenants(self) -> list[Tenant]:
        """Get all tenants."""
        return list(self._tenants.values())


class InMemoryAPIKeyProvider(APIKeyProvider):
    """In-memory API key provider."""

    def __init__(self) -> None:
        self._api_keys: dict[str, APIKey] = {}

    async def create_api_key(self, api_key: APIKey) -> str:
        """Create a new API key."""
        raw_key, key_hash, prefix = generate_api_key()
        api_key.key_hash = key_hash
        api_key.prefix = prefix
        self._api_keys[api_key.id] = api_key
        logger.info(f"API key {api_key.id} created for user {api_key.user_id}")
        return raw_key

    async def get_api_key(self, key_id: str) -> APIKey | None:
        """Get an API key by ID."""
        return self._api_keys.get(key_id)

    async def validate_api_key(self, raw_key: str) -> APIKey | None:
        """Validate an API key."""
        import hashlib
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        for api_key in self._api_keys.values():
            if api_key.key_hash == key_hash and api_key.is_active:
                # Check expiration
                if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
                    return None
                api_key.last_used = datetime.now(timezone.utc)
                return api_key
        return None

    async def delete_api_key(self, key_id: str) -> bool:
        """Delete an API key."""
        if key_id in self._api_keys:
            del self._api_keys[key_id]
            logger.info(f"API key {key_id} deleted")
            return True
        return False

    async def get_api_keys_by_user(self, user_id: str) -> list[APIKey]:
        """Get all API keys for a user."""
        return [k for k in self._api_keys.values() if k.user_id == user_id]


class InMemoryAuditProvider(AuditProvider):
    """In-memory audit provider."""

    def __init__(self) -> None:
        self._logs: list[AuditLog] = []

    async def log(self, entry: AuditLog) -> None:
        """Log an audit entry."""
        self._logs.append(entry)
        logger.info(f"Audit log: {entry.action} by {entry.user_id} on {entry.resource_type}")

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
        """Get audit logs."""
        filtered = [l for l in self._logs if l.tenant_id == tenant_id]

        if user_id:
            filtered = [l for l in filtered if l.user_id == user_id]

        if action:
            filtered = [l for l in filtered if l.action == action]

        if start_time:
            filtered = [l for l in filtered if l.timestamp >= start_time]

        if end_time:
            filtered = [l for l in filtered if l.timestamp <= end_time]

        # Sort by timestamp descending
        filtered.sort(key=lambda x: x.timestamp, reverse=True)

        # Apply pagination
        return filtered[offset:offset + limit]
