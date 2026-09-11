from __future__ import annotations
import requests
from .models import Offer

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, offer: Offer, desired_quantity: int = 120):
        if not self.configured:
            print("[TELEGRAM] not configured; skipping notification")
            return False
        per = offer.price_per_can or offer.price_total
        est = per * desired_quantity if per is not None else None
        stock = "✅ в наявності" if offer.in_stock else "❓ наявність не підтверджена"
        cod = "✅ післяплата" if offer.cod else "❓ післяплата не підтверджена"
        lines = [
            "🥤 <b>Знайдена Coca-Cola</b>",
            f"<b>{offer.title}</b>",
            f"💵 {per:.2f} грн/банка" if per is not None else "💵 ціна невідома",
            f"📦 {offer.units_in_offer} шт у пропозиції" if offer.units_in_offer > 1 else "📦 поштучно/не визначено",
            stock,
            cod,
            f"🧮 {desired_quantity} шт ≈ {est:.0f} грн" if est is not None else "",
            f"🏪 {offer.domain}",
            f"🔗 {offer.url}",
            f"🎯 confidence {offer.confidence:.2f}",
        ]
        text = "\n".join(x for x in lines if x)
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        r = requests.post(url, data={
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=20)
        r.raise_for_status()
        return True
