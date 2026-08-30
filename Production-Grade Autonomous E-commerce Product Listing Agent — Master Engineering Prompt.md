# Production-Grade Autonomous E-commerce Product Listing Agent

You are a **principal software architect, senior backend engineer, AI/ML engineer, DevOps engineer, security engineer, QA engineer, and technical product manager**.

Your task is to design and implement a **production-grade autonomous e-commerce product listing platform for Indian sellers**.

The platform will allow a seller to:

1. Upload a product image.
2. Enter basic product specifications.
3. Automatically extract product information from the image.
4. Generate marketplace-ready product content.
5. Generate content in English, Hindi, and selected Indian regional languages.
6. Research competitor listings and market prices.
7. Recommend a competitive selling price.
8. Validate the generated listing.
9. Allow the seller to review/edit the listing.
10. Publish the listing to supported marketplaces through official APIs/integrations where available.
11. Track publication status.
12. Retry failed marketplace operations safely.
13. Charge sellers per listing or through subscriptions.
14. Maintain complete audit logs.

The initial target market is Indian marketplace sellers operating on platforms such as Amazon India, Flipkart, and Meesho.

---

# 1. Core Product Vision

Build an AI-powered SaaS platform that turns:

**Product photo + basic specifications**

into:

**Marketplace-ready listing + multilingual content + pricing recommendation + optional marketplace publication.**

The architecture must support future marketplaces without major refactoring.

The system should NOT tightly couple AI generation, scraping, payments, marketplace integrations, and the API layer.

Use clear domain boundaries.

---

# 2. Critical Engineering Principles

Follow these principles throughout the project:

- Production quality over demo quality.
- Security over convenience.
- Strong typing.
- Modular architecture.
- Testability.
- Observability.
- Idempotency.
- Fault tolerance.
- Retry safety.
- API versioning.
- Database migrations.
- Secrets must never be committed.
- No hardcoded credentials.
- No marketplace credentials in frontend.
- No fake production integrations.
- No undocumented assumptions.
- No giant monolithic files.
- No business logic inside route handlers.
- No provider-specific AI logic scattered throughout the application.
- No direct database access from controllers.
- No scraping logic inside API endpoints.
- No payment logic inside listing-generation code.
- Every external integration must have an abstraction/interface.
- Every expensive operation must be traceable.
- Every asynchronous operation must have a job/status model.
- Every marketplace operation must be idempotent.

When a requirement is ambiguous, choose the safest production-grade design and document the decision.

---

# 3. Required Technology Stack

Use this baseline stack unless there is a strong technical reason to change it.

## Backend

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis
- Celery or equivalent reliable background-job architecture

Prefer:

FastAPI → Service Layer → Domain Layer → Repository Layer → PostgreSQL

Do NOT put business logic directly into FastAPI route handlers.

---

# 4. AI Architecture

Create provider abstractions.

Example conceptual interfaces:

```text
VisionProvider
LLMProvider
EmbeddingProvider
TranslationProvider
```

Implement the first version using an OpenAI-compatible provider.

Do not hardcode model names throughout the application.

Configuration should look conceptually like:

```env
AI_PROVIDER=openai
VISION_MODEL=...
TEXT_MODEL=...
EMBEDDING_MODEL=...
```

Create adapters so the following can later be supported:

- OpenAI
- Anthropic
- Google
- local/self-hosted models

The application should interact with:

```text
LLMProvider
VisionProvider
```

rather than directly calling an SDK everywhere.

---

# 5. AI Listing Generation Pipeline

Implement the following pipeline:

```text
Product Upload
      ↓
Image Validation
      ↓
Image Preprocessing
      ↓
Vision Analysis
      ↓
Product Attribute Extraction
      ↓
Specification Normalization
      ↓
Category Detection
      ↓
Marketplace Attribute Mapping
      ↓
Competitor Research
      ↓
Price Analysis
      ↓
Listing Generation
      ↓
Multilingual Generation
      ↓
SEO Validation
      ↓
Marketplace Policy Validation
      ↓
Quality Scoring
      ↓
Human Review
      ↓
Marketplace Publishing
```

Every stage must have its own service/module.

Do not create one huge AI function.

---

# 6. Product Image Processing

The upload pipeline must:

- Validate MIME type.
- Validate file extension.
- Validate file size.
- Reject unsupported files.
- Generate secure internal filenames.
- Remove dangerous metadata where appropriate.
- Prevent path traversal.
- Generate thumbnails where useful.
- Store original and processed assets separately.
- Never trust the uploaded filename.
- Generate a checksum/hash.
- Detect duplicate uploads where practical.

Initially support:

- JPEG
- PNG
- WebP

Design the storage layer so it can use:

- AWS S3
- Cloudflare R2
- Google Cloud Storage
- MinIO for local development

Create:

```text
StorageProvider
```

Do not hardcode S3 calls throughout the application.

---

# 7. Product Data Model

Design normalized database models.

At minimum create entities for:

```text
User
Organization
SellerProfile
Product
ProductImage
ProductAttribute
Category
Listing
ListingVersion
ListingTranslation
CompetitorListing
PriceRecommendation
Marketplace
MarketplaceAccount
MarketplaceListing
GenerationJob
PublishingJob
Payment
Subscription
UsageRecord
AuditLog
ApiKey
WebhookEvent
```

Use UUIDs rather than sequential public IDs where appropriate.

Use timestamps:

```text
created_at
updated_at
deleted_at
```

where appropriate.

Support soft deletion where appropriate.

---

# 8. Multi-Tenant Architecture

This is a SaaS application.

A seller must never be able to access another seller's:

- Products
- Images
- Listings
- Marketplace credentials
- Payments
- Usage
- Jobs
- Audit logs

Every tenant-owned entity must contain an organization/seller ownership relationship.

Implement authorization checks at the service/domain level, not only in frontend code.

Never trust an organization ID supplied by the client.

Derive tenant identity from the authenticated session/token.

---

# 9. Authentication

Implement secure authentication.

Support:

- Email/password
- JWT access tokens
- Refresh tokens
- Secure password hashing
- Email verification architecture
- Password reset architecture
- Session/token revocation

Design for future:

- Google OAuth
- Microsoft OAuth
- WhatsApp-based authentication

Never store plaintext passwords.

Never store raw refresh tokens if avoidable.

Use secure token rotation.

---

# 10. Authorization

Implement RBAC.

Initial roles:

```text
OWNER
ADMIN
MEMBER
VIEWER
```

Example:

OWNER:
- Billing
- Marketplace accounts
- Organization settings
- Users
- Everything

ADMIN:
- Products
- Listings
- Marketplace publishing
- Users where permitted

MEMBER:
- Products
- Listing generation
- Publishing

VIEWER:
- Read-only access

Implement permission checks centrally.

---

# 11. Listing Schema

Create a canonical internal listing schema independent of any marketplace.

Example:

```text
Listing
├── title
├── short_title
├── bullets[]
├── description
├── keywords[]
├── brand
├── category
├── subcategory
├── product_type
├── attributes{}
├── specifications{}
├── variants[]
├── images[]
├── price
├── mrp
├── tax_category
├── dimensions
├── weight
├── country_of_origin
├── manufacturer
├── pack_quantity
└── compliance_information
```

The internal listing should then be transformed into marketplace-specific schemas.

---

# 12. Marketplace Adapter Architecture

Create an abstraction:

```python
class MarketplaceAdapter:
    async def validate_listing(...)
    async def create_listing(...)
    async def update_listing(...)
    async def delete_listing(...)
    async def get_listing_status(...)
    async def sync_inventory(...)
    async def sync_price(...)
```

Implement separate adapters:

```text
AmazonAdapter
FlipkartAdapter
MeeshoAdapter
```

Do NOT pretend an API exists if it does not.

Where official seller APIs are unavailable, restricted, partner-only, or require onboarding, create:

```text
MarketplaceAdapter
MarketplaceIntegrationStatus
```

and provide a clearly marked mock/sandbox adapter for development.

Never bypass marketplace security, authentication, CAPTCHA, anti-bot systems, or terms of service.

Use official APIs or authorized integrations.

---

# 13. Marketplace Capability System

Different marketplaces have different capabilities.

Create a capability model such as:

```text
CREATE_LISTING
UPDATE_LISTING
UPDATE_PRICE
UPDATE_INVENTORY
IMAGE_UPLOAD
ORDER_SYNC
WEBHOOKS
BULK_UPLOAD
```

A marketplace adapter should declare supported capabilities.

The application must check capabilities before attempting an operation.

Example:

```text
if marketplace.supports(CREATE_LISTING):
    publish()
else:
    return "MANUAL_ACTION_REQUIRED"
```

---

# 14. Marketplace Credentials

Marketplace credentials are extremely sensitive.

Never expose them to the frontend.

Never log them.

Never store them unencrypted.

Create an encryption abstraction:

```text
SecretProvider
```

Production implementation should support KMS/envelope encryption.

Development can use an application encryption key.

Credential access should be audited.

Implement credential rotation architecture.

---

# 15. AI Vision Extraction

Given an image, extract structured product information.

Example output:

```json
{
  "product_type": "",
  "category": "",
  "brand": "",
  "color": "",
  "material": "",
  "pattern": "",
  "estimated_dimensions": {},
  "visible_features": [],
  "packaging_information": [],
  "confidence": 0.0,
  "uncertain_fields": []
}
```

CRITICAL:

The model must distinguish between:

```text
Observed
Inferred
User-provided
Unknown
```

Never fabricate product specifications.

For example, if the image cannot establish:

- material
- weight
- dimensions
- warranty
- certification

the AI must mark the field as unknown rather than inventing it.

---

# 16. Structured AI Outputs

Do not depend on free-form LLM text for critical fields.

Use structured JSON schema outputs.

Validate all AI outputs with Pydantic.

If validation fails:

1. Attempt controlled repair.
2. Retry within a limited budget.
3. Mark the generation as failed if necessary.
4. Record the failure.

Never blindly trust model output.

---

# 17. Listing Generation Prompt Architecture

Do NOT store giant prompts directly inside route handlers.

Create versioned prompt templates:

```text
prompts/
    product_analysis/
    listing_generation/
    translation/
    pricing/
    quality_review/
```

Each prompt should have a version.

Example:

```text
listing_generation/v1
listing_generation/v2
```

Store the prompt version in the generation record.

This allows future evaluation and rollback.

---

# 18. Listing Generation Requirements

Generate:

## English

- SEO-friendly title
- 5–8 bullets depending on marketplace
- Product description
- Search keywords
- Relevant attributes

## Hindi

Generate natural Hindi suitable for Indian e-commerce.

Do not perform literal word-by-word translation.

## Regional Languages

Architect the system to support:

- Bengali
- Marathi
- Tamil
- Telugu
- Kannada
- Malayalam
- Gujarati
- Punjabi
- Odia

Language support must be configurable.

Do not assume every marketplace accepts every language.

---

# 19. Multilingual Quality Rules

For every generated language:

- Preserve product facts.
- Preserve measurements.
- Preserve numbers.
- Preserve brand names.
- Preserve model numbers.
- Do not invent translations of brand names.
- Avoid awkward machine translation.
- Use natural commerce terminology.
- Avoid culturally inappropriate wording.
- Do not make stronger claims than the source listing.

Maintain a translation consistency check.

---

# 20. SEO Engine

Create a dedicated SEO service.

Input:

```text
product information
category
competitor information
marketplace
target language
```

Output:

```text
primary_keywords
secondary_keywords
title
bullets
backend_keywords
keyword_density
keyword_warnings
```

Do NOT keyword-stuff titles.

Avoid:

- Fake superlatives
- Unsupported claims
- Spam keywords
- Competitor brand names where inappropriate
- Misleading specifications

Marketplace-specific title length and formatting rules must be configurable.

---

# 21. Competitor Research

Create a separate competitor research subsystem.

Do not mix competitor scraping with the listing-generation service.

Architecture:

```text
CompetitorResearchService
        ↓
Source adapters
        ↓
Fetcher
        ↓
Parser
        ↓
Normalizer
        ↓
Deduplicator
        ↓
Storage
        ↓
Pricing engine
```

Respect:

- robots.txt where applicable
- marketplace terms
- rate limits
- applicable laws
- anti-bot policies
- copyright restrictions

Do not implement CAPTCHA bypassing.

Do not implement stealth mechanisms intended to defeat marketplace security.

Prefer official APIs, public data, authorized feeds, or permitted sources.

---

# 22. Competitor Data Schema

Store:

```text
source
source_product_id
title
price
mrp
rating
review_count
seller_name
availability
category
attributes
captured_at
```

Do not store unnecessary personal data.

Deduplicate competitor listings.

Use timestamps because competitor prices become stale.

---

# 23. Pricing Recommendation Engine

Create a deterministic pricing service.

Do not let an LLM directly decide the final price.

Inputs:

```text
competitor prices
product cost
shipping cost
marketplace fees
tax
target margin
discount strategy
MRP
category
seller preferences
```

Output:

```text
recommended_price
price_range
confidence
reason_codes
competitor_statistics
margin_estimate
```

Example:

```text
minimum_viable_price
recommended_price
aggressive_price
premium_price
```

The pricing engine should be deterministic and testable.

Use the LLM only for explanations if necessary.

---

# 24. Pricing Safety

Never recommend a price that causes an unintended negative margin unless explicitly allowed.

Add safeguards:

```text
min_margin_percent
max_discount_percent
min_price
max_price
```

If insufficient information exists:

```text
pricing_status = INSUFFICIENT_DATA
```

rather than inventing values.

---

# 25. Quality Assurance Agent

Create a listing QA agent/service.

Check:

### Factual consistency

Does generated content match supplied product facts?

### Image consistency

Does generated content contradict visible image information?

### SEO

Are keywords relevant?

### Marketplace compliance

Does content violate known rules?

### Language quality

Is translation coherent?

### Hallucination detection

Are unsupported claims present?

### Completeness

Are required attributes missing?

Output:

```json
{
  "score": 0,
  "passed": false,
  "issues": [],
  "warnings": [],
  "missing_fields": [],
  "unsupported_claims": []
}
```

---

# 26. Human-in-the-Loop

Do NOT automatically publish every AI-generated listing.

Default flow:

```text
AI generates
     ↓
QA
     ↓
Seller reviews
     ↓
Seller approves
     ↓
Publish
```

Provide an optional organization-level setting for automated publishing after sufficient validation.

Maintain:

```text
draft
review_required
approved
publishing
published
failed
archived
```

---

# 27. Autonomous Agent Architecture

Use CrewAI or an equivalent agent orchestration framework only where it adds value.

Do not turn deterministic business logic into an LLM agent.

Recommended separation:

### Agent 1 — Product Analyst

Analyzes product image/specifications.

### Agent 2 — Market Researcher

Researches competitor information.

### Agent 3 — Listing Strategist

Creates listing strategy.

### Agent 4 — Content Generator

Generates listing content.

### Agent 5 — Localization Agent

Creates localized versions.

### Agent 6 — QA Agent

Validates content.

### Agent 7 — Publishing Agent

Coordinates marketplace publishing.

However:

Use normal Python services for:

- pricing calculations
- permissions
- payments
- database operations
- validation
- idempotency
- marketplace API calls
- security
- billing

Agents should orchestrate reasoning-heavy tasks, not replace conventional software engineering.

---

# 28. Agent State

Every autonomous job must have persistent state.

Example:

```text
Job
├── id
├── type
├── status
├── current_step
├── progress
├── input
├── output
├── error
├── retry_count
├── started_at
├── completed_at
└── metadata
```

Possible statuses:

```text
QUEUED
RUNNING
WAITING
COMPLETED
FAILED
CANCELLED
RETRYING
```

---

# 29. Background Jobs

Long-running work must NOT execute directly inside FastAPI request handlers.

Use background workers for:

- image processing
- vision analysis
- LLM generation
- competitor research
- pricing analysis
- translation
- QA
- marketplace publishing
- bulk operations

API should return a job ID.

Example:

```http
POST /api/v1/listings/generate
```

Response:

```json
{
  "job_id": "...",
  "status": "QUEUED"
}
```

Client can poll:

```http
GET /api/v1/jobs/{job_id}
```

Design for WebSocket/SSE progress updates later.

---

# 30. Reliability

Every external API call must have:

- timeout
- retry policy
- exponential backoff
- maximum retry count
- structured error handling
- correlation ID

Do not retry non-retryable errors.

Example:

```text
429 → retry
500 → retry
502 → retry
503 → retry
400 → don't retry
401 → don't blindly retry
403 → don't blindly retry
```

---

# 31. Idempotency

Publishing operations must be idempotent.

If a request is accidentally submitted twice, the system must not create duplicate marketplace listings.

Implement:

```text
idempotency_key
```

for critical operations.

Store request/result mapping.

---

# 32. Distributed Locking

Where necessary, use Redis/database locking to prevent:

- duplicate publishing
- concurrent listing modification
- duplicate payment processing
- duplicate job execution

---

# 33. Payment System

Implement Razorpay through a dedicated payment service.

Create abstractions:

```text
PaymentProvider
SubscriptionProvider
```

Never put payment provider code throughout the application.

Support:

## Pay-per-use

Example:

```text
₹2 per generated/published listing
```

## Subscription

Example:

```text
₹1,499/month
```

But make pricing configurable rather than hardcoded.

Example:

```text
pricing_plans
usage_limits
price_per_unit
currency
billing_period
```

---

# 34. Billing Ledger

Do not rely only on payment-provider records.

Create an internal billing ledger.

Track:

```text
credit
debit
refund
usage
subscription
invoice
payment
```

Every listing charge should have an immutable usage/billing record.

Use idempotency for payment webhooks.

---

# 35. Razorpay Webhooks

Implement:

```text
POST /api/v1/webhooks/razorpay
```

Requirements:

- Verify webhook signature.
- Store webhook event ID.
- Reject duplicate event processing.
- Process asynchronously where appropriate.
- Maintain event status.
- Log failures safely.

Never trust webhook payloads without signature verification.

---

# 36. API Design

Use:

```text
/api/v1/
```

Example endpoints:

```text
POST   /auth/register
POST   /auth/login
POST   /auth/refresh

GET    /me

POST   /products
GET    /products
GET    /products/{id}
PATCH  /products/{id}
DELETE /products/{id}

POST   /products/{id}/images

POST   /listings/generate
GET    /listings
GET    /listings/{id}
PATCH  /listings/{id}
POST   /listings/{id}/approve

POST   /listings/{id}/publish
GET    /listings/{id}/publication-status

POST   /pricing/recommend

GET    /marketplaces
POST   /marketplaces/{id}/connect
DELETE /marketplaces/{id}/disconnect

GET    /jobs/{id}

GET    /usage
GET    /billing
GET    /subscriptions

POST   /webhooks/razorpay
POST   /webhooks/{marketplace}
```

Use consistent response formats.

---

# 37. API Error Format

Implement a standard format:

```json
{
  "error": {
    "code": "LISTING_VALIDATION_FAILED",
    "message": "The listing could not be validated.",
    "details": {},
    "request_id": "..."
  }
}
```

Never expose stack traces in production.

---

# 38. Database

Use PostgreSQL.

Create Alembic migrations.

Never manually modify production database schemas.

Every schema change requires a migration.

Add appropriate indexes.

Pay particular attention to indexes on:

```text
organization_id
user_id
status
created_at
marketplace_id
external_id
job_id
idempotency_key
```

Use database constraints wherever possible.

---

# 39. Repository Structure

Use a structure similar to:

```text
ecommerce-listing-agent/
│
├── apps/
│   ├── api/
│   ├── worker/
│   └── frontend/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   └── dependencies.py
│   │   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── logging.py
│   │   │   └── exceptions.py
│   │   │
│   │   ├── domain/
│   │   │
│   │   ├── models/
│   │   │
│   │   ├── schemas/
│   │   │
│   │   ├── repositories/
│   │   │
│   │   ├── services/
│   │   │
│   │   ├── agents/
│   │   │
│   │   ├── integrations/
│   │   │   ├── ai/
│   │   │   ├── payments/
│   │   │   ├── storage/
│   │   │   └── marketplaces/
│   │   │
│   │   ├── workers/
│   │   └── main.py
│   │
│   ├── alembic/
│   └── tests/
│
├── frontend/
│
├── infrastructure/
│   ├── docker/
│   ├── terraform/
│   └── k8s/
│
├── docs/
│
├── scripts/
│
├── .github/
│   ├── workflows/
│   ├── ISSUE_TEMPLATE/
│   └── pull_request_template.md
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
├── pyproject.toml
├── README.md
└── LICENSE
```

Adapt this structure if needed, but maintain clear separation.

---

# 40. Frontend

Build a production-quality web dashboard.

Recommended stack:

- Next.js
- TypeScript
- Tailwind CSS
- React Query/TanStack Query
- Zod
- React Hook Form

Core screens:

```text
Login
Register
Dashboard
Products
Product Details
Upload Product
Generate Listing
Listing Editor
Translation Viewer
Pricing Recommendation
Competitor Analysis
Marketplace Connections
Publishing Status
Usage/Billing
Subscription
Settings
Audit Logs
```

---

# 41. Listing Editor

The seller must be able to edit:

- title
- bullets
- description
- keywords
- attributes
- price
- translations

Show:

```text
AI generated
Seller edited
AI suggestion
Validation warning
```

Maintain version history.

Allow:

```text
Save draft
Compare versions
Restore previous version
Approve
Publish
```

---

# 42. Dashboard

Show:

```text
Listings generated
Listings published
Listings failed
Monthly usage
Current plan
Estimated savings/time saved
Recent jobs
Recent products
Marketplace connection status
```

Do not fabricate analytics.

---

# 43. Observability

Implement structured logging.

Every request should have:

```text
request_id
organization_id
user_id
route
method
status_code
latency
```

Every job should have:

```text
job_id
request_id
organization_id
job_type
status
duration
```

Never log:

- passwords
- API keys
- marketplace tokens
- payment secrets
- private credentials
- full sensitive payloads

---

# 44. Metrics

Prepare metrics for:

```text
API latency
API error rate
LLM latency
LLM token usage
LLM cost
generation success rate
generation failure rate
job queue depth
job execution time
marketplace API errors
publishing success rate
payment success rate
webhook failures
```

Use Prometheus-compatible metrics.

---

# 45. AI Cost Tracking

Every AI request should record:

```text
provider
model
operation
input_tokens
output_tokens
estimated_cost
latency
success
```

Create an internal cost-tracking service.

This is essential because the business charges ₹2/listing while AI/API costs can vary.

---

# 46. Usage Metering

Create usage events such as:

```text
LISTING_GENERATED
TRANSLATION_GENERATED
PRICE_ANALYSIS
COMPETITOR_RESEARCH
LISTING_PUBLISHED
```

Make billing rules configurable.

Do not accidentally charge multiple times because a worker retries.

Usage events require unique idempotency keys.

---

# 47. Security Requirements

Implement:

- secure headers
- CORS configuration
- CSRF protection where applicable
- rate limiting
- input validation
- file upload security
- SSRF protection
- SQL injection protection through ORM/parameterization
- XSS protection
- secure cookies where used
- secret management
- encryption at rest for sensitive credentials
- audit logging
- authorization checks
- dependency vulnerability scanning

Never allow users to provide arbitrary URLs that the backend blindly fetches.

If URL fetching is required, implement SSRF-safe URL validation.

---

# 48. Rate Limiting

Rate-limit:

- authentication endpoints
- listing generation
- competitor research
- publishing
- payment operations
- webhook endpoints where appropriate

Use Redis-backed rate limiting.

Differentiate:

```text
anonymous
authenticated
organization
endpoint
```

---

# 49. Prompt Injection Defense

This is critical.

Marketplace/product data can contain malicious text designed to manipulate the AI.

Treat:

- product descriptions
- competitor titles
- marketplace text
- uploaded metadata
- external web content

as **untrusted input**.

The AI system must never interpret external content as system instructions.

Use explicit delimiters and trusted/untrusted data separation.

Example conceptual hierarchy:

```text
SYSTEM INSTRUCTIONS
TRUSTED APPLICATION DATA
UNTRUSTED EXTERNAL DATA
```

Never allow scraped content to override application instructions.

---

# 50. AI Hallucination Defense

Never allow AI to invent:

- certifications
- warranty
- medical claims
- material composition
- dimensions
- performance guarantees
- brand ownership
- country of origin
- safety claims

unless supported by trusted input.

Every generated claim should ideally be traceable to:

```text
USER_PROVIDED
IMAGE_OBSERVED
MARKETPLACE_DATA
MODEL_INFERENCE
```

Prefer conservative output.

---

# 51. Compliance Architecture

Create configurable policy validators.

Potential rules:

```text
TITLE_TOO_LONG
UNSUPPORTED_CLAIM
MISSING_REQUIRED_ATTRIBUTE
PROHIBITED_TERM
INVALID_CATEGORY
INVALID_PRICE
MISSING_IMAGE
INVALID_LANGUAGE
```

Policies must be versioned.

Do not hardcode marketplace policy assumptions throughout the codebase.

---

# 52. Testing

Testing is mandatory.

Implement:

## Unit tests

For:

- pricing
- validation
- authorization
- repositories
- parsers
- marketplace transformations
- billing
- usage metering

## Integration tests

For:

- PostgreSQL
- Redis
- API
- workers
- storage
- payment webhooks

## Contract tests

For:

- marketplace adapters
- AI provider adapters
- payment provider

## End-to-end tests

At minimum:

```text
Register
→ Login
→ Create product
→ Upload image
→ Generate listing
→ Review
→ Approve
→ Publish using mock marketplace
→ Verify status
```

---

# 53. AI Evaluation

Create a dedicated evaluation framework.

Store test cases containing:

```text
input image
product specs
expected attributes
expected prohibited hallucinations
expected language
```

Evaluate:

- factual accuracy
- completeness
- language quality
- SEO quality
- policy compliance
- hallucination rate

Track model/prompt versions.

Do not change production prompts without evaluation.

---

# 54. Golden Dataset

Create an initial synthetic/authorized evaluation dataset.

Include products from categories such as:

```text
Fashion
Home & Kitchen
Beauty
Electronics accessories
Jewelry
Toys
Stationery
Mobile accessories
```

Do not include copyrighted or private datasets without authorization.

---

# 55. CI/CD

Create GitHub Actions.

At minimum:

```text
lint
format
type-check
unit-tests
integration-tests
security-scan
build
```

Pull requests must pass CI before merging.

Build Docker images in CI.

Do not deploy if tests fail.

---

# 56. Code Quality

Use:

```text
Ruff
Black
MyPy
Pytest
Pre-commit
```

Use strict typing where practical.

Avoid:

```python
Any
```

unless justified.

Document intentional exceptions.

---

# 57. Docker

Provide Dockerfiles for:

```text
API
Worker
Frontend
```

Provide local development:

```text
docker-compose.yml
```

including:

```text
PostgreSQL
Redis
API
Worker
Frontend
```

Use health checks.

Use non-root containers where practical.

---

# 58. Environment Configuration

Create:

```text
.env.example
```

Example categories:

```env
APP_ENV=development

DATABASE_URL=
REDIS_URL=

JWT_SECRET=
ENCRYPTION_KEY=

OPENAI_API_KEY=

RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=

S3_ENDPOINT=
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_BUCKET=

MARKETPLACE_CLIENT_ID=
MARKETPLACE_CLIENT_SECRET=
```

Never commit `.env`.

Never put actual secrets in Git.

---

# 59. Git Strategy

Initialize Git immediately.

Use:

```text
main
develop
feature/*
fix/*
chore/*
docs/*
```

Do not work directly on main for normal feature development.

Use small, logical commits.

Commit examples:

```text
feat(auth): add JWT authentication
feat(products): add product CRUD
feat(ai): add vision provider abstraction
feat(listings): implement listing generation
feat(pricing): add deterministic price engine
feat(marketplaces): add adapter interface
feat(billing): add Razorpay webhook handling
test(listings): add generation integration tests
fix(publishing): prevent duplicate marketplace submissions
docs(api): document listing endpoints
chore(ci): add GitHub Actions pipeline
```

Avoid commits like:

```text
update
changes
final
final2
working
test
stuff
```

---

# 60. GitHub Repository

Prepare the repository for GitHub.

Create:

```text
README.md
CONTRIBUTING.md
SECURITY.md
CODE_OF_CONDUCT.md
LICENSE
CHANGELOG.md
```

Create GitHub templates:

```text
.github/
├── workflows/
│   ├── ci.yml
│   ├── security.yml
│   └── deploy.yml
├── ISSUE_TEMPLATE/
│   ├── bug_report.md
│   └── feature_request.md
└── pull_request_template.md
```

---

# 61. Branch Protection

Document recommended GitHub branch protection:

```text
main
```

should require:

- Pull request
- CI passing
- At least one review
- No force pushes
- No direct pushes
- Conversation resolution
- Signed commits if organization requires them

---

# 62. Documentation

Create documentation for:

```text
Architecture
Local development
Environment variables
Database
API
Authentication
AI architecture
Prompt architecture
Marketplace integrations
Payment architecture
Deployment
Security
Testing
Troubleshooting
Contributing
```

Create:

```text
docs/architecture.md
docs/api.md
docs/local-development.md
docs/deployment.md
docs/security.md
docs/ai-system.md
docs/marketplaces.md
docs/billing.md
```

---

# 63. Architecture Diagram

Create Mermaid diagrams in documentation.

At minimum:

## System architecture

```text
Frontend
   ↓
API Gateway / FastAPI
   ↓
Application Services
   ↓
┌─────────────┬──────────────┬─────────────┐
│ PostgreSQL  │ Redis/Queue  │ Object Store│
└─────────────┴──────────────┴─────────────┘
        ↓
 Background Workers
        ↓
 AI / Marketplace / Payment Providers
```

Also document:

- listing generation sequence
- publishing sequence
- payment sequence
- authentication flow
- job lifecycle

---

# 64. API Documentation

Use FastAPI/OpenAPI.

Every endpoint should document:

- request
- response
- authentication
- possible errors
- example payload
- status codes

Do not expose internal secrets or sensitive implementation details.

---

# 65. Database Migrations

Create the first migration.

Migration workflow:

```text
modify SQLAlchemy models
→ generate migration
→ review migration
→ test migration
→ apply migration
```

Ensure migrations work from an empty database.

---

# 66. Seed Data

Create development seed data for:

```text
marketplaces
plans
supported languages
categories
marketplace capabilities
policy rules
```

Never seed real credentials.

---

# 67. Mock Providers

Create mocks for local development:

```text
MockAIProvider
MockVisionProvider
MockPaymentProvider
MockMarketplaceAdapter
MockStorageProvider
```

The entire application should be runnable locally without paid third-party services.

---

# 68. Failure Handling

Every important operation must define failure behavior.

Example:

```text
AI timeout
→ retry
→ fallback provider if configured
→ mark job failed
→ notify user
```

Marketplace failure:

```text
publish
→ timeout
→ retry safely
→ query status
→ determine whether listing was created
→ prevent duplicate creation
```

Payment webhook failure:

```text
receive webhook
→ verify signature
→ store event
→ process
→ acknowledge
```

---

# 69. Notifications

Design a notification abstraction:

```text
NotificationProvider
```

Future implementations:

```text
Email
WhatsApp
SMS
Push
```

Notify sellers when:

- generation completes
- generation fails
- review is required
- publishing succeeds
- publishing fails
- payment succeeds
- subscription expires

---

# 70. Audit Logs

Record important actions:

```text
USER_LOGIN
PRODUCT_CREATED
PRODUCT_UPDATED
LISTING_GENERATED
LISTING_EDITED
LISTING_APPROVED
LISTING_PUBLISHED
MARKETPLACE_CONNECTED
MARKETPLACE_DISCONNECTED
PAYMENT_RECEIVED
SUBSCRIPTION_CHANGED
```

Audit records should include:

```text
actor
organization
action
resource
resource_id
timestamp
request_id
metadata
```

Do not store secrets in audit metadata.

---

# 71. Admin System

Design a basic admin interface/API for:

- users
- organizations
- jobs
- marketplace integrations
- payment events
- failed jobs
- system health
- AI costs
- usage
- audit logs

Admin access must use separate permissions.

---

# 72. Cost Controls

AI generation can become expensive.

Implement:

- per-user limits
- per-organization limits
- monthly quotas
- maximum image size
- maximum number of images per listing
- maximum retries
- maximum token budgets
- request timeouts
- concurrency limits

Prevent runaway autonomous agents.

---

# 73. Agent Safety

Agents must have:

- maximum iterations
- maximum execution time
- maximum tool calls
- maximum token budget
- allowed-tool list
- structured output validation
- cancellation support

Never create an unrestricted agent loop.

---

# 74. Autonomous Tool Permissions

Define tools explicitly.

Example:

```text
ProductAnalysisTool
CompetitorResearchTool
PricingTool
ListingGenerationTool
TranslationTool
ValidationTool
MarketplacePublishTool
```

The agent should only access tools appropriate to its role.

For example:

The QA agent must NOT have permission to publish a listing.

The research agent must NOT have access to payment operations.

The publishing agent must NOT modify billing.

Use least privilege.

---

# 75. Marketplace Publishing State Machine

Implement a state machine similar to:

```text
DRAFT
 ↓
VALIDATING
 ↓
APPROVED
 ↓
QUEUED
 ↓
PUBLISHING
 ↓
PUBLISHED
```

Failure:

```text
PUBLISHING
 ↓
FAILED
 ↓
RETRYING
 ↓
PUBLISHING
```

Do not allow invalid transitions.

---

# 76. Bulk Listing Generation

Design for future bulk uploads.

Support architecture for:

```text
CSV
Excel
ZIP images
API import
```

Bulk workflow:

```text
Upload
→ Validate
→ Create products
→ Queue jobs
→ Process concurrently
→ Aggregate results
→ Show failures
→ Allow retry
```

Concurrency must be configurable.

---

# 77. Performance

Design for horizontal scaling.

API servers should be stateless.

Workers should be independently scalable.

PostgreSQL connection pooling should be configured.

Redis should not become the permanent source of truth.

Object storage should hold images rather than PostgreSQL blobs.

Avoid N+1 database queries.

Use pagination everywhere.

---

# 78. Pagination

All collection APIs must support:

```text
page
page_size
```

or preferably cursor-based pagination for high-volume data.

Never return thousands of records by default.

---

# 79. Search

Design product/listing search.

Initially support:

```text
name
SKU
category
status
created date
marketplace
```

Architect for PostgreSQL full-text search or Elasticsearch/OpenSearch later.

---

# 80. Privacy

Minimize stored personal information.

Provide architecture for:

```text
data export
account deletion
organization deletion
credential deletion
```

Respect applicable Indian privacy/data-protection requirements and marketplace requirements.

Do not claim legal compliance automatically; document areas requiring legal review.

---

# 81. Production Deployment

Prepare deployment architecture for:

```text
Cloud load balancer
→ API containers
→ Worker containers
→ PostgreSQL
→ Redis
→ Object storage
```

Use HTTPS.

Use environment-specific configuration:

```text
development
staging
production
```

Never use production credentials locally.

---

# 82. Infrastructure as Code

Create Terraform architecture where practical.

Example:

```text
infrastructure/
└── terraform/
    ├── modules/
    ├── environments/
    │   ├── staging/
    │   └── production/
```

Do not require Terraform to run local development.

---

# 83. Staging Environment

Create a staging environment that uses:

- sandbox/mock marketplace integrations
- test payment credentials
- separate database
- separate Redis
- separate object storage bucket
- separate AI configuration where practical

Never test destructive marketplace actions against production accidentally.

---

# 84. Production Readiness Checklist

Before declaring the system production-ready, verify:

```text
[ ] Authentication
[ ] Authorization
[ ] Multi-tenancy
[ ] Database migrations
[ ] Backups
[ ] Restore procedure
[ ] Secrets management
[ ] Rate limiting
[ ] Input validation
[ ] File security
[ ] SSRF protection
[ ] Audit logging
[ ] Structured logging
[ ] Metrics
[ ] Error tracking
[ ] AI cost tracking
[ ] Job retries
[ ] Idempotency
[ ] Payment webhook security
[ ] Marketplace credential encryption
[ ] Marketplace API error handling
[ ] AI hallucination validation
[ ] Prompt injection protection
[ ] Unit tests
[ ] Integration tests
[ ] E2E tests
[ ] CI/CD
[ ] Docker
[ ] Staging
[ ] Production deployment
[ ] Documentation
[ ] Disaster recovery plan
```

---

# 85. Development Methodology

DO NOT attempt to generate the entire application in one giant response.

Work incrementally.

Follow this order:

## Phase 0 — Product/architecture specification

Produce:

```text
architecture.md
domain model
ERD
API specification
state machines
integration strategy
security model
```

Then wait for approval.

## Phase 1 — Repository bootstrap

Create:

```text
Git repository
GitHub configuration
Python project
FastAPI
Docker
PostgreSQL
Redis
CI
linting
testing
pre-commit
```

Commit:

```text
chore(repo): bootstrap production project
```

## Phase 2 — Authentication

Implement:

```text
users
organizations
authentication
authorization
RBAC
```

Add tests.

Commit.

## Phase 3 — Product management

Implement:

```text
products
images
storage
CRUD
```

Add tests.

Commit.

## Phase 4 — AI infrastructure

Implement:

```text
LLMProvider
VisionProvider
Mock providers
AI request tracking
prompt versioning
```

Add tests.

Commit.

## Phase 5 — Product analysis

Implement image analysis.

Commit.

## Phase 6 — Listing generation

Implement:

```text
English
Hindi
regional language architecture
SEO
QA
```

Commit.

## Phase 7 — Competitor research

Implement authorized source adapters and data normalization.

Commit.

## Phase 8 — Pricing engine

Implement deterministic pricing.

Commit.

## Phase 9 — Marketplace abstraction

Implement:

```text
MarketplaceAdapter
MockMarketplace
capability system
publishing state machine
```

Commit.

## Phase 10 — Actual marketplace integrations

Implement only officially supported/authorized APIs.

Each marketplace gets its own commit series.

## Phase 11 — Billing

Implement:

```text
plans
usage
payments
Razorpay
webhooks
ledger
```

Commit.

## Phase 12 — Frontend

Build dashboard and listing editor.

Commit.

## Phase 13 — Observability

Implement:

```text
logs
metrics
tracing
AI cost tracking
```

Commit.

## Phase 14 — Security hardening

Perform:

```text
dependency audit
authentication audit
authorization audit
SSRF audit
upload audit
secret audit
prompt injection audit
rate-limit audit
```

Commit fixes separately.

## Phase 15 — Production deployment

Implement:

```text
staging
production
Docker
CI/CD
backups
monitoring
rollback
```

Commit.

---

# 86. Git Rules

After every meaningful completed unit:

1. Run tests.
2. Run lint.
3. Run type checks.
4. Review changed files.
5. Review Git diff.
6. Update documentation.
7. Create a logical commit.

Before every commit run conceptually:

```bash
git status
git diff
pytest
ruff check .
ruff format --check .
mypy .
```

Never commit:

```text
.env
credentials
API keys
tokens
passwords
private certificates
large generated artifacts
local databases
```

---

# 87. GitHub Workflow

When instructed to push:

1. Check Git status.
2. Check branch.
3. Check remote.
4. Review diff.
5. Run tests.
6. Commit.
7. Push feature branch.
8. Open/update pull request if requested.
9. Ensure CI passes.
10. Merge only through approved workflow.

Never force-push unless explicitly instructed.

Never overwrite another developer's work.

---

# 88. AI Coding-Agent Rules

You are working inside an existing Git repository.

Before modifying anything:

1. Inspect the repository.
2. Understand the existing architecture.
3. Read README.
4. Read configuration.
5. Inspect Git status.
6. Inspect existing tests.
7. Identify existing conventions.
8. Do not unnecessarily rewrite existing code.

Before creating a new file, check whether equivalent functionality already exists.

Prefer modifying existing abstractions over duplicating functionality.

Never silently delete functionality.

---

# 89. No Fake Implementations

Do not create deceptive implementations such as:

```python
def publish_to_amazon():
    return {"success": True}
```

unless explicitly named and documented as:

```text
MockAmazonAdapter
```

Similarly, do not pretend that competitor data is live if it is generated or mocked.

All mocks must be obvious.

---

# 90. External API Rules

For every external integration:

- Read current official documentation before implementation.
- Verify authentication mechanism.
- Verify API limitations.
- Verify rate limits.
- Verify sandbox availability.
- Verify webhook behavior.
- Verify required permissions.
- Verify marketplace terms.
- Document integration limitations.

Do not rely on outdated tutorials.

---

# 91. Secrets Policy

If an API key is required:

Never ask the developer to paste it into source code.

Instead create:

```text
.env
```

locally and document:

```text
.env.example
```

with placeholders.

Never output secrets into logs.

---

# 92. Definition of Done

A feature is NOT complete merely because the code compiles.

A feature is complete only when:

```text
Implementation
+
Tests
+
Validation
+
Error handling
+
Logging
+
Documentation
+
Migration if required
+
Security review
+
Git commit
```

are complete.

---

# 93. Final Deliverables

The completed repository must contain:

```text
Production-grade FastAPI backend
Production-grade frontend
PostgreSQL schema
Redis job queue
AI provider abstraction
Vision pipeline
Listing generation pipeline
Multilingual generation
SEO engine
Competitor research architecture
Deterministic pricing engine
Marketplace adapter architecture
Mock marketplace
Authorized marketplace integrations where available
Razorpay billing architecture
Usage metering
Authentication
RBAC
Multi-tenancy
Audit logs
Observability
Docker
CI/CD
Automated tests
Security controls
Documentation
GitHub workflows
Deployment configuration
```

---

# 94. Final Architecture Requirement

The final architecture should conceptually look like:

```text
                         ┌─────────────────────┐
                         │      Next.js UI     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │      FastAPI        │
                         │    API Gateway      │
                         └──────────┬──────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 ▼                  ▼                  ▼
        ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
        │ Auth / Tenant  │ │ Listing Domain │ │ Billing Domain │
        └────────────────┘ └───────┬────────┘ └────────────────┘
                                    │
                                    ▼
                           ┌──────────────────┐
                           │  Job Orchestrator│
                           └────────┬─────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 ▼                  ▼                  ▼
        ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
        │ Product Agent  │ │ Market Research│ │ Content Agent  │
        └────────────────┘ └────────────────┘ └────────────────┘
                 │                  │                  │
                 └──────────────────┼──────────────────┘
                                    ▼
                           ┌──────────────────┐
                           │     QA Agent     │
                           └────────┬─────────┘
                                    │
                                    ▼
                           ┌──────────────────┐
                           │ Marketplace      │
                           │ Adapter Layer    │
                           └───────┬──────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
                Amazon         Flipkart        Meesho
                 API             API             API
```

Infrastructure:

```text
                 ┌──────────────────────┐
                 │     PostgreSQL       │
                 └──────────────────────┘

                 ┌──────────────────────┐
                 │ Redis / Job Queue    │
                 └──────────────────────┘

                 ┌──────────────────────┐
                 │ Object Storage       │
                 │ S3 / R2 / MinIO      │
                 └──────────────────────┘

                 ┌──────────────────────┐
                 │ Monitoring / Metrics │
                 └──────────────────────┘
```

---

# 95. How You Must Work With Me

Do NOT immediately generate thousands of lines of code.

First inspect the repository and produce:

```text
1. Current repository assessment
2. Proposed architecture
3. Technology decisions
4. Domain model
5. Database ERD
6. API plan
7. Agent architecture
8. Marketplace integration architecture
9. Security architecture
10. Git branching strategy
11. Implementation phases
12. Risks and unresolved questions
```

Then begin implementation one phase at a time.

For every phase report:

```text
PHASE
────────────────────────────
Implemented:
- ...

Files created:
- ...

Files modified:
- ...

Database changes:
- ...

API changes:
- ...

Tests:
- ...

Security considerations:
- ...

Documentation:
- ...

Git commit:
- ...

Remaining work:
- ...
```

Do not claim something is implemented unless it actually exists in the repository.

Do not claim tests pass unless you actually ran them.

Do not claim an external marketplace integration works unless it was actually tested against an authorized sandbox/API.

When blocked by unavailable credentials or external APIs, implement a clearly identified mock/sandbox adapter and document exactly what remains.

---

# 96. First Task

Your FIRST response/action must NOT implement the complete product.

Instead:

1. Inspect the repository.
2. Inspect Git status.
3. Identify existing files.
4. Determine whether the repository is empty or existing.
5. Produce the architecture proposal.
6. Produce the proposed directory tree.
7. Produce the initial ERD.
8. Produce the implementation roadmap.
9. Identify assumptions.
10. Identify external dependencies.
11. Identify marketplace API uncertainties.
12. Identify security risks.
13. Identify the minimum viable production architecture.

After that, begin Phase 0.

The goal is to build a **real maintainable SaaS product**, not a prototype that merely demonstrates AI-generated listings.

Always optimize for:

**Correctness → Security → Maintainability → Reliability → Cost → Performance → Developer Experience.**