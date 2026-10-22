"""Domain model and validation rules for marketplace listings.

The domain is deliberately free of infrastructure concerns: these types are
what the business reasons about, and they are what the API serialises.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class ListingStatus(str, Enum):
    """Lifecycle of a listing draft."""

    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class PublicationStatus(str, Enum):
    """Per-marketplace publication outcome."""

    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class Marketplace(str, Enum):
    """Supported marketplaces (extensible without refactoring)."""

    AMAZON_IN = "amazon_in"
    FLIPKART = "flipkart"
    MEESHO = "meesho"


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------
class ProductInput(BaseModel):
    """What the seller provides: a photo plus rough specifications."""

    title_hint: str = Field(default="", max_length=200)
    brand: str = Field(default="", max_length=120)
    category_hint: str = Field(default="", max_length=120)
    specs: dict[str, Any] = Field(default_factory=dict)
    image_path: str | None = None

    @field_validator("title_hint", "brand", "category_hint")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class ExtractedAttributes(BaseModel):
    """Attributes recovered from the product image."""

    title: str
    brand: str = ""
    category: str = ""
    color: str = ""
    material: str = ""
    features: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class MarketListing(BaseModel):
    """A competitor listing observed during research."""

    marketplace: Marketplace
    title: str
    price: float = Field(gt=0)
    currency: str = "INR"
    rating: float | None = Field(default=None, ge=0, le=5)
    source_url: str = ""


class PriceRecommendation(BaseModel):
    """A defensible price with the reasoning behind it."""

    recommended_price: float = Field(gt=0)
    currency: str = "INR"
    floor_price: float = Field(gt=0)
    ceiling_price: float = Field(gt=0)
    competitor_median: float | None = None
    competitor_count: int = 0
    margin_pct: float = 0.0
    rationale: str = ""


class ListingContent(BaseModel):
    """Marketplace-ready copy for one language."""

    language: str
    title: str
    bullets: list[str] = Field(default_factory=list)
    description: str = ""
    search_terms: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class PublicationResult(BaseModel):
    """Outcome of one marketplace publication attempt."""

    marketplace: Marketplace
    status: PublicationStatus
    external_id: str | None = None
    url: str | None = None
    error: str | None = None
    attempts: int = 0
    idempotency_key: str = ""


class Listing(BaseModel):
    """The complete, reviewable listing draft."""

    listing_id: str
    status: ListingStatus = ListingStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    attributes: ExtractedAttributes | None = None
    content: list[ListingContent] = Field(default_factory=list)
    price: PriceRecommendation | None = None
    publications: list[PublicationResult] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    audit: list[dict[str, Any]] = Field(default_factory=list)

    def language(self, code: str) -> ListingContent | None:
        for item in self.content:
            if item.language == code:
                return item
        return None


# ---------------------------------------------------------------------------
# Validation rules
# ---------------------------------------------------------------------------
_TITLE_MAX = 200
_BULLET_MAX = 250
_BULLET_COUNT = (3, 5)
_DESCRIPTION_MIN = 80
_KEYWORD_MAX = 250
_HINDI_RE = re.compile(r"[\u0900-\u097F]")


def validate_listing(listing: Listing, *, strict: bool = True) -> list[str]:
    """Return the list of validation errors (empty means publishable).

    ``strict`` applies the marketplace hard limits (title length, bullet
    count, description length). Non-strict checks are advisory.
    """
    errors: list[str] = []

    if listing.attributes is None:
        errors.append("attributes missing - image analysis did not complete")
        return errors

    if not listing.content:
        errors.append("no listing content generated")
    for content in listing.content:
        prefix = f"[{content.language}]"
        if strict:
            if not content.title or len(content.title) > _TITLE_MAX:
                errors.append(f"{prefix} title must be 1-{_TITLE_MAX} characters")
            if not _BULLET_COUNT[0] <= len(content.bullets) <= _BULLET_COUNT[1]:
                errors.append(
                    f"{prefix} must have {_BULLET_COUNT[0]}-{_BULLET_COUNT[1]} bullets"
                )
            if any(len(bullet) > _BULLET_MAX for bullet in content.bullets):
                errors.append(f"{prefix} a bullet exceeds {_BULLET_MAX} characters")
            if len(content.description) < _DESCRIPTION_MIN:
                errors.append(f"{prefix} description shorter than {_DESCRIPTION_MIN} characters")
        if content.language.startswith("hi") and not _HINDI_RE.search(
            content.title + content.description
        ):
            errors.append(f"{prefix} content is not in Devanagari script")
        if len(content.keywords) > _KEYWORD_MAX:
            errors.append(f"{prefix} keyword count exceeds {_KEYWORD_MAX}")

    if listing.price is None:
        errors.append("no price recommendation")
    else:
        if listing.price.recommended_price < listing.price.floor_price:
            errors.append("recommended price is below the floor price")
        if listing.price.recommended_price > listing.price.ceiling_price:
            errors.append("recommended price is above the ceiling price")

    return errors


__all__ = [
    "ExtractedAttributes",
    "Listing",
    "ListingContent",
    "ListingStatus",
    "MarketListing",
    "Marketplace",
    "PriceRecommendation",
    "ProductInput",
    "PublicationResult",
    "PublicationStatus",
    "validate_listing",
]
