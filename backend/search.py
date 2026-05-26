"""
Search module: uses OpenAI's web search tool to retrieve context.
Falls back to DuckDuckGo if needed.
"""
import os
import json
import httpx
from typing import List, Dict, Optional
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


async def generate_search_queries(post_text: str, image_description: Optional[str] = None) -> List[str]:
    """
    Use GPT to generate targeted search queries for a post.
    Returns 2-3 specific queries.
    """
    context = post_text
    if image_description:
        context += f"\n\n[Image in post shows: {image_description}]"

    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert at formulating web search queries. "
                    "Given a social media post, generate 2-3 targeted search queries "
                    "that would help explain the references, context, and background. "
                    "Focus on: named entities, jargon, events, memes, or cultural references. "
                    "Return ONLY a JSON array of strings, nothing else."
                ),
            },
            {"role": "user", "content": f"Post: {context}"},
        ],
        temperature=0.3,
    )

    raw = resp.choices[0].message.content.strip()
    # Strip markdown code fences if present
    raw = raw.strip("```json").strip("```").strip()
    queries = json.loads(raw)
    return queries[:3]


async def web_search(query: str) -> List[Dict]:
    """
    Perform a web search using OpenAI's built-in web search tool.
    Returns list of {title, url, snippet}.
    """
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini-search-preview",
            messages=[{"role": "user", "content": query}],
            web_search_options={},
        )
        # Extract annotations/citations from the response
        message = resp.choices[0].message
        results = []

        # The search model returns text with inline citations
        # Parse annotations if available
        if hasattr(message, "annotations") and message.annotations:
            for ann in message.annotations:
                if hasattr(ann, "url_citation"):
                    results.append({
                        "title": getattr(ann.url_citation, "title", ""),
                        "url": getattr(ann.url_citation, "url", ""),
                        "snippet": message.content[:300] if message.content else "",
                    })

        # Also include the full response text as context
        if message.content:
            results.append({
                "title": f"Search: {query}",
                "url": "",
                "snippet": message.content,
                "is_summary": True,
            })

        return results
    except Exception as e:
        # Fallback to DuckDuckGo
        return await ddg_search(query)


async def ddg_search(query: str) -> List[Dict]:
    """DuckDuckGo instant answer API as fallback."""
    try:
        async with httpx.AsyncClient(timeout=8) as client_http:
            resp = await client_http.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1"},
                headers={"User-Agent": "PostExplainer/1.0"},
            )
            data = resp.json()

        results = []
        # Abstract
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", ""),
                "url": data.get("AbstractURL", ""),
                "snippet": data["AbstractText"],
            })
        # Related topics
        for topic in data.get("RelatedTopics", [])[:3]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:80],
                    "url": topic.get("FirstURL", ""),
                    "snippet": topic.get("Text", ""),
                })
        return results
    except Exception:
        return []
