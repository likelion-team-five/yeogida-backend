from typing import List, Optional

from ninja import Field, Schema


class EstimatedCostSchema(Schema):
    currency: str
    amount: int


class SiteSchema(Schema):
    siteId: int = Field(alias="id")
    name: str
    type: str


class CourseOut(Schema):
    id: int
    name: str
    description: str
    duration: str
    location: str
    theme: List[str]
    imageUrl: Optional[str] = None
    rating: float
    estimatedCost: EstimatedCostSchema
    sites: List[SiteSchema]
