"""Pipeline behaviour: extraction, pricing, copy, validation, publishing, idempotency."""

from __future__ import annotations

import pytest
from app.config import Settings
from app.domain import (
    ListingStatus,
    Marketplace,
    ProductInput,
    PublicationStatus,
    validate_listing,
)
from app.pipeline import ListingPipeline, recommend_price
from app.providers import (
    HeuristicResearch,
    MarketplaceRegistry,
    MockLLM,
    MockVision,
    SandboxPublisher,
)
from app.store import ListingStore


@pytest.fixture()
def pipeline(tmp_path):
    settings = Settings(
        DB_PATH=str(tmp_path / "kitsunecart.db"),
        LLM_PROVIDER="mock",
        VISION_PROVIDER="mock",
        PUBLISH_ENABLED=True,
        TARGET_MARGIN_PCT=18.0,
    )
    store = ListingStore(settings.DB_PATH)
    return ListingPipeline(
        llm=MockLLM(),
        vision=MockVision(),
        research=HeuristicResearch(),
        publishers=MarketplaceRegistry(default=SandboxPublisher()),
        store=store,
        settings=settings,
    )


def test_pipeline_produces_a_validated_listing(pipeline):
    listing = pipeline.run(
        ProductInput(title_hint="Cotton Bed Sheet", brand="Nimbus"),
        languages=["en", "hi"],
    )

    assert listing.status is ListingStatus.VALIDATED
    assert listing.validation_errors == []
    assert listing.attributes is not None
    assert listing.attributes.title
    assert len(listing.content) == 2
    assert {item.language for item in listing.content} == {"en", "hi"}
    assert listing.price is not None
    assert listing.price.recommended_price > 0


def test_pipeline_writes_an_audit_trail_for_every_stage(pipeline):
    listing = pipeline.run(ProductInput(title_hint="Ceramic Mug"))

    stages = {event["stage"] for event in listing.audit}
    assert {"extraction", "research", "pricing", "copywriting", "validation"} <= stages
    assert pipeline.audit(listing.listing_id)


def test_idempotency_key_replays_the_stored_listing(pipeline):
    first = pipeline.run(ProductInput(title_hint="Steel Bottle"), idempotency_key="key-1")
    second = pipeline.run(ProductInput(title_hint="Steel Bottle"), idempotency_key="key-1")

    assert first.listing_id == second.listing_id
    assert len(pipeline.list()) == 1  # the replay did not create a second listing


def test_publishing_records_a_result_per_marketplace(pipeline):
    listing = pipeline.run(
        ProductInput(title_hint="Desk Lamp"),
        marketplaces=[Marketplace.AMAZON_IN, Marketplace.MEESHO],
    )

    assert listing.status is ListingStatus.PUBLISHED
    assert {item.marketplace for item in listing.publications} == {
        Marketplace.AMAZON_IN,
        Marketplace.MEESHO,
    }
    assert all(item.status is PublicationStatus.PUBLISHED for item in listing.publications)
    assert all(item.idempotency_key for item in listing.publications)


def test_publishing_is_skipped_when_disabled(tmp_path):
    settings = Settings(DB_PATH=str(tmp_path / "k.db"), PUBLISH_ENABLED=False)
    store = ListingStore(settings.DB_PATH)
    pipeline = ListingPipeline(
        llm=MockLLM(),
        vision=MockVision(),
        research=HeuristicResearch(),
        publishers=MarketplaceRegistry(default=SandboxPublisher()),
        store=store,
        settings=settings,
    )

    listing = pipeline.run(
        ProductInput(title_hint="Wall Clock"), marketplaces=[Marketplace.FLIPKART]
    )

    assert listing.publications[0].status is PublicationStatus.SKIPPED


def test_store_survives_a_reopen(tmp_path):
    db_path = tmp_path / "k.db"
    settings = Settings(DB_PATH=str(db_path))
    store = ListingStore(db_path)
    pipeline = ListingPipeline(
        llm=MockLLM(),
        vision=MockVision(),
        research=HeuristicResearch(),
        publishers=MarketplaceRegistry(default=SandboxPublisher()),
        store=store,
        settings=settings,
    )
    listing = pipeline.run(ProductInput(title_hint="Notebook"))
    store.close()

    reopened = ListingStore(db_path)
    assert reopened.get(listing.listing_id) is not None
    assert reopened.audit_trail(listing.listing_id)


# -- pricing ---------------------------------------------------------------
def test_price_recommendation_sits_inside_the_market_band():
    competitors = pipeline_competitors()
    price = recommend_price(competitors, margin_pct=20.0)

    assert price.floor_price <= price.recommended_price <= price.ceiling_price
    assert price.competitor_count == len(competitors)
    assert "competitor" in price.rationale.lower()


def test_price_recommendation_without_data_falls_back():
    price = recommend_price([])

    assert price.competitor_count == 0
    assert price.recommended_price > 0
    assert "no competitor data" in price.rationale.lower()


def pipeline_competitors():
    from app.domain import ExtractedAttributes

    attributes = ExtractedAttributes(title="Cotton Sheet")
    return HeuristicResearch().competitors(attributes)


# -- validation ------------------------------------------------------------
def test_validation_rejects_an_empty_listing():
    from app.domain import Listing

    errors = validate_listing(Listing(listing_id="x"))

    assert errors
    assert any("attributes" in error for error in errors)
