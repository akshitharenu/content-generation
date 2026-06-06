from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ResearchInput(BaseModel):
    topic: str
    facts: List[str] = Field(default_factory=list, description="5-8 realistic research facts")
    sources: List[str] = Field(default_factory=list, description="Plausible source citations")
    suggested_angle: str = Field(default="", description="The editorial angle recommended")
    key_players: List[str] = Field(default_factory=list, description="Key companies or individuals")


class QualityScore(BaseModel):
    newsworthiness: float = Field(ge=0, le=10)
    specificity: float = Field(ge=0, le=10)
    readability: float = Field(ge=0, le=10)
    structure: float = Field(ge=0, le=10)
    category_fit: float = Field(ge=0, le=10)
    overall: float = Field(ge=0, le=10)
    passed: bool
    feedback: Optional[str] = None

    @classmethod
    def compute(
        cls,
        newsworthiness: float,
        specificity: float,
        readability: float,
        structure: float,
        category_fit: float,
        threshold: float,
        feedback: Optional[str] = None,
    ) -> "QualityScore":
        overall = (newsworthiness + specificity + readability + structure + category_fit) / 5
        return cls(
            newsworthiness=newsworthiness,
            specificity=specificity,
            readability=readability,
            structure=structure,
            category_fit=category_fit,
            overall=round(overall, 2),
            passed=overall >= threshold,
            feedback=feedback,
        )


class Article(BaseModel):
    topic: str
    category: str
    category_confidence: float = Field(ge=0, le=1)
    category_reasoning: str
    headline: str
    dateline: str
    body: str
    word_count: int
    sources: List[str] = Field(default_factory=list)
    key_players: List[str] = Field(default_factory=list)
    quality_score: Optional[QualityScore] = None
    slug: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
