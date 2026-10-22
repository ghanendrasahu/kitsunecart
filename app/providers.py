"""Ports and adapters for everything outside the domain.

Every external dependency is behind a Protocol so the pipeline can run
offline and deterministically (the ``Mock*`` adapters), and so a new
marketplace, LLM or research source is added without touching the domain.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

from app.domain import (
    ExtractedAttributes,
    Listing,
    ListingContent,
    MarketListing,
    Marketplace,
    PriceRecommendation,
    ProductInput,
    PublicationResult,
    PublicationStatus,
)


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
class LLMProvider(Protocol):
    """Text generation that must answer with JSON."""

    def complete_json(self, prompt: str) -> dict[str, Any]: ...


class MockLLM:
    """Deterministic provider used offline and in the tests.

    The response is derived from a hash of the prompt, so the same input
    always produces the same listing - which is what makes the pipeline
    testable end to end. It also honours the requested language, because the
    validator checks that non-Latin scripts really are used.
    """

    _DEVANAGARI = {
        "title": "{stem} - प्रीमियम गुणवत्ता",
        "bullets": [
            "टिकाऊ और लंबे समय तक चलने वाला निर्माण",
            "रोज़मर्रा के उपयोग के लिए आरामदायक",
            "शिपिंग से पहले गुणवत्ता की जाँच की जाती है",
            "सुरक्षित और पुनर्चक्रण योग्य पैकेजिंग",
        ],
        "description": (
            "उत्कृष्ट सामग्री और साफ फिनिश वाला विश्वसनीय उत्पाद। हर इकाई "
            "शिपमेंट से पहले जाँची जाती है और पैकेजिंग ढुलाई के दौरान सुरक्षा "
            "बनाए रखती है।"
        ),
    }

    def complete_json(self, prompt: str) -> dict[str, Any]:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        stem = " ".join(prompt.splitlines()[0:1]).strip()
        if "(hi)" in prompt or "Hindi" in prompt:
            return {
                "title": self._DEVANAGARI["title"].format(stem=stem),
                "bullets": list(self._DEVANAGARI["bullets"]),
                "description": self._DEVANAGARI["description"],
                "search_terms": ["रोज़मर्रा", "टिकाऊ", "गुणवत्ता"],
                "keywords": ["उत्पाद", "टिकाऊ", "प्रीमियम"],
            }
        return {
            "title": f"Product listing {digest[:8]}",
            "bullets": [
                "Premium build with a durable finish",
                "Designed for everyday use and easy maintenance",
                "Backed by quality checks before dispatch",
                "Ships in protective, recyclable packaging",
            ],
            "description": (
                "A thoughtfully made product that combines reliable materials with "
                "a clean finish. Every unit is inspected before dispatch, and the "
                "packaging is chosen to protect the item in transit while staying "
                "recyclable where possible."
            ),
            "search_terms": ["everyday use", "durable finish", "quality checked"],
            "keywords": ["product", "durable", "premium"],
        }


class GroqLLM:
    """Groq-backed provider (production path)."""

    def __init__(self, api_key: str, model: str) -> None:
        from groq import Groq  # imported lazily so the mock path needs no key

        self._client = Groq(api_key=api_key)
        self._model = model

    def complete_json(self, prompt: str) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0.3,
            messages=[
                {
                    "role": "system",
                    "content": "You write marketplace listings. Answer with JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        text = response.choices[0].message.content or "{}"
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("LLM did not return a JSON object")
        return json.loads(text[start : end + 1])


# ---------------------------------------------------------------------------
# Vision
# ---------------------------------------------------------------------------
class VisionProvider(Protocol):
    """Product-image understanding."""

    def extract(self, product: ProductInput) -> ExtractedAttributes: ...


class MockVision:
    """Derives attributes from the file name and the seller's hints."""

    def extract(self, product: ProductInput) -> ExtractedAttributes:
        stem = Path(product.image_path).stem if product.image_path else "product"
        tokens = [token for token in stem.replace("-", " ").replace("_", " ").split() if token]
        title = product.title_hint or " ".join(tokens).title() or "Product"
        return ExtractedAttributes(
            title=title[:200],
            brand=product.brand or (tokens[0].title() if tokens else ""),
            category=product.category_hint or "General",
            color="Multi",
            material="Not specified",
            features=["clear product photograph", "packaged for retail"],
            confidence=0.55,
        )


class OpenAIVision:
    """Vision-capable provider (production path)."""

    def __init__(self, api_key: str, model: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def extract(self, product: ProductInput) -> ExtractedAttributes:
        if not product.image_path or not Path(product.image_path).is_file():
            raise FileNotFoundError("product image not found")
        data = Path(product.image_path).read_bytes()
        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract product attributes as JSON with title, brand, "
                                "category, color, material, features (list) and confidence."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{_b64(data)}"
                            },
                        },
                    ],
                }
            ],
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        payload.setdefault("title", product.title_hint or "Product")
        payload.setdefault("confidence", 0.5)
        return ExtractedAttributes(**payload)


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")


# ---------------------------------------------------------------------------
# Competitor research
# ---------------------------------------------------------------------------
class ResearchProvider(Protocol):
    """Competitor listing and price research."""

    def competitors(self, attributes: ExtractedAttributes) -> list[MarketListing]: ...


class HeuristicResearch:
    """Deterministic research stand-in.

    Real research (scraping, marketplace APIs, third-party price feeds) is
    licensed and rate-limited; this adapter produces a stable market
    envelope so the pricing logic can be developed and tested offline.
    """

    def competitors(self, attributes: ExtractedAttributes) -> list[MarketListing]:
        seed = int(
            hashlib.sha256(attributes.title.encode("utf-8")).hexdigest()[:8], 16
        )
        base = 400 + (seed % 1600)
        listings: list[MarketListing] = []
        for index, marketplace in enumerate(Marketplace):
            for variant in range(3):
                price = round(base * (0.9 + 0.12 * variant) + index * 37, 2)
                listings.append(
                    MarketListing(
                        marketplace=marketplace,
                        title=f"{attributes.title} - variant {variant + 1}",
                        price=price,
                        currency="INR",
                        rating=round(3.4 + ((seed + variant) % 15) / 10, 1),
                        source_url=f"https://example.invalid/{marketplace.value}/{seed}",
                    )
                )
        return listings


# ---------------------------------------------------------------------------
# Marketplace publishing
# ---------------------------------------------------------------------------
class MarketplacePublisher(Protocol):
    """Publishes a validated listing to one marketplace."""

    def publish(
        self,
        listing: Listing,
        content: ListingContent,
        price: PriceRecommendation,
        marketplace: Marketplace,
    ) -> PublicationResult: ...


class SandboxPublisher:
    """Records the publication intent without contacting a marketplace.

    Real adapters (Amazon SP-API, Flipkart Partner, Meesho) implement the same
    protocol; they need seller accounts and credentials, which are injected
    per deployment.
    """

    def publish(
        self,
        listing: Listing,
        content: ListingContent,
        price: PriceRecommendation,
        marketplace: Marketplace,
    ) -> PublicationResult:
        key = f"{listing.listing_id}:{marketplace.value}:{content.language}"
        external_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
        return PublicationResult(
            marketplace=marketplace,
            status=PublicationStatus.PUBLISHED,
            external_id=external_id,
            url=f"https://example.invalid/{marketplace.value}/{external_id}",
            attempts=1,
            idempotency_key=key,
        )


class MarketplaceRegistry:
    """Resolves a publisher per marketplace, with a default fallback."""

    def __init__(self, default: MarketplacePublisher, overrides: dict[Marketplace, MarketplacePublisher] | None = None) -> None:
        self._default = default
        self._overrides = overrides or {}

    def for_marketplace(self, marketplace: Marketplace) -> MarketplacePublisher:
        return self._overrides.get(marketplace, self._default)


__all__ = [
    "GroqLLM",
    "HeuristicResearch",
    "LLMProvider",
    "MarketplacePublisher",
    "MarketplaceRegistry",
    "MockLLM",
    "MockVision",
    "OpenAIVision",
    "ResearchProvider",
    "SandboxPublisher",
    "VisionProvider",
]
