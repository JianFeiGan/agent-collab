"""Tests for enterprise security module."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from agent_collab.security import (
    APIKey,
    AuditLog,
    Permission,
    Tenant,
    User,
    UserRole,
    generate_api_key,
    hash_password,
    has_permission,
    verify_password,
    ROLE_PERMISSIONS,
)
from agent_collab.security.providers import (
    InMemoryAPIKeyProvider,
    InMemoryAuditProvider,
    InMemoryAuthProvider,
    InMemoryTenantProvider,
)


class TestPasswordHashing:
    """Tests for password hashing."""

    def test_hash_password(self):
        hashed = hash_password("test_password")
        assert "$" in hashed
        salt, hash_value = hashed.split("$", 1)
        assert len(salt) == 32  # 16 bytes hex
        assert len(hash_value) == 64  # SHA-256 hex

    def test_verify_password_correct(self):
        hashed = hash_password("test_password")
        assert verify_password("test_password", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("test_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_password_invalid_hash(self):
        assert verify_password("test_password", "invalid") is False


class TestAPIKeyGeneration:
    """Tests for API key generation."""

    def test_generate_api_key(self):
        raw_key, key_hash, prefix = generate_api_key()
        assert raw_key.startswith("ac_")
        assert len(raw_key) > 32
        assert len(key_hash) == 64  # SHA-256 hex
        assert len(prefix) == 8

    def test_generate_api_key_uniqueness(self):
        keys = [generate_api_key()[0] for _ in range(100)]
        assert len(set(keys)) == 100


class TestPermissions:
    """Tests for permissions and RBAC."""

    def test_admin_has_all_permissions(self):
        assert has_permission(UserRole.ADMIN, Permission.WORKFLOW_CREATE) is True
        assert has_permission(UserRole.ADMIN, Permission.USER_DELETE) is True
        assert has_permission(UserRole.ADMIN, Permission.ADMIN_ALL) is True

    def test_manager_permissions(self):
        assert has_permission(UserRole.MANAGER, Permission.WORKFLOW_CREATE) is True
        assert has_permission(UserRole.MANAGER, Permission.WORKFLOW_DELETE) is True
        assert has_permission(UserRole.MANAGER, Permission.USER_CREATE) is False
        assert has_permission(UserRole.MANAGER, Permission.TENANT_CREATE) is False

    def test_developer_permissions(self):
        assert has_permission(UserRole.DEVELOPER, Permission.WORKFLOW_CREATE) is True
        assert has_permission(UserRole.DEVELOPER, Permission.WORKFLOW_DELETE) is False
        assert has_permission(UserRole.DEVELOPER, Permission.USER_CREATE) is False

    def test_viewer_permissions(self):
        assert has_permission(UserRole.VIEWER, Permission.WORKFLOW_READ) is True
        assert has_permission(UserRole.VIEWER, Permission.WORKFLOW_CREATE) is False
        assert has_permission(UserRole.VIEWER, Permission.TASK_READ) is True
        assert has_permission(UserRole.VIEWER, Permission.TASK_CREATE) is False


class TestUser:
    """Tests for User model."""

    def test_default_values(self):
        user = User()
        assert user.id is not None
        assert user.username == ""
        assert user.email == ""
        assert user.role == UserRole.DEVELOPER
        assert user.is_active is True

    def test_custom_values(self):
        user = User(
            username="testuser",
            email="test@example.com",
            role=UserRole.MANAGER,
            tenant_id="tenant_1",
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == UserRole.MANAGER
        assert user.tenant_id == "tenant_1"


class TestTenant:
    """Tests for Tenant model."""

    def test_default_values(self):
        tenant = Tenant()
        assert tenant.id is not None
        assert tenant.name == ""
        assert tenant.plan == "free"
        assert tenant.max_users == 10
        assert tenant.max_workflows == 100
        assert tenant.is_active is True

    def test_custom_values(self):
        tenant = Tenant(
            name="Acme Corp",
            slug="acme",
            plan="enterprise",
            max_users=100,
            max_workflows=1000,
        )
        assert tenant.name == "Acme Corp"
        assert tenant.slug == "acme"
        assert tenant.plan == "enterprise"
        assert tenant.max_users == 100
        assert tenant.max_workflows == 1000


class TestAPIKey:
    """Tests for APIKey model."""

    def test_default_values(self):
        api_key = APIKey()
        assert api_key.id is not None
        assert api_key.user_id == ""
        assert api_key.name == ""
        assert api_key.is_active is True
        assert api_key.expires_at is None

    def test_custom_values(self):
        api_key = APIKey(
            user_id="user_1",
            tenant_id="tenant_1",
            name="My API Key",
            permissions={Permission.WORKFLOW_READ, Permission.TASK_READ},
        )
        assert api_key.user_id == "user_1"
        assert api_key.tenant_id == "tenant_1"
        assert api_key.name == "My API Key"
        assert Permission.WORKFLOW_READ in api_key.permissions


class TestAuditLog:
    """Tests for AuditLog model."""

    def test_default_values(self):
        log = AuditLog()
        assert log.id is not None
        assert log.tenant_id == ""
        assert log.user_id == ""
        assert log.action == ""
        assert log.resource_type == ""

    def test_custom_values(self):
        log = AuditLog(
            tenant_id="tenant_1",
            user_id="user_1",
            action="create",
            resource_type="workflow",
            resource_id="wf_1",
            details={"name": "test"},
        )
        assert log.tenant_id == "tenant_1"
        assert log.user_id == "user_1"
        assert log.action == "create"
        assert log.resource_type == "workflow"


class TestInMemoryAuthProvider:
    """Tests for InMemoryAuthProvider."""

    @pytest.fixture
    def provider(self):
        return InMemoryAuthProvider()

    async def test_create_user(self, provider):
        user = User(
            id="user_1",
            username="testuser",
            hashed_password=hash_password("password123"),
            tenant_id="tenant_1",
        )
        created = await provider.create_user(user)
        assert created.id == "user_1"
        assert created.username == "testuser"

    async def test_authenticate_success(self, provider):
        user = User(
            id="user_1",
            username="testuser",
            hashed_password=hash_password("password123"),
            tenant_id="tenant_1",
        )
        await provider.create_user(user)

        authenticated = await provider.authenticate("testuser", "password123")
        assert authenticated is not None
        assert authenticated.id == "user_1"

    async def test_authenticate_wrong_password(self, provider):
        user = User(
            id="user_1",
            username="testuser",
            hashed_password=hash_password("password123"),
            tenant_id="tenant_1",
        )
        await provider.create_user(user)

        authenticated = await provider.authenticate("testuser", "wrongpassword")
        assert authenticated is None

    async def test_authenticate_nonexistent_user(self, provider):
        authenticated = await provider.authenticate("nonexistent", "password")
        assert authenticated is None

    async def test_get_user(self, provider):
        user = User(id="user_1", username="testuser", hashed_password=hash_password("password"))
        await provider.create_user(user)

        retrieved = await provider.get_user("user_1")
        assert retrieved is not None
        assert retrieved.username == "testuser"

    async def test_get_users_by_tenant(self, provider):
        user1 = User(id="user_1", username="user1", tenant_id="tenant_1", hashed_password=hash_password("password"))
        user2 = User(id="user_2", username="user2", tenant_id="tenant_1", hashed_password=hash_password("password"))
        user3 = User(id="user_3", username="user3", tenant_id="tenant_2", hashed_password=hash_password("password"))

        await provider.create_user(user1)
        await provider.create_user(user2)
        await provider.create_user(user3)

        users = await provider.get_users_by_tenant("tenant_1")
        assert len(users) == 2


class TestInMemoryTenantProvider:
    """Tests for InMemoryTenantProvider."""

    @pytest.fixture
    def provider(self):
        return InMemoryTenantProvider()

    async def test_create_tenant(self, provider):
        tenant = Tenant(id="tenant_1", name="Acme Corp")
        created = await provider.create_tenant(tenant)
        assert created.id == "tenant_1"
        assert created.name == "Acme Corp"

    async def test_get_tenant(self, provider):
        tenant = Tenant(id="tenant_1", name="Acme Corp")
        await provider.create_tenant(tenant)

        retrieved = await provider.get_tenant("tenant_1")
        assert retrieved is not None
        assert retrieved.name == "Acme Corp"

    async def test_get_all_tenants(self, provider):
        tenant1 = Tenant(id="tenant_1", name="Acme")
        tenant2 = Tenant(id="tenant_2", name="Beta")
        await provider.create_tenant(tenant1)
        await provider.create_tenant(tenant2)

        tenants = await provider.get_all_tenants()
        assert len(tenants) == 2

    async def test_delete_tenant(self, provider):
        tenant = Tenant(id="tenant_1", name="Acme")
        await provider.create_tenant(tenant)

        deleted = await provider.delete_tenant("tenant_1")
        assert deleted is True

        retrieved = await provider.get_tenant("tenant_1")
        assert retrieved is None


class TestInMemoryAPIKeyProvider:
    """Tests for InMemoryAPIKeyProvider."""

    @pytest.fixture
    def provider(self):
        return InMemoryAPIKeyProvider()

    async def test_create_api_key(self, provider):
        api_key = APIKey(
            id="key_1",
            user_id="user_1",
            tenant_id="tenant_1",
            name="Test Key",
        )
        raw_key = await provider.create_api_key(api_key)
        assert raw_key.startswith("ac_")

    async def test_validate_api_key(self, provider):
        api_key = APIKey(
            id="key_1",
            user_id="user_1",
            tenant_id="tenant_1",
            name="Test Key",
        )
        raw_key = await provider.create_api_key(api_key)

        validated = await provider.validate_api_key(raw_key)
        assert validated is not None
        assert validated.id == "key_1"

    async def test_validate_invalid_key(self, provider):
        validated = await provider.validate_api_key("invalid_key")
        assert validated is None

    async def test_delete_api_key(self, provider):
        api_key = APIKey(id="key_1", user_id="user_1")
        await provider.create_api_key(api_key)

        deleted = await provider.delete_api_key("key_1")
        assert deleted is True

        retrieved = await provider.get_api_key("key_1")
        assert retrieved is None


class TestInMemoryAuditProvider:
    """Tests for InMemoryAuditProvider."""

    @pytest.fixture
    def provider(self):
        return InMemoryAuditProvider()

    async def test_log(self, provider):
        entry = AuditLog(
            tenant_id="tenant_1",
            user_id="user_1",
            action="create",
            resource_type="workflow",
        )
        await provider.log(entry)

        logs = await provider.get_logs("tenant_1")
        assert len(logs) == 1
        assert logs[0].action == "create"

    async def test_get_logs_with_filters(self, provider):
        entry1 = AuditLog(tenant_id="tenant_1", user_id="user_1", action="create")
        entry2 = AuditLog(tenant_id="tenant_1", user_id="user_2", action="delete")
        entry3 = AuditLog(tenant_id="tenant_2", user_id="user_1", action="create")

        await provider.log(entry1)
        await provider.log(entry2)
        await provider.log(entry3)

        # Filter by tenant
        logs = await provider.get_logs("tenant_1")
        assert len(logs) == 2

        # Filter by user
        logs = await provider.get_logs("tenant_1", user_id="user_1")
        assert len(logs) == 1

        # Filter by action
        logs = await provider.get_logs("tenant_1", action="create")
        assert len(logs) == 1

    async def test_get_logs_with_pagination(self, provider):
        for i in range(10):
            entry = AuditLog(tenant_id="tenant_1", action=f"action_{i}")
            await provider.log(entry)

        logs = await provider.get_logs("tenant_1", limit=5)
        assert len(logs) == 5

        logs = await provider.get_logs("tenant_1", limit=5, offset=5)
        assert len(logs) == 5


class TestJWTToken:
    """Tests for JWT token generation and verification."""

    def test_generate_and_verify_token(self):
        from agent_collab.security import generate_token, verify_token

        user = User(
            id="user-123",
            username="testuser",
            hashed_password=hash_password("pass"),
            role=UserRole.DEVELOPER,
            tenant_id="t1",
        )
        token = generate_token(user, secret="test-secret")
        assert token.access_token.count(".") == 2  # header.payload.signature
        assert token.token_type == "bearer"
        assert token.user_id == "user-123"
        assert token.tenant_id == "t1"
        assert token.role == UserRole.DEVELOPER

        payload = verify_token(token.access_token, secret="test-secret")
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["username"] == "testuser"
        assert payload["role"] == "developer"

    def test_verify_wrong_secret(self):
        from agent_collab.security import generate_token, verify_token

        user = User(id="u1", username="u", hashed_password="p", role=UserRole.DEVELOPER)
        token = generate_token(user, secret="correct")
        assert verify_token(token.access_token, secret="wrong") is None

    def test_verify_tampered_token(self):
        from agent_collab.security import generate_token, verify_token

        user = User(id="u1", username="u", hashed_password="p", role=UserRole.DEVELOPER)
        token = generate_token(user, secret="s")
        assert verify_token(token.access_token + "x", secret="s") is None

    def test_verify_expired_token(self):
        from agent_collab.security import generate_token, verify_token

        user = User(id="u1", username="u", hashed_password="p", role=UserRole.DEVELOPER)
        token = generate_token(user, expires_in=-1, secret="s")  # already expired
        assert verify_token(token.access_token, secret="s") is None

    def test_verify_malformed_token(self):
        from agent_collab.security import verify_token

        assert verify_token("not.a.token.at.all", secret="s") is None
        assert verify_token("", secret="s") is None

    def test_admin_role_in_token(self):
        from agent_collab.security import generate_token, verify_token

        user = User(id="u1", username="admin", hashed_password="p", role=UserRole.ADMIN)
        token = generate_token(user, secret="s")
        payload = verify_token(token.access_token, secret="s")
        assert payload is not None
        assert payload["role"] == "admin"
