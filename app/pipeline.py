"""The listing pipeline: image + specs -> validated, publishable listing.

Stages are explicit and every one of them writes an audit event, so a seller
can see exactly what the platform inferred and why a price was chosen. The
run is idempotent: the same idempotency key returns the stored listing
instead of re-running the expensive stages.
"""

from __future__ import annotations

import statistics
import uuid
from typing import Any

from app.config import Settings
from app.domain import (
    ExtractedAttributes,
    Listing,
    ListingContent,
    ListingStatus,
    MarketListing,
    Marketplace,
    PriceRecommendation,
    ProductInput,
    PublicationResult,
    PublicationStatus,
    validate_listing,
)
from app.providers import (
    LLMProvider,
    MarketplaceRegistry,
    ResearchProvider,
    VisionProvider,
)
from app.store import ListingStore

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "kn": "Kannada",
    "ml": "Malayalam",
    "gu": "Gujarati",
    "pa": "Punjabi",
}


def recommend_price(
    competitors: list[MarketListing],
    *,
    currency: str = "INR",
    margin_pct: float = 18.0,
) -> PriceRecommendation:
    """Turn the observed market into a defensible price band."""
    if not competitors:
        return PriceRecommendation(
            recommended_price=999.0,
            currency=currency,
            floor_price=799.0,
            ceiling_price=1499.0,
            competitor_count=0,
            margin_pct=margin_pct,
            rationale="No competitor data - showing a default band; research before publishing.",
        )

    prices = [item.price for item in competitors]
    median = statistics.median(prices)
    recommended = round(median * (1 - margin_pct / 100), 2)
    floor = round(median * 0.8, 2)
    ceiling = round(median * 1.25, 2)
    return PriceRecommendation(
        recommended_price=recommended,
        currency=currency,
        floor_price=floor,
        ceiling_price=ceiling,
        competitor_median=round(median, 2),
        competitor_count=len(competitors),
        margin_pct=margin_pct,
        rationale=(
            f"Median of {len(prices)} competitor prices is {median:.2f} {currency}; "
            f"pricing {margin_pct:.0f}% below the median keeps the offer competitive "
            f"while staying above the {floor:.2f} floor."
        ),
    )


class ListingPipeline:
    """Orchestrates extraction, research, copywriting, validation and publishing."""

    def __init__(
        self,
        *,
        llm: LLMProvider,
        vision: VisionProvider,
        research: ResearchProvider,
        publishers: MarketplaceRegistry,
        store: ListingStore,
        settings: Settings,
    ) -> None:
        self.llm = llm
        self.vision = vision
        self.research = research
        self.publishers = publishers
        self.store = store
        self.settings = settings

    # -- stages -----------------------------------------------------------
    def _extract(self, product: ProductInput, listing: Listing) -> ExtractedAttributes:
        attributes = self.vision.extract(product)
        self.store.append_audit(
            listing.listing_id, "extraction", "attributes_extracted", attributes.model_dump()
        )
        return attributes

    def _research(
        self, attributes: ExtractedAttributes, listing: Listing
    ) -> list[MarketListing]:
        competitors = self.research.competitors(attributes)
        self.store.append_audit(
            listing.listing_id,
            "research",
            "competitors_observed",
            {"count": len(competitors)},
        )
        return competitors

    def _write_copy(
        self,
        attributes: ExtractedAttributes,
        price: PriceRecommendation,
        languages: list[str],
        listing: Listing,
    ) -> list[ListingContent]:
        contents: list[ListingContent] = []
        for language in languages:
            prompt = self._copy_prompt(attributes, price, language)
            payload = self.llm.complete_json(prompt)
            contents.append(
                ListingContent(
                    language=language,
                    title=str(payload.get("title", attributes.title))[:200],
                    bullets=[str(item)[:250] for item in payload.get("bullets", [])],
                    description=str(payload.get("description", "")),
                    search_terms=[str(item) for item in payload.get("search_terms", [])],
                    keywords=[str(item) for item in payload.get("keywords", [])],
                )
            )
            self.store.append_audit(
                listing.listing_id,
                "copywriting",
                "content_generated",
                {"language": language, "title": contents[-1].title},
            )
        return contents

    def _copy_prompt(
        self, attributes: ExtractedAttributes, price: PriceRecommendation, language: str
    ) -> str:
        language_name = LANGUAGE_NAMES.get(language, language)
        return (
            f"Write a marketplace listing in {language_name} ({language}).\n"
            f"Product: {attributes.title}\n"
            f"Brand: {attributes.brand or 'unknown'}\n"
            f"Category: {attributes.category}\n"
            f"Material: {attributes.material}\n"
            f"Colour: {attributes.color}\n"
            f"Key features: {', '.join(attributes.features)}\n"
            f"Target price: {price.recommended_price} {price.currency}\n"
            "Answer with JSON: title, bullets (3-5), description, search_terms, keywords."
        )

    def _publish(
        self,
        listing: Listing,
        content: ListingContent,
        price: PriceRecommendation,
        marketplaces: list[Marketplace],
    ) -> list[PublicationResult]:
        results: list[PublicationResult] = []
        for marketplace in marketplaces:
            publisher = self.publishers.for_marketplace(marketplace)
            result = publisher.publish(listing, content, price, marketplace)
            results.append(result)
            self.store.append_audit(
                listing.listing_id,
                "publishing",
                f"publish_{marketplace.value}",
                {"status": result.status.value, "external_id": result.external_id},
            )
        return results

    # -- orchestration ----------------------------------------------------
    def run(
        self,
        product: ProductInput,
        *,
        languages: list[str] | None = None,
        marketplaces: list[Marketplace] | None = None,
        idempotency_key: str | None = None,
    ) -> Listing:
        """Run the full pipeline and return the listing."""
        if idempotency_key:
            existing = self.store.find_by_idempotency(idempotency_key)
            if existing is not None:
                self.store.append_audit(
                    existing.listing_id, "run", "idempotent_replay", {"key": idempotency_key}
                )
                return existing

        listing = Listing(listing_id=str(uuid.uuid4()))
        languages = languages or [self.settings.language_list[0]]
        marketplaces = marketplaces or []
        self.store.save(listing, idempotency_key)

        listing.attributes = self._extract(product, listing)

        competitors = self._research(listing.attributes, listing)
        listing.price = recommend_price(
            competitors,
            currency=self.settings.DEFAULT_CURRENCY,
            margin_pct=self.settings.TARGET_MARGIN_PCT,
        )
        self.store.append_audit(
            listing.listing_id, "pricing", "price_recommended", listing.price.model_dump()
        )

        listing.content = self._write_copy(
            listing.attributes, listing.price, languages, listing
        )

        errors = validate_listing(listing)
        listing.validation_errors = errors
        listing.status = ListingStatus.REJECTED if errors else ListingStatus.VALIDATED
        self.store.append_audit(
            listing.listing_id,
            "validation",
            "validation_failed" if errors else "validation_passed",
            {"errors": errors},
        )

        if not errors and self.settings.PUBLISH_ENABLED and marketplaces:
            primary = listing.content[0] if listing.content else None
            if primary is not None and listing.price is not None:
                listing.publications = self._publish(
                    listing, primary, listing.price, marketplaces
                )
                listing.status = ListingStatus.PUBLISHED
        elif marketplaces and not self.settings.PUBLISH_ENABLED:
            listing.publications = [
                PublicationResult(
                    marketplace=marketplace,
                    status=PublicationStatus.SKIPPED,
                    error="publishing disabled (PUBLISH_ENABLED=false)",
                    idempotency_key=f"{listing.listing_id}:{marketplace.value}",
                )
                for marketplace in marketplaces
            ]

        listing.audit = self.store.audit_trail(listing.listing_id)
        self.store.save(listing, idempotency_key)
        return listing

    def get(self, listing_id: str) -> Listing | None:
        return self.store.get(listing_id)

    def list(self, limit: int = 50) -> list[Listing]:
        return self.store.list(limit)

    def audit(self, listing_id: str) -> list[dict[str, Any]]:
        return self.store.audit_trail(listing_id)


__all__ = ["LANGUAGE_NAMES", "ListingPipeline", "recommend_price"]
