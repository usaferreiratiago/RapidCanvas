from pydantic import BaseModel, HttpUrl
from typing import Optional, List


class ExplainRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    image_url: Optional[str] = None

    class Config:
        # Allow either url or text
        pass


class Bullet(BaseModel):
    text: str
    source: Optional[str] = None
    source_url: Optional[str] = None


class ExplainResponse(BaseModel):
    bullets: List[Bullet]
    post_text: Optional[str] = None
    post_author: Optional[str] = None
    platform: Optional[str] = None
    image_description: Optional[str] = None
    search_queries_used: Optional[List[str]] = None


class ProviderResult(BaseModel):
    provider: str
    model: str
    bullets: List[Bullet]
    latency_ms: float
    error: Optional[str] = None


class CompareResponse(BaseModel):
    results: List[ProviderResult]
    post_text: Optional[str] = None
