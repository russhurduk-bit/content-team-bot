"""TikTok fetcher — thin wrapper over the radar's yt-dlp based fetcher."""

from competitor_radar import _fetch_tiktok


def fetch_videos(username: str, limit: int = 20) -> list[dict]:
    """Fetch recent TikTok videos and expose them with a uniform schema."""
    videos = _fetch_tiktok(username, limit)
    for v in videos:
        v.setdefault("title", v.get("caption", ""))
    return videos
