"""
AI News Parser — мониторинг топовых AI-источников, ежедневный дайджест.
Используется content_bot.py для отправки в TG + генерации скриптов по новостям.
"""

import logging
import re
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional
import time

import requests

logger = logging.getLogger(__name__)

# ── RSS Sources ──────────────────────────────────────────────

RSS_SOURCES = {
    # Company blogs (verified working)
    "OpenAI Blog": "https://openai.com/news/rss.xml",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",

    # Tech news (AI-focused, reliable RSS)
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",

    # Research
    "arXiv CS.AI": "http://export.arxiv.org/rss/cs.AI",
}

# Twitter/X accounts — we try nitter RSS bridges (multiple instances as fallback)
TWITTER_ACCOUNTS = ["sama", "AnthropicAI", "GoogleDeepMind", "ylecun"]
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.cz",
]

# Keywords for relevance filtering
AI_KEYWORDS = re.compile(
    r'\b(ai|artificial.intelligence|machine.learning|deep.learning|llm|gpt|claude|gemini|'
    r'neural|transformer|diffusion|language.model|foundation.model|'
    r'openai|anthropic|deepmind|meta.ai|mistral|'
    r'agi|alignment|rlhf|fine.tun|multimodal|reasoning|'
    r'copilot|chatbot|agent|rag|vector|embedding|'
    r'stable.diffusion|midjourney|dall.e|sora|'
    r'искусственн.{0,3}\s*интеллект|нейросет|модел)\b',
    re.IGNORECASE
)

# Headers to avoid blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def _parse_date(entry) -> Optional[datetime]:
    """Extract published date from feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        tp = getattr(entry, attr, None)
        if tp:
            try:
                from calendar import timegm
                return datetime.fromtimestamp(timegm(tp), tz=timezone.utc)
            except Exception:
                pass
    return None


def _text_hash(text: str) -> str:
    """Normalize and hash text for dedup."""
    normalized = re.sub(r'\s+', ' ', text.lower().strip())
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def _strip_html(text: str) -> str:
    """Remove HTML tags."""
    return re.sub(r'<[^>]+>', '', text or "").strip()


def _is_relevant(title: str, summary: str) -> bool:
    """Check if the article is AI-related by keywords."""
    text = f"{title} {summary}"
    return bool(AI_KEYWORDS.search(text))


def fetch_rss_news(hours: int = 24) -> list[dict]:
    """Fetch news from all RSS sources within last N hours."""
    import feedparser

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    all_items = []
    seen_hashes = set()

    for source_name, url in RSS_SOURCES.items():
        try:
            logger.info(f"Fetching RSS: {source_name}")
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"RSS {source_name}: HTTP {resp.status_code}")
                continue

            feed = feedparser.parse(resp.text)

            for entry in feed.entries[:30]:  # Max 30 per source
                pub_date = _parse_date(entry)
                if pub_date and pub_date < cutoff:
                    continue  # Too old

                title = _strip_html(getattr(entry, 'title', ''))
                summary = _strip_html(getattr(entry, 'summary', getattr(entry, 'description', '')))
                link = getattr(entry, 'link', '')

                if not title:
                    continue

                # For non-AI-specific sources, filter by keywords
                if source_name in ("Ars Technica",):
                    if not _is_relevant(title, summary):
                        continue

                # Dedup by title hash
                h = _text_hash(title)
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)

                all_items.append({
                    "title": title[:300],
                    "summary": summary[:500],
                    "url": link,
                    "source": source_name,
                    "published": pub_date.isoformat() if pub_date else "",
                    "pub_dt": pub_date,
                })

        except Exception as e:
            logger.error(f"RSS {source_name} error: {e}")
            continue

        # Small delay between sources
        time.sleep(0.3)

    # Try Twitter/X via nitter (best effort)
    for account in TWITTER_ACCOUNTS:
        for nitter_base in NITTER_INSTANCES:
            try:
                url = f"{nitter_base}/{account}/rss"
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code != 200:
                    continue

                feed = feedparser.parse(resp.text)
                for entry in feed.entries[:10]:
                    pub_date = _parse_date(entry)
                    if pub_date and pub_date < cutoff:
                        continue

                    title = _strip_html(getattr(entry, 'title', ''))
                    if not title or not _is_relevant(title, ""):
                        continue

                    h = _text_hash(title)
                    if h in seen_hashes:
                        continue
                    seen_hashes.add(h)

                    all_items.append({
                        "title": title[:300],
                        "summary": "",
                        "url": getattr(entry, 'link', ''),
                        "source": f"X/@{account}",
                        "published": pub_date.isoformat() if pub_date else "",
                        "pub_dt": pub_date,
                    })
                break  # Success — no need to try other nitter instances
            except Exception:
                continue

    # Sort by date (newest first)
    all_items.sort(key=lambda x: x.get("pub_dt") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    logger.info(f"Fetched {len(all_items)} AI news items from {len(RSS_SOURCES)} RSS + Twitter")
    return all_items


def _dedup_by_similarity(items: list[dict], threshold: float = 0.6) -> list[dict]:
    """Remove items with very similar titles (simple word overlap)."""
    result = []
    seen_words = []

    for item in items:
        words = set(re.findall(r'\w{4,}', item["title"].lower()))
        if not words:
            continue

        is_dup = False
        for prev_words in seen_words:
            overlap = len(words & prev_words) / max(len(words | prev_words), 1)
            if overlap > threshold:
                is_dup = True
                break

        if not is_dup:
            result.append(item)
            seen_words.append(words)

    return result


async def analyze_news_with_ai(items: list[dict], call_ai_fn) -> list[dict]:
    """Analyze top news items with AI. Returns items enriched with AI analysis."""
    import asyncio

    # Take top 10, dedup, then analyze
    deduped = _dedup_by_similarity(items[:30])[:10]

    if not deduped:
        return []

    # Batch analyze — send all items in one prompt for efficiency
    news_text = "\n\n".join(
        f"{i+1}. [{item['source']}] {item['title']}\n{item['summary'][:200]}"
        for i, item in enumerate(deduped)
    )

    prompt = f"""Ты — AI-аналитик новостей. Вот последние новости из мира AI:

{news_text}

Для КАЖДОЙ новости дай (строго в формате):
НОМЕР|КРАТКОЕ_ОПИСАНИЕ_1_СТРОКА_НА_РУССКОМ|ПОЧЕМУ_ВАЖНО_ДЛЯ_БИЗНЕСА|ХУК_ДЛЯ_ВИДЕО|ВИРАЛЬНОСТЬ_0_100

Правила:
- Краткое описание: 1 предложение на русском, суть новости
- Почему важно: 1 предложение — как это влияет на бизнес/автоматизацию
- Хук для видео: конкретная фраза-крючок для Reels (от лица AI-эксперта, ведущего личный бренд)
- Виральность: число 0-100 (насколько это зацепит аудиторию предпринимателей)
- Разделитель — |
- Никаких лишних слов, только данные

Пример:
1|OpenAI выпустил GPT-5 с мультимодальным reasoning|Бизнес сможет автоматизировать сложные задачи без программистов|Короче, GPT-5 вышел. И вот почему тебе пофиг на программистов теперь|85"""

    try:
        result = await call_ai_fn(prompt)
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        return deduped[:5]

    # Parse AI response
    for line in result.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        parts = line.split("|")
        if len(parts) < 5:
            continue

        try:
            idx = int(re.search(r'\d+', parts[0]).group()) - 1
            if 0 <= idx < len(deduped):
                deduped[idx]["ai_summary"] = parts[1].strip()
                deduped[idx]["ai_why"] = parts[2].strip()
                deduped[idx]["ai_hook"] = parts[3].strip()
                try:
                    deduped[idx]["virality"] = int(re.search(r'\d+', parts[4]).group())
                except (ValueError, AttributeError):
                    deduped[idx]["virality"] = 50
        except (ValueError, AttributeError, IndexError):
            continue

    # Sort by virality score
    for item in deduped:
        item.setdefault("virality", 30)
        item.setdefault("ai_summary", item["title"])
        item.setdefault("ai_why", "")
        item.setdefault("ai_hook", "")

    deduped.sort(key=lambda x: x.get("virality", 0), reverse=True)
    return deduped[:5]


def format_news_brief(items: list[dict], date_str: str = "") -> str:
    """Format analyzed news into a TG message."""
    if not date_str:
        from datetime import datetime, timezone, timedelta
        MSK = timezone(timedelta(hours=3))
        date_str = datetime.now(MSK).strftime("%d.%m.%Y")

    if not items:
        return f"AI НОВОСТИ ({date_str})\n\nСегодня значимых AI-новостей не найдено."

    lines = [f"AI НОВОСТИ ({date_str})\n"]

    for i, item in enumerate(items[:5], 1):
        title = item.get("ai_summary") or item["title"]
        why = item.get("ai_why", "")
        hook = item.get("ai_hook", "")
        virality = item.get("virality", "?")
        source = item.get("source", "")
        url = item.get("url", "")

        block = f"{i}. *{title}*"
        if source:
            block += f" ({source})"
        block += "\n"
        if why:
            block += f"Почему важно: {why}\n"
        if hook:
            block += f"Хук для видео: \"{hook}\"\n"
        block += f"Виральность: {virality}/100"
        if url:
            block += f"\n{url}"
        block += "\n"

        lines.append(block)

    return "\n".join(lines)


async def get_daily_news_brief(call_ai_fn) -> tuple[str, list[dict]]:
    """Full pipeline: fetch → analyze → format. Returns (brief_text, items)."""
    import asyncio

    items = await asyncio.to_thread(fetch_rss_news, 24)

    if not items:
        # Try 48h if nothing in 24h
        items = await asyncio.to_thread(fetch_rss_news, 48)

    analyzed = await analyze_news_with_ai(items, call_ai_fn)
    brief = format_news_brief(analyzed)
    return brief, analyzed


def get_most_viral_news_topic(items: list[dict]) -> Optional[str]:
    """Pick the most viral news item as a topic for script generation."""
    if not items:
        return None

    best = max(items, key=lambda x: x.get("virality", 0))
    title = best.get("ai_summary") or best["title"]
    hook = best.get("ai_hook", "")
    why = best.get("ai_why", "")

    topic = (
        f"AI НОВОСТЬ ДНЯ: {title}. "
        f"{why} "
        f"Хук: {hook}. "
        f"Объясни эту новость простым языком как практикующий AI-эксперт. "
        f"Почему это важно для предпринимателей. Что конкретно изменится."
    )
    return topic
