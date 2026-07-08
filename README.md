# Content Team Bot

A Telegram bot that runs a **multi-agent AI "content team"** for a short-form
creator (Instagram Reels / TikTok). Seven specialized AI agents brief each
other, debate, and hand off work to produce ready-to-shoot scripts, weekly
content plans, and virality reviews — plus a competitor radar, own-account
analytics, Google Sheets tracking, and a fully automated daily/weekly pilot.

Built with **aiogram** (async Telegram) and a provider-agnostic LLM layer
(Groq → OpenAI → OpenRouter fallback chain).

> This is a sanitized, brand-neutral portfolio version. All owner-specific
> identity, credentials, chat IDs and personal data have been removed and
> replaced with placeholders. Configure it via `.env` for your own brand.

---

## Highlight: the multi-agent orchestration

The core of the project is [`content_team.py`](content_team.py) — a small
orchestration engine over a team of seven role-specialized agents:

| Agent | Role |
|-------|------|
| 📊 Trend Analyst | Reads current formats/sounds, adapts trends to the niche |
| 🧠 Strategist | Maps content to funnel stage and business goals |
| 🎨 Content Creator | Generates ideas, formats, series, visual treatments |
| ✍️ Scriptwriter | Writes the second-by-second script in the brand voice |
| 💬 Copywriter | Sharpens hooks, captions and CTAs |
| 🔥 Virality Analyst | Scores ideas/scripts across 10 criteria, suggests fixes |
| 🎬 Production Manager | Merges everything into one final, shoot-ready deliverable |

**How it works.** Agents run in an ordered chain and each one sees the full
running transcript of everyone before it — so later agents genuinely build on,
or argue against, earlier contributions instead of answering in isolation. The
Production Manager always runs last and compiles a single clean result. The
orchestration is task-shaped, with different agent orders and final-output
formats for:

- `run_team_briefing` — open discussion on a topic
- `run_team_script` — collaborative, ready-to-shoot video script
- `run_team_plan` — full 7-day content plan
- `run_team_review` — team critique of an uploaded video
- `quick_idea_check` / `quick_hook_battle` — fast 2-3 agent chains

The LLM call is injected as a function (`ai_func`), so the engine is decoupled
from any specific provider and each agent has per-step retry/skip resilience so
one failed call never poisons the shared transcript.

The agents draw on two knowledge modules:
[`viral_kb.py`](viral_kb.py) (a distilled short-form content playbook) and
[`brand_voice.py`](brand_voice.py) (the on-camera speaking style) — both
brand-neutral and meant to be customized.

## Other capabilities

- **Competitor Radar** ([`competitor_radar.py`](competitor_radar.py)) —
  fetches recent posts for a configured list of Instagram/TikTok competitors,
  detects "viral" posts (≥2× account average, or top-N by engagement), and runs
  an AI teardown of *why* each one worked and how to adapt it (a
  "steal-ability" score included). Self-contained fetchers (Instagram web API +
  `yt-dlp` for TikTok).
- **Analytics** ([`content_analytics.py`](content_analytics.py)) — collects
  own-account post metrics, matches published posts back to the scenario that
  generated them (±1 day), and computes a virality tier + engagement rate.
- **Google Sheets tracking** ([`content_sheets.py`](content_sheets.py)) —
  auto-creates and maintains a spreadsheet (Scenarios, Analytics, TG Channel,
  Idea Bank tabs); logs every shot script, back-fills 24h/48h/7d view snapshots
  and click counts.
- **AI news briefings** ([`ai_news_parser.py`](ai_news_parser.py)) — pulls RSS
  from major AI sources, dedupes, AI-ranks by virality, and can turn the top
  item into a script topic.
- **UTM link tracker** ([`link_tracker.py`](link_tracker.py)) — a small FastAPI
  redirect server with per-link click + geo-IP analytics, used for CTA
  attribution.
- **Autopilot** — background tasks send a ready daily script (09:00), tomorrow's
  hooks (21:00), a Monday weekly plan, a Monday competitor scan, a Sunday
  weekly report, and daily AI news — all on an MSK schedule.

## Architecture

```
content_bot.py         # aiogram entrypoint: handlers, callbacks, autopilot
├── content_team.py    # ★ 7-agent orchestration engine
│   ├── viral_kb.py    # viral short-form content playbook (agent knowledge)
│   └── brand_voice.py # on-camera speaking style (agent knowledge)
├── competitor_radar.py# competitor scan + AI teardown
├── content_analytics.py# own-account metrics & virality scoring
├── content_sheets.py  # Google Sheets tracker
├── ai_news_parser.py  # AI news RSS digest
├── link_tracker.py    # FastAPI UTM redirect + click analytics
├── ai_helper.py       # provider-agnostic LLM layer (Groq→OpenAI→OpenRouter)
└── platforms/         # self-contained IG/TikTok fetchers for own-account stats
```

The LLM layer ([`ai_helper.py`](ai_helper.py)) is a compact fallback chain
across Groq (free), OpenAI, and OpenRouter, plus a GPT-4o-mini vision helper for
analyzing a frame of an uploaded video. It reads keys only from the environment.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# external binaries for TikTok fetching and video-frame analysis
#   yt-dlp, ffmpeg   (install via your package manager)

cp .env.example .env      # fill in BOT_TOKEN, OWNER_ID, at least one LLM key
python content_bot.py
```

The bot is single-owner: every handler checks the sender against `OWNER_ID`.

Optional integrations (Google Sheets, link tracker, TG-channel analytics) are
each gated on their own env vars and degrade gracefully when unconfigured.

## Notes

- Prompts and user-facing strings are in Russian (the bot's original target
  audience); the code, docs and knowledge modules are English.
- No credentials are bundled. All secrets are read from `.env` (git-ignored).
