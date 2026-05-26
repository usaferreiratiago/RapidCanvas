# RapidCanvas
RapidCanvas

# Context — AI Post Explainer

An AI agent that explains social media posts by searching for and synthesizing relevant context. Takes a post URL or raw text, searches the web, and returns 3–5 bullet points explaining references, jargon, events, and background.

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- An OpenAI API key

### 1. Clone & configure

```bash
git clone https://github.com/YOUR_USERNAME/post-explainer
cd post-explainer
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### 2. Start the backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
# API now running at http://localhost:8000
```

### 3. Start the frontend

```bash
cd frontend
npm install
npm start
# UI now at http://localhost:3000
```

### 4. Run the eval harness

```bash
cd evals
OPENAI_API_KEY=your_key python eval.py
# Outputs pass/fail table + eval_results.json
```

---

## Architecture

```
post-explainer/
├── backend/
│   ├── main.py        # FastAPI app, /explain and /compare endpoints
│   ├── agent.py       # Orchestration: scrape → search → synthesize
│   ├── scraper.py     # Platform-aware post fetcher (Bluesky, Twitter, Reddit, generic)
│   ├── search.py      # OpenAI web search tool + DuckDuckGo fallback
│   ├── models.py      # Pydantic request/response models
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.js     # Main UI component
│       └── App.css    # Design system + styles
└── evals/
    └── eval.py        # Evaluation harness (12 test cases, 3 scoring dimensions)
```

### Agent Pipeline

```
URL or text input
        │
        ▼
[Scraper] ─── Platform detection ──► Bluesky API / Twitter oEmbed / Reddit JSON / OG tags
        │
        ▼
[Vision] ─── If image present: GPT-4o describes image for extra context
        │
        ▼
[Query Gen] ─── GPT-4o-mini generates 2–3 targeted search queries from post content
        │
        ▼
[Search] ─── OpenAI web search tool (parallel) → DuckDuckGo fallback
        │
        ▼
[Synthesis] ─── GPT-4o combines post + image desc + search results → JSON bullets
        │
        ▼
3–5 bullet points with source citations
```

---

## API

### `POST /explain`

```json
{
  "url": "https://bsky.app/profile/user.bsky.social/post/abc123",
  "text": "optional raw post text override",
  "image_url": "https://cdn.bsky.app/img/..."
}
```

At least one of `url` or `text` must be provided.

**Response:**
```json
{
  "bullets": [
    { "text": "...", "source": "Wired", "source_url": "https://..." }
  ],
  "post_text": "Original post text",
  "post_author": "username",
  "platform": "bluesky",
  "image_description": "GPT-4o vision description if image present",
  "search_queries_used": ["query 1", "query 2"]
}
```

### `POST /compare`

Same request shape. Returns side-by-side results from GPT-4o and GPT-4o-mini with latency.

---

## Eval Harness

`evals/eval.py` tests 12 posts spanning AI/tech culture. Each test case defines:

- **`text`** – the post content
- **`expected_keywords`** – terms that should appear in the output
- **`expected_bullets_min`** – minimum acceptable bullet count
- **`notes`** – what context the agent should surface

### Scoring (three dimensions, weighted)

| Dimension | Weight | Method |
|-----------|--------|--------|
| Keyword coverage | 40% | Fraction of expected keywords found in bullets |
| Semantic relevance | 30% | Cosine similarity (text-embedding-3-small) of bullets to post |
| Length quality | 20% | Bullets in the 30–220 char "goldilocks" range |
| Bullet count | 10% | ≥ expected minimum |

**Overall score ≥ 0.5 = pass.**

Results are printed to console and saved to `evals/eval_results.json`.

---

## Design Decisions

### Why GPT-4o for synthesis, GPT-4o-mini for query gen?
Query generation is a simple extraction task — mini is fast and cheap enough. Synthesis is the quality-critical step where 4o's stronger reasoning produces measurably better bullets (confirmed in manual testing).

### Why structured JSON output throughout?
The `response_format: {type: "json_object"}` parameter eliminates parsing failures from markdown code fences or explanatory prose. Every LLM call returns clean JSON, making the pipeline reliable.

### Why a separate scraping layer instead of passing URLs directly to the LLM?
Some platforms (Bluesky, Reddit) have structured APIs that return clean data. Using them gives better author attribution, embedded image URLs, and full post text — all of which improve synthesis quality. Passing raw URLs to the LLM would mean it sees only whatever the model can infer from the URL string.

### Why parallel search queries?
Generating 2–3 queries and running them concurrently (asyncio.gather) rather than sequentially halves latency. Each query targets a different angle: entity identification, event context, jargon definition.

### Why DuckDuckGo as fallback?
The OpenAI web search model (`gpt-4o-mini-search-preview`) is the primary search mechanism. DuckDuckGo's instant answer API is free, requires no key, and handles well-known entities well — making it a reliable fallback for timeouts or quota limits.

### Why embeddings for eval, not just LLM-as-judge?
LLM-as-judge scoring is expensive and can be gameable (the model scores its own outputs highly). Embedding cosine similarity is objective, cheap, and reproducible. Keyword coverage catches specific factual requirements. Together they approximate human evaluation at low cost.

### What assumptions were made?
- Platform support is prioritized for Bluesky (as specified) but the architecture handles any URL or raw text.
- Image inputs can be URLs (fetched and base64-encoded server-side) or base64 data URLs from the frontend upload.
- The comparison endpoint uses only OpenAI models. Extending to Anthropic/Gemini requires adding their SDKs and parallel async calls — the `compare_providers` structure supports this.
- The `.env` file contains the API key; the frontend reads `REACT_APP_API_URL` to point at the backend.

---

## Bonus Features Implemented

- ✅ **Image understanding** — GPT-4o vision describes post images; description is passed to synthesis
- ✅ **Multi-LLM comparison** — `/compare` endpoint returns GPT-4o vs GPT-4o-mini side-by-side with latency
- ✅ **Source citations** — each bullet includes `source` title and `source_url` when available
- ✅ **ML-powered eval** — semantic scoring via `text-embedding-3-small`

---

I designed and built a full-stack AI agent that explains social media posts by transforming short-form content into structured, contextual insights.

The product accepts either a social media URL or raw text as input and returns concise bullet-point explanations that help users understand references, jargon, trends, events, or cultural context behind the post. The goal was to create a practical “what does this mean?” experience for internet content.

Architecture

The solution is built with Python/FastAPI on the backend and React on the frontend, with LLM orchestration handled through OpenAI models.

Backend
API Layer — FastAPI

I used FastAPI as the service layer because of its async-native architecture and strong performance for I/O-heavy workflows.

Main endpoints:

/explain → receives a URL or text and returns contextual bullet-point explanations
/compare → runs the same workflow through multiple LLMs (GPT-4o and GPT-4o-mini) to compare quality, latency, and output consistency

Because the pipeline depends on multiple external calls—scraping, search, vision, and synthesis—FastAPI’s async model was a strong fit.

Content Acquisition Layer

Before any reasoning happens, the system first extracts the actual content behind the post.

The scraper supports platform-aware extraction:

Bluesky → via AT Protocol API
Twitter/X → via oEmbed endpoint
Reddit → via native JSON endpoint
Fallback websites → via OpenGraph metadata extraction

This step is important because LLMs do not browse URLs directly. Converting URLs into structured text, author metadata, and image references significantly improves downstream explanation quality.

Retrieval & Search Layer

For contextual enrichment, I implemented a layered search strategy.

Primary
GPT-4o-mini-search-preview for real-time web retrieval and citation-based search
Fallback
DuckDuckGo Instant Answer API for resilience and graceful degradation

Additionally, I use GPT-4o-mini to dynamically generate targeted search queries based on the post content rather than searching raw text directly. This improved retrieval precision substantially.

AI Orchestration Layer

The core orchestration happens in a multi-step agent pipeline:

Scrape → extract text, author, media
Vision Analysis → if image exists, generate image description using GPT-4o Vision
Query Generation → generate contextual search queries
Parallel Search Execution → execute searches concurrently using asyncio.gather
Synthesis → combine all collected context into structured bullet-point explanations with citations

The final synthesis step uses structured JSON output (response_format=json_object) to guarantee predictable responses and eliminate post-processing/parsing instability.

Data Modeling

I used Pydantic models to define API contracts end-to-end.

This provided:

input validation
typed request/response schemas
autogenerated API documentation
cleaner maintainability across services
Frontend

The frontend is a React-based single-page application focused on usability and explainability.

Users can:

paste a social media URL
submit raw text
upload screenshots/images
compare model outputs side-by-side

Results display:

original post
detected platform and author
image interpretation
generated explanations
supporting sources
search queries used during retrieval

I intentionally kept the interface minimal and technical, prioritizing transparency and traceability over visual complexity.

Evaluation & Quality Measurement

To validate output quality, I built an evaluation framework with real-world AI/tech social posts.

The benchmark evaluates:

Keyword Coverage → expected concepts identified
Semantic Relevance → embedding similarity between post and generated explanation
Length Quality → concise but informative responses
Bullet Count Completeness

Instead of using LLM-as-judge, I chose an embedding-based evaluation approach because it is:

more objective
reproducible
lower cost
easier to benchmark over time
Key Engineering Decisions

A few design decisions were especially important:

Parallelized Search Execution

Using asyncio.gather reduced latency significantly compared with sequential retrieval.

Structured JSON Responses

Every LLM interaction returns structured output, which made the system much more reliable in production.

Retrieval Before Reasoning

Extracting the real post content before inference improved context quality dramatically versus passing only URLs.

Cost/Performance Model Routing
GPT-4o-mini → lightweight query generation
GPT-4o → higher-quality synthesis and reasoning

This balanced cost efficiency with response quality.

Graceful Fallback Strategy

By layering OpenAI search with DuckDuckGo fallback, the system remains resilient even when one provider is unavailable.

Outcome

The result is a production-style AI agent that combines:

web scraping
multimodal vision
retrieval
LLM reasoning
structured output generation
measurable evaluation

into a single end-to-end workflow.

From a technical leadership perspective, this project demonstrates AI orchestration, scalable backend design, retrieval-augmented generation, multimodal processing, evaluation methodology, and practical product thinking around user-facing AI systems

## License

MIT
