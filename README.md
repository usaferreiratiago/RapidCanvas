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

## License

MIT
