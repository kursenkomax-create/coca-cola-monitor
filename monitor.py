from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import os
from .discovery import discover_urls
from .fetchers import Fetcher
from .parser import parse_offer
from .db import DB
from .notifier import TelegramNotifier

ROOT = Path(__file__).resolve().parent.parent

class Monitor:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        mon = cfg["monitor"]
        default_db = "/data/monitor.db" if Path("/data").exists() else str(ROOT / "monitor.db")
        db_path = os.getenv("MONITOR_DB_PATH", default_db)
        self.db = DB(db_path)
        print(f"[DB] {db_path}")
        self.fetcher = Fetcher(
            timeout=mon.get("request_timeout_seconds", 20),
            domain_delay=mon.get("domain_delay_seconds", 2.0),
            use_playwright=mon.get("use_playwright_fallback", True),
        )
        tg = cfg.get("telegram", {})
        self.notifier = TelegramNotifier(tg.get("bot_token", ""), tg.get("chat_id", ""))
        self.cycle = 0


    def close(self):
        self.db.close()

    def _product_limits(self):
        return {p["id"]: p.get("max_price_per_can", self.cfg["filters"]["max_price_per_can"])
                for p in self.cfg.get("products", []) if p.get("enabled", True)}

    def _matches(self, offer):
        f = self.cfg["filters"]
        limits = self._product_limits()
        if offer.product_id not in limits:
            return False, "product disabled/unknown"
        if offer.price_per_can is None:
            return False, "no price"
        if offer.price_per_can > float(limits[offer.product_id]):
            return False, "price too high"
        if offer.currency not in ("UAH", "UAH.", "₴"):
            return False, "currency"
        if f.get("require_in_stock", True) and offer.in_stock is not True:
            return False, "stock not confirmed"
        if f.get("require_cod", True) and offer.cod is not True:
            return False, "cod not confirmed"
        if offer.confidence < float(f.get("min_confidence", 0.58)):
            return False, "low confidence"
        return True, "ok"

    @staticmethod
    def _state(row):
        if not row or not row["last_state"]:
            return None
        try:
            return json.loads(row["last_state"])
        except Exception:
            return None

    def _should_notify(self, offer, previous_row) -> bool:
        ncfg = self.cfg.get("notifications", {})
        prev = self._state(previous_row)
        if prev is None:
            return ncfg.get("notify_on_first_match", True)
        old_price = prev.get("price_per_can")
        if ncfg.get("notify_on_price_drop", True) and old_price and offer.price_per_can and offer.price_per_can < old_price - 0.01:
            return True
        if ncfg.get("notify_on_back_in_stock", True) and prev.get("in_stock") is not True and offer.in_stock is True:
            return True
        if ncfg.get("notify_on_cod_becomes_available", True) and prev.get("cod") is not True and offer.cod is True:
            return True
        # periodic reminder if still valid
        if previous_row and previous_row["last_notified"]:
            try:
                last = datetime.fromisoformat(previous_row["last_notified"])
                hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
                return hours >= float(ncfg.get("repeat_after_hours", 24))
            except Exception:
                pass
        return False

    def discover(self):
        queries = []
        for p in self.cfg.get("products", []):
            if p.get("enabled", True):
                queries.extend(p.get("discovery_queries", []))
        urls = list(self.cfg.get("seed_urls", []))
        if queries:
            urls += discover_urls(queries, self.cfg["monitor"].get("max_search_results_per_query", 20))
        dedup = list(dict.fromkeys(urls))
        self.db.add_candidates(dedup)
        print(f"[DISCOVERY] candidates total/new batch: {len(dedup)}")

    def run_once(self):
        self.cycle += 1
        every = int(self.cfg["monitor"].get("discovery_every_cycles", 3))
        if self.cycle == 1 or self.cycle % every == 0:
            self.discover()

        limit = int(self.cfg["monitor"].get("max_candidates_per_cycle", 120))
        urls = self.db.get_candidates(limit)
        print(f"[MONITOR] checking {len(urls)} URLs")
        for idx, url in enumerate(urls, 1):
            try:
                print(f"[{idx}/{len(urls)}] {url}")
                html, source = self.fetcher.fetch(url)
                self.db.mark_checked(url)
                offer = parse_offer(url, html, source)
                if not offer:
                    continue
                previous = self.db.get_offer_row(url)
                matched, reason = self._matches(offer)
                print(f"  -> {offer.product_id} price={offer.price_per_can} stock={offer.in_stock} cod={offer.cod} conf={offer.confidence:.2f} [{reason}]")
                self.db.upsert_offer(offer)
                if matched and self._should_notify(offer, previous):
                    if self.notifier.send(offer, int(self.cfg["filters"].get("desired_quantity", 120))):
                        self.db.set_notified(url)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[ERROR] {url}: {e}")
