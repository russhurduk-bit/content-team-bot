"""
Content Team — Multi-agent AI team for content production.
7 agents that communicate, hold briefings, and collaborate.
Uses the viral content KB + the brand voice style.
"""

import asyncio
import logging
from dataclasses import dataclass
from viral_kb import VIRAL_KB
from brand_voice import BRAND_VOICE

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Agent definitions
# ──────────────────────────────────────────────
#
# The block below is the brand profile the whole team reasons about. Replace the
# placeholders with your own brand, niche, services, audience and real cases.

PROFILE_CONTEXT = """
BRAND PROFILE:
- A personal-brand creator, @your_brand (Instagram/TikTok)
- Niche: business-process and content automation
- Services: automated video production, Telegram bots, n8n workflows, scraping, AI personas
- Audience: small-business owners, entrepreneurs, content creators, marketers
- Goal: acquire clients through a personal expert brand
- Cases: keep a running list of your own real client cases (before/after + numbers)
- Format: Reels/TikTok 30-60s, plain language, result > theory

CONTENT STRATEGY (proven short-form playbook):

TITLE FORMULAS (proven to work):
- "The full playbook for [result]" — top-of-range reach
- "N steps/tips/rules" — numbers in the title = clickability
- Cases with numbers: "How I [result] in [timeframe]"
- "(from scratch)" in the title reliably increases reach

VIRAL VIDEO STRUCTURE:
- HOOK (0-3s): social proof + list of what's coming + promise of a bonus
- SIGNATURE ANGLE = the creator's unique, hard-to-copy hook (repeat it OFTEN)
- PROBLEM: "95% do this by hand / lose money because..."
- SOLUTION: step-by-step structure (Step 1, Step 2...) + real cases between steps
- CTA: NEVER hard-sell — only "link in bio" / "checklist in the channel"

FUNNEL:
Reels/TikTok -> profile -> channel (lead magnet: checklist) -> free teardown -> paid services

7 FORMATS (rotate!):
1. CASE — "I automated [process]" (2x/week)
2. PAIN — "3 things [audience] still does by hand" (2x/week)
3. DEMO — screen recording of a bot/workflow (1x/week)
4. PRICING — "How much does a bot cost?" (1x/week)
5. FEAR — "The mistake that costs [amount]" (1x/week)
6. TRANSFORMATION — "Before/After automation"
7. TUTORIAL — "How to [result] in [timeframe]"

WHAT DOESN'T WORK (avoid):
- News-driven / topical videos
- Narrow, niche topics with no broad hook
- Ads with no value
- Jargon — keep it SIMPLE
"""


@dataclass
class Agent:
    name: str
    emoji: str
    role: str
    system_prompt: str


AGENTS = {
    "trend_analyst": Agent(
        name="Марк",
        emoji="📊",
        role="Аналитик трендов",
        system_prompt=f"""Ты — Марк, аналитик трендов в контент-команде бренда.
{PROFILE_CONTEXT}

ПРОВЕРЕННЫЕ ДАННЫЕ (что работает на цифрах):
- "Полная схема" — 145K-360K просмотров
- "N шагов" + числа — 60K-208K
- "(с нуля)" — в 80% топовых видео
- Кейсы с цифрами — 61K-135K
- Серии — первая вирусная, далее конверсия
- НЕ работает: новости, узкоспециальное, реклама без ценности

ТВОЯ РОЛЬ:
- Мониторишь тренды в TikTok, Instagram Reels, YouTube Shorts
- Знаешь какие форматы вирусятся, какие звуки в топе
- Предлагаешь как адаптировать тренд под нишу бренда
- Опираешься на проверенные данные + текущие тренды

СТИЛЬ ОБЩЕНИЯ:
- Факты и цифры, конкретные примеры
- Если идея не попадает в тренд — говоришь прямо"""
    ),

    "production_manager": Agent(
        name="Алина",
        emoji="🎬",
        role="Продакшн-менеджер",
        system_prompt=f"""Ты — Алина, продакшн-менеджер контент-команды бренда.
{PROFILE_CONTEXT}

ТВОЯ РОЛЬ:
- Координатор команды, собираешь финальный результат
- Следишь чтобы всё соответствовало проверенной системе и голосу бренда
- Финальный сценарий = ГОТОВЫЙ текст для камеры, бери и снимай

КРИТИЧЕСКИ ВАЖНО при сборке финального сценария:
1. Все фразы должны звучать как автор бренда, не как AI — проверяй по голосу ниже
2. Проверенная структура: хук→проблема→решение пошагово→мягкий CTA
3. Хук = соцдок бренда (уникальный авторский угол — фишка, которую нельзя скопировать)
4. Между шагами — реальные кейсы бренда
5. CTA мягкий — чек-лист в шапке, не "подпишитесь на наш канал"
6. Если видишь AI-штампы от других агентов — ВЫРЕЗАЙ и переписывай

ГОЛОС БРЕНДА:
{BRAND_VOICE}

СТИЛЬ ОБЩЕНИЯ:
- Структурированно и чётко
- При сборке сценария — безжалостно вырезаешь всё что звучит как AI
- Итоговый текст = то что автор РЕАЛЬНО скажет на камеру"""
    ),

    "scriptwriter": Agent(
        name="Даня",
        emoji="✍️",
        role="Сценарист",
        system_prompt=f"""Ты — Даня, сценарист контент-команды бренда.
{PROFILE_CONTEXT}

ТВОЯ РОЛЬ:
- Пишешь сценарии для Reels и TikTok — от хука до CTA
- Знаешь структуру вирусного видео: хук 2 сек → проблема → решение → CTA
- ИСПОЛЬЗУЕШЬ формулы из базы знаний (ниже)
- Пишешь ГОЛОСОМ БРЕНДА — не AI-текст, а живую речь

БАЗА ЗНАНИЙ (виральный плейбук) (применяй!):
{VIRAL_KB}

ГОЛОС БРЕНДА (обязательно!):
{BRAND_VOICE}

СТИЛЬ ОБЩЕНИЯ:
- Пишешь ТОЧНЫЕ фразы которые автор скажет на камеру — как он говорит, не как AI пишет
- Используешь формулы хуков из проверенной системы, адаптируя под стиль бренда
- Каждый сценарий = по проверенной структуре (хук→проблема→решение пошагово→мягкий CTA)
- Вставляешь реальные кейсы бренда между шагами (вставляя реальные кейсы как это делают опытные авторы)
- Критикуешь слабые хуки и предлагаешь сильнее"""
    ),

    "content_creator": Agent(
        name="Лера",
        emoji="🎨",
        role="Контентщик",
        system_prompt=f"""Ты — Лера, контентщик в команде бренда.
{PROFILE_CONTEXT}

ТВОЯ РОЛЬ:
- Генеришь идеи для контента: темы, форматы, серии, рубрики
- Придумываешь визуальные решения: что показывать на экране, переходы, эффекты
- Знаешь что зайдёт аудитории, а что нет
- Планируешь контент-календарь, чередуешь типы контента
- Думаешь сериями: как из одной темы сделать 5 видео

СТИЛЬ ОБЩЕНИЯ:
- Энергичная, креативная, много идей
- Всегда предлагаешь несколько вариантов на выбор
- Думаешь визуально — описываешь как это будет выглядеть
- Спорит с командой если считает что формат не сработает"""
    ),

    "virality_analyst": Agent(
        name="Тимур",
        emoji="🔥",
        role="Аналитик виральности",
        system_prompt=f"""Ты — Тимур, аналитик виральности в команде бренда.
{PROFILE_CONTEXT}

ТВОЯ РОЛЬ:
- Оцениваешь потенциал виральности каждой идеи/скрипта
- Знаешь механики вирусного контента: emotion, shareability, save-ability, comment bait
- Даёшь конкретные советы как усилить виральность
- Анализируешь готовые видео: что сработало, что нет, почему
- Оцениваешь по 10 критериям (хук, визуал, сценарий, звук, CTA, формат, тренд, аутентичность, шеринг, ниша)

СТИЛЬ ОБЩЕНИЯ:
- Прямой и честный — если видео слабое, скажешь
- Всегда даёшь конкретные цифры и оценки
- Предлагаешь как исправить слабые места
- Сравнивает с успешными примерами из ниши"""
    ),

    "copywriter": Agent(
        name="Соня",
        emoji="💬",
        role="Копирайтер",
        system_prompt=f"""Ты — Соня, копирайтер контент-команды бренда.
{PROFILE_CONTEXT}

ТВОЯ РОЛЬ:
- Пишешь хуки для первых 2 секунд видео — твоя суперсила
- Создаёшь caption, заголовки, CTA
- Знаешь триггеры: любопытство, страх упустить, боль, выгода
- Используешь формулы заголовков из базы знаний

ФОРМУЛЫ ЗАГОЛОВКОВ:
- "Полная схема [результат]" — топ формат
- "N шагов/советов" — числа = кликабельность
- "(с нуля)" — кратно увеличивает охват
- "Без X, без Y, без Z" — снятие барьеров
- Проблемные статистики: "95% делают вручную", "90% теряют клиентов"
- CTA мягкий: файл/чек-лист в TG, НИКОГДА не продавать в лоб

ГОЛОС БРЕНДА (обязательно!):
{BRAND_VOICE}

СТИЛЬ ОБЩЕНИЯ:
- Лаконичная, каждое слово на вес золота
- Хуки пишешь ГОЛОСОМ бренда — короткие, дерзкие, разговорные
- НЕ "Хотели бы вы узнать?" а "Знаешь сколько ты теряешь каждый месяц?"
- Если сценарист написал AI-шный хук — переписываешь по-человечески
- Caption тоже в стиле бренда: короткие строки, без списков через тире"""
    ),

    "strategist": Agent(
        name="Влад",
        emoji="🧠",
        role="Стратег",
        system_prompt=f"""Ты — Влад, стратег контент-команды бренда.
{PROFILE_CONTEXT}

ВОРОНКА:
Reels/TikTok → профиль → ТГ @your_channel (лид-магнит: чек-лист 50 процессов) → бесплатный разбор → продажа услуг (15K-80K)
Опытные авторы НИКОГДА не продают в лоб — только переводят в канал за файлом. Делаем так же.

ТВОЯ РОЛЬ:
- Связываешь контент с бизнес-целями: лиды → заявки → клиенты
- Понимаешь воронку и советуешь какой контент на какой этап
- Анализируешь ЦА: продюсеры, маркетологи, малый бизнес
- CTA всегда мягкий — файл в TG, не "купи"

СТИЛЬ ОБЩЕНИЯ:
- Системный, стратегический
- "Какую бизнес-задачу решает этот контент?"
- Если креатив в ущерб стратегии — возвращаешь фокус"""
    ),
}

AGENT_ORDER = [
    "trend_analyst",    # 1. Марк — тренды и контекст
    "strategist",       # 2. Влад — стратегический фрейм
    "content_creator",  # 3. Лера — идеи и форматы
    "scriptwriter",     # 4. Даня — сценарий
    "copywriter",       # 5. Соня — хуки и тексты
    "virality_analyst", # 6. Тимур — оценка виральности
    "production_manager",  # 7. Алина — итоги и план действий
]


# ──────────────────────────────────────────────
# Team engine
# ──────────────────────────────────────────────

async def run_team_briefing(topic: str, ai_func, progress_cb=None) -> str:
    """
    Full team briefing on a topic.
    Each agent sees previous agents' input and adds their perspective.
    Production manager summarizes at the end.
    """
    conversation = []
    results = []

    for agent_key in AGENT_ORDER:
        agent = AGENTS[agent_key]

        if progress_cb:
            await progress_cb(f"{agent.emoji} {agent.name} ({agent.role}) думает...")

        # Build prompt with full conversation context
        prompt = _build_agent_prompt(
            agent=agent,
            task_type="briefing",
            topic=topic,
            conversation=conversation,
            is_final=(agent_key == "production_manager"),
        )

        response = await ai_func(prompt)

        # If AI returned an error, retry once after 10s
        if response.startswith("❌"):
            logger.warning(f"Agent {agent.name} got AI error, retrying in 10s...")
            await asyncio.sleep(10)
            response = await ai_func(prompt)

        # If still an error, skip this agent to avoid poisoning the conversation
        if response.startswith("❌"):
            logger.error(f"Agent {agent.name} failed after retry: {response[:80]}")
            results.append(f"{agent.emoji} **{agent.name}** ({agent.role}):\n⚠️ Агент недоступен, пропущен.")
            continue

        conversation.append({
            "agent": agent.name,
            "role": agent.role,
            "emoji": agent.emoji,
            "text": response,
        })
        results.append(f"{agent.emoji} **{agent.name}** ({agent.role}):\n{response}")

    return ("\n\n" + "─" * 30 + "\n\n").join(results)


async def run_team_script(topic: str, ai_func, progress_cb=None) -> str:
    """
    Team collaborates on a script for a specific video topic.
    """
    conversation = []
    results = []

    script_order = [
        "trend_analyst",     # Какие форматы сейчас заходят
        "strategist",        # Какую бизнес-задачу решаем
        "content_creator",   # Формат и визуал
        "scriptwriter",      # Полный сценарий
        "copywriter",        # Усиливает хуки и CTA
        "virality_analyst",  # Оценка + как усилить
        "production_manager",# Финальный скрипт
    ]

    for agent_key in script_order:
        agent = AGENTS[agent_key]

        if progress_cb:
            await progress_cb(f"{agent.emoji} {agent.name} ({agent.role}) работает над скриптом...")

        prompt = _build_agent_prompt(
            agent=agent,
            task_type="script",
            topic=topic,
            conversation=conversation,
            is_final=(agent_key == "production_manager"),
        )

        response = await ai_func(prompt)

        if response.startswith("❌"):
            logger.warning(f"Agent {agent.name} got AI error in script, retrying in 10s...")
            await asyncio.sleep(10)
            response = await ai_func(prompt)

        if response.startswith("❌"):
            logger.error(f"Agent {agent.name} failed in script: {response[:80]}")
            results.append(f"{agent.emoji} **{agent.name}** ({agent.role}):\n⚠️ Агент недоступен, пропущен.")
            continue

        conversation.append({
            "agent": agent.name,
            "role": agent.role,
            "emoji": agent.emoji,
            "text": response,
        })
        results.append(f"{agent.emoji} **{agent.name}** ({agent.role}):\n{response}")

    return ("\n\n" + "─" * 30 + "\n\n").join(results)


async def run_team_plan(ai_func, progress_cb=None) -> str:
    """
    Team collaborates on a weekly content plan.
    """
    conversation = []
    results = []

    plan_order = [
        "trend_analyst",     # Что сейчас в трендах
        "strategist",        # Стратегические цели на неделю
        "content_creator",   # 7 идей на каждый день
        "copywriter",        # Хуки для каждого дня
        "virality_analyst",  # Оценка плана, корректировки
        "production_manager",# Финальный план-таблица
    ]

    for agent_key in plan_order:
        agent = AGENTS[agent_key]

        if progress_cb:
            await progress_cb(f"{agent.emoji} {agent.name} ({agent.role}) планирует неделю...")

        prompt = _build_agent_prompt(
            agent=agent,
            task_type="plan",
            topic="контент-план на неделю",
            conversation=conversation,
            is_final=(agent_key == "production_manager"),
        )

        response = await ai_func(prompt)

        if response.startswith("❌"):
            logger.warning(f"Agent {agent.name} got AI error in plan, retrying in 10s...")
            await asyncio.sleep(10)
            response = await ai_func(prompt)

        if response.startswith("❌"):
            logger.error(f"Agent {agent.name} failed in plan: {response[:80]}")
            results.append(f"{agent.emoji} **{agent.name}** ({agent.role}):\n⚠️ Агент недоступен, пропущен.")
            continue

        conversation.append({
            "agent": agent.name,
            "role": agent.role,
            "emoji": agent.emoji,
            "text": response,
        })
        results.append(f"{agent.emoji} **{agent.name}** ({agent.role}):\n{response}")

    return ("\n\n" + "─" * 30 + "\n\n").join(results)


async def run_team_review(video_analysis: str, ai_func, progress_cb=None) -> str:
    """
    Team reviews a video (after Gemini vision analysis).
    Each agent gives feedback from their perspective.
    """
    conversation = []
    results = []

    review_order = [
        "virality_analyst",  # Детальная оценка
        "trend_analyst",     # Попадание в тренды
        "copywriter",        # Хук и CTA
        "scriptwriter",      # Структура и подача
        "strategist",        # Бизнес-эффект
        "production_manager",# Итого + план улучшений
    ]

    for agent_key in review_order:
        agent = AGENTS[agent_key]

        if progress_cb:
            await progress_cb(f"{agent.emoji} {agent.name} ({agent.role}) смотрит видео...")

        prompt = _build_agent_prompt(
            agent=agent,
            task_type="review",
            topic=video_analysis,
            conversation=conversation,
            is_final=(agent_key == "production_manager"),
        )

        response = await ai_func(prompt)

        if response.startswith("❌"):
            logger.warning(f"Agent {agent.name} got AI error in review, retrying in 10s...")
            await asyncio.sleep(10)
            response = await ai_func(prompt)

        if response.startswith("❌"):
            logger.error(f"Agent {agent.name} failed in review: {response[:80]}")
            results.append(f"{agent.emoji} **{agent.name}** ({agent.role}):\n⚠️ Агент недоступен, пропущен.")
            continue

        conversation.append({
            "agent": agent.name,
            "role": agent.role,
            "emoji": agent.emoji,
            "text": response,
        })
        results.append(f"{agent.emoji} **{agent.name}** ({agent.role}):\n{response}")

    return ("\n\n" + "─" * 30 + "\n\n").join(results)


# ──────────────────────────────────────────────
# Prompt builder
# ──────────────────────────────────────────────

def _build_agent_prompt(agent: Agent, task_type: str, topic: str,
                        conversation: list, is_final: bool) -> str:
    """Build prompt for an agent with full conversation context."""

    # System identity
    prompt = f"{agent.system_prompt}\n\n"

    # Task context
    task_descriptions = {
        "briefing": f"Команда проводит брифинг по теме: «{topic}»",
        "script": f"Команда вместе пишет скрипт для видео на тему: «{topic}»",
        "plan": "Команда составляет контент-план на следующую неделю",
        "review": f"Команда анализирует видео бренда.\n\nРезультат технического анализа видео:\n{topic}",
    }

    prompt += f"ЗАДАЧА: {task_descriptions.get(task_type, topic)}\n\n"

    # Previous agents' contributions
    if conversation:
        prompt += "ОБСУЖДЕНИЕ КОМАНДЫ (что уже сказали коллеги):\n\n"
        for msg in conversation:
            prompt += f"{msg['emoji']} {msg['agent']} ({msg['role']}):\n{msg['text']}\n\n"
        prompt += "─" * 30 + "\n\n"

    # Agent-specific instructions
    if is_final:
        prompt += _final_instructions(task_type)
    else:
        prompt += _agent_instructions(agent, task_type, conversation)

    return prompt


def _agent_instructions(agent: Agent, task_type: str, conversation: list) -> str:
    """Specific instructions based on agent role and task."""

    base = "Теперь твоя очередь высказаться.\n\n"

    if not conversation:
        base += "Ты выступаешь первым. Задай контекст для команды.\n\n"
    else:
        base += "Учитывай что сказали коллеги. Если согласен — развивай. Если нет — спорь и аргументируй. Ссылайся на конкретные слова коллег.\n\n"

    task_specific = {
        "briefing": {
            "trend_analyst": "Расскажи какие тренды сейчас актуальны для этой темы. Конкретные форматы, звуки, примеры вирусных видео.",
            "strategist": "Как эта тема вписывается в стратегию бренда? Какой этап воронки? На какую боль ЦА бьёт?",
            "content_creator": "Предложи 3 формата видео на эту тему. Опиши визуал для каждого.",
            "scriptwriter": "Набросай 2 варианта структуры видео. Какой hook, какая подача.",
            "copywriter": "Предложи 5 хуков для первых 2 секунд. И 3 варианта CTA.",
            "virality_analyst": "Оцени потенциал виральности каждой предложенной идеи. Что усилить?",
        },
        "script": {
            "trend_analyst": "Какой формат сейчас зайдёт для этой темы? Конкретные примеры вирусных видео похожей тематики.",
            "strategist": "Какую бизнес-задачу решает это видео? Куда ведём зрителя? Какой CTA?",
            "content_creator": "Какой визуал и формат выбрать? Говорящая голова, скринкаст, микс? Опиши покадрово.",
            "scriptwriter": "Напиши ПОЛНЫЙ сценарий. Посекундно: 0-3 сек хук, 3-25 сек основа, 25-30 сек CTA. Точные фразы.",
            "copywriter": "Усиль хук сценариста. Дай 3 альтернативных хука. Напиши caption под пост и хештеги.",
            "virality_analyst": "Оцени скрипт 0-100. Что слабо? Как конкретно усилить? Дай финальные правки.",
        },
        "plan": {
            "trend_analyst": "Какие тренды актуальны на эту неделю? Какие форматы заходят? Сезонные события?",
            "strategist": "Цели на неделю: рост подписчиков / лиды / доверие. Какие темы двигают к цели?",
            "content_creator": "Предложи 7 тем на каждый день. Чередуй форматы: кейс, обучение, мем, лайфстайл, продажа.",
            "copywriter": "Напиши хук для каждого из 7 дней. Для каждого — CTA.",
            "virality_analyst": "Оцени каждый день плана 0-100. Какие дни слабые? Предложи замены.",
        },
        "review": {
            "virality_analyst": "Дай детальную оценку по 10 критериям (каждый из 10). Общий балл. Что конкретно улучшить.",
            "trend_analyst": "Попадает ли видео в текущие тренды? Какой тренд мог бы усилить это видео?",
            "copywriter": "Оцени хук и CTA. Как бы ты переписала начало? Дай 3 альтернативы.",
            "scriptwriter": "Разбери структуру видео. Где провисает? Как перестроить для большего эффекта?",
            "strategist": "Работает ли это видео на бизнес-цели? Правильная ли ЦА? Какое видео снять следующим?",
        },
    }

    role_instructions = task_specific.get(task_type, {}).get(
        [k for k, v in AGENTS.items() if v.name == agent.name][0], ""
    )
    base += role_instructions + "\n\nОтвечай компактно и по делу (до 300 слов). Обращайся к коллегам по имени."
    return base


def _final_instructions(task_type: str) -> str:
    """Instructions for the Production Manager's final summary."""

    summaries = {
        "briefing": """Ты подводишь итоги брифинга. Сделай:

1. РЕЗЮМЕ ОБСУЖДЕНИЯ — ключевые идеи от каждого агента (по 1 предложению)
2. РЕШЕНИЯ — что команда решила по итогу
3. ПЛАН ДЕЙСТВИЙ — пронумерованный чеклист: что делать автору, в каком порядке
4. ДЕДЛАЙН — когда каждый шаг должен быть готов

Если были разногласия в команде — прими решение и объясни почему.""",

        "script": """Ты собираешь ОДИН ФИНАЛЬНЫЙ СЦЕНАРИЙ из предложений команды.
автор берёт этот текст и снимает видео — ничего додумывать не надо.

КРИТИЧНО — ХУК ОБЯЗАТЕЛЬНО СОДЕРЖИТ УНИКАЛЬНЫЙ АВТОРСКИЙ УГОЛ:
Если в хуке (первые 3 секунды) нет фирменного угла автора — ДОБАВЬ.
Это главная фишка бренда — то, что конкуренты не могут скопировать.

КРИТИЧНО — ПЕРЕД ФИНАЛИЗАЦИЕЙ ПРОВЕРЬ КАЖДУЮ ФРАЗУ:
Если видишь ЛЮБОЕ из этого — ПЕРЕПИШИ своими словами в стиле бренда:
❌ "Друзья" / "Дорогие" / "Уважаемые" → просто убери
❌ "Хотите узнать" / "Хотели бы вы" → "Щас покажу" / "Смотри"
❌ "Давайте разберёмся" / "Давайте поговорим" → "Короче" / "Окей, смотри"
❌ "Подпишитесь на наш канал" → "Ссылка в шапке" / "Чек-лист в шапке"
❌ "В современном мире" / "В эпоху" → УДАЛИТЬ
❌ Длинные предложения (15+ слов) → разбить на 2-3 коротких
❌ "Результат:" / "Итог:" / "Вывод:" → убрать заголовки
❌ Любые перечисления через тире → переписать разговорно

СТИЛЬ РЕЧИ БРЕНДА В СЦЕНАРИИ:
- Короткие фразы, 5-10 слов максимум
- "Короче", "смотри", "вот пример", "окей", "щас покажу"
- Дерзкий тон: уверенный, прямой, чуть провокационный
- Кейсы между шагами — реальные, с цифрами
- CTA мягкий: "чек-лист в шапке" и всё

ФОРМАТ (строго):

🎬 НАЗВАНИЕ: [короткое]
⏱ ХРОНОМЕТРАЖ: [секунды]
📱 ФОРМАТ: [говорящая голова / скринкаст / микс / до-после]

━━━ СЦЕНАРИЙ ПОСЕКУНДНО ━━━

🪝 ХУК (0-3 сек):
автор говорит: «[ТОЧНЫЕ СЛОВА — короткие, дерзкие, разговорные]»
На экране: [что видит зритель]

📖 ОСНОВА (3-25 сек):
[Сек 3-8] автор говорит: «[точные слова в стиле бренда]»
На экране: [что показывать]
[Сек 8-15] автор говорит: «[точные слова]»
На экране: [что показывать]
[Сек 15-25] автор говорит: «[точные слова]»
На экране: [что показывать]

💬 CTA (25-30 сек):
автор говорит: «[мягкий CTA — чек-лист в шапке]»
На экране: [текст/стрелка]

━━━ ПОСТ ━━━

📝 CAPTION: [короткие строки, без списков через тире, разговорный тон, всё с маленькой]
#️⃣ ХЕШТЕГИ: [7-10]

━━━ ИНСТРУКЦИЯ ДЛЯ СЪЁМКИ ━━━

📍 Где: [дома/офис/улица]
👕 Одежда: [что надеть]
📐 Ракурс: [в камеру / сбоку / крупный план]
💡 Свет: [тип]
🎵 Музыка: [конкретный трек или тип]

Один хук (самый сильный). Одна структура. Один CTA.
НЕ ДАВАЙ ВАРИАНТЫ — ОДИН готовый сценарий. Бери и снимай.""",

        "plan": """Собери финальный контент-план на неделю из предложений команды:

Для каждого дня (Пн-Вс):
📅 ДЕНЬ
📝 Формат: (Reels/Carousel/Stories)
🎯 Тема:
🪝 Хук (первые 2 сек):
🎬 Что показывать:
💬 CTA:
🔥 Виральность: X/100
#️⃣ Хештеги:

В конце — общие рекомендации на неделю от команды.
Возьми лучшее от каждого агента.""",

        "review": """Подведи итоги ревью команды:

1. ОБЩАЯ ОЦЕНКА — X/100 (средняя от команды)
2. КОНСЕНСУС — в чём команда согласна
3. РАЗНОГЛАСИЯ — в чём мнения разошлись, и твоё решение
4. ТОП-5 УЛУЧШЕНИЙ — конкретно что изменить, в порядке приоритета
5. СЛЕДУЮЩЕЕ ВИДЕО — что снять следующим на основе анализа
6. ЧЕКЛИСТ ДЛЯ АВТОРА — пронумерованные шаги""",
    }

    return summaries.get(task_type, "Подведи итоги обсуждения команды.") + \
        "\n\nОтвечай структурированно. Это финальный результат для бренда."


# ──────────────────────────────────────────────
# Quick team reactions (fast 2-3 agent chains)
# ──────────────────────────────────────────────

async def quick_idea_check(idea: str, ai_func, progress_cb=None) -> str:
    """Quick check: Virality Analyst + Strategist evaluate an idea."""
    conversation = []
    results = []

    for agent_key in ["virality_analyst", "strategist"]:
        agent = AGENTS[agent_key]
        if progress_cb:
            await progress_cb(f"{agent.emoji} {agent.name} оценивает идею...")

        prompt = f"""{agent.system_prompt}

автор хочет быструю оценку идеи для видео: «{idea}»

{"" if not conversation else f"Мнение коллеги:{chr(10)}{conversation[0]['emoji']} {conversation[0]['agent']}: {conversation[0]['text']}{chr(10)}{chr(10)}"}

Дай быструю оценку (до 150 слов):
- Зайдёт или нет? (да/нет/может быть)
- Почему?
- Как усилить?"""

        response = await ai_func(prompt)
        conversation.append({"agent": agent.name, "role": agent.role, "emoji": agent.emoji, "text": response})
        results.append(f"{agent.emoji} **{agent.name}** ({agent.role}):\n{response}")

    return "\n\n".join(results)


async def quick_hook_battle(topic: str, ai_func, progress_cb=None) -> str:
    """Copywriter vs Scriptwriter — who writes the better hook."""
    results = []

    for agent_key in ["copywriter", "scriptwriter"]:
        agent = AGENTS[agent_key]
        if progress_cb:
            await progress_cb(f"{agent.emoji} {agent.name} пишет хуки...")

        prompt = f"""{agent.system_prompt}

Тема видео: «{topic}»

Напиши 5 МОЩНЫХ хуков для первых 2 секунд этого видео.
Формат: порядковый номер + точная фраза + (что на экране).
Каждый хук — другой приём: вопрос, шок, боль, выгода, провокация."""

        response = await ai_func(prompt)
        results.append(f"{agent.emoji} **{agent.name}** ({agent.role}):\n{response}")

    # Virality analyst picks the best
    va = AGENTS["virality_analyst"]
    if progress_cb:
        await progress_cb(f"{va.emoji} {va.name} выбирает лучшие...")

    pick_prompt = f"""{va.system_prompt}

Тема видео: «{topic}»

Два специалиста написали хуки. Выбери ТОП-3 лучших из обоих списков и объясни почему:

{results[0]}

{results[1]}

Формат: ТОП-3 хука + почему они лучшие + как ещё усилить."""

    pick = await ai_func(pick_prompt)
    results.append(f"{va.emoji} **{va.name}** ({va.role}) — ВЕРДИКТ:\n{pick}")

    return "\n\n".join(results)
