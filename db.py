from __future__ import annotations
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from .models import Offer

class DB:
    def __init__(self, path: str | Path):
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(db_path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            url TEXT PRIMARY KEY,
            product_id TEXT,
            last_seen TEXT,
            last_state TEXT,
            last_notified TEXT
        )
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            url TEXT PRIMARY KEY,
            discovered_at TEXT,
            last_checked TEXT
        )
        """)
        self.conn.commit()

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    def add_candidates(self, urls: list[str]):
        now = self.now()
        self.conn.executemany(
            "INSERT OR IGNORE INTO candidates(url, discovered_at, last_checked) VALUES (?, ?, NULL)",
            [(u, now) for u in urls]
        )
        self.conn.commit()

    def get_candidates(self, limit: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT url FROM candidates ORDER BY COALESCE(last_checked, '') ASC, discovered_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [r["url"] for r in rows]

    def mark_checked(self, url: str):
        self.conn.execute("UPDATE candidates SET last_checked=? WHERE url=?", (self.now(), url))
        self.conn.commit()

    def get_offer_row(self, url: str):
        return self.conn.execute("SELECT * FROM offers WHERE url=?", (url,)).fetchone()

    def upsert_offer(self, offer: Offer):
        state = json.dumps(offer.to_dict(), ensure_ascii=False, sort_keys=True)
        self.conn.execute("""
        INSERT INTO offers(url, product_id, last_seen, last_state, last_notified)
        VALUES (?, ?, ?, ?, NULL)
        ON CONFLICT(url) DO UPDATE SET
            product_id=excluded.product_id,
            last_seen=excluded.last_seen,
            last_state=excluded.last_state
        """, (offer.url, offer.product_id, self.now(), state))
        self.conn.commit()

    def set_notified(self, url: str):
        self.conn.execute("UPDATE offers SET last_notified=? WHERE url=?", (self.now(), url))
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
