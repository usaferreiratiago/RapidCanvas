"""
PostExplainerAgent: orchestrates scraping, searching, and synthesizing context.
"""
import os
import time
import base64
import httpx
from typing import Optional, List
from openai import AsyncOpenAI

from scraper import fetch_post, detect_platform
from search import generate_search_queries, web_search
from models import ExplainResponse, Bullet, CompareResponse, ProviderResult

client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """You are an expert context researcher for social media posts.

Given a social media post (text + optional image description) and search results,
produce 3-5 concise bullet points that explain:
- Key references, jargon, memes, or in-jokes in the post
- Background context needed to understand why this was posted
- Who or what is being discussed
- Why it's notable or trending

Rules:
- Each bullet must be a standalone insight (not just restating the post)
- Be specific — names, dates, events matter
- Cite sources where possible using [Source: Title](URL) at end of bullet
- If the post is self-explanatory, still add relevant background
- Write for someone unfamiliar with the topic
- Return ONLY valid JSON: {"bullets": [{"text": "...", "source": "Title", "source_url": "https://..."}]}
"""


class PostExplainerAgent:

    async def explain(
        self,
        url: Optional[str] = None,
        text: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> ExplainResponse:
        """Main entry point: explain a post from a URL or raw text."""

        post_text = text
        post_author = None
        platform = None
        fetched_image_url = image_url

        # Step 1: If URL provided, scrape the post
        if url:
            platform = detect_platform(url)
            scraped_text, scraped_author, scraped_image = await fetch_post(url)
            if scraped_text:
                post_text = scraped_text
            post_author = scraped_author
            if scraped_image and not fetched_image_url:
                fetched_image_url = scraped_image

        if not post_text:
            post_text = url or "Unknown post"

        # Step 2: Describe image if present
        image_description = None
        if fetched_image_url:
            image_description = await self._describe_image(fetched_image_url)

        # Step 3: Generate search queries
        queries = await generate_search_queries(post_text, image_description)

        # Step 4: Run searches in parallel
        import asyncio
        search_results = await asyncio.gather(*[web_search(q) for q in queries])
        all_results = [r for results in search_results for r in results]

        # Step 5: Synthesize into bullets
        bullets = await self._synthesize(post_text, image_description, all_results, queries)

        return ExplainResponse(
            bullets=bullets,
            post_text=post_text,
            post_author=post_author,
            platform=platform or "unknown",
            image_description=image_description,
            search_queries_used=queries,
        )

    async def _describe_image(self, image_url: str) -> Optional[str]:
        """Use GPT-4o vision to describe an image in the post."""
        try:
            # Try to fetch and encode image
            async with httpx.AsyncClient(timeout=10) as http_client:
                resp = await http_client.get(image_url)
                if resp.status_code != 200:
                    return None
                img_data = base64.b64encode(resp.content).decode()
                content_type = resp.headers.get("content-type", "image/jpeg")

            vision_resp = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{content_type};base64,{img_data}"
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Describe this image concisely for a researcher trying to understand "
                                    "a social media post. Include: people/characters shown, text visible, "
                                    "memes or cultural references, and overall context. 2-3 sentences max."
                                ),
                            },
                        ],
                    }
                ],
                max_tokens=200,
            )
            return vision_resp.choices[0].message.content
        except Exception as e:
            return None

    async def _synthesize(
        self,
        post_text: str,
        image_description: Optional[str],
        search_results: list,
        queries: List[str],
    ) -> List[Bullet]:
        """Use GPT-4o to synthesize search results into bullet points."""

        # Format search context
        search_context = ""
        for i, r in enumerate(search_results[:12]):
            if r.get("snippet"):
                src = f"[{r.get('title', 'Source')}]({r.get('url', '')})" if r.get("url") else r.get("title", "")
                search_context += f"\n{i+1}. {src}\n{r['snippet'][:400]}\n"

        user_content = f"""POST TEXT:
{post_text}
"""
        if image_description:
            user_content += f"\nIMAGE DESCRIPTION:\n{image_description}\n"

        user_content += f"""
SEARCH RESULTS:
{search_context}

Return 3-5 bullet points as JSON."""

        import json
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        raw = resp.choices[0].message.content.strip()
        data = json.loads(raw)
        bullets_data = data.get("bullets", [])

        bullets = []
        for b in bullets_data:
            bullets.append(Bullet(
                text=b.get("text", ""),
                source=b.get("source"),
                source_url=b.get("source_url"),
            ))
        return bullets

    async def compare_providers(
        self,
        url: Optional[str] = None,
        text: Optional[str] = None,
    ) -> CompareResponse:
        """
        Compare explanations across providers: GPT-4o vs GPT-4o-mini.
        Extendable to Anthropic/Gemini with respective SDKs.
        """
        import asyncio
        import json

        post_text = text
        if url:
            scraped_text, _, _ = await fetch_post(url)
            if scraped_text:
                post_text = scraped_text

        if not post_text:
            post_text = url or "Unknown post"

        queries = await generate_search_queries(post_text)
        search_results = await asyncio.gather(*[web_search(q) for q in queries])
        all_results = [r for results in search_results for r in results]

        providers = [
            ("openai", "gpt-4o"),
            ("openai", "gpt-4o-mini"),
        ]

        async def run_provider(provider: str, model: str) -> ProviderResult:
            start = time.time()
            try:
                # Use the same synthesis but with different model
                search_context = ""
                for i, r in enumerate(all_results[:10]):
                    if r.get("snippet"):
                        search_context += f"\n{i+1}. {r['snippet'][:300]}\n"

                user_msg = f"POST: {post_text}\n\nSEARCH CONTEXT:\n{search_context}\n\nReturn 3-5 bullets as JSON."
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.3,
                    response_format={"type": "json_object"},
                )
                raw = resp.choices[0].message.content
                data = json.loads(raw)
                bullets = [Bullet(text=b.get("text", "")) for b in data.get("bullets", [])]
                latency = (time.time() - start) * 1000
                return ProviderResult(provider=provider, model=model, bullets=bullets, latency_ms=latency)
            except Exception as e:
                latency = (time.time() - start) * 1000
                return ProviderResult(provider=provider, model=model, bullets=[], latency_ms=latency, error=str(e))

        results = await asyncio.gather(*[run_provider(p, m) for p, m in providers])

        return CompareResponse(results=list(results), post_text=post_text)
