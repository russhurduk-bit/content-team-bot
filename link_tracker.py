"""
UTM Link Tracker — redirect server with click analytics.
FastAPI on port 8612. SQLite storage.
"""

import os
import sqlite3
import string
import random
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
import uvicorn
import aiohttp

logger = logging.getLogger("link_tracker")
logging.basicConfig(level=logging.INFO)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "links.db")
SERVER_IP = os.environ.get("LINK_TRACKER_HOST", "127.0.0.1")
SERVER_PORT = 8612

MSK = timezone(timedelta(hours=3))

app = FastAPI(title="Link Tracker", docs_url=None, redoc_url=None)


# --- Database ---

def _init_db():
    """Create tables if they don't exist."""
    with _get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                destination TEXT NOT NULL,
                source TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_id INTEGER NOT NULL,
                clicked_at TEXT NOT NULL,
                referrer TEXT DEFAULT '',
                country TEXT DEFAULT '',
                ip TEXT DEFAULT '',
                FOREIGN KEY (link_id) REFERENCES links(id)
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_clicks_link_id ON clicks(link_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_clicks_clicked_at ON clicks(clicked_at)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_links_code ON links(code)")


@contextmanager
def _get_db():
    """Get a database connection with WAL mode."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# --- Link Management ---

def _generate_code(length: int = 6) -> str:
    """Generate a random short code."""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=length))


def create_tracked_link(destination: str, source: str = "") -> dict:
    """
    Create a tracked redirect link.
    Returns {"code": "abc123", "url": "http://IP:8612/r/abc123", "id": 1}
    """
    code = _generate_code()
    now = datetime.now(MSK).isoformat()

    with _get_db() as db:
        # Ensure code is unique
        for _ in range(10):
            existing = db.execute("SELECT id FROM links WHERE code = ?", (code,)).fetchone()
            if not existing:
                break
            code = _generate_code()

        db.execute(
            "INSERT INTO links (code, destination, source, created_at) VALUES (?, ?, ?, ?)",
            (code, destination, source, now)
        )
        link_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    url = f"http://{SERVER_IP}:{SERVER_PORT}/r/{code}"
    return {"code": code, "url": url, "id": link_id}


def get_link_by_source(source: str) -> dict | None:
    """Get existing link by source identifier."""
    with _get_db() as db:
        row = db.execute("SELECT * FROM links WHERE source = ?", (source,)).fetchone()
        if row:
            return dict(row)
    return None


def get_click_stats(link_id: int = None, code: str = None) -> dict:
    """Get click statistics for a link."""
    with _get_db() as db:
        if code and not link_id:
            row = db.execute("SELECT id FROM links WHERE code = ?", (code,)).fetchone()
            if not row:
                return {"total": 0, "today": 0, "countries": {}}
            link_id = row["id"]

        if not link_id:
            return {"total": 0, "today": 0, "countries": {}}

        total = db.execute(
            "SELECT COUNT(*) as cnt FROM clicks WHERE link_id = ?", (link_id,)
        ).fetchone()["cnt"]

        today_start = datetime.now(MSK).replace(hour=0, minute=0, second=0).isoformat()
        today = db.execute(
            "SELECT COUNT(*) as cnt FROM clicks WHERE link_id = ? AND clicked_at >= ?",
            (link_id, today_start)
        ).fetchone()["cnt"]

        countries = {}
        rows = db.execute(
            "SELECT country, COUNT(*) as cnt FROM clicks WHERE link_id = ? GROUP BY country ORDER BY cnt DESC LIMIT 10",
            (link_id,)
        ).fetchall()
        for r in rows:
            countries[r["country"] or "unknown"] = r["cnt"]

        return {"total": total, "today": today, "countries": countries}


def get_all_links_stats(limit: int = 20) -> list[dict]:
    """Get stats for all recent links."""
    with _get_db() as db:
        links = db.execute(
            "SELECT * FROM links ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()

        results = []
        for link in links:
            stats = get_click_stats(link_id=link["id"])
            results.append({
                "id": link["id"],
                "code": link["code"],
                "source": link["source"],
                "destination": link["destination"][:80],
                "created_at": link["created_at"],
                "clicks": stats["total"],
                "today": stats["today"],
                "top_country": max(stats["countries"], key=stats["countries"].get) if stats["countries"] else "-",
            })
        return results


def get_clicks_for_source(source: str) -> int:
    """Get total click count for a link by source name."""
    with _get_db() as db:
        row = db.execute(
            """SELECT COUNT(*) as cnt FROM clicks c
               JOIN links l ON c.link_id = l.id
               WHERE l.source = ?""",
            (source,)
        ).fetchone()
        return row["cnt"] if row else 0


# --- Geo-IP (free, no key) ---

async def _get_country(ip: str) -> str:
    """Get country from IP using free ip-api.com."""
    if not ip or ip.startswith("127.") or ip.startswith("10.") or ip == "::1":
        return "local"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ip-api.com/json/{ip}?fields=countryCode",
                timeout=aiohttp.ClientTimeout(total=3)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("countryCode", "??")
    except Exception:
        pass
    return "??"


# --- FastAPI Routes ---

@app.on_event("startup")
async def startup():
    _init_db()
    logger.info(f"Link Tracker started on port {SERVER_PORT}")


@app.get("/r/{code}")
async def redirect(code: str, request: Request):
    """Redirect and log click."""
    with _get_db() as db:
        link = db.execute("SELECT * FROM links WHERE code = ?", (code,)).fetchone()

    if not link:
        return JSONResponse({"error": "link not found"}, status_code=404)

    # Get client IP
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not ip:
        ip = request.client.host if request.client else ""

    referrer = request.headers.get("referer", "")
    now = datetime.now(MSK).isoformat()

    # Log click asynchronously (don't block redirect)
    async def _log_click():
        country = await _get_country(ip)
        with _get_db() as db:
            db.execute(
                "INSERT INTO clicks (link_id, clicked_at, referrer, country, ip) VALUES (?, ?, ?, ?, ?)",
                (link["id"], now, referrer[:500], country, ip[:45])
            )

    asyncio.create_task(_log_click())

    return RedirectResponse(url=link["destination"], status_code=302)


@app.get("/stats")
async def stats():
    """Quick stats endpoint."""
    return get_all_links_stats()


@app.get("/health")
async def health():
    return {"status": "ok"}


# --- Entry point ---

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT, log_level="info")
