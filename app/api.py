"""FastAPI surface for the listing platform (API v1)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.domain import Marketplace, ProductInput
from app.pipeline import ListingPipeline
from app.providers import (
    GroqLLM,
    HeuristicResearch,
    MarketplaceRegistry,
    MockLLM,
    MockVision,
    OpenAIVision,
    SandboxPublisher,
)
from app.store import ListingStore

_pipeline: ListingPipeline | None = None


def build_pipeline() -> ListingPipeline:
    """Wire the adapters selected by configuration."""
    if settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY:
        llm = GroqLLM(settings.GROQ_API_KEY, settings.LLM_MODEL)
    else:
        llm = MockLLM()

    if settings.VISION_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        vision = OpenAIVision(settings.OPENAI_API_KEY, settings.VISION_MODEL)
    else:
        vision = MockVision()

    store = ListingStore(settings.DB_PATH)
    return ListingPipeline(
        llm=llm,
        vision=vision,
        research=HeuristicResearch(),
        publishers=MarketplaceRegistry(default=SandboxPublisher()),
        store=store,
        settings=settings,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _pipeline
    _pipeline = build_pipeline()
    yield
    if _pipeline is not None:
        _pipeline.store.close()


app = FastAPI(
    title="Kitsunecart Listing Platform",
    version="1.0.0",
    description=(
        "Autonomous e-commerce product listings for Indian sellers: image "
        "extraction, competitor research, multilingual copy, price "
        "recommendation, validation and marketplace publishing."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in settings.BACKEND_ORIGINS.split(",") if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_pipeline() -> ListingPipeline:
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline is not ready")
    return _pipeline


async def require_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """Gate the write endpoints when ``API_KEY`` is configured."""
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")


class CreateListingRequest(BaseModel):
    """Seller input: a photo plus rough specifications."""

    product: ProductInput
    languages: list[str] = Field(default_factory=lambda: ["en"])
    marketplaces: list[Marketplace] = Field(default_factory=list)


class PublishRequest(BaseModel):
    """Publish an approved listing to marketplaces."""

    marketplaces: list[Marketplace]
    language: str = "en"


@app.get("/health")
async def health() -> dict[str, Any]:
    """Liveness - independent of the database and the providers."""
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    """Readiness - the store answers and the pipeline is wired."""
    pipeline = get_pipeline()
    database = pipeline.store.ping()
    return {
        "status": "ready" if database else "unavailable",
        "checks": {"database": "up" if database else "down"},
        "llm_provider": settings.LLM_PROVIDER,
        "vision_provider": settings.VISION_PROVIDER,
    }


@app.get("/api/v1/listings")
async def list_listings(
    limit: int = 50, pipeline: ListingPipeline = Depends(get_pipeline)
) -> dict[str, Any]:
    """Most recent listings, newest first."""
    listings = pipeline.list(limit)
    return {
        "count": len(listings),
        "listings": [
            {
                "listing_id": item.listing_id,
                "status": item.status.value,
                "title": item.attributes.title if item.attributes else "",
                "recommended_price": item.price.recommended_price if item.price else None,
                "created_at": item.created_at,
            }
            for item in listings
        ],
    }


@app.post("/api/v1/listings", dependencies=[Depends(require_api_key)])
async def create_listing(
    payload: CreateListingRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    pipeline: ListingPipeline = Depends(get_pipeline),
) -> dict[str, Any]:
    """Run the pipeline for a product and return the reviewable listing."""
    listing = pipeline.run(
        payload.product,
        languages=payload.languages,
        marketplaces=payload.marketplaces,
        idempotency_key=idempotency_key,
    )
    return listing.model_dump(mode="json")


@app.get("/api/v1/listings/{listing_id}")
async def get_listing(
    listing_id: str, pipeline: ListingPipeline = Depends(get_pipeline)
) -> dict[str, Any]:
    """One listing with its content, price, validation result and audit trail."""
    listing = pipeline.get(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing.model_dump(mode="json")


@app.get("/api/v1/listings/{listing_id}/audit")
async def get_audit(
    listing_id: str, pipeline: ListingPipeline = Depends(get_pipeline)
) -> dict[str, Any]:
    """The full audit trail for a listing."""
    if pipeline.get(listing_id) is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return {"listing_id": listing_id, "events": pipeline.audit(listing_id)}


@app.post("/api/v1/listings/{listing_id}/publish", dependencies=[Depends(require_api_key)])
async def publish_listing(
    listing_id: str,
    payload: PublishRequest,
    pipeline: ListingPipeline = Depends(get_pipeline),
) -> dict[str, Any]:
    """Publish an approved listing (the review step)."""
    listing = pipeline.get(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.validation_errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Listing failed validation", "errors": listing.validation_errors},
        )
    content = listing.language(payload.language)
    if content is None or listing.price is None:
        raise HTTPException(status_code=422, detail="Listing has no publishable content")

    publisher = pipeline.publishers.for_marketplace(payload.marketplaces[0])
    result = publisher.publish(listing, content, listing.price, payload.marketplaces[0])
    pipeline.store.append_audit(
        listing.listing_id,
        "publishing",
        f"publish_{payload.marketplaces[0].value}",
        {"status": result.status.value, "external_id": result.external_id},
    )
    return result.model_dump(mode="json")
