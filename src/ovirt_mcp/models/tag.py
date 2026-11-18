"""Pydantic data models for oVirt / OLVM Inventory Tags."""

from pydantic import BaseModel, Field


class TagSummary(BaseModel):
    """Summary of an inventory tag."""

    id: str = Field(description="Tag UUID")
    name: str = Field(description="Tag name")
    description: str | None = Field(default=None, description="Tag description")
    parent_id: str | None = Field(default=None, description="Parent tag UUID in hierarchy")


class TagAssignmentResult(BaseModel):
    """Result of tagging or untagging a VM or Host."""

    success: bool = Field(description="Whether assignment succeeded")
    tag_id: str = Field(description="Tag UUID")
    tag_name: str = Field(description="Tag name")
    entity_id: str = Field(description="Entity UUID (VM or Host)")
    entity_name: str = Field(description="Entity display name")
    entity_type: str = Field(description="Entity type ('vm', 'host', or 'user')")
    action: str = Field(description="Action executed ('assign' or 'unassign')")
    message: str = Field(description="Human-readable outcome description")


class TagResult(BaseModel):
    """Outcome of a tag creation or deletion operation."""

    success: bool = Field(description="Whether the operation succeeded")
    tag_id: str = Field(description="Tag UUID")
    tag_name: str = Field(description="Tag name")
    action: str = Field(description="Action executed ('create' or 'delete')")
    message: str = Field(description="Human-readable outcome description")
