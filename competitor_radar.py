"""
Competitor Radar — мониторинг конкурентов в Instagram и TikTok.
Находит вирусные посты, анализирует через AI, даёт рекомендации.
"""

import json
import logging
import subprocess
import time
from datetime import datetime, timezone, timedelta

import requests
from ai_helper import call_ai

logger = logging.getLogger("content_bot.radar")

MSK = timezone(timedelta(hours=3))

# --- Competitor List ---

# Competitor handles to monitor. Replace with the accounts you want to track,
# or load them from configuration.
COMPETITORS = {
    "instagram": [
        "competitor_one",
        "competitor_two",
        "competitor_three",
    ],
    "tiktok": [
        "competitor_one",
        "competitor_two",
    ],
}


# --- Fetchers (self-contained) ---

_IG_HEADERS = {
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


def _fetch_instagram(username: str, limit: int = 10) -> list[dict]:
    """Fetch recent posts for an Instagram user."""
    username = username.lstrip("@")
    posts = []
    max_id = None

    for attempt in range(3):
        try:
            while len(posts) < limit:
                batch_size = min(20, limit - len(posts))
                url = f"https://www.instagram.com/api/v1/feed/user/{username}/username/?count={batch_size}"
                if max_id:
                    url += f"&max_id={max_id}"

                resp = requests.get(url, headers=_IG_HEADERS, timeout=15)

                if resp.status_code == 429:
                    logger.warning(f"Rate limited on IG @{username}")
                    time.sleep(30)
                    break

                if resp.status_code != 200:
                    logger.warning(f"IG API {resp.status_code} for @{username}")
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

                    # For carousels, check carousel_media
                    if media_type == 8:
                        carousel = item.get("carousel_media", [])
                        for cm in carousel:
                            if cm.get("media_type") == 2:
                                views = max(views, cm.get("play_count", 0) or cm.get("view_count", 0) or 0)

                    posted_at = None
                    taken_at = item.get("taken_at")
                    if taken_at:
                        posted_at = datetime.fromtimestamp(taken_at, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

                    posts.append({
                        "url": post_url,
                        "caption": caption_text,
                        "views": views,
                        "likes": item.get("like_count", 0) or 0,
                        "comments": item.get("comment_count", 0) or 0,
                        "posted_at": posted_at,
                        "platform": "instagram",
                        "username": username,
                    })

                more_available = data.get("more_available", False)
                max_id = data.get("next_max_id")
                if not more_available or not max_id:
                    break
                time.sleep(2)

            if posts:
                return posts

        except requests.RequestException as e:
            logger.error(f"IG fetch error @{username}: {e}")
            if attempt < 2:
                time.sleep(10)
        except Exception as e:
            logger.error(f"IG fetch error @{username}: {e}")
            if attempt < 2:
                time.sleep(5)

    return posts


def _fetch_tiktok(username: str, limit: int = 10) -> list[dict]:
    """Fetch recent videos for a TikTok user via yt-dlp."""
    username = username.lstrip("@")
    url = f"https://www.tiktok.com/@{username}"

    cmd = [
        "yt-dlp",
        "--dump-json",
        "--flat-playlist",
        "--sleep-interval", "3",
        "--playlist-end", str(limit),
        "--no-warnings",
        url,
    ]

    videos = []

    for attempt in range(3):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0 and not result.stdout.strip():
                logger.warning(f"yt-dlp error @{username}: {result.stderr[:200]}")
                if attempt < 2:
                    continue
                return []

            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    title = data.get("title") or data.get("description") or ""

                    posted_at = None
                    ts = data.get("timestamp")
                    if ts:
                        posted_at = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
                    elif data.get("upload_date") and len(data["upload_date"]) == 8:
                        d = data["upload_date"]
                        posted_at = f"{d[:4]}-{d[4:6]}-{d[6:8]}"

                    videos.append({
                        "url": data.get("webpage_url") or data.get("url", ""),
                        "caption": (title or f"TikTok @{username}")[:200],
                        "views": data.get("view_count") or 0,
                        "likes": data.get("like_count") or 0,
                        "comments": data.get("comment_count") or 0,
                        "posted_at": posted_at,
                        "platform": "tiktok",
                        "username": username,
                    })
                except json.JSONDecodeError:
                    continue

            if videos:
                return videos

        except subprocess.TimeoutExpired:
            logger.warning(f"TikTok timeout @{username} (attempt {attempt + 1})")
        except Exception as e:
            logger.error(f"TikTok fetch error @{username}: {e}")

    return videos


# --- Viral Detection ---

def _detect_viral(posts: list[dict]) -> list[dict]:
    """
    Detect viral posts for a single account's post list.
    Viral = views > 2x account average OR top 3 by views.
    For posts with 0 views (photos), use engagement (likes + comments).
    """
    if not posts:
        return []

    # Check if most posts have views
    posts_with_views = [p for p in posts if p.get("views", 0) > 0]

    if len(posts_with_views) >= 3:
        # Use views as primary metric
        avg_views = sum(p["views"] for p in posts_with_views) / len(posts_with_views)
        sorted_posts = sorted(posts, key=lambda p: p.get("views", 0), reverse=True)
        top3_urls = {p["url"] for p in sorted_posts[:3]}

        viral = []
        for p in posts:
            is_viral = False
            reason = []
            if p.get("views", 0) > avg_views * 2:
                is_viral = True
                reason.append(f"views {p['views']} > 2x avg ({int(avg_views)})")
            if p["url"] in top3_urls:
                is_viral = True
                reason.append("top 3 by views")
            if is_viral:
                p["viral_reason"] = ", ".join(reason)
                p["avg_views"] = int(avg_views)
                viral.append(p)
        return viral
    else:
        # Fallback to engagement for photo-heavy accounts
        engagement = lambda p: p.get("likes", 0) + p.get("comments", 0)
        avg_eng = sum(engagement(p) for p in posts) / len(posts)
        sorted_posts = sorted(posts, key=engagement, reverse=True)
        top3_urls = {p["url"] for p in sorted_posts[:3]}

        viral = []
        for p in posts:
            is_viral = False
            reason = []
            eng = engagement(p)
            if eng > avg_eng * 2:
                is_viral = True
                reason.append(f"engagement {eng} > 2x avg ({int(avg_eng)})")
            if p["url"] in top3_urls:
                is_viral = True
                reason.append("top 3 by engagement")
            if is_viral:
                p["viral_reason"] = ", ".join(reason)
                p["avg_engagement"] = int(avg_eng)
                viral.append(p)
        return viral


# --- AI Analysis ---

def _analyze_viral_posts(viral_posts: list[dict]) -> str:
    """Use AI to analyze viral posts and generate insights."""
    if not viral_posts:
        return "Вирусных постов не найдено."

    # Build context for AI
    posts_text = ""
    for i, p in enumerate(viral_posts, 1):
        posts_text += (
            f"\n{i}. @{p['username']} ({p['platform']})\n"
            f"   Views: {p.get('views', 0):,} | Likes: {p.get('likes', 0):,} | Comments: {p.get('comments', 0):,}\n"
            f"   Viral reason: {p.get('viral_reason', '?')}\n"
            f"   Caption: {p.get('caption', '')}\n"
            f"   URL: {p.get('url', '')}\n"
            f"   Date: {p.get('posted_at', '?')}\n"
        )

    prompt = f"""Ты — аналитик контента для персонального бренда (ниша: AI-автоматизация бизнеса).

Вот вирусные посты конкурентов за последнее время:
{posts_text}

Проанализируй каждый пост:

1. Формат (карусель, talking head, скринкаст, мем, закадровый голос, текст на экране)
2. Какой хук использован (первые слова/секунды, что цепляет)
3. Почему это сработало (тема, эмоция, тренд)
4. Как автор может адаптировать это под свою нишу AI-автоматизации
5. Оценка steal-ability от 0 до 100 (насколько легко и эффективно автор может сделать свою версию)

ВАЖНО:
- Пиши по-русски
- Не используй списки через тире. Пиши абзацами, как человек
- Каждый пост разбирай отдельным блоком
- В конце дай общий вывод: какие 2-3 формата/хука сейчас работают лучше всего и что снимать на этой неделе"""

    result = call_ai(prompt, temperature=0.4, max_tokens=4096,
                     system="Ты контент-аналитик. Пиши конкретно, без воды. По-русски.")
    return result


# --- Main Radar Function ---

def run_competitor_radar() -> str:
    """
    Full competitor scan: fetch posts, detect viral, analyze via AI.
    Returns formatted TG message.
    """
    all_viral = []
    fetch_log = []

    # Instagram
    for username in COMPETITORS["instagram"]:
        try:
            posts = _fetch_instagram(username, limit=10)
            fetch_log.append(f"IG @{username}: {len(posts)} posts")
            if posts:
                viral = _detect_viral(posts)
                all_viral.extend(viral)
                if viral:
                    fetch_log[-1] += f" ({len(viral)} viral)"
        except Exception as e:
            fetch_log.append(f"IG @{username}: error — {e}")
        time.sleep(3)  # delay between accounts

    # TikTok
    for username in COMPETITORS["tiktok"]:
        try:
            posts = _fetch_tiktok(username, limit=10)
            fetch_log.append(f"TT @{username}: {len(posts)} posts")
            if posts:
                viral = _detect_viral(posts)
                all_viral.extend(viral)
                if viral:
                    fetch_log[-1] += f" ({len(viral)} viral)"
        except Exception as e:
            fetch_log.append(f"TT @{username}: error — {e}")
        time.sleep(3)

    # Log summary
    logger.info(f"Radar scan: {len(all_viral)} viral posts found. {'; '.join(fetch_log)}")

    if not all_viral:
        return (
            f"RADAR SCAN {datetime.now(MSK).strftime('%d.%m.%Y %H:%M')} MSK\n\n"
            f"Сканировал {len(COMPETITORS['instagram'])} IG + {len(COMPETITORS['tiktok'])} TT аккаунтов.\n"
            f"Вирусных постов не обнаружено.\n\n"
            + "\n".join(fetch_log)
        )

    # AI analysis
    analysis = _analyze_viral_posts(all_viral)

    # Build report
    header = (
        f"COMPETITOR RADAR {datetime.now(MSK).strftime('%d.%m.%Y %H:%M')} MSK\n\n"
        f"Сканировал: "
        + ", ".join(f"@{u}" for u in COMPETITORS["instagram"])
        + " (IG), "
        + ", ".join(f"@{u}" for u in COMPETITORS["tiktok"])
        + " (TT)\n"
        f"Найдено вирусных постов: {len(all_viral)}\n"
    )

    # Quick stats per viral post
    stats = "\n"
    for i, p in enumerate(all_viral, 1):
        views_str = f"{p['views']:,}".replace(",", " ") if p.get("views") else "N/A"
        likes_str = f"{p['likes']:,}".replace(",", " ") if p.get("likes") else "0"
        stats += (
            f"{i}. @{p['username']} ({p['platform']})\n"
            f"   {views_str} views | {likes_str} likes\n"
            f"   {p.get('caption', '')[:80]}\n"
            f"   {p.get('url', '')}\n\n"
        )

    report = header + stats + "\nANALYSIS\n\n" + analysis

    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run_competitor_radar())
