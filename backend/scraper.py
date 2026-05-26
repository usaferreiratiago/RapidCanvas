"""
Scrapes post content from various social platforms and generic URLs.
Uses BeautifulSoup + httpx for lightweight scraping.
"""
import re
import httpx
from typing import Optional, Tuple
from urllib.parse import urlparse


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def detect_platform(url: str) -> str:
    """Detect which social platform a URL belongs to."""
    domain = urlparse(url).netloc.lower()
    if "bsky.app" in domain or "bluesky" in domain:
        return "bluesky"
    if "twitter.com" in domain or "x.com" in domain:
        return "twitter"
    if "reddit.com" in domain:
        return "reddit"
    if "threads.net" in domain:
        return "threads"
    if "mastodon" in domain:
        return "mastodon"
    return "generic"


async def fetch_post(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Fetch post text, author, and image from a URL.
    Returns (text, author, image_url).
    """
    platform = detect_platform(url)

    try:
        if platform == "bluesky":
            return await fetch_bluesky(url)
        elif platform == "twitter":
            return await fetch_twitter_oembed(url)
        elif platform == "reddit":
            return await fetch_reddit(url)
        else:
            return await fetch_generic(url)
    except Exception as e:
        return None, None, None


async def fetch_bluesky(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Fetch Bluesky post via the public AT Protocol API.
    URL format: https://bsky.app/profile/{handle}/post/{rkey}
    """
    # Parse handle and rkey from URL
    match = re.search(r"bsky\.app/profile/([^/]+)/post/([^/?#]+)", url)
    if not match:
        return await fetch_generic(url)

    handle, rkey = match.group(1), match.group(2)

    # First resolve handle to DID
    async with httpx.AsyncClient(timeout=10) as client:
        # Try direct API call
        api_url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.getPostThread"
        params = {"uri": f"at://{handle}/app.bsky.feed.post/{rkey}"}

        resp = await client.get(api_url, params=params, headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            post = data.get("thread", {}).get("post", {})
            record = post.get("record", {})
            author = post.get("author", {})

            text = record.get("text", "")
            author_name = author.get("displayName") or author.get("handle", "")

            # Check for embedded image
            image_url = None
            embed = post.get("embed", {})
            images = embed.get("images", [])
            if images:
                image_url = images[0].get("fullsize") or images[0].get("thumb")

            return text, author_name, image_url

    return await fetch_generic(url)


async def fetch_twitter_oembed(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Fetch Twitter/X post via oEmbed."""
    oembed_url = f"https://publish.twitter.com/oembed?url={url}&omit_script=true"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(oembed_url, headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            html = data.get("html", "")
            # Strip HTML tags for plain text
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            author = data.get("author_name", "")
            return text, author, None
    return await fetch_generic(url)


async def fetch_reddit(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Fetch Reddit post via JSON API."""
    json_url = url.rstrip("/") + ".json"
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        resp = await client.get(json_url, headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            try:
                post = data[0]["data"]["children"][0]["data"]
                title = post.get("title", "")
                selftext = post.get("selftext", "")
                author = post.get("author", "")
                text = f"{title}\n\n{selftext}".strip()
                return text, author, None
            except (IndexError, KeyError):
                pass
    return await fetch_generic(url)


async def fetch_generic(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Fallback: fetch URL and extract meaningful text from meta tags / OG data.
    """
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            html = resp.text

        # Try OG tags first
        og_desc = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', html)
        og_title = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
        og_image = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)

        text_parts = []
        if og_title:
            text_parts.append(og_title.group(1))
        if og_desc:
            text_parts.append(og_desc.group(1))

        text = " — ".join(text_parts) if text_parts else None
        image_url = og_image.group(1) if og_image else None

        return text, None, image_url
    except Exception:
        return None, None, None
