"""Instagram fetcher — thin wrapper over the analytics collector."""

from content_analytics import fetch_recent_posts


def fetch_videos(username: str, limit: int = 20) -> list[dict]:
    """Fetch recent Instagram posts and expose them with a uniform schema."""
    posts = fetch_recent_posts(username, limit)
    for p in posts:
        p.setdefault("title", p.get("caption", ""))
        p.setdefault("platform", "instagram")
    return posts
