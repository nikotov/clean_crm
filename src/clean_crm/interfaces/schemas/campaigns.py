from pydantic import BaseModel, Field

class templateComponentSchema(BaseModel):
    type: str = Field(..., description="Component type")
    text: str = Field(..., description="Component text")


class createTemplateRequest(BaseModel):
    name: str = Field(..., description="Template name")
    language_code: str = Field(..., description="Language code")
    text: str = Field(..., description="Template text")
    category: str = Field(..., description="Template category")
    components: list[templateComponentSchema] = Field(...,description="List of template components")


class createTemplateResponse(BaseModel):
    id: str = Field(..., description="Template ID")
    name: str = Field(..., description="Template name")
    language_code: str = Field(..., description="Language code")
    category: str = Field(..., description="Template category")
    components: list[templateComponentSchema] = Field(..., description="List of template components")
    status: str = Field(..., description="Template status")


class 
