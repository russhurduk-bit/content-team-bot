"""
Content Assistant Bot — AI контентщик для Instagram.
Даёт идеи для рилсов, контент-планы, скрипты.
Анализирует видео на виральность. Мониторит TikTok/Instagram.
Multi-agent Content Team: 7 AI-агентов с брифингами и коллаборацией.
По запросу + еженедельно автоматически (понедельник 10:00 MSK).
"""

import os
import json
import asyncio
import logging
import random
import tempfile
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from ai_helper import call_ai, call_ai_vision
from content_team import (
    run_team_briefing, run_team_script, run_team_plan, run_team_review,
    quick_idea_check, quick_hook_battle, AGENTS,
)
from content_sheets import (
    save_scenario, get_scenarios_needing_analytics,
    update_scenario_analytics, update_analytics_sheet,
    get_sheet_url, extract_hook_from_script,
    update_scenario_link, update_scenario_clicks,
    get_all_scenario_sources,
    save_to_idea_bank, get_ideas_from_bank,
    update_idea_bank_status, get_weekly_report_data,
    extract_format_from_script,
)
from link_tracker import create_tracked_link, get_all_links_stats, get_clicks_for_source
from content_analytics import (
    fetch_recent_posts, match_post_to_scenario,
    calculate_virality, collect_analytics,
)
from competitor_radar import run_competitor_radar
from ai_news_parser import (
    get_daily_news_brief, get_most_viral_news_topic, format_news_brief,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# TikTok/Instagram usernames to monitor (owner's accounts)
MONITOR_TIKTOK = os.environ.get("MONITOR_TIKTOK", "").strip()
MONITOR_INSTAGRAM = os.environ.get("MONITOR_INSTAGRAM", "").strip()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

MSK = timezone(timedelta(hours=3))

# TG channel for auto-posting
TG_CHANNEL = os.environ.get("TG_CHANNEL", "@your_channel")
TG_CHANNEL_URL = f"https://t.me/{TG_CHANNEL.lstrip('@')}"

# Persistent storage for daily scripts and news (survives restarts)
_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bot_state.json")


def _load_state() -> dict:
    try:
        with open(_STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"daily_scripts": {}, "latest_news_items": [], "latest_news_date": ""}


def _save_state():
    try:
        state = {
            "daily_scripts": _daily_scripts,
            "latest_news_items": _latest_news_items,
            "latest_news_date": _latest_news_date,
        }
        with open(_STATE_FILE, "w") as f:
            json.dump(state, f, ensure_ascii=False, default=str)
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to save state: {e}")


_initial_state = _load_state()
_daily_scripts: dict[str, dict] = _initial_state.get("daily_scripts", {})

# --- Profile context ---

# The brand profile the assistant reasons about. Replace the placeholders below
# with your own brand, niche, services and real cases.
PROFILE_CONTEXT = """
Ты — AI контент-менеджер для Instagram аккаунта личного бренда (@your_brand).

ПРОФИЛЬ БРЕНДА:
- Персональный бренд-эксперт (замените на свои данные)
- Ниша: AI-автоматизация бизнес-процессов и контента
- Услуги: автоматизация видеоконтента, AI video production,
  Telegram-боты, n8n воркфлоу, парсинг/скрейпинг, интеграции платежей,
  AI-персоны для контента
- Стек: Python, Node.js, FastAPI, React, n8n, Docker, Playwright, LLM API
- ЦА: владельцы малого бизнеса, предприниматели e-commerce, контент-мейкеры, маркетологи
- Цель: привлечение клиентов + личный бренд эксперта-автоматизатора

РЕАЛЬНЫЕ КЕЙСЫ (веди список своих кейсов и используй их для контента):
1. [Кейс 1 — что было ДО, что сделал, результат с цифрами]
2. [Кейс 2 — ...]
3. [Кейс 3 — ...]

КОНТЕНТ-СТРАТЕГИЯ (проверенный плейбук короткого формата):

ФОРМУЛЫ ЗАГОЛОВКОВ (доказано работают):
- "Полная схема [результат]" — топовый охват
- "N шагов/советов/правил" — числа = кликабельность
- Кейсы с цифрами: "Как я [результат] за [срок]"
- "(с нуля)" в заголовке КРАТНО увеличивает просмотры

СТРУКТУРА ВИРУСНОГО ВИДЕО:
- ХУК (0-3 сек): соцдок + перечисление + обещание бонуса
- УТП = уникальный авторский угол (фишка, которую нельзя скопировать) — повторять ЧАСТО
- ПРОБЛЕМА: "95% делают это вручную / теряют деньги потому что..."
- РЕШЕНИЕ: пошаговая структура + реальные кейсы между шагами
- CTA: НИКОГДА не продавать в лоб — только "ссылка в шапке" / "чек-лист в TG"

ВОРОНКА:
Reels/TikTok → профиль → ТГ канал (лид-магнит: чек-лист) → бесплатный разбор → продажа услуг

7 ФОРМАТОВ (чередовать!):
1. КЕЙС — "Я автоматизировал [процесс]" (2/нед)
2. БОЛЬ — "3 вещи которые [ЦА] делает вручную" (2/нед)
3. ДЕМО — запись экрана бота/воркфлоу (1/нед)
4. ЦЕННИК — "Сколько стоит бот?" (1/нед)
5. СТРАХ — "Ошибка которая стоит [сумма]" (1/нед)
6. ТРАНСФОРМАЦИЯ — "До/После автоматизации"
7. ОБУЧАЛКА — "Как [результат] за [срок]"

СТИЛЬ: простым языком, результат > теория, до/после, хук 2 сек, 30-60 сек, тон дружелюбный экспертный.
"""

# --- Prompts ---

REELS_IDEAS_PROMPT = PROFILE_CONTEXT + """
Придумай 5 идей для Instagram Reels. Для каждой:
1. Хук (первые 2 секунды — что скажу/покажу чтобы зацепить)
2. Тема и суть (1-2 предложения)
3. Формат (говорящая голова / экран записывается / до-после / мем-формат)
4. Примерный хронометраж
5. CTA (призыв к действию)

Темы должны быть разнообразные: кейс, обучающий, мем/трендовый, лайфстайл эксперта, продающий.
"""

CONTENT_PLAN_PROMPT = PROFILE_CONTEXT + """
Составь контент-план на неделю (7 дней, по 1 посту в день).
Для каждого дня:

📅 День (Пн/Вт/...):
📝 Тип: (Reels / Carousel / Stories)
🎯 Тема:
🪝 Хук:
📋 Краткое описание что показывать/говорить:
#️⃣ Хештеги (5-7 штук):

Чередуй типы контента. Используй реальные кейсы.
Понедельник — мотивация/кейс, Пятница — развлекательный.
"""

SCRIPT_PROMPT = PROFILE_CONTEXT + """
Напиши полный скрипт для Instagram Reels на тему: {topic}

Формат:
🪝 ХУК (0-3 сек): [что сказать/показать]
📖 ОСНОВА (3-30 сек): [по предложениям, что говорить]
🎬 ВИЗУАЛ: [что показывать на экране в каждый момент]
💬 CTA (последние 5 сек): [призыв к действию]
📝 ТЕКСТ ДЛЯ ПОСТА: [описание под рилсом]
#️⃣ ХЕШТЕГИ: [7-10 штук]

Скрипт должен быть на 30-45 секунд. Простым языком.
"""

TREND_PROMPT = PROFILE_CONTEXT + """
Предложи 3 актуальных тренда в Instagram Reels, которые автор может адаптировать под свою нишу автоматизации.
Для каждого тренда:
1. Описание тренда и почему он вирусный
2. Как адаптировать под автоматизацию
3. Примерный сценарий
4. Какой звук/музыку использовать
"""

CAPTION_PROMPT = PROFILE_CONTEXT + """
Напиши 3 варианта текста (caption) для Instagram поста на тему: {topic}

Каждый вариант:
- Хук в первой строке (чтобы нажали "ещё")
- 3-5 предложений основного текста
- CTA (подписывайся/пиши в DM/сохраняй)
- 7-10 хештегов

Варианты: 1) серьёзный экспертный 2) живой разговорный 3) провокационный
"""


async def ask_gemini(prompt: str) -> str:
    """Send prompt to AI via ai_helper (Groq free → GPT fallback → OpenRouter free).
    Retries up to 3 times with backoff if all providers fail."""
    import requests as _requests

    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    openrouter_free_models = [
        "google/gemma-4-26b-a4b-it:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-14b:free",
    ]

    for attempt in range(3):
        # 1. ai_helper chain: Groq → GPT-4o-mini → OpenRouter
        try:
            result = await asyncio.to_thread(call_ai, prompt, 0.9, 4000)
            if result:
                return result
        except Exception as e:
            logger.warning(f"ai_helper error (attempt {attempt+1}): {e}")

        # 2. OpenRouter free models rotation
        if openrouter_key:
            for model in openrouter_free_models:
                try:
                    r = await asyncio.to_thread(
                        lambda m=model: _requests.post("https://openrouter.ai/api/v1/chat/completions",
                            headers={"Authorization": f"Bearer {openrouter_key}", "Content-Type": "application/json"},
                            json={"model": m,
                                  "messages": [{"role": "user", "content": prompt}],
                                  "temperature": 0.9, "max_tokens": 4000},
                            timeout=60)
                    )
                    if r.status_code == 200:
                        text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                        if text:
                            return text
                    else:
                        logger.warning(f"OpenRouter {model}: HTTP {r.status_code}")
                except Exception as e:
                    logger.warning(f"OpenRouter {model} error: {e}")

        if attempt < 2:
            await asyncio.sleep(5 * (attempt + 1))

    return "❌ Все AI провайдеры недоступны. Проверь GROQ_API_KEY / OPENROUTER_API_KEY в .env"


async def analyze_video_virality(video_path: str) -> str:
    """Analyze video virality. Uses GPT-4o-mini vision if available, otherwise text-only."""
    import base64

    # Try OpenAI GPT-4o-mini vision (paid but cheap)
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        try:
            # Extract a frame from video for vision analysis
            import subprocess
            frame_path = video_path + ".thumb.jpg"
            subprocess.run([
                "ffmpeg", "-i", video_path, "-ss", "1", "-vframes", "1",
                "-vf", "scale=512:-1", "-y", frame_path
            ], capture_output=True, timeout=15)

            if os.path.exists(frame_path):
                with open(frame_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                os.remove(frame_path)

                result = call_ai_vision(
                    PROFILE_CONTEXT + VIDEO_ANALYSIS_PROMPT,
                    img_b64, "image/jpeg", 0.7, 4000
                )
                if result:
                    return result
        except Exception as e:
            logger.warning(f"Vision analysis failed: {e}")

    return "❌ Видео-анализ временно недоступен (нужен Gemini или OpenAI ключ). Отправь описание видео текстом — команда оценит!"


VIDEO_ANALYSIS_PROMPT = """
Ты — эксперт по вирусному контенту в TikTok и Instagram Reels.

Проанализируй кадр из видео автора. Дай детальную оценку виральности.

ФОРМАТ ОТВЕТА:

🎯 ОБЩИЙ БАЛЛ ВИРАЛЬНОСТИ: X/100

📊 РАЗБИВКА ПО КРИТЕРИЯМ (каждый из 10):
🪝 Хук (первые 3 сек): X/10
👁 Визуал и монтаж: X/10
📖 Сценарий и подача: X/10
💬 CTA и вовлечение: X/10
📱 Формат для платформы: X/10
🔥 Трендовость: X/10
🎭 Аутентичность: X/10
📈 Потенциал шеринга: X/10
🏷 Ниша и позиционирование: X/10

💡 ТОП-3 ЧТО УЛУЧШИТЬ:
✅ ТОП-3 ЧТО ХОРОШО:
🎬 РЕКОМЕНДАЦИЯ ДЛЯ СЛЕДУЮЩЕГО ВИДЕО:
"""


# --- Handlers ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("⛔ Бот только для владельца.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 КОМАНДА — брифинг", callback_data="team_brief")],
        [InlineKeyboardButton(text="👥 КОМАНДА — скрипт", callback_data="team_script")],
        [InlineKeyboardButton(text="👥 КОМАНДА — план на неделю", callback_data="team_plan")],
        [InlineKeyboardButton(text="⚡ Быстрая оценка идеи", callback_data="quick_check")],
        [InlineKeyboardButton(text="⚡ Битва хуков", callback_data="hook_battle")],
        [InlineKeyboardButton(text="💡 Идеи для Reels", callback_data="ideas")],
        [InlineKeyboardButton(text="📅 Контент-план на неделю", callback_data="plan")],
        [InlineKeyboardButton(text="🔥 Тренды", callback_data="trends")],
        [InlineKeyboardButton(text="🎬 Написать скрипт", callback_data="script")],
        [InlineKeyboardButton(text="✍️ Написать caption", callback_data="caption")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="mystats")],
    ])

    # Team intro
    team_list = "\n".join(f"  {a.emoji} {a.name} — {a.role}" for a in AGENTS.values())

    await message.answer(
        "🎬 Content Team HQ\n\n"
        "Твоя AI контент-команда для @your_brand:\n"
        f"{team_list}\n\n"
        "👥 /team <тема> — полный брифинг команды\n"
        "👥 /team_script <тема> — командный скрипт\n"
        "👥 /team_plan — план на неделю от команды\n"
        "⚡ /check <идея> — быстрая оценка\n"
        "⚡ /hooks <тема> — битва хуков\n"
        "📹 Отправь видео — командный ревью\n\n"
        "Или выбери из меню:",
        reply_markup=kb
    )


@dp.message(Command("ideas"))
async def cmd_ideas(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    await message.answer("💡 Генерирую идеи для Reels...")
    result = await ask_gemini(REELS_IDEAS_PROMPT)
    await send_long_message(message, f"💡 **Идеи для Reels:**\n\n{result}")


@dp.message(Command("plan"))
async def cmd_plan(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    await message.answer("📅 Составляю контент-план...")
    result = await ask_gemini(CONTENT_PLAN_PROMPT)
    await send_long_message(message, f"📅 **Контент-план на неделю:**\n\n{result}")


@dp.message(Command("trends"))
async def cmd_trends(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    await message.answer("🔥 Ищу тренды...")
    result = await ask_gemini(TREND_PROMPT)
    await send_long_message(message, f"🔥 **Актуальные тренды:**\n\n{result}")


@dp.message(Command("script"))
async def cmd_script(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    topic = message.text.replace("/script", "").strip()
    if not topic:
        await message.answer("🎬 Напиши тему: `/script как я автоматизировал магазин`", parse_mode="Markdown")
        return
    await message.answer(f"🎬 Пишу скрипт на тему: {topic}...")
    result = await ask_gemini(SCRIPT_PROMPT.replace("{topic}", topic))
    await send_long_message(message, f"🎬 **Скрипт:**\n\n{result}")


@dp.message(Command("caption"))
async def cmd_caption(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    topic = message.text.replace("/caption", "").strip()
    if not topic:
        await message.answer("✍️ Напиши тему: `/caption кейс автоматизации для магазина`", parse_mode="Markdown")
        return
    await message.answer(f"✍️ Пишу caption на тему: {topic}...")
    result = await ask_gemini(CAPTION_PROMPT.replace("{topic}", topic))
    await send_long_message(message, f"✍️ **Caption варианты:**\n\n{result}")


@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    await cmd_start(message)


# --- TEAM COMMANDS ---

@dp.message(Command("team"))
async def cmd_team(message: Message):
    """Full team briefing on a topic."""
    if message.from_user.id != OWNER_ID:
        return
    topic = message.text.replace("/team", "").strip()
    if not topic:
        await message.answer("👥 Напиши тему: `/team автоматизация для цветочного бизнеса`", parse_mode="Markdown")
        return

    status_msg = await message.answer(f"👥 Команда собирается на брифинг по теме: *{topic}*\n\n⏳ Это займёт 1-2 минуты — 7 агентов работают...", parse_mode="Markdown")

    async def progress(text):
        try:
            await status_msg.edit_text(f"👥 Брифинг: *{topic}*\n\n{text}", parse_mode="Markdown")
        except Exception:
            pass

    result = await run_team_briefing(topic, ask_gemini, progress)
    await send_long_message(message, f"👥 *БРИФИНГ КОМАНДЫ: {topic}*\n\n{result}")


@dp.message(Command("team_script"))
async def cmd_team_script(message: Message):
    """Team collaborates on a script."""
    if message.from_user.id != OWNER_ID:
        return
    topic = message.text.replace("/team_script", "").strip()
    if not topic:
        await message.answer("👥 Напиши тему: `/team_script как я сэкономил клиенту 100 часов`", parse_mode="Markdown")
        return

    status_msg = await message.answer(f"👥 Команда пишет скрипт: *{topic}*\n\n⏳ 1-2 минуты...", parse_mode="Markdown")

    async def progress(text):
        try:
            await status_msg.edit_text(f"🎬 Скрипт: *{topic}*\n\n{text}", parse_mode="Markdown")
        except Exception:
            pass

    result = await run_team_script(topic, ask_gemini, progress)
    await send_long_message(message, f"🎬 *КОМАНДНЫЙ СКРИПТ: {topic}*\n\n{result}")


@dp.message(Command("team_plan"))
async def cmd_team_plan(message: Message):
    """Team creates weekly content plan."""
    if message.from_user.id != OWNER_ID:
        return

    status_msg = await message.answer("👥 Команда планирует неделю...\n\n⏳ 1-2 минуты...", parse_mode="Markdown")

    async def progress(text):
        try:
            await status_msg.edit_text(f"📅 Планирование недели\n\n{text}", parse_mode="Markdown")
        except Exception:
            pass

    result = await run_team_plan(ask_gemini, progress)
    await send_long_message(message, f"📅 *КОМАНДНЫЙ ПЛАН НА НЕДЕЛЮ*\n\n{result}")


@dp.message(Command("check"))
async def cmd_quick_check(message: Message):
    """Quick idea evaluation by 2 agents."""
    if message.from_user.id != OWNER_ID:
        return
    idea = message.text.replace("/check", "").strip()
    if not idea:
        await message.answer("⚡ Напиши идею: `/check видео про то как бот отвечает клиентам за 2 секунды`", parse_mode="Markdown")
        return

    status_msg = await message.answer(f"⚡ Быстрая оценка идеи...", parse_mode="Markdown")

    async def progress(text):
        try:
            await status_msg.edit_text(text)
        except Exception:
            pass

    result = await quick_idea_check(idea, ask_gemini, progress)
    await send_long_message(message, f"⚡ *ОЦЕНКА ИДЕИ: {idea}*\n\n{result}")


@dp.message(Command("hooks"))
async def cmd_hooks(message: Message):
    """Hook battle — Copywriter vs Scriptwriter."""
    if message.from_user.id != OWNER_ID:
        return
    topic = message.text.replace("/hooks", "").strip()
    if not topic:
        await message.answer("⚡ Напиши тему: `/hooks автоматизация рутины`", parse_mode="Markdown")
        return

    status_msg = await message.answer("⚡ Соня vs Даня — битва хуков...", parse_mode="Markdown")

    async def progress(text):
        try:
            await status_msg.edit_text(text)
        except Exception:
            pass

    result = await quick_hook_battle(topic, ask_gemini, progress)
    await send_long_message(message, f"⚡ *БИТВА ХУКОВ: {topic}*\n\n{result}")


# News items state (loaded from disk on startup)
_latest_news_items: list[dict] = _initial_state.get("latest_news_items", [])
_latest_news_date: str = _initial_state.get("latest_news_date", "")


@dp.message(Command("news"))
async def cmd_news(message: Message):
    """Fetch and show AI news right now."""
    if message.from_user.id != OWNER_ID:
        return
    status = await message.answer("Собираю AI новости из 12+ источников... 1-2 минуты")
    try:
        brief, items = await get_daily_news_brief(ask_gemini)
        global _latest_news_items, _latest_news_date
        _latest_news_items = items
        now = datetime.now(MSK)
        _latest_news_date = now.strftime("%Y%m%d")
        _save_state()

        await send_long_to_owner(brief)

        # Send buttons for each news item
        if items:
            buttons = []
            for i, item in enumerate(items[:5]):
                title_short = (item.get("ai_summary") or item["title"])[:40]
                buttons.append([InlineKeyboardButton(
                    text=f"Скрипт: {title_short}",
                    callback_data=f"news_script_{i}_{_latest_news_date}",
                )])
            kb = InlineKeyboardMarkup(inline_keyboard=buttons)
            await bot.send_message(OWNER_ID, "Сделать скрипт по новости?", reply_markup=kb)

        try:
            await status.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"/news error: {e}")
        await message.answer(f"Ошибка при сборе новостей: {e}")


@dp.callback_query(F.data.startswith("news_script_"))
async def cb_news_script(callback: CallbackQuery):
    """Generate a script based on a specific news item."""
    await callback.answer()
    parts = callback.data.split("_")
    try:
        idx = int(parts[2])
    except (IndexError, ValueError):
        await callback.message.answer("Ошибка: неверный индекс новости")
        return

    if idx >= len(_latest_news_items):
        await callback.message.answer("Новость не найдена в кэше. Используй /news заново.")
        return

    item = _latest_news_items[idx]
    title = item.get("ai_summary") or item["title"]

    status_msg = await bot.send_message(
        OWNER_ID,
        f"Команда пишет скрипт по новости:\n_{title}_\n\nЖди 2-3 мин...",
        parse_mode="Markdown",
    )

    topic = get_most_viral_news_topic([item])
    if not topic:
        topic = f"AI новость: {title}"

    async def progress(text):
        try:
            await status_msg.edit_text(text)
        except Exception:
            pass

    try:
        result = await run_team_script(topic, ask_gemini, progress)
        script_parts = result.split("\u2500" * 30)
        final = script_parts[-1].strip() if len(script_parts) > 1 else result

        now = datetime.now(MSK)
        date_key = now.strftime("%Y%m%d")
        date_str = now.strftime("%d.%m.%Y")
        day_name = WEEKDAYS_RU[now.weekday()]

        _daily_scripts[date_key] = {
            "script": final,
            "theme": f"AI новость: {title}",
            "day_name": day_name,
            "date_str": date_str,
        }
        _save_state()

        await send_long_to_owner(
            f"*СЦЕНАРИЙ ПО AI НОВОСТИ*\n"
            f"_{title}_\n\n"
            f"{final}"
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Снял", callback_data=f"shot_yes_{date_key}"),
                InlineKeyboardButton(text="Не снял", callback_data=f"shot_no_{date_key}"),
            ]
        ])
        await bot.send_message(OWNER_ID, "Снял видео по этому сценарию?", reply_markup=kb)
    except Exception as e:
        logger.error(f"News script error: {e}")
        await bot.send_message(OWNER_ID, f"Ошибка генерации скрипта: {e}")


@dp.message(Command("autopilot"))
async def cmd_autopilot(message: Message):
    """Show autopilot schedule."""
    if message.from_user.id != OWNER_ID:
        return
    now = datetime.now(MSK)
    weekday = WEEKDAYS_RU[now.weekday()]
    theme_today = DAILY_THEMES[now.weekday()]
    theme_tomorrow = DAILY_THEMES[(now.weekday() + 1) % 7]

    text = (
        "🤖 *Автопилот контент-команды*\n\n"
        "*Расписание (МСК):*\n"
        "⏰ 09:00 — готовый скрипт на сегодня (ежедневно)\n"
        "🌙 21:00 — хуки на завтра (ежедневно)\n"
        "📅 Пн 09:00 — план на неделю от всей команды\n"
        "📡 Каждые 6ч — статистика TikTok/Instagram\n\n"
        f"*Сегодня ({weekday}):*\n"
        f"Тема: _{theme_today}_\n\n"
        f"*Завтра:*\n"
        f"Тема: _{theme_tomorrow}_\n\n"
        "Тебе приходит только готовый результат.\n"
        "Команда работает сама — 7 агентов обсуждают и выдают финал."
    )
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("team_members"))
async def cmd_team_members(message: Message):
    """Show team members info."""
    if message.from_user.id != OWNER_ID:
        return
    lines = ["👥 *Твоя контент-команда:*\n"]
    for agent in AGENTS.values():
        lines.append(f"{agent.emoji} *{agent.name}* — {agent.role}")
    lines.append("\n*Команды:*")
    lines.append("/team <тема> — полный брифинг (7 агентов)")
    lines.append("/team\\_script <тема> — командный скрипт")
    lines.append("/team\\_plan — план на неделю")
    lines.append("/check <идея> — быстрая оценка (2 агента)")
    lines.append("/hooks <тема> — битва хуков (3 агента)")
    lines.append("📹 Видео — командный ревью (6 агентов)")
    await message.answer("\n".join(lines), parse_mode="Markdown")


# --- Video analysis (now with team review) ---

@dp.message(F.video | F.video_note | F.animation)
async def handle_video(message: Message):
    """Analyze video — first Gemini vision, then full team review."""
    if message.from_user.id != OWNER_ID:
        return

    await message.answer("🎬 Анализирую видео на виральность... Подожди 30-60 сек.")

    tmp_path = None
    try:
        # Get file from Telegram
        if message.video:
            file = await bot.get_file(message.video.file_id)
            ext = ".mp4"
        elif message.video_note:
            file = await bot.get_file(message.video_note.file_id)
            ext = ".mp4"
        else:
            file = await bot.get_file(message.animation.file_id)
            ext = ".mp4"

        # Download to temp file
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name

        await bot.download_file(file.file_path, tmp_path)
        logger.info(f"Video downloaded: {tmp_path} ({os.path.getsize(tmp_path)} bytes)")

        # Step 1: Gemini vision analysis
        vision_result = await analyze_video_virality(tmp_path)
        await send_long_message(message, f"🎬 *Технический анализ (Gemini):*\n\n{vision_result}")

        # Step 2: Full team review based on vision analysis
        status_msg = await message.answer("👥 Теперь команда смотрит видео и даёт фидбэк... ⏳ 1-2 мин")

        async def progress(text):
            try:
                await status_msg.edit_text(f"👥 Командный ревью\n\n{text}")
            except Exception:
                pass

        team_result = await run_team_review(vision_result, ask_gemini, progress)
        await send_long_message(message, f"👥 *КОМАНДНЫЙ РЕВЬЮ:*\n\n{team_result}")

    except Exception as e:
        logger.error(f"Video handler error: {e}")
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# --- Monitoring commands ---

@dp.message(Command("monitor"))
async def cmd_monitor(message: Message):
    """Set accounts to monitor: /monitor tiktok:username instagram:username"""
    if message.from_user.id != OWNER_ID:
        return

    args = message.text.replace("/monitor", "").strip()
    if not args:
        # Show current monitoring status
        lines = ["📡 *Мониторинг аккаунтов:*\n"]
        if MONITOR_TIKTOK:
            lines.append(f"🎵 TikTok: @{MONITOR_TIKTOK}")
        if MONITOR_INSTAGRAM:
            lines.append(f"📸 Instagram: @{MONITOR_INSTAGRAM}")
        if not MONITOR_TIKTOK and not MONITOR_INSTAGRAM:
            lines.append("Нет отслеживаемых аккаунтов.")
            lines.append("\nДобавь в `.env`:")
            lines.append("`MONITOR_TIKTOK=username`")
            lines.append("`MONITOR_INSTAGRAM=username`")
        else:
            lines.append("\nИспользуй /mystats для просмотра статистики")
        await message.answer("\n".join(lines), parse_mode="Markdown")
        return

    await message.answer("ℹ️ Для настройки мониторинга добавь в `.env`:\n"
                         "`MONITOR_TIKTOK=username`\n"
                         "`MONITOR_INSTAGRAM=username`\n"
                         "И перезапусти бот.", parse_mode="Markdown")


@dp.message(Command("links"))
async def cmd_links(message: Message):
    """Show click stats for tracked links."""
    if message.from_user.id != OWNER_ID:
        return

    try:
        stats = await asyncio.to_thread(get_all_links_stats, 15)
        if not stats:
            await message.answer("Пока нет отслеживаемых ссылок.")
            return

        lines = ["🔗 *Статистика ссылок:*\n"]
        for s in stats:
            source = s["source"] or s["code"]
            lines.append(
                f"`{source}` — {s['clicks']} кликов "
                f"(сегодня: {s['today']}, страна: {s['top_country']})"
            )

        await message.answer("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error showing link stats: {e}")
        await message.answer(f"Ошибка: {e}")


@dp.message(Command("mystats"))
async def cmd_mystats(message: Message):
    """Show stats for monitored accounts."""
    if message.from_user.id != OWNER_ID:
        return

    if not MONITOR_TIKTOK and not MONITOR_INSTAGRAM:
        await message.answer("📡 Нет отслеживаемых аккаунтов. Используй /monitor для настройки.")
        return

    await message.answer("📊 Собираю статистику... Подожди минуту.")

    lines = ["📊 *Статистика аккаунтов:*\n"]

    if MONITOR_TIKTOK:
        try:
            from platforms.tiktok import fetch_videos as fetch_tiktok
            videos = await asyncio.to_thread(fetch_tiktok, MONITOR_TIKTOK, 20)
            if videos:
                total_views = sum(v.get("views", 0) for v in videos)
                total_likes = sum(v.get("likes", 0) for v in videos)
                total_comments = sum(v.get("comments", 0) for v in videos)
                avg_views = total_views // len(videos) if videos else 0

                lines.append(f"🎵 *TikTok @{MONITOR_TIKTOK}*")
                lines.append(f"  Видео: {len(videos)}")
                lines.append(f"  Просмотры: {total_views:,}".replace(",", " "))
                lines.append(f"  Средние просмотры: {avg_views:,}".replace(",", " "))
                lines.append(f"  Лайки: {total_likes:,}".replace(",", " "))
                lines.append(f"  Комменты: {total_comments:,}".replace(",", " "))

                # Top 5 videos
                top = sorted(videos, key=lambda x: x.get("views", 0), reverse=True)[:5]
                lines.append("\n  *Топ-5 видео:*")
                for i, v in enumerate(top, 1):
                    title = (v.get("title", "") or "—")[:40]
                    views = v.get("views", 0)
                    lines.append(f"  {i}. {title}")
                    lines.append(f"     👁 {views:,} | ❤️ {v.get('likes', 0):,}".replace(",", " "))
            else:
                lines.append(f"🎵 TikTok @{MONITOR_TIKTOK}: нет данных")
        except Exception as e:
            lines.append(f"🎵 TikTok: ❌ {e}")

    if MONITOR_INSTAGRAM:
        try:
            from platforms.instagram import fetch_videos as fetch_instagram
            posts = await asyncio.to_thread(fetch_instagram, MONITOR_INSTAGRAM, 20)
            if posts:
                total_views = sum(v.get("views", 0) for v in posts)
                total_likes = sum(v.get("likes", 0) for v in posts)
                total_comments = sum(v.get("comments", 0) for v in posts)
                reels = [p for p in posts if p.get("views", 0) > 0]
                avg_views = total_views // len(reels) if reels else 0

                lines.append(f"\n📸 *Instagram @{MONITOR_INSTAGRAM}*")
                lines.append(f"  Постов: {len(posts)} (из них reels: {len(reels)})")
                lines.append(f"  Просмотры reels: {total_views:,}".replace(",", " "))
                lines.append(f"  Средние просмотры: {avg_views:,}".replace(",", " "))
                lines.append(f"  Лайки: {total_likes:,}".replace(",", " "))
                lines.append(f"  Комменты: {total_comments:,}".replace(",", " "))

                # Top 5 by engagement
                top = sorted(posts, key=lambda x: x.get("likes", 0) + x.get("comments", 0), reverse=True)[:5]
                lines.append("\n  *Топ-5 по вовлечению:*")
                for i, v in enumerate(top, 1):
                    title = (v.get("title", "") or "—")[:40]
                    lines.append(f"  {i}. {title}")
                    lines.append(f"     👁 {v.get('views', 0):,} | ❤️ {v.get('likes', 0):,} | 💬 {v.get('comments', 0):,}".replace(",", " "))
            else:
                lines.append(f"\n📸 Instagram @{MONITOR_INSTAGRAM}: нет данных")
        except Exception as e:
            lines.append(f"\n📸 Instagram: ❌ {e}")

    await send_long_message(message, "\n".join(lines))


@dp.message(Command("radar"))
async def cmd_radar(message: Message):
    """Run competitor radar scan on demand."""
    if message.from_user.id != OWNER_ID:
        return

    await message.answer("Сканирую конкурентов... Это займёт 1-3 минуты.")

    try:
        report = await asyncio.to_thread(run_competitor_radar)
        await send_long_message(message, report)
    except Exception as e:
        logger.error(f"Radar scan error: {e}")
        await message.answer(f"Ошибка сканирования: {e}")


# --- Periodic monitoring report ---

async def monitoring_report():
    """Send monitoring report every 6 hours if accounts configured."""
    await asyncio.sleep(6 * 3600)  # First report after 6h, not on startup
    while True:
        try:
            if not MONITOR_TIKTOK and not MONITOR_INSTAGRAM:
                await asyncio.sleep(6 * 3600)
                continue

            lines = [f"📡 *Автоотчёт* ({datetime.now(MSK).strftime('%d.%m %H:%M')} MSK)\n"]
            has_data = False

            if MONITOR_TIKTOK:
                try:
                    from platforms.tiktok import fetch_videos as fetch_tiktok
                    videos = await asyncio.to_thread(fetch_tiktok, MONITOR_TIKTOK, 10)
                    if videos:
                        has_data = True
                        total_views = sum(v.get("views", 0) for v in videos)
                        total_likes = sum(v.get("likes", 0) for v in videos)
                        lines.append(f"🎵 TikTok @{MONITOR_TIKTOK}")
                        lines.append(f"  {len(videos)} видео | 👁 {total_views:,} | ❤️ {total_likes:,}".replace(",", " "))

                        # Newest video stats
                        newest = max(videos, key=lambda x: x.get("posted_at", "") or "")
                        if newest:
                            lines.append(f"  Последнее: {(newest.get('title', '') or '—')[:50]}")
                            lines.append(f"  👁 {newest.get('views', 0):,} | ❤️ {newest.get('likes', 0):,}".replace(",", " "))
                except Exception as e:
                    lines.append(f"🎵 TikTok: ❌ {e}")

            if MONITOR_INSTAGRAM:
                try:
                    from platforms.instagram import fetch_videos as fetch_instagram
                    posts = await asyncio.to_thread(fetch_instagram, MONITOR_INSTAGRAM, 10)
                    if posts:
                        has_data = True
                        total_likes = sum(v.get("likes", 0) for v in posts)
                        total_views = sum(v.get("views", 0) for v in posts)
                        lines.append(f"\n📸 Instagram @{MONITOR_INSTAGRAM}")
                        lines.append(f"  {len(posts)} постов | 👁 {total_views:,} | ❤️ {total_likes:,}".replace(",", " "))

                        newest = max(posts, key=lambda x: x.get("posted_at", "") or "")
                        if newest:
                            lines.append(f"  Последний: {(newest.get('title', '') or '—')[:50]}")
                            lines.append(f"  👁 {newest.get('views', 0):,} | ❤️ {newest.get('likes', 0):,}".replace(",", " "))
                except Exception as e:
                    lines.append(f"\n📸 Instagram: ❌ {e}")

            if has_data:
                text = "\n".join(lines)
                text = text.replace("*", "")  # Safe for Telegram
                try:
                    await bot.send_message(OWNER_ID, text)
                except Exception as e:
                    logger.error(f"Failed to send monitoring report: {e}")

            logger.info("Monitoring report sent")

        except Exception as e:
            logger.error(f"Monitoring report error: {e}")

        await asyncio.sleep(6 * 3600)


# --- Callbacks ---

_waiting_topic: dict[int, str] = {}


@dp.callback_query(F.data == "team_brief")
async def cb_team_brief(callback: CallbackQuery):
    await callback.answer()
    _waiting_topic[callback.from_user.id] = "team_brief"
    await callback.message.answer("👥 На какую тему провести брифинг команды? Напиши:")


@dp.callback_query(F.data == "team_script")
async def cb_team_script(callback: CallbackQuery):
    await callback.answer()
    _waiting_topic[callback.from_user.id] = "team_script"
    await callback.message.answer("🎬 На какую тему команда напишет скрипт? Напиши:")


@dp.callback_query(F.data == "team_plan")
async def cb_team_plan(callback: CallbackQuery):
    await callback.answer()
    status_msg = await callback.message.answer("👥 Команда планирует неделю... ⏳ 1-2 мин")

    async def progress(text):
        try:
            await status_msg.edit_text(f"📅 Планирование недели\n\n{text}")
        except Exception:
            pass

    result = await run_team_plan(ask_gemini, progress)
    await send_long_message(callback.message, f"📅 *КОМАНДНЫЙ ПЛАН НА НЕДЕЛЮ*\n\n{result}")


@dp.callback_query(F.data == "quick_check")
async def cb_quick_check(callback: CallbackQuery):
    await callback.answer()
    _waiting_topic[callback.from_user.id] = "quick_check"
    await callback.message.answer("⚡ Напиши идею для быстрой оценки:")


@dp.callback_query(F.data == "hook_battle")
async def cb_hook_battle(callback: CallbackQuery):
    await callback.answer()
    _waiting_topic[callback.from_user.id] = "hook_battle"
    await callback.message.answer("⚡ На какую тему битва хуков? Напиши:")


@dp.callback_query(F.data == "ideas")
async def cb_ideas(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("💡 Генерирую идеи для Reels...")
    result = await ask_gemini(REELS_IDEAS_PROMPT)
    await send_long_message(callback.message, f"💡 **Идеи для Reels:**\n\n{result}")


@dp.callback_query(F.data == "plan")
async def cb_plan(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("📅 Составляю контент-план...")
    result = await ask_gemini(CONTENT_PLAN_PROMPT)
    await send_long_message(callback.message, f"📅 **Контент-план на неделю:**\n\n{result}")


@dp.callback_query(F.data == "trends")
async def cb_trends(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("🔥 Ищу тренды...")
    result = await ask_gemini(TREND_PROMPT)
    await send_long_message(callback.message, f"🔥 **Актуальные тренды:**\n\n{result}")


@dp.callback_query(F.data == "script")
async def cb_script(callback: CallbackQuery):
    await callback.answer()
    _waiting_topic[callback.from_user.id] = "script"
    await callback.message.answer("🎬 На какую тему скрипт? Напиши:")


@dp.callback_query(F.data == "caption")
async def cb_caption(callback: CallbackQuery):
    await callback.answer()
    _waiting_topic[callback.from_user.id] = "caption"
    await callback.message.answer("✍️ На какую тему caption? Напиши:")


@dp.callback_query(F.data == "mystats")
async def cb_mystats(callback: CallbackQuery):
    await callback.answer()
    if not MONITOR_TIKTOK and not MONITOR_INSTAGRAM:
        await callback.message.answer("📡 Нет отслеживаемых аккаунтов. Настрой через /monitor")
        return
    await callback.message.answer("📊 Собираю статистику... Подожди минуту.")

    lines = ["📊 Статистика аккаунтов:\n"]

    if MONITOR_TIKTOK:
        try:
            from platforms.tiktok import fetch_videos as fetch_tiktok
            videos = await asyncio.to_thread(fetch_tiktok, MONITOR_TIKTOK, 20)
            if videos:
                total_views = sum(v.get("views", 0) for v in videos)
                total_likes = sum(v.get("likes", 0) for v in videos)
                avg_views = total_views // len(videos) if videos else 0
                lines.append(f"🎵 TikTok @{MONITOR_TIKTOK}")
                lines.append(f"  Видео: {len(videos)} | Просмотры: {total_views:,} | Средние: {avg_views:,} | Лайки: {total_likes:,}".replace(",", " "))
                top = sorted(videos, key=lambda x: x.get("views", 0), reverse=True)[:3]
                for i, v in enumerate(top, 1):
                    lines.append(f"  {i}. {(v.get('title','') or '—')[:40]} — 👁 {v.get('views',0):,}".replace(",", " "))
            else:
                lines.append(f"🎵 TikTok @{MONITOR_TIKTOK}: нет данных")
        except Exception as e:
            lines.append(f"🎵 TikTok: ❌ {e}")

    if MONITOR_INSTAGRAM:
        try:
            from platforms.instagram import fetch_videos as fetch_instagram
            posts = await asyncio.to_thread(fetch_instagram, MONITOR_INSTAGRAM, 20)
            if posts:
                total_likes = sum(v.get("likes", 0) for v in posts)
                total_views = sum(v.get("views", 0) for v in posts)
                lines.append(f"\n📸 Instagram @{MONITOR_INSTAGRAM}")
                lines.append(f"  Постов: {len(posts)} | Просмотры: {total_views:,} | Лайки: {total_likes:,}".replace(",", " "))
                top = sorted(posts, key=lambda x: x.get("likes",0)+x.get("comments",0), reverse=True)[:3]
                for i, v in enumerate(top, 1):
                    lines.append(f"  {i}. {(v.get('title','') or '—')[:40]} — ❤️ {v.get('likes',0):,}".replace(",", " "))
            else:
                lines.append(f"\n📸 Instagram @{MONITOR_INSTAGRAM}: нет данных")
        except Exception as e:
            lines.append(f"\n📸 Instagram: ❌ {e}")

    await send_long_message(callback.message, "\n".join(lines))


# --- Free text ---

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message):
    if message.from_user.id != OWNER_ID:
        return

    # Check if waiting for topic
    waiting = _waiting_topic.pop(message.from_user.id, None)

    if waiting == "team_brief":
        status_msg = await message.answer(f"👥 Команда собирается на брифинг: *{message.text}*\n\n⏳ 1-2 мин...", parse_mode="Markdown")
        async def progress(text):
            try: await status_msg.edit_text(f"👥 Брифинг\n\n{text}")
            except: pass
        result = await run_team_briefing(message.text, ask_gemini, progress)
        await send_long_message(message, f"👥 *БРИФИНГ: {message.text}*\n\n{result}")
        return

    elif waiting == "team_script":
        status_msg = await message.answer(f"🎬 Команда пишет скрипт: *{message.text}*\n\n⏳ 1-2 мин...", parse_mode="Markdown")
        async def progress(text):
            try: await status_msg.edit_text(f"🎬 Скрипт\n\n{text}")
            except: pass
        result = await run_team_script(message.text, ask_gemini, progress)
        await send_long_message(message, f"🎬 *КОМАНДНЫЙ СКРИПТ: {message.text}*\n\n{result}")
        return

    elif waiting == "quick_check":
        status_msg = await message.answer("⚡ Быстрая оценка...")
        async def progress(text):
            try: await status_msg.edit_text(text)
            except: pass
        result = await quick_idea_check(message.text, ask_gemini, progress)
        await send_long_message(message, f"⚡ *ОЦЕНКА: {message.text}*\n\n{result}")
        return

    elif waiting == "hook_battle":
        status_msg = await message.answer("⚡ Битва хуков...")
        async def progress(text):
            try: await status_msg.edit_text(text)
            except: pass
        result = await quick_hook_battle(message.text, ask_gemini, progress)
        await send_long_message(message, f"⚡ *ХУКИ: {message.text}*\n\n{result}")
        return

    elif waiting == "script":
        await message.answer(f"🎬 Пишу скрипт...")
        result = await ask_gemini(SCRIPT_PROMPT.replace("{topic}", message.text))
        await send_long_message(message, f"🎬 **Скрипт:**\n\n{result}")
        return
    elif waiting == "caption":
        await message.answer(f"✍️ Пишу caption...")
        result = await ask_gemini(CAPTION_PROMPT.replace("{topic}", message.text))
        await send_long_message(message, f"✍️ **Caption:**\n\n{result}")
        return

    # Free question to AI
    prompt = PROFILE_CONTEXT + f"\nВопрос от пользователя: {message.text}\n\nОтветь как контент-менеджер, помоги с этим запросом."
    await message.answer("🤔 Думаю...")
    result = await ask_gemini(prompt)
    await send_long_message(message, result)


# --- Helpers ---

async def send_long_message(message: Message, text: str):
    """Send message, splitting if too long for Telegram (4096 chars)."""
    # Strip markdown that Telegram can't handle
    import re
    text = text.replace("**", "*")
    # Fix unclosed markdown entities
    # Count asterisks — if odd, strip all
    if text.count("*") % 2 != 0:
        text = text.replace("*", "")
    # Same for backticks
    if text.count("`") % 2 != 0:
        text = text.replace("`", "")

    if len(text) <= 4000:
        try:
            await message.answer(text, parse_mode="Markdown")
        except Exception:
            # Fallback — send without any formatting
            await message.answer(text.replace("*", "").replace("`", "").replace("_", ""))
        return

    # Split by paragraphs
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > 3900:
            chunks.append(current)
            current = line
        else:
            current += "\n" + line if current else line
    if current:
        chunks.append(current)

    for chunk in chunks:
        try:
            await message.answer(chunk.strip(), parse_mode="Markdown")
        except Exception:
            await message.answer(chunk.strip().replace("*", "").replace("`", "").replace("_", ""))
        await asyncio.sleep(0.3)


# --- AUTOPILOT: Team works on its own, sends ready results ---

# Days of the week in Russian
WEEKDAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

# 4 дня = автоматизация/кейсы (основа бренда, продажа услуг)
# 3 дня = AI новости/нейросети (экспертность, показать что шаришь)
# Пн=кейс, Вт=нейросети, Ср=боль, Чт=нейросети, Пт=демо, Сб=нейросети, Вс=лайфстайл
DAILY_THEMES = [
    "КЕЙС: конкретный клиент — что было ДО, что сделал, результат с цифрами. Продающий контент",
    "НЕЙРОСЕТИ: свежая новость из мира AI — что вышло, почему важно, как изменит бизнес. Простым языком как практик",
    "БОЛЬ: проблема предпринимателя — рутина, потеря денег/времени. Как автоматизация решает. Продающий",
    "НЕЙРОСЕТИ: обзор нового AI-инструмента. Покажи как ты используешь в реальной работе. Практика не теория",
    "ДЕМО: живой показ автоматизации — скринкаст n8n/бота/Claude. До/после. Продающий",
    "НЕЙРОСЕТИ: тренд или прорыв в AI за неделю. Что значит для бизнеса. Мнение практикующего эксперта",
    "ЛАЙФСТАЙЛ: закулисье, процесс, заработок, что автоматизировал. Личный бренд",
]

# Дни с рубрикой AI новости (ср=2, сб=5)
AI_NEWS_DAYS = {2, 5}


async def send_long_to_owner(text: str):
    """Send long text to owner, splitting if needed. Strips broken markdown."""
    text = text.replace("**", "*")
    if text.count("*") % 2 != 0:
        text = text.replace("*", "")
    if text.count("`") % 2 != 0:
        text = text.replace("`", "")

    if len(text) <= 4000:
        try:
            await bot.send_message(OWNER_ID, text, parse_mode="Markdown")
        except Exception:
            await bot.send_message(OWNER_ID, text.replace("*", "").replace("`", "").replace("_", ""))
        return

    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > 3900:
            chunks.append(current)
            current = line
        else:
            current += "\n" + line if current else line
    if current:
        chunks.append(current)

    for chunk in chunks:
        try:
            await bot.send_message(OWNER_ID, chunk.strip(), parse_mode="Markdown")
        except Exception:
            await bot.send_message(OWNER_ID, chunk.strip().replace("*", "").replace("`", "").replace("_", ""))
        await asyncio.sleep(0.5)


async def _wait_until(hour: int, minute: int = 0, weekday: int = None):
    """Sleep until next occurrence of HH:MM MSK (optionally specific weekday 0=Mon)."""
    while True:
        now = datetime.now(MSK)
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if weekday is not None:
            days_ahead = (weekday - now.weekday()) % 7
            if days_ahead == 0 and now >= target:
                days_ahead = 7
            target += timedelta(days=days_ahead)
        else:
            if now >= target:
                target += timedelta(days=1)

        wait = (target - now).total_seconds()
        logger.info(f"Autopilot: next run at {target.strftime('%Y-%m-%d %H:%M')} MSK (in {wait/3600:.1f}h)")
        await asyncio.sleep(wait)
        return


async def autopilot_daily_script():
    """Every day at 9:00 MSK — team creates today's script and sends it ready."""
    await asyncio.sleep(30)  # Let bot start up
    while True:
        await _wait_until(hour=9, minute=0)

        try:
            now = datetime.now(MSK)
            weekday = now.weekday()  # 0=Mon
            day_name = WEEKDAYS_RU[weekday]
            theme = DAILY_THEMES[weekday]
            date_str = now.strftime("%d.%m.%Y")

            logger.info(f"Autopilot: daily script for {day_name} ({date_str})")

            # Notify start
            await bot.send_message(
                OWNER_ID,
                f"🤖 *Автопилот запущен*\n\n"
                f"Сегодня {day_name}, {date_str}\n"
                f"Команда готовит скрипт на тему:\n_{theme}_\n\n"
                f"⏳ 2-3 минуты...",
                parse_mode="Markdown"
            )

            # For AI news days (Wed, Sat) — override theme with fresh AI news
            topic = None
            if weekday in AI_NEWS_DAYS:
                try:
                    _brief, _news_items = await get_daily_news_brief(ask_gemini)
                    if _news_items:
                        global _latest_news_items, _latest_news_date
                        _latest_news_items = _news_items
                        _latest_news_date = now.strftime("%Y%m%d")
                        _save_state()

                        news_topic = get_most_viral_news_topic(_news_items)
                        if news_topic:
                            theme = "AI НОВОСТИ ДНЯ (рубрика нейросети)"
                            topic = (
                                f"Сегодня {day_name}, {date_str}. "
                                f"РУБРИКА: AI НОВОСТИ. "
                                f"{news_topic} "
                                f"Сделай скрипт который автор может снять ПРЯМО СЕЙЧАС — "
                                f"готовый текст для камеры, визуал, caption, хештеги."
                            )
                except Exception as e:
                    logger.warning(f"AI news fetch for autopilot failed: {e}")

            # Fallback to regular theme
            if not topic:
                topic = (
                    f"Сегодня {day_name}, {date_str}. "
                    f"Тема дня: {theme}. "
                    f"Сделай скрипт который автор может снять ПРЯМО СЕЙЧАС — "
                    f"готовый текст для камеры, визуал, caption, хештеги."
                )

            result = await run_team_script(topic, ask_gemini)

            # Extract ONLY the Production Manager's final script
            parts = result.split("─" * 30)
            final_part = parts[-1].strip() if len(parts) > 1 else result

            # Send ONLY the ready-to-shoot script — no discussion
            await send_long_to_owner(
                f"🎬 *СЦЕНАРИЙ НА СЕГОДНЯ*\n"
                f"_{day_name}, {date_str}_\n\n"
                f"{final_part}"
            )

            # Store script in memory for tracking
            date_key = now.strftime("%Y%m%d")
            _daily_scripts[date_key] = {
                "script": final_part,
                "theme": theme,
                "day_name": day_name,
                "date_str": date_str,
            }
            _save_state()

            # Send tracking buttons
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Снял", callback_data=f"shot_yes_{date_key}"),
                    InlineKeyboardButton(text="❌ Не снял", callback_data=f"shot_no_{date_key}"),
                ]
            ])
            await bot.send_message(
                OWNER_ID,
                "Снял видео по этому сценарию?",
                reply_markup=kb,
            )

            logger.info("Autopilot: daily script sent!")

        except Exception as e:
            logger.error(f"Autopilot daily script error: {e}")
            # Instead of sending error, try to suggest a random idea from the bank
            try:
                bank_ideas = await asyncio.to_thread(get_ideas_from_bank, 0, "не снято")
                if bank_ideas:
                    idea = random.choice(bank_ideas)
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="Снять эту",
                            callback_data=f"bank_shoot_{idea['row']}"
                        )]
                    ])
                    await bot.send_message(
                        OWNER_ID,
                        f"AI не смог сгенерить новый скрипт. Вот идея из банка:\n\n"
                        f"Тема: {idea['theme']}\n"
                        f"Хук: {idea['hook']}\n"
                        f"Формат: {idea['format']}",
                        reply_markup=kb,
                    )
                else:
                    await bot.send_message(OWNER_ID, f"Автопилот (скрипт): ошибка, банк пуст — {e}")
            except Exception:
                try:
                    await bot.send_message(OWNER_ID, f"Автопилот (скрипт): ошибка — {e}")
                except Exception:
                    pass

        await asyncio.sleep(120)  # Prevent double-fire


async def autopilot_weekly_plan():
    """Every Monday at 9:15 MSK — team creates weekly plan (after daily script at 9:00)."""
    await asyncio.sleep(60)  # Let bot start up
    while True:
        await _wait_until(hour=9, minute=15, weekday=0)  # Monday 9:15 (daily script at 9:00)

        try:
            date_str = datetime.now(MSK).strftime("%d.%m.%Y")
            logger.info(f"Autopilot: weekly plan for {date_str}")

            await bot.send_message(
                OWNER_ID,
                f"🤖 *Автопилот: еженедельное планирование*\n\n"
                f"Команда составляет план на неделю {date_str}\n"
                f"⏳ 3-4 минуты...",
                parse_mode="Markdown"
            )

            result = await run_team_plan(ask_gemini)

            parts = result.split("─" * 30)
            final_part = parts[-1].strip() if len(parts) > 1 else result

            await send_long_to_owner(
                f"📅 *ПЛАН НА НЕДЕЛЮ ({date_str})*\n\n"
                f"{final_part}"
            )

            logger.info("Autopilot: weekly plan sent!")

        except Exception as e:
            logger.error(f"Autopilot weekly plan error: {e}")
            try:
                await bot.send_message(OWNER_ID, f"❌ Автопилот (план): ошибка — {e}")
            except Exception:
                pass

        await asyncio.sleep(120)


async def autopilot_evening_hooks():
    """Every day at 21:00 MSK — prepare hooks for tomorrow."""
    await asyncio.sleep(90)
    while True:
        await _wait_until(hour=21, minute=0)

        try:
            now = datetime.now(MSK)
            tomorrow = now + timedelta(days=1)
            tomorrow_weekday = tomorrow.weekday()
            tomorrow_name = WEEKDAYS_RU[tomorrow_weekday]
            tomorrow_theme = DAILY_THEMES[tomorrow_weekday]

            logger.info(f"Autopilot: evening hooks for tomorrow ({tomorrow_name})")

            result = await quick_hook_battle(
                f"Тема на завтра ({tomorrow_name}): {tomorrow_theme}",
                ask_gemini
            )

            await send_long_to_owner(
                f"🌙 *ХУКИ НА ЗАВТРА ({tomorrow_name})*\n\n"
                f"Тема: _{tomorrow_theme}_\n\n"
                f"{result}\n\n"
                f"Утром в 9:00 придёт полный скрипт."
            )

            logger.info("Autopilot: evening hooks sent!")

        except Exception as e:
            logger.error(f"Autopilot evening hooks error: {e}")

        await asyncio.sleep(120)


# --- Channel Post Helper ---

TG_CHANNEL_STYLE = """
Напиши пост для TG канала личного бренда (AI-автоматизация).

СТИЛЬ КАНАЛА (строго!):
- Пишешь живым разговорным тоном практика, который шарит. Не инфобизнесмен. Не ChatGPT.
- Как другу в чат: "короч", "прикинь", "ну типа"
- Короткие абзацы, 1-2 строки каждый
- Без эмодзи (максимум 1-2 если к месту)
- Без списков через тире/буллеты
- Без "Друзья!" / "Привет!" / "Хотите узнать?"
- Без канцелярита и AI-штампов
- Цифры, факты, результат
- Хук в первой строке — зацепить за 2 секунды
- 3-5 абзацев максимум, ~100-150 слов

ФОРМУЛА: Хук → История/Факт → Суть → Панч

ПРИМЕР ХОРОШЕГО ПОСТА:
"собрал бота за вечер который отвечает клиентам 24/7

у чувака был магазин, 3 менеджера сидели в директе. отвечали по 2-3 часа на каждое сообщение. половина клиентов уходила

поставил ему бота. бот отвечает за 2 секунды, квалифицирует лида, кидает ссылку на оплату. менеджеры больше не нужны

экономия — 150к/мес на зарплатах. бот стоил 40к один раз

чек-лист процессов для автоматизации — в шапке профиля"
"""


async def _generate_channel_post(theme: str) -> str:
    """Generate a TG channel post in the brand voice about today's video topic."""
    prompt = TG_CHANNEL_STYLE + f"\n\nТема сегодняшнего видео: {theme}\n\nНапиши пост-анонс для канала. Не пересказывай видео — расскажи историю/кейс по теме. В конце — 'полное видео в профиле'"
    try:
        result = await asyncio.to_thread(call_ai, prompt, 0.9, 1000)
        return result if result else None
    except Exception as e:
        logger.error(f"Channel post generation error: {e}")
        return None


# --- Content Tracking Callbacks ---

@dp.callback_query(F.data.startswith("shot_yes_"))
async def cb_shot_yes(callback: CallbackQuery):
    """User confirmed they shot the video — save to Google Sheet."""
    await callback.answer("Сохраняю...")

    date_key = callback.data.replace("shot_yes_", "")
    script_data = _daily_scripts.get(date_key)

    if not script_data:
        await callback.message.answer(
            "Сценарий не найден в памяти (возможно, бот перезапускался). "
            "Но записал дату — аналитика подтянется автоматически."
        )
        # Still save a minimal record
        try:
            date_str = f"{date_key[6:8]}.{date_key[4:6]}.{date_key[:4]}"
            now = datetime.now(MSK)
            day_name = WEEKDAYS_RU[now.weekday()]
            await asyncio.to_thread(
                save_scenario, date_str, day_name, "тема не сохранена", "(сценарий не сохранён в памяти)"
            )
        except Exception as e:
            logger.error(f"Error saving minimal scenario: {e}")
        return

    try:
        row = await asyncio.to_thread(
            save_scenario,
            script_data["date_str"],
            script_data["day_name"],
            script_data["theme"],
            script_data["script"],
        )
        sheet_url = get_sheet_url()

        # Create tracked link for this scenario
        link_info = None
        try:
            source_id = f"reels_{date_key}"
            link_info = await asyncio.to_thread(
                create_tracked_link,
                TG_CHANNEL_URL,
                source_id,
            )
            if link_info and row > 0:
                await asyncio.to_thread(update_scenario_link, row, link_info["url"])
        except Exception as e:
            logger.warning(f"Link tracker error: {e}")

        link_msg = f"\n🔗 Ссылка для CTA: `{link_info['url']}`" if link_info else ""
        await callback.message.answer(
            f"✅ Записал! Скоро подтяну аналитику с инсты.\n\n"
            f"📊 Таблица: {sheet_url}{link_msg}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error saving scenario to sheet: {e}")
        await callback.message.answer(f"Ошибка записи в таблицу: {e}")

    # Generate TG channel post suggestion (don't auto-post — channel has its own style)
    try:
        tg_post = await _generate_channel_post(script_data["theme"])
        if tg_post:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Отправить в канал", callback_data=f"post_channel_{date_key}")],
                [InlineKeyboardButton(text="✏️ Не надо", callback_data=f"post_skip_{date_key}")],
            ])
            _daily_scripts[f"tg_post_{date_key}"] = tg_post
            await callback.message.answer(
                f"💬 Пост для {TG_CHANNEL}:\n\n{tg_post}",
                reply_markup=kb
            )
    except Exception as e:
        logger.warning(f"Channel post generation failed: {e}")

    # Remove from memory
    _daily_scripts.pop(date_key, None)
    _save_state()


@dp.callback_query(F.data.startswith("shot_no_"))
async def cb_shot_no(callback: CallbackQuery):
    """User didn't shoot the video — save idea to bank."""
    await callback.answer()
    date_key = callback.data.replace("shot_no_", "")
    script_data = _daily_scripts.pop(date_key, None)
    _daily_scripts.pop(f"tg_post_{date_key}", None)
    _save_state()

    if script_data:
        try:
            hook = extract_hook_from_script(script_data.get("script", ""))
            fmt = extract_format_from_script(script_data.get("script", ""))
            await asyncio.to_thread(
                save_to_idea_bank,
                script_data.get("date_str", ""),
                script_data.get("theme", ""),
                hook,
                fmt,
            )
            await callback.message.answer(
                "Сохранил идею в банк. Можешь вернуться к ней через /bank"
            )
        except Exception as e:
            logger.error(f"Error saving to idea bank: {e}")
            await callback.message.answer("Ок, идея остаётся на потом. Завтра новая!")
    else:
        await callback.message.answer("Ок, идея остаётся на потом. Завтра новая!")


@dp.message(Command("bank"))
async def cmd_bank(message: Message):
    """Show last 5 unsaved ideas from the idea bank."""
    if message.from_user.id != OWNER_ID:
        return

    try:
        ideas = await asyncio.to_thread(get_ideas_from_bank, 5, "не снято")
    except Exception as e:
        await message.answer(f"Ошибка чтения банка: {e}")
        return

    if not ideas:
        await message.answer("Банк идей пуст. Все идеи сняты или ещё не накопились.")
        return

    for idea in ideas:
        text = (
            f"#{idea['num']} ({idea['date']})\n"
            f"Тема: {idea['theme']}\n"
            f"Хук: {idea['hook']}\n"
            f"Формат: {idea['format']}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="Снять эту",
                callback_data=f"bank_shoot_{idea['row']}"
            )]
        ])
        await message.answer(text, reply_markup=kb)
        await asyncio.sleep(0.3)


@dp.callback_query(F.data.startswith("bank_shoot_"))
async def cb_bank_shoot(callback: CallbackQuery):
    """User wants to shoot an idea from the bank."""
    await callback.answer("Готовлю сценарий...")
    row_str = callback.data.replace("bank_shoot_", "")

    try:
        row = int(row_str)
    except ValueError:
        await callback.message.answer("Некорректный ID идеи")
        return

    # Get the idea details
    try:
        ideas = await asyncio.to_thread(get_ideas_from_bank, 0, "не снято")
        idea = None
        for i in ideas:
            if i["row"] == row:
                idea = i
                break
    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}")
        return

    if not idea:
        await callback.message.answer("Идея не найдена или уже снята")
        return

    # Generate a full script from the idea theme (same flow as shot_yes)
    now = datetime.now(MSK)
    date_key = now.strftime("%Y%m%d")
    date_str = now.strftime("%d.%m.%Y")
    day_name = WEEKDAYS_RU[now.weekday()]

    topic = (
        f"Тема: {idea['theme']}. Хук: {idea['hook']}. Формат: {idea['format']}. "
        f"Сделай готовый скрипт для камеры."
    )

    try:
        result = await run_team_script(topic, ask_gemini)
        parts = result.split("\u2500" * 30)
        final_part = parts[-1].strip() if len(parts) > 1 else result

        await send_long_to_owner(
            f"*СЦЕНАРИЙ ИЗ БАНКА ИДЕЙ*\n"
            f"_{idea['theme']}_\n\n"
            f"{final_part}"
        )

        # Store in daily scripts for tracking
        _daily_scripts[date_key] = {
            "script": final_part,
            "theme": idea["theme"],
            "day_name": day_name,
            "date_str": date_str,
            "bank_row": row,
        }

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Снял", callback_data=f"bankshot_yes_{date_key}_{row}"),
                InlineKeyboardButton(text="Не снял", callback_data=f"bankshot_no_{date_key}"),
            ]
        ])
        await bot.send_message(OWNER_ID, "Снял видео?", reply_markup=kb)

    except Exception as e:
        logger.error(f"Error generating script from bank: {e}")
        await callback.message.answer(f"Ошибка генерации: {e}")


@dp.callback_query(F.data.startswith("bankshot_yes_"))
async def cb_bankshot_yes(callback: CallbackQuery):
    """User shot a video from bank idea."""
    await callback.answer("Сохраняю...")
    parts = callback.data.replace("bankshot_yes_", "").split("_")
    date_key = parts[0]
    bank_row = int(parts[1]) if len(parts) > 1 else 0

    script_data = _daily_scripts.pop(date_key, None)

    if script_data:
        try:
            row = await asyncio.to_thread(
                save_scenario,
                script_data["date_str"],
                script_data["day_name"],
                script_data["theme"],
                script_data["script"],
            )
            if bank_row:
                await asyncio.to_thread(update_idea_bank_status, bank_row, "снято позже")
            sheet_url = get_sheet_url()
            await callback.message.answer(
                f"Записал! Идея из банка отмечена как снятая.\n"
                f"Таблица: {sheet_url}"
            )
        except Exception as e:
            logger.error(f"Error saving bank scenario: {e}")
            await callback.message.answer(f"Ошибка: {e}")
    else:
        await callback.message.answer("Сценарий не найден в памяти (бот мог перезапуститься)")


@dp.callback_query(F.data.startswith("bankshot_no_"))
async def cb_bankshot_no(callback: CallbackQuery):
    """User didn't shoot the bank idea."""
    await callback.answer()
    date_key = callback.data.replace("bankshot_no_", "")
    _daily_scripts.pop(date_key, None)
    await callback.message.answer("Ок, идея остаётся в банке.")


@dp.callback_query(F.data.startswith("post_channel_"))
async def cb_post_channel(callback: CallbackQuery):
    """Send generated post to TG channel."""
    await callback.answer("Отправляю...")
    date_key = callback.data.replace("post_channel_", "")
    post_text = _daily_scripts.pop(f"tg_post_{date_key}", None)

    if not post_text:
        await callback.message.answer("Пост не найден в памяти")
        return

    try:
        await bot.send_message(TG_CHANNEL, post_text)
        await callback.message.answer(f"📢 Отправлено в {TG_CHANNEL}")
    except Exception as e:
        # The bot must be an admin of the channel to post there.
        await callback.message.answer(
            f"Не удалось отправить в {TG_CHANNEL}: {e}\n"
            f"Убедись, что бот добавлен админом канала."
        )


@dp.callback_query(F.data.startswith("post_skip_"))
async def cb_post_skip(callback: CallbackQuery):
    """Skip channel post."""
    await callback.answer()
    date_key = callback.data.replace("post_skip_", "")
    _daily_scripts.pop(f"tg_post_{date_key}", None)
    await callback.message.answer("Ок, без поста в канал")


# --- Instagram Analytics Background Task ---

async def content_analytics_task():
    """Every 6 hours: fetch Instagram posts and update scenario analytics."""
    await asyncio.sleep(600)  # Wait 10 min after startup
    ig_username = MONITOR_INSTAGRAM

    while True:
        try:
            if not ig_username:
                await asyncio.sleep(6 * 3600)
                continue

            logger.info("Content analytics: checking scenarios needing updates...")

            scenarios = await asyncio.to_thread(get_scenarios_needing_analytics)
            if not scenarios:
                logger.info("Content analytics: no scenarios need updates")
                await asyncio.sleep(6 * 3600)
                continue

            # Fetch Instagram posts once
            posts = await asyncio.to_thread(fetch_recent_posts, ig_username, 30)
            if not posts:
                logger.warning("Content analytics: no Instagram posts fetched")
                await asyncio.sleep(6 * 3600)
                continue

            updated = 0
            for scenario in scenarios:
                try:
                    matched = match_post_to_scenario(posts, scenario["scenario_date"])
                    if not matched:
                        continue

                    views = matched.get("views", 0)
                    likes = matched.get("likes", 0)
                    comments = matched.get("comments", 0)
                    virality = calculate_virality(views, likes, comments)

                    update_kwargs = {
                        "row_number": scenario["row"],
                        "instagram_url": matched.get("url", ""),
                        "views": views,
                        "likes": likes,
                        "comments": comments,
                        "virality": virality,
                    }

                    # Set time-based view snapshots
                    days = scenario["days_since"]
                    if scenario["needs_24h"] and days >= 1:
                        update_kwargs["views_24h"] = views
                    if scenario["needs_48h"] and days >= 2:
                        update_kwargs["views_48h"] = views
                    if scenario["needs_7d"] and days >= 7:
                        update_kwargs["views_7d"] = views

                    await asyncio.to_thread(update_scenario_analytics, **update_kwargs)
                    updated += 1

                except Exception as e:
                    logger.error(f"Error updating scenario row {scenario['row']}: {e}")

            # Update Аналитика summary sheet
            try:
                analytics = await asyncio.to_thread(collect_analytics, ig_username)
                if analytics.get("posts"):
                    await asyncio.to_thread(
                        update_analytics_sheet,
                        total_videos=analytics["total_videos"],
                        best_video=analytics.get("best_caption", "")[:100],
                        best_views=analytics.get("best_views", 0),
                    )
            except Exception as e:
                logger.error(f"Error updating analytics sheet: {e}")

            logger.info(f"Content analytics: updated {updated}/{len(scenarios)} scenarios")

            # Update click counts in sheet from link tracker
            try:
                scenario_sources = await asyncio.to_thread(get_all_scenario_sources)
                click_updated = 0
                for ss in scenario_sources:
                    clicks = await asyncio.to_thread(get_clicks_for_source, ss["source"])
                    if clicks > 0:
                        await asyncio.to_thread(update_scenario_clicks, ss["row"], clicks)
                        click_updated += 1
                if click_updated:
                    logger.info(f"Link tracker: updated clicks for {click_updated} scenarios")
            except Exception as e:
                logger.warning(f"Click update error: {e}")

        except Exception as e:
            logger.error(f"Content analytics task error: {e}")

        await asyncio.sleep(6 * 3600)


async def tg_channel_analytics_task():
    """Every 24h: collect TG channel analytics via Telethon (account 3) and save to sheet."""
    await asyncio.sleep(900)  # Wait 15 min after startup
    prev_subscribers = 0

    while True:
        try:
            logger.info("TG channel analytics: collecting via Telethon...")

            stats = await asyncio.to_thread(_fetch_tg_channel_stats)

            if stats:
                sub_growth = stats["subscribers"] - prev_subscribers if prev_subscribers > 0 else 0
                prev_subscribers = stats["subscribers"]

                from content_sheets import update_tg_channel_analytics
                await asyncio.to_thread(
                    update_tg_channel_analytics,
                    subscribers=stats["subscribers"],
                    total_posts=stats["total_posts"],
                    avg_views=stats["avg_views"],
                    best_post=stats["best_post"],
                    best_views=stats["best_views"],
                    sub_growth=sub_growth,
                )

                logger.info(
                    f"TG channel analytics: {stats['subscribers']} subs (+{sub_growth}), "
                    f"{stats['total_posts']} posts, avg {stats['avg_views']} views"
                )

        except Exception as e:
            logger.error(f"TG channel analytics error: {e}")

        await asyncio.sleep(24 * 3600)  # Once per day


def _fetch_tg_channel_stats() -> dict | None:
    """Fetch TG channel stats via a read-only Telethon user session.

    Requires TG_SESSION_STRING, TG_API_ID and TG_API_HASH in the environment
    (a user session that can read the channel). Optional — the bot works
    without it, TG-channel analytics are simply skipped.
    """
    import asyncio as aio
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.channels import GetFullChannelRequest

    session_str = os.environ.get("TG_SESSION_STRING", "").strip()
    api_id = os.environ.get("TG_API_ID", "").strip()
    api_hash = os.environ.get("TG_API_HASH", "").strip()

    if not session_str or not api_id or not api_hash:
        return None

    channel_username = TG_CHANNEL.lstrip("@")

    async def _collect():
        client = TelegramClient(StringSession(session_str), int(api_id), api_hash)
        await client.start()

        try:
            channel = await client.get_entity(channel_username)
            full = await client(GetFullChannelRequest(channel))
            subscribers = full.full_chat.participants_count

            messages = await client.get_messages(channel, limit=50)

            total_posts = len(messages)
            views_list = [m.views for m in messages if m.views]
            avg_views = sum(views_list) // len(views_list) if views_list else 0

            best_msg = max(messages, key=lambda m: m.views or 0) if messages else None
            best_post = (best_msg.text or "")[:100] if best_msg else ""
            best_views = best_msg.views or 0 if best_msg else 0

            return {
                "subscribers": subscribers,
                "total_posts": total_posts,
                "avg_views": avg_views,
                "best_post": best_post,
                "best_views": best_views,
            }
        finally:
            await client.disconnect()

    loop = aio.new_event_loop()
    try:
        return loop.run_until_complete(_collect())
    finally:
        loop.close()


async def autopilot_competitor_radar():
    """Every Monday at 8:00 MSK — scan competitors before weekly plan."""
    await asyncio.sleep(45)  # Let bot start up
    while True:
        await _wait_until(hour=8, minute=0, weekday=0)  # Monday 8:00

        try:
            logger.info("Autopilot: competitor radar scan starting")
            report = await asyncio.to_thread(run_competitor_radar)

            await send_long_to_owner(f"COMPETITOR RADAR (авто, пн 8:00)\n\n{report}")
            logger.info("Autopilot: competitor radar sent!")

        except Exception as e:
            logger.error(f"Autopilot competitor radar error: {e}")
            try:
                await bot.send_message(OWNER_ID, f"Radar error: {e}")
            except Exception:
                pass

        await asyncio.sleep(120)  # Prevent double-fire


async def weekly_report_task():
    """Every Sunday at 20:00 MSK — compile and send weekly content report."""
    await asyncio.sleep(90)  # Let bot start up
    while True:
        await _wait_until(hour=20, minute=0, weekday=6)  # Sunday = 6

        try:
            logger.info("Weekly report: compiling...")
            data = await asyncio.to_thread(get_weekly_report_data)

            # Build stats summary for AI recommendation
            stats_summary = (
                f"За неделю снято {data['videos_shot']} видео. "
                f"Общий охват: {data['total_views']} просмотров. "
                f"Лучшее видео: {data['best_video_theme']} ({data['best_video_views']} views). "
                f"Instagram: {data['insta_followers_end']} подписчиков (рост {data['insta_growth']:+d}). "
                f"Telegram: {data['tg_followers_end']} подписчиков (рост {data['tg_growth']:+d})."
            )

            # Get AI recommendation
            ai_prompt = (
                f"Ты контент-стратег для Instagram @your_brand (AI-автоматизация). "
                f"Статистика за неделю: {stats_summary} "
                f"Дай 2-3 конкретные рекомендации на следующую неделю. "
                f"Коротко, по делу, без списков с тире. Числа и факты."
            )

            try:
                recommendation = await asyncio.to_thread(call_ai, ai_prompt, 0.3, 500)
            except Exception:
                recommendation = ""

            # Format report
            report_lines = [
                f"КОНТЕНТ-ОТЧЁТ ЗА НЕДЕЛЮ\n",
                f"Видео снято: {data['videos_shot']}",
                f"Общий охват: {data['total_views']}",
            ]

            if data["best_video_theme"]:
                report_lines.append(
                    f"Лучшее видео: {data['best_video_theme']} — {data['best_video_views']} views"
                )

            if data["insta_followers_end"]:
                report_lines.append(
                    f"Instagram: {data['insta_followers_end']} подписчиков ({data['insta_growth']:+d})"
                )

            if data["tg_followers_end"]:
                report_lines.append(
                    f"Telegram: {data['tg_followers_end']} подписчиков ({data['tg_growth']:+d})"
                )

            if recommendation:
                report_lines.append(f"\nРекомендации:\n{recommendation}")

            report_text = "\n".join(report_lines)
            await bot.send_message(OWNER_ID, report_text)
            logger.info("Weekly report sent!")

        except Exception as e:
            logger.error(f"Weekly report error: {e}")
            try:
                await bot.send_message(OWNER_ID, f"Ошибка еженедельного отчёта: {e}")
            except Exception:
                pass

        await asyncio.sleep(120)  # Prevent double-fire


async def ai_news_daily_task():
    """Every day at 8:30 MSK — fetch AI news and send brief with script buttons."""
    await asyncio.sleep(35)  # Let bot start up
    while True:
        await _wait_until(hour=8, minute=30)

        try:
            logger.info("AI News: daily fetch starting")
            brief, items = await get_daily_news_brief(ask_gemini)

            if items:
                global _latest_news_items, _latest_news_date
                _latest_news_items = items
                now = datetime.now(MSK)
                _latest_news_date = now.strftime("%Y%m%d")
                _save_state()

                await send_long_to_owner(brief)

                # Send buttons for script generation
                buttons = []
                for i, item in enumerate(items[:5]):
                    title_short = (item.get("ai_summary") or item["title"])[:40]
                    buttons.append([InlineKeyboardButton(
                        text=f"Скрипт: {title_short}",
                        callback_data=f"news_script_{i}_{_latest_news_date}",
                    )])
                kb = InlineKeyboardMarkup(inline_keyboard=buttons)
                await bot.send_message(OWNER_ID, "Сделать скрипт по новости?", reply_markup=kb)

                logger.info(f"AI News: sent {len(items)} items")
            else:
                logger.info("AI News: no relevant items found")

        except Exception as e:
            logger.error(f"AI News daily task error: {e}")
            try:
                await bot.send_message(OWNER_ID, f"AI News error: {e}")
            except Exception:
                pass

        await asyncio.sleep(120)  # Prevent double-fire


async def main():
    if not BOT_TOKEN:
        print("ERROR: Set BOT_TOKEN in .env")
        return

    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="team", description="👥 Брифинг команды (7 агентов)"),
        BotCommand(command="team_script", description="👥 Командный скрипт"),
        BotCommand(command="team_plan", description="👥 План на неделю от команды"),
        BotCommand(command="check", description="⚡ Быстрая оценка идеи"),
        BotCommand(command="hooks", description="⚡ Битва хуков"),
        BotCommand(command="team_members", description="👥 Показать команду"),
        BotCommand(command="autopilot", description="🤖 Расписание автопилота"),
        BotCommand(command="ideas", description="💡 Идеи для Reels"),
        BotCommand(command="plan", description="📅 Контент-план на неделю"),
        BotCommand(command="trends", description="🔥 Актуальные тренды"),
        BotCommand(command="script", description="🎬 Скрипт для Reels"),
        BotCommand(command="caption", description="✍️ Caption для поста"),
        BotCommand(command="mystats", description="📊 Статистика TikTok/Instagram"),
        BotCommand(command="radar", description="Радар конкурентов"),
        BotCommand(command="monitor", description="📡 Настройка мониторинга"),
        BotCommand(command="links", description="🔗 Статистика ссылок"),
        BotCommand(command="bank", description="💡 Банк несъёмленных идей"),
        BotCommand(command="news", description="AI новости дня"),
        BotCommand(command="menu", description="Показать меню"),
    ])

    # Start autopilot background tasks
    asyncio.create_task(autopilot_daily_script())    # 9:00 MSK — скрипт на сегодня
    asyncio.create_task(autopilot_weekly_plan())      # Пн 9:00 MSK — план на неделю
    asyncio.create_task(autopilot_evening_hooks())    # 21:00 MSK — хуки на завтра
    asyncio.create_task(monitoring_report())           # Каждые 6ч — статистика
    asyncio.create_task(content_analytics_task())      # Каждые 6ч — аналитика контента
    asyncio.create_task(tg_channel_analytics_task())   # Каждые 24ч — аналитика ТГК
    asyncio.create_task(autopilot_competitor_radar())  # Пн 8:00 MSK — радар конкурентов
    asyncio.create_task(weekly_report_task())          # Вс 20:00 MSK — еженедельный отчёт
    asyncio.create_task(ai_news_daily_task())          # 8:30 MSK — AI новости дня

    logger.info("Content Team autopilot starting... Daily 9:00, Evening 21:00, Weekly Mon 9:00 MSK, Analytics every 6h, TGK daily, Radar Mon 8:00, News 8:30, Report Sun 20:00")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
