"""
Evaluation harness for the Post Explainer agent.
Tests 10+ posts and scores outputs using:
  1. Coverage  – expected keywords present in bullets
  2. Relevance – semantic similarity via embeddings
  3. Conciseness – bullet length within acceptable range
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional
import sys

sys.path.insert(0, os.path.dirname(__file__))

from agent import PostExplainerAgent
from openai import AsyncOpenAI

openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ── Test cases ────────────────────────────────────────────────────────────────

TEST_POSTS = [
    {
        "id": "ralph_wiggum",
        "text": (
            "Ralph Wiggum is the craziest thing to happen in the coding agents space in 2026 so far. "
            "not the technique itself, just the fact that someone was like 'here's a technique it's "
            "called the Ralph Wiggum technique because of the Simpsons guy' and everyone was like 'OK sounds good'"
        ),
        "expected_keywords": ["bash", "loop", "agent", "Geoffrey Huntley", "Simpsons", "technique", "coding"],
        "expected_bullets_min": 3,
        "notes": "Reference to the Ralph Wiggum agentic coding technique",
    },
    {
        "id": "gpt5_release",
        "text": "GPT-5 drops and suddenly everyone's a prompt engineer again 💀",
        "expected_keywords": ["OpenAI", "GPT", "language model", "AI"],
        "expected_bullets_min": 3,
        "notes": "Sarcastic take on GPT-5 hype",
    },
    {
        "id": "vibe_coding",
        "text": "Vibe coding is just pair programming where your partner never questions your decisions",
        "expected_keywords": ["vibe coding", "AI", "Andrej Karpathy", "code generation"],
        "expected_bullets_min": 3,
        "notes": "Joke about AI-assisted vibe coding trend",
    },
    {
        "id": "cursor_ai",
        "text": "Cursor just shipped agents that can edit 50 files at once. The IDE wars are genuinely insane right now.",
        "expected_keywords": ["Cursor", "IDE", "editor", "agent", "code"],
        "expected_bullets_min": 3,
        "notes": "News about Cursor AI IDE",
    },
    {
        "id": "devin_ai",
        "text": "6 months after launch, Devin is quietly being used at real companies to ship real code",
        "expected_keywords": ["Devin", "Cognition", "software engineer", "AI agent"],
        "expected_bullets_min": 3,
        "notes": "Update on Devin the AI software engineer",
    },
    {
        "id": "arc_agi",
        "text": "ARC-AGI score just hit 85%. Two years ago people said 30% would never happen.",
        "expected_keywords": ["ARC-AGI", "benchmark", "François Chollet", "reasoning", "general intelligence"],
        "expected_bullets_min": 3,
        "notes": "Progress on the ARC-AGI benchmark",
    },
    {
        "id": "mcp_protocol",
        "text": "MCP is quietly becoming the USB-C of AI tooling. Every framework just... adopted it.",
        "expected_keywords": ["MCP", "Model Context Protocol", "Anthropic", "tools", "standard"],
        "expected_bullets_min": 3,
        "notes": "MCP (Model Context Protocol) adoption metaphor",
    },
    {
        "id": "sam_altman_tweet",
        "text": "we believe we know how to build AGI. we may build it in 2025.",
        "expected_keywords": ["Sam Altman", "OpenAI", "AGI", "artificial general intelligence"],
        "expected_bullets_min": 3,
        "notes": "Sam Altman's AGI claim",
    },
    {
        "id": "llm_context_window",
        "text": "1M token context window and people are still chunking PDFs into 512 token pieces lmao",
        "expected_keywords": ["context window", "RAG", "chunking", "embeddings", "retrieval"],
        "expected_bullets_min": 3,
        "notes": "Mocking outdated RAG approaches given large context windows",
    },
    {
        "id": "open_source_ai",
        "text": "Llama 4 Scout runs at 15 tok/s on an M3 MacBook Pro. Open source won.",
        "expected_keywords": ["Llama", "Meta", "open source", "local", "inference"],
        "expected_bullets_min": 3,
        "notes": "Llama 4 local inference capabilities",
    },
    {
        "id": "anthropic_claude",
        "text": "Claude refuses to write the 6 lines of bash that would automate my job. Absolutely cooked.",
        "expected_keywords": ["Claude", "Anthropic", "safety", "refusal", "alignment"],
        "expected_bullets_min": 3,
        "notes": "Frustration with Claude's safety refusals",
    },
    {
        "id": "reasoning_models",
        "text": "o3 used 172 hours of compute to solve a single chemistry problem. This is not intelligence, this is brute force.",
        "expected_keywords": ["o3", "OpenAI", "reasoning", "compute", "test-time"],
        "expected_bullets_min": 3,
        "notes": "Critique of reasoning model compute costs",
    },
]


# ── Scoring ───────────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    test_id: str
    passed: bool
    keyword_score: float       # 0–1: fraction of expected keywords found
    bullet_count: int
    bullet_count_ok: bool
    avg_bullet_length: float
    length_score: float        # 1.0 if 30–200 chars, else 0.5
    semantic_score: float      # 0–1 from embedding similarity
    overall_score: float       # weighted average
    bullets: List[str] = field(default_factory=list)
    error: Optional[str] = None
    latency_ms: float = 0.0


def keyword_score(bullets: List[str], expected: List[str]) -> float:
    """Fraction of expected keywords that appear (case-insensitive) in any bullet."""
    if not expected:
        return 1.0
    combined = " ".join(bullets).lower()
    hits = sum(1 for kw in expected if kw.lower() in combined)
    return hits / len(expected)


def length_score(bullets: List[str]) -> float:
    """Score based on bullet lengths being in [30, 220] char range."""
    if not bullets:
        return 0.0
    scores = []
    for b in bullets:
        l = len(b)
        if 30 <= l <= 220:
            scores.append(1.0)
        elif l < 20 or l > 350:
            scores.append(0.3)
        else:
            scores.append(0.7)
    return sum(scores) / len(scores)


async def semantic_score(bullets: List[str], post_text: str) -> float:
    """
    Use embeddings to check that bullets are semantically related to the post.
    Score = mean cosine similarity of each bullet to the post.
    """
    import numpy as np

    try:
        texts = [post_text] + bullets
        resp = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        vecs = [e.embedding for e in resp.data]
        post_vec = vecs[0]
        bullet_vecs = vecs[1:]

        def cosine(a, b):
            a, b = [x for x in a], [x for x in b]
            dot = sum(x * y for x, y in zip(a, b))
            na = sum(x**2 for x in a) ** 0.5
            nb = sum(x**2 for x in b) ** 0.5
            return dot / (na * nb) if na * nb else 0

        sims = [cosine(post_vec, bv) for bv in bullet_vecs]
        return sum(sims) / len(sims) if sims else 0.0
    except Exception:
        return 0.5  # neutral if embeddings fail


async def run_test(agent: PostExplainerAgent, case: dict) -> TestResult:
    start = time.time()
    try:
        result = await agent.explain(text=case["text"])
        latency = (time.time() - start) * 1000

        bullet_texts = [b.text for b in result.bullets]

        kw = keyword_score(bullet_texts, case["expected_keywords"])
        lscore = length_score(bullet_texts)
        sem = await semantic_score(bullet_texts, case["text"])
        count_ok = result.bullets and len(result.bullets) >= case["expected_bullets_min"]

        # Weighted overall score
        overall = 0.4 * kw + 0.3 * sem + 0.2 * lscore + 0.1 * (1.0 if count_ok else 0.0)

        avg_len = sum(len(b) for b in bullet_texts) / len(bullet_texts) if bullet_texts else 0

        return TestResult(
            test_id=case["id"],
            passed=overall >= 0.5,
            keyword_score=round(kw, 3),
            bullet_count=len(result.bullets),
            bullet_count_ok=bool(count_ok),
            avg_bullet_length=round(avg_len, 1),
            length_score=round(lscore, 3),
            semantic_score=round(sem, 3),
            overall_score=round(overall, 3),
            bullets=bullet_texts,
            latency_ms=round(latency, 1),
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return TestResult(
            test_id=case["id"],
            passed=False,
            keyword_score=0.0,
            bullet_count=0,
            bullet_count_ok=False,
            avg_bullet_length=0.0,
            length_score=0.0,
            semantic_score=0.0,
            overall_score=0.0,
            error=str(e),
            latency_ms=round(latency, 1),
        )


# ── Runner ────────────────────────────────────────────────────────────────────

async def run_all(concurrency: int = 3):
    agent = PostExplainerAgent()
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded(case):
        async with semaphore:
            print(f"  → Running: {case['id']}")
            return await run_test(agent, case)

    results = await asyncio.gather(*[bounded(c) for c in TEST_POSTS])

    # Summary
    passed = sum(1 for r in results if r.passed)
    avg_score = sum(r.overall_score for r in results) / len(results)
    avg_latency = sum(r.latency_ms for r in results) / len(results)

    print("\n" + "=" * 60)
    print(f"EVAL RESULTS  |  {passed}/{len(results)} passed  |  avg score: {avg_score:.2f}  |  avg latency: {avg_latency:.0f}ms")
    print("=" * 60)

    for r in results:
        status = "✓" if r.passed else "✗"
        print(
            f"  {status} {r.test_id:<25} "
            f"overall={r.overall_score:.2f}  "
            f"kw={r.keyword_score:.2f}  "
            f"sem={r.semantic_score:.2f}  "
            f"bullets={r.bullet_count}  "
            f"{r.latency_ms:.0f}ms"
            + (f"  ERROR: {r.error}" if r.error else "")
        )

    # Save detailed results
    out_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
    with open(out_path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    print(f"\nDetailed results saved to {out_path}")

    return results


if __name__ == "__main__":
    asyncio.run(run_all())
