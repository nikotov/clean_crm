from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TemplateCreateRequest(BaseModel):
    wabaId: str = Field(..., description="WhatsApp Business Account ID")
    name: str = Field(..., description="Template name")
    language: str = Field(..., description="Template language code")
    category: str = Field(..., description="Template category")
    components: list[dict[str, Any]] = Field(
        default_factory=list,
        description="YCloud template components payload",
    )
    subCategory: str | None = Field(default=None, description="Optional template subcategory")
    messageSendTtlSeconds: int | None = Field(default=None, description="Optional TTL for template messages")

    model_config = ConfigDict(extra="allow")


class TemplateEditRequest(BaseModel):
    components: list[dict[str, Any]] | None = Field(
        default=None,
        description="Updated YCloud template components payload",
    )

    model_config = ConfigDict(extra="allow")


class MessageSendRequest(BaseModel):
    from_: str = Field(..., alias="from", description="Sender phone number in E.164 format")
    type: str = Field(..., description="WhatsApp outbound message type")
    to: str | None = Field(default=None, description="Recipient phone number in E.164 format")
    recipient: str | None = Field(default=None, description="Recipient BSUID or parent BSUID")
    externalId: str | None = Field(default=None, description="External id for reconciliation")

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class TemplateListQuery(BaseModel):
    page: int = Field(default=1, ge=1, le=100)
    limit: int = Field(default=10, ge=1, le=100)
    includeTotal: bool = Field(default=False)
    filterWabaId: str | None = Field(default=None)
    filterName: str | None = Field(default=None)
    filterLanguage: str | None = Field(default=None)
    filterStatus: str | None = Field(default=None)
