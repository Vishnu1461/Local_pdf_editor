from typing import Literal

from pydantic import BaseModel, Field, field_validator

FieldType = Literal[
    "text",
    "multiline",
    "date",
    "number",
    "email",
    "address",
    "checkbox",
    "radio",
    "dropdown",
    "signature",
    "image",
]

Alignment = Literal["left", "center", "right"]


class FieldSpec(BaseModel):
    """A field in canonical page space: top-left origin, y down, points.

    Canonical space is the unrotated page box as reported by PyMuPDF
    (cropbox origin normalised to 0,0). The value is intentionally
    independent of browser pixels and zoom.
    """

    id: str = ""
    page: int = Field(ge=0)
    rect: list[float]
    type: FieldType = "text"
    name: str = ""
    label: str = ""
    value: str | bool | None = None
    checked: bool = False
    background: Literal["white", "none"] = "white"
    required: bool = False
    fontSize: float = 0
    alignment: Alignment = "left"
    maxLength: int | None = None
    options: list[str] = Field(default_factory=list)
    group: str | None = None
    confidence: float = 1.0
    source: str = "manual"
    tooltip: str = ""

    @field_validator("rect")
    @classmethod
    def _validate_rect(cls, v: list[float]) -> list[float]:
        if len(v) != 4:
            raise ValueError("rect must be [x0, y0, x1, y1]")
        x0, y0, x1, y1 = v
        if x1 <= x0 or y1 <= y0:
            raise ValueError("rect must have positive width and height")
        return [float(x) for x in v]

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        if len(v) > 128:
            raise ValueError("field id is too long")
        return v


class PageInfo(BaseModel):
    index: int
    width: float
    height: float
    rotation: int


class DocumentInfo(BaseModel):
    id: str
    name: str
    size: int
    sha256: str
    pageCount: int
    pages: list[PageInfo]
    fields: list[FieldSpec]
    templateMatch: str | None = None


class DetectionResult(BaseModel):
    fields: list[FieldSpec]
    stats: dict[str, int]


class ApplyTemplateRequest(BaseModel):
    templateId: str


class SaveRequest(BaseModel):
    fields: list[FieldSpec]
    flatten: bool = False
    fileName: str | None = None


class SaveReport(BaseModel):
    outputId: str
    fileName: str
    downloadUrl: str
    sha256: str
    pageCount: int
    widgetCount: int
    flattened: bool
    warnings: list[str] = Field(default_factory=list)
    preservedPages: bool


class TemplateSummary(BaseModel):
    id: str
    name: str
    description: str
    pageCount: int
    fieldCount: int
    pageSizes: list[list[float]]
