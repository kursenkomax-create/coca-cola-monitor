from __future__ import annotations
import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str | None = None) -> dict:
    load_dotenv(ROOT / ".env")
    cfg_path = Path(path) if path else ROOT / "config.yaml"
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["telegram"] = {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID", "").strip(),
    }
    return cfg
