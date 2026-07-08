"""Google Sheets integration for Content Tracker."""

import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta

import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

logger = logging.getLogger("content_bot.sheets")

OAUTH_CREDS_PATH = os.environ.get("GOOGLE_OAUTH_CREDS", "google_oauth_cred.json")
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

MSK = timezone(timedelta(hours=3))

SCENARIOS_HEADERS = [
    "#", "Дата", "День недели", "Тема", "Хук", "Формат", "Статус",
    "Полный сценарий", "Instagram URL", "Views", "Likes", "Comments",
    "Views 24h", "Views 48h", "Views 7d", "Виральность", "Ссылка", "Клики",
]

ANALYTICS_HEADERS = [
    "Дата", "Всего видео", "Подписчики", "Охват",
    "Лучшее видео", "Views лучшего",
]

TG_CHANNEL_HEADERS = [
    "Дата", "Подписчики", "Всего постов", "Средние просмотры",
    "Лучший пост", "Views лучшего", "Рост подписчиков",
]

IDEA_BANK_HEADERS = [
    "#", "Дата", "Тема", "Хук", "Формат", "Статус",
]


def _load_credentials() -> Credentials:
    """Load OAuth credentials from the shared creds file."""
    with open(OAUTH_CREDS_PATH, "r") as f:
        cred_data = json.load(f)

    token_data = cred_data.get("oauthTokenData", {})

    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cred_data["clientId"],
        client_secret=cred_data["clientSecret"],
        scopes=SCOPES,
    )

    if creds.expired or not creds.valid:
        creds.refresh(Request())
        token_data["access_token"] = creds.token
        cred_data["oauthTokenData"] = token_data
        with open(OAUTH_CREDS_PATH, "w") as f:
            json.dump(cred_data, f)

    return creds


def _get_client() -> gspread.Client:
    """Get authenticated gspread client."""
    creds = _load_credentials()
    return gspread.authorize(creds)


def _get_or_create_sheet_id() -> str:
    """Get existing sheet ID from .env or create new spreadsheet."""
    from dotenv import load_dotenv, set_key
    load_dotenv(ENV_PATH)

    sheet_id = os.getenv("CONTENT_SHEET_ID", "").strip()
    if sheet_id:
        return sheet_id

    logger.info("Creating new Google Spreadsheet: Content Tracker")
    client = _get_client()
    spreadsheet = client.create(os.environ.get("CONTENT_SHEET_NAME", "Content Tracker"))

    # Create tabs
    scenarios_ws = spreadsheet.add_worksheet(title="Сценарии", rows=1000, cols=20)
    scenarios_ws.update(range_name="A1", values=[SCENARIOS_HEADERS])

    analytics_ws = spreadsheet.add_worksheet(title="Аналитика", rows=500, cols=10)
    analytics_ws.update(range_name="A1", values=[ANALYTICS_HEADERS])

    # Remove default Sheet1
    try:
        default = spreadsheet.worksheet("Sheet1")
        spreadsheet.del_worksheet(default)
    except Exception:
        pass

    sheet_id = spreadsheet.id
    logger.info(f"Created Content Tracker spreadsheet: {sheet_id}")

    # Save to .env
    set_key(ENV_PATH, "CONTENT_SHEET_ID", sheet_id)

    # Share with anyone with the link (view only)
    spreadsheet.share(None, perm_type="anyone", role="reader")

    return sheet_id


def _get_spreadsheet() -> gspread.Spreadsheet:
    """Get the Content Tracker spreadsheet."""
    client = _get_client()
    sheet_id = _get_or_create_sheet_id()
    return client.open_by_key(sheet_id)


def get_sheet_url() -> str:
    """Get URL to the spreadsheet."""
    sheet_id = _get_or_create_sheet_id()
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}"


def extract_hook_from_script(script_text: str) -> str:
    """Try to extract the hook from a script."""
    # Look for common hook patterns
    for pattern in [
        r'[Хх][Уу][Кк]\s*[\(:：]\s*(.+?)(?:\n|$)',
        r'ХУК.*?[:\-]\s*(.+?)(?:\n|$)',
        r'🪝\s*(?:ХУК)?[^:]*:\s*(.+?)(?:\n|$)',
        r'Первые \d+ сек[^:]*:\s*(.+?)(?:\n|$)',
    ]:
        m = re.search(pattern, script_text, re.IGNORECASE)
        if m:
            hook = m.group(1).strip()
            # Clean up
            hook = re.sub(r'\[.*?\]', '', hook).strip()
            if hook and len(hook) > 5:
                return hook[:200]

    # Fallback: first meaningful line
    for line in script_text.split("\n"):
        line = line.strip()
        if len(line) > 15 and not line.startswith(("#", "📅", "🤖", "⏳", "_")):
            return line[:200]

    return ""


def extract_format_from_script(script_text: str) -> str:
    """Try to extract the format from a script."""
    for pattern in [
        r'[Фф]ормат\s*[:\-]\s*(.+?)(?:\n|$)',
        r'🎬\s*(?:ВИЗУАЛ)?[^:]*:\s*(.+?)(?:\n|$)',
    ]:
        m = re.search(pattern, script_text, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:100]
    return "Reels"


def save_scenario(date_str: str, day_name: str, theme: str, script_text: str) -> int:
    """Save a scenario to the Сценарии sheet. Returns the row number."""
    retries = 3
    for attempt in range(retries):
        try:
            spreadsheet = _get_spreadsheet()

            try:
                ws = spreadsheet.worksheet("Сценарии")
            except gspread.WorksheetNotFound:
                ws = spreadsheet.add_worksheet(title="Сценарии", rows=1000, cols=20)
                ws.update(range_name="A1", values=[SCENARIOS_HEADERS])

            # Find next row number
            all_values = ws.get_all_values()
            next_row = len(all_values) + 1
            row_num = next_row - 1  # Scenario number (excluding header)

            hook = extract_hook_from_script(script_text)
            fmt = extract_format_from_script(script_text)

            # Truncate script for sheet (max ~50000 chars per cell)
            script_for_sheet = script_text[:45000] if len(script_text) > 45000 else script_text

            row = [
                row_num,           # #
                date_str,          # Дата
                day_name,          # День недели
                theme[:200],       # Тема
                hook,              # Хук
                fmt,               # Формат
                "снято",           # Статус
                script_for_sheet,  # Полный сценарий
                "",                # Instagram URL
                "",                # Views
                "",                # Likes
                "",                # Comments
                "",                # Views 24h
                "",                # Views 48h
                "",                # Views 7d
                "",                # Виральность
            ]

            ws.append_row(row, value_input_option="USER_ENTERED")
            logger.info(f"Saved scenario #{row_num} for {date_str}")
            return next_row

        except Exception as e:
            logger.error(f"Error saving scenario (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                import time
                time.sleep(5)

    return -1


def update_scenario_analytics(row_number: int, instagram_url: str = None,
                               views: int = None, likes: int = None,
                               comments: int = None, views_24h: int = None,
                               views_48h: int = None, views_7d: int = None,
                               virality: str = None):
    """Update analytics columns for a specific scenario row."""
    retries = 3
    for attempt in range(retries):
        try:
            spreadsheet = _get_spreadsheet()
            ws = spreadsheet.worksheet("Сценарии")

            updates = {}
            if instagram_url is not None:
                updates["I" + str(row_number)] = instagram_url
            if views is not None:
                updates["J" + str(row_number)] = views
            if likes is not None:
                updates["K" + str(row_number)] = likes
            if comments is not None:
                updates["L" + str(row_number)] = comments
            if views_24h is not None:
                updates["M" + str(row_number)] = views_24h
            if views_48h is not None:
                updates["N" + str(row_number)] = views_48h
            if views_7d is not None:
                updates["O" + str(row_number)] = views_7d
            if virality is not None:
                updates["P" + str(row_number)] = virality

            for cell, value in updates.items():
                ws.update(range_name=cell, values=[[value]])

            logger.info(f"Updated analytics for row {row_number}")
            return True

        except Exception as e:
            logger.error(f"Error updating analytics (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                import time
                time.sleep(5)

    return False


def get_scenarios_needing_analytics() -> list[dict]:
    """Get all scenarios with status 'снято' that need analytics updates."""
    retries = 3
    for attempt in range(retries):
        try:
            spreadsheet = _get_spreadsheet()
            ws = spreadsheet.worksheet("Сценарии")
            all_rows = ws.get_all_values()

            if len(all_rows) <= 1:
                return []

            header = all_rows[0]
            results = []

            for i, row in enumerate(all_rows[1:], start=2):
                if len(row) < 9:
                    continue

                status = row[6] if len(row) > 6 else ""
                if status.lower() != "снято":
                    continue

                date_str = row[1] if len(row) > 1 else ""
                ig_url = row[8] if len(row) > 8 else ""
                views_24h = row[12] if len(row) > 12 else ""
                views_48h = row[13] if len(row) > 13 else ""
                views_7d = row[14] if len(row) > 14 else ""

                # Parse date
                scenario_date = None
                try:
                    scenario_date = datetime.strptime(date_str, "%d.%m.%Y").replace(tzinfo=MSK)
                except Exception:
                    pass

                if not scenario_date:
                    continue

                now = datetime.now(MSK)
                days_since = (now - scenario_date).days

                # Determine what needs updating
                needs_url = not ig_url
                needs_24h = not views_24h and days_since >= 1
                needs_48h = not views_48h and days_since >= 2
                needs_7d = not views_7d and days_since >= 7
                needs_views_update = days_since <= 14  # Keep updating views for 2 weeks

                if needs_url or needs_24h or needs_48h or needs_7d or needs_views_update:
                    results.append({
                        "row": i,
                        "date": date_str,
                        "scenario_date": scenario_date,
                        "days_since": days_since,
                        "ig_url": ig_url,
                        "needs_url": needs_url,
                        "needs_24h": needs_24h,
                        "needs_48h": needs_48h,
                        "needs_7d": needs_7d,
                    })

            return results

        except Exception as e:
            logger.error(f"Error reading scenarios (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                import time
                time.sleep(5)

    return []


def update_analytics_sheet(total_videos: int, followers: int = 0,
                           reach: int = 0, best_video: str = "",
                           best_views: int = 0):
    """Add a row to the Аналитика sheet."""
    retries = 3
    for attempt in range(retries):
        try:
            spreadsheet = _get_spreadsheet()

            try:
                ws = spreadsheet.worksheet("Аналитика")
            except gspread.WorksheetNotFound:
                ws = spreadsheet.add_worksheet(title="Аналитика", rows=500, cols=10)
                ws.update(range_name="A1", values=[ANALYTICS_HEADERS])

            today = datetime.now(MSK).strftime("%d.%m.%Y")
            row = [today, total_videos, followers, reach, best_video, best_views]
            ws.append_row(row, value_input_option="USER_ENTERED")
            logger.info(f"Updated Аналитика sheet for {today}")
            return True

        except Exception as e:
            logger.error(f"Error updating Аналитика (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                import time
                time.sleep(5)

    return False


def update_tg_channel_analytics(subscribers: int = 0, total_posts: int = 0,
                                 avg_views: int = 0, best_post: str = "",
                                 best_views: int = 0, sub_growth: int = 0):
    """Add a row to the ТГ Канал sheet."""
    retries = 3
    for attempt in range(retries):
        try:
            spreadsheet = _get_spreadsheet()

            try:
                ws = spreadsheet.worksheet("ТГ Канал")
            except gspread.WorksheetNotFound:
                ws = spreadsheet.add_worksheet(title="ТГ Канал", rows=500, cols=10)
                ws.update(range_name="A1", values=[TG_CHANNEL_HEADERS])

            today = datetime.now(MSK).strftime("%d.%m.%Y")
            row = [today, subscribers, total_posts, avg_views, best_post[:200], best_views, sub_growth]
            ws.append_row(row, value_input_option="USER_ENTERED")
            logger.info(f"Updated ТГ Канал sheet for {today}")
            return True

        except Exception as e:
            logger.error(f"Error updating ТГ Канал (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                import time
                time.sleep(5)

    return False


def update_scenario_link(row_number: int, link_url: str) -> bool:
    """Update the Ссылка (Q) column for a scenario row."""
    retries = 3
    for attempt in range(retries):
        try:
            spreadsheet = _get_spreadsheet()
            ws = spreadsheet.worksheet("Сценарии")
            ws.update(range_name=f"Q{row_number}", values=[[link_url]])
            logger.info(f"Updated link for row {row_number}")
            return True
        except Exception as e:
            logger.error(f"Error updating link (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                import time
                time.sleep(5)
    return False


def update_scenario_clicks(row_number: int, clicks: int) -> bool:
    """Update the Клики (R) column for a scenario row."""
    retries = 3
    for attempt in range(retries):
        try:
            spreadsheet = _get_spreadsheet()
            ws = spreadsheet.worksheet("Сценарии")
            ws.update(range_name=f"R{row_number}", values=[[clicks]])
            logger.info(f"Updated clicks for row {row_number}: {clicks}")
            return True
        except Exception as e:
            logger.error(f"Error updating clicks (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                import time
                time.sleep(5)
    return False


def get_all_scenario_sources() -> list[dict]:
    """Get all scenario rows with their source identifiers and row numbers."""
    retries = 3
    for attempt in range(retries):
        try:
            spreadsheet = _get_spreadsheet()
            ws = spreadsheet.worksheet("Сценарии")
            all_rows = ws.get_all_values()
            if len(all_rows) <= 1:
                return []

            results = []
            for i, row in enumerate(all_rows[1:], start=2):
                date_str = row[1] if len(row) > 1 else ""
                link_url = row[16] if len(row) > 16 else ""
                if date_str and link_url:
                    source = f"reels_{date_str.replace('.', '')}"
                    results.append({
                        "row": i,
                        "date": date_str,
                        "source": source,
                        "link": link_url,
                    })
            return results
        except Exception as e:
            logger.error(f"Error reading scenario sources (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                import time
                time.sleep(5)
    return []


# --- Idea Bank ---

def _get_or_create_idea_bank_ws():
    """Get or create the Банк идей worksheet."""
    spreadsheet = _get_spreadsheet()
    try:
        ws = spreadsheet.worksheet("Банк идей")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="Банк идей", rows=500, cols=10)
        ws.update(range_name="A1", values=[IDEA_BANK_HEADERS])
    return ws


def save_to_idea_bank(date: str, theme: str, hook: str, fmt: str) -> bool:
    """Save an unsaved idea to the Банк идей sheet."""
    retries = 3
    for attempt in range(retries):
        try:
            ws = _get_or_create_idea_bank_ws()
            all_values = ws.get_all_values()
            next_num = len(all_values)  # header is row 1

            row = [
                next_num,
                date,
                theme[:200],
                hook[:200],
                fmt[:100] if fmt else "Reels",
                "не снято",
            ]
            ws.append_row(row, value_input_option="USER_ENTERED")
            logger.info(f"Saved idea #{next_num} to bank: {theme[:50]}")
            return True

        except Exception as e:
            logger.error(f"Error saving to idea bank (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                import time
                time.sleep(5)
    return False


def get_ideas_from_bank(limit: int = 5, status: str = "не снято") -> list[dict]:
    """Get ideas from bank filtered by status. Returns list of dicts with row number."""
    retries = 3
    for attempt in range(retries):
        try:
            ws = _get_or_create_idea_bank_ws()
            all_values = ws.get_all_values()

            if len(all_values) <= 1:
                return []

            results = []
            for i, row in enumerate(all_values[1:], start=2):
                if len(row) < 6:
                    continue
                row_status = row[5].strip().lower()
                if status and row_status != status.lower():
                    continue
                results.append({
                    "row": i,
                    "num": row[0],
                    "date": row[1],
                    "theme": row[2],
                    "hook": row[3],
                    "format": row[4],
                    "status": row[5],
                })

            # Return last N (most recent)
            return results[-limit:] if limit else results

        except Exception as e:
            logger.error(f"Error reading idea bank (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                import time
                time.sleep(5)
    return []


def update_idea_bank_status(row: int, status: str) -> bool:
    """Update the status of an idea in the bank."""
    retries = 3
    for attempt in range(retries):
        try:
            ws = _get_or_create_idea_bank_ws()
            ws.update(range_name=f"F{row}", values=[[status]])
            logger.info(f"Updated idea bank row {row} status to: {status}")
            return True

        except Exception as e:
            logger.error(f"Error updating idea bank (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                import time
                time.sleep(5)
    return False


# --- Weekly Report Data ---

def get_weekly_report_data() -> dict:
    """Collect data for the weekly content report (last 7 days)."""
    now = datetime.now(MSK)
    week_ago = now - timedelta(days=7)

    data = {
        "videos_shot": 0,
        "total_views": 0,
        "best_video_theme": "",
        "best_video_views": 0,
        "insta_followers_start": 0,
        "insta_followers_end": 0,
        "insta_growth": 0,
        "tg_followers_start": 0,
        "tg_followers_end": 0,
        "tg_growth": 0,
    }

    try:
        spreadsheet = _get_spreadsheet()

        # 1. Scenarios — videos shot this week
        try:
            ws = spreadsheet.worksheet("Сценарии")
            all_rows = ws.get_all_values()
            for row in all_rows[1:]:
                if len(row) < 10:
                    continue
                status = row[6].strip().lower() if len(row) > 6 else ""
                if status != "снято":
                    continue
                try:
                    row_date = datetime.strptime(row[1], "%d.%m.%Y").replace(tzinfo=MSK)
                except Exception:
                    continue
                if row_date < week_ago:
                    continue

                data["videos_shot"] += 1

                views = 0
                try:
                    views = int(row[9]) if row[9] else 0
                except (ValueError, IndexError):
                    pass
                data["total_views"] += views

                if views > data["best_video_views"]:
                    data["best_video_views"] = views
                    data["best_video_theme"] = row[3] if len(row) > 3 else ""
        except gspread.WorksheetNotFound:
            pass

        # 2. Analytics — Instagram followers
        try:
            ws = spreadsheet.worksheet("Аналитика")
            all_rows = ws.get_all_values()
            week_rows = []
            for row in all_rows[1:]:
                if len(row) < 3:
                    continue
                try:
                    row_date = datetime.strptime(row[0], "%d.%m.%Y").replace(tzinfo=MSK)
                except Exception:
                    continue
                if row_date >= week_ago:
                    week_rows.append(row)
            if week_rows:
                try:
                    data["insta_followers_start"] = int(week_rows[0][2]) if week_rows[0][2] else 0
                except (ValueError, IndexError):
                    pass
                try:
                    data["insta_followers_end"] = int(week_rows[-1][2]) if week_rows[-1][2] else 0
                except (ValueError, IndexError):
                    pass
                data["insta_growth"] = data["insta_followers_end"] - data["insta_followers_start"]
        except gspread.WorksheetNotFound:
            pass

        # 3. TG Channel — TG followers
        try:
            ws = spreadsheet.worksheet("ТГ Канал")
            all_rows = ws.get_all_values()
            week_rows = []
            for row in all_rows[1:]:
                if len(row) < 2:
                    continue
                try:
                    row_date = datetime.strptime(row[0], "%d.%m.%Y").replace(tzinfo=MSK)
                except Exception:
                    continue
                if row_date >= week_ago:
                    week_rows.append(row)
            if week_rows:
                try:
                    data["tg_followers_start"] = int(week_rows[0][1]) if week_rows[0][1] else 0
                except (ValueError, IndexError):
                    pass
                try:
                    data["tg_followers_end"] = int(week_rows[-1][1]) if week_rows[-1][1] else 0
                except (ValueError, IndexError):
                    pass
                data["tg_growth"] = data["tg_followers_end"] - data["tg_followers_start"]
        except gspread.WorksheetNotFound:
            pass

    except Exception as e:
        logger.error(f"Error collecting weekly report data: {e}")

    return data
