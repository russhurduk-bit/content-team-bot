"""Instagram analytics collector for Content Tracker."""

import logging
import time
from datetime import datetime, timezone, timedelta

import requests

logger = logging.getLogger("content_bot.analytics")

MSK = timezone(timedelta(hours=3))

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; SM-G991B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
    "X-IG-App-ID": "936619743392459",
    "X-ASBD-ID": "129477",
    "X-IG-WWW-Claim": "0",
    "Origin": "https://www.instagram.com",
    "Referer": "https://www.instagram.com/",
}


def fetch_recent_posts(username: str, limit: int = 20) -> list[dict]:
    """Fetch recent posts from Instagram. Returns list of post dicts."""
    username = username.lstrip("@")
    posts = []
    max_id = None
    retries = 3

    for attempt in range(retries):
        try:
            logger.info(f"Fetching Instagram @{username} (attempt {attempt + 1})")

            while len(posts) < limit:
                batch_size = min(20, limit - len(posts))
                url = f"https://www.instagram.com/api/v1/feed/user/{username}/username/?count={batch_size}"
                if max_id:
                    url += f"&max_id={max_id}"

                resp = requests.get(url, headers=_HEADERS, timeout=15)

                if resp.status_code == 429:
                    logger.warning(f"Rate limited on Instagram @{username}")
                    time.sleep(30)
                    break

                if resp.status_code != 200:
                    logger.warning(f"Instagram API returned {resp.status_code} for @{username}")
                    break

                data = resp.json()
                items = data.get("items", [])

                if not items:
                    break

                for item in items:
                    if len(posts) >= limit:
                        break

                    code = item.get("code", "")
                    post_url = f"https://www.instagram.com/p/{code}/" if code else ""

                    caption_text = ""
                    caption = item.get("caption")
                    if caption:
                        caption_text = (caption.get("text") or "")[:200]

                    media_type = item.get("media_type", 0)
                    views = 0
                    if media_type == 2:  # video/reel
                        views = item.get("play_count", 0) or item.get("view_count", 0) or 0

                    like_count = item.get("like_count", 0) or 0
                    comment_count = item.get("comment_count", 0) or 0

                    posted_at = None
                    taken_at = item.get("taken_at")
                    if taken_at:
                        posted_at = datetime.fromtimestamp(taken_at, tz=timezone.utc)

                    posts.append({
                        "url": post_url,
                        "caption": caption_text,
                        "views": views,
                        "likes": like_count,
                        "comments": comment_count,
                        "posted_at": posted_at,
                        "media_type": media_type,
                    })

                more_available = data.get("more_available", False)
                max_id = data.get("next_max_id")

                if not more_available or not max_id:
                    break

                time.sleep(2)

            if posts:
                logger.info(f"Instagram @{username}: got {len(posts)} posts")
                return posts

        except requests.RequestException as e:
            logger.error(f"Error fetching Instagram @{username}: {e}")
            if attempt < retries - 1:
                time.sleep(10)
                continue
        except Exception as e:
            logger.error(f"Error fetching Instagram @{username}: {e}")
            if attempt < retries - 1:
                continue

    return posts


def match_post_to_scenario(posts: list[dict], scenario_date: datetime) -> dict | None:
    """Find a post that matches the scenario date (±1 day)."""
    if not posts:
        return None

    scenario_date_only = scenario_date.date()

    best_match = None
    best_diff = None

    for post in posts:
        posted_at = post.get("posted_at")
        if not posted_at:
            continue

        # Convert to MSK for date comparison
        posted_msk = posted_at.astimezone(MSK)
        diff = abs((posted_msk.date() - scenario_date_only).days)

        if diff <= 1:
            if best_diff is None or diff < best_diff:
                best_match = post
                best_diff = diff

    return best_match


def calculate_virality(views: int, likes: int, comments: int) -> str:
    """Calculate a simple virality score."""
    if views == 0:
        return "—"

    engagement_rate = ((likes + comments) / views) * 100 if views > 0 else 0

    if views >= 100000:
        tier = "🔥🔥🔥 Вирусное"
    elif views >= 50000:
        tier = "🔥🔥 Отлично"
    elif views >= 10000:
        tier = "🔥 Хорошо"
    elif views >= 1000:
        tier = "👍 Нормально"
    else:
        tier = "📊 Набирает"

    return f"{tier} ({engagement_rate:.1f}% ER)"


def collect_analytics(username: str) -> dict:
    """Collect analytics for the account. Returns summary dict."""
    posts = fetch_recent_posts(username, limit=20)

    if not posts:
        return {"posts": [], "total_videos": 0}

    total_views = sum(p.get("views", 0) for p in posts)
    total_likes = sum(p.get("likes", 0) for p in posts)
    videos_only = [p for p in posts if p.get("media_type") == 2]

    best = max(posts, key=lambda p: p.get("views", 0)) if posts else None

    return {
        "posts": posts,
        "total_videos": len(videos_only),
        "total_posts": len(posts),
        "total_views": total_views,
        "total_likes": total_likes,
        "best_video": best.get("url", "") if best else "",
        "best_views": best.get("views", 0) if best else 0,
        "best_caption": best.get("caption", "") if best else "",
    }
