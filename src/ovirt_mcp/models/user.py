"""Pydantic models for oVirt / OLVM users, roles, and authorization permissions."""

from pydantic import BaseModel, Field


class UserSummary(BaseModel):
    """Summary representation of an oVirt / OLVM user account."""

    id: str = Field(description="Unique UUID of the user")
    name: str = Field(description="Display name or username")
    user_name: str = Field(
        description="Full username including realm / domain (e.g. admin@internal-authz)"
    )
    principal: str | None = Field(
        default=None, description="Principal username without realm (e.g. admin)"
    )
    domain_name: str | None = Field(
        default=None, description="Authorization domain name (e.g. internal-authz)"
    )
    email: str | None = Field(default=None, description="User email address")
    department: str | None = Field(default=None, description="Department name if configured")
    logged_in: bool = Field(
        default=False, description="Whether the user is currently authenticated and active"
    )


class UserDetail(UserSummary):
    """Detailed representation of an oVirt / OLVM user including authorization roles and permissions."""

    roles: list[str] = Field(
        default_factory=list, description="Names of authorization roles assigned to this user"
    )
    permissions_count: int = Field(
        default=0, description="Total number of discrete permission grants for this user"
    )


class UserResult(BaseModel):
    """Result of a user account mutation (add, delete)."""

    success: bool = Field(description="Whether the user operation succeeded")
    action: str = Field(description="Action executed: 'add' or 'delete'")
    user_id: str | None = Field(default=None, description="UUID of the affected user")
    user_name: str = Field(description="Username of the affected user")
    message: str = Field(description="Human-readable outcome description")


class RoleSummary(BaseModel):
    """Authorization role defining operational permits and privileges."""

    id: str = Field(description="Unique UUID of the role")
    name: str = Field(
        description="Role name (e.g. SuperUser, DataCenterAdmin, UserRole, PowerUserRole)"
    )
    description: str | None = Field(default=None, description="Description of the role privileges")
    administrative: bool = Field(
        default=False, description="Whether this is an administrative role"
    )
    mutable: bool = Field(default=False, description="Whether this role can be modified")


class PermissionSummary(BaseModel):
    """Discrete authorization permission granting a role to a user or group on a target entity."""

    id: str = Field(description="Unique UUID of the permission grant")
    user_id: str | None = Field(default=None, description="UUID of the user")
    user_name: str | None = Field(default=None, description="Name of the user")
    role_id: str = Field(description="UUID of the granted role")
    role_name: str | None = Field(
        default=None, description="Name of the granted role (e.g. SuperUser, UserRole)"
    )
    target_type: str = Field(
        description="Target entity type: 'system', 'data_center', 'cluster', 'vm', 'storage_domain', or 'unknown'"
    )
    target_id: str | None = Field(
        default=None, description="UUID of the target entity (None for system-wide)"
    )
    target_name: str | None = Field(
        default=None, description="Name of the target entity (None for system-wide)"
    )


class PermissionResult(BaseModel):
    """Result of a permission grant or revoke operation."""

    success: bool = Field(description="Whether the permission operation succeeded")
    action: str = Field(description="Action executed: 'add' or 'remove'")
    permission_id: str | None = Field(default=None, description="UUID of the affected permission")
    user_name: str = Field(description="Target username")
    role_name: str = Field(description="Target role name")
    target_type: str = Field(
        description="Target entity type ('system', 'data_center', 'cluster', 'vm', etc.)"
    )
    target_name: str | None = Field(default=None, description="Name of the target entity")
    message: str = Field(description="Human-readable outcome description")
