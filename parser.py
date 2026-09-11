from __future__ import annotations
import json
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from .models import Offer

PRICE_RE = re.compile(r"(?<!\d)(\d{1,4}(?:[\s\u00a0]\d{3})*(?:[.,]\d{1,2})?)\s*(?:грн|₴|UAH)", re.I)
PACK_PATTERNS = [
    re.compile(r"(?:упаковк\w*|ящик\w*|pack|уп\.?)[^\d]{0,10}(\d{1,3})\s*(?:шт|бан)", re.I),
    re.compile(r"(\d{1,3})\s*[xх×]\s*0[.,]33\s*(?:л)?", re.I),
    re.compile(r"0[.,]33\s*(?:л)?\s*[xх×]\s*(\d{1,3})", re.I),
]

POS_COD = [
    "післяплата", "післяплат", "накладений платіж", "наложений платіж",
    "оплата при отриманні", "оплата під час отримання", "cash on delivery", "cod"
]
NEG_COD = [
    "без післяплати", "післяплата недоступна", "післяплати немає",
    "накладений платіж недоступний", "тільки передплата", "100% передплата"
]
POS_STOCK = ["в наявності", "є в наявності", "готово до відправки", "available", "instock"]
NEG_STOCK = ["немає в наявності", "немає на складі", "закінчився", "out of stock", "outofstock", "sold out"]


def _num(v) -> float | None:
    if v is None:
        return None
    try:
        s = str(v).replace("\u00a0", " ").replace(" ", "").replace(",", ".")
        return float(re.sub(r"[^0-9.]", "", s))
    except Exception:
        return None


def _flatten_jsonld(node):
    if isinstance(node, list):
        for x in node:
            yield from _flatten_jsonld(x)
    elif isinstance(node, dict):
        if "@graph" in node:
            yield from _flatten_jsonld(node["@graph"])
        yield node


def _offer_from_jsonld(soup: BeautifulSoup):
    best = None
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        txt = script.string or script.get_text(" ", strip=True)
        if not txt:
            continue
        try:
            data = json.loads(txt)
        except Exception:
            continue
        for obj in _flatten_jsonld(data):
            typ = obj.get("@type")
            types = typ if isinstance(typ, list) else [typ]
            if not any(str(t).lower() == "product" for t in types if t):
                continue
            title = str(obj.get("name") or "")
            offers = obj.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = _num(offers.get("price") or offers.get("lowPrice"))
            currency = str(offers.get("priceCurrency") or "UAH")
            availability = str(offers.get("availability") or "")
            cand = (title, price, currency, availability)
            if price is not None:
                return cand
            best = best or cand
    return best


def _text_stock(text: str) -> bool | None:
    low = text.lower()
    for x in NEG_STOCK:
        if x in low:
            return False
    for x in POS_STOCK:
        if x in low:
            return True
    return None


def _text_cod(text: str) -> bool | None:
    low = text.lower()
    for x in NEG_COD:
        if x in low:
            return False
    for x in POS_COD:
        if x in low:
            return True
    return None


def _pack_size(text: str) -> int:
    for pat in PACK_PATTERNS:
        m = pat.search(text)
        if m:
            try:
                n = int(m.group(1))
                if 1 <= n <= 120:
                    return n
            except Exception:
                pass
    return 1


def _classify_product(text: str) -> str | None:
    t = text.lower().replace(",", ".")
    if "coca" not in t or "cola" not in t:
        return None
    if not re.search(r"0\.33|330\s*мл|330ml", t):
        return None
    is_zero = any(k in t for k in ["zero", "зеро", "без цукру", "без сахара", "no sugar"])
    return "coca_zero_033" if is_zero else "coca_classic_033"


def parse_offer(url: str, html: str, source: str = "") -> Offer | None:
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(" ", strip=True) if soup.title else "")
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True) or title
    visible = soup.get_text(" ", strip=True)
    combined = (title + " " + visible)[:500000]
    product_id = _classify_product(combined)
    if not product_id:
        return None

    price = None
    currency = "UAH"
    raw_avail = ""
    structured = _offer_from_jsonld(soup)
    structured_hit = False
    if structured:
        st_title, st_price, st_currency, raw_avail = structured
        if st_title and len(st_title) > len(title):
            title = st_title
        if st_price is not None:
            price = st_price
            structured_hit = True
        currency = st_currency or currency

    if price is None:
        # prefer nearby product price/meta tags before broad text regex
        candidates = []
        for attrs in [
            {"itemprop": "price"}, {"property": "product:price:amount"},
            {"name": "price"}, {"data-price": True}
        ]:
            for tag in soup.find_all(attrs=attrs):
                val = tag.get("content") or tag.get("data-price") or tag.get_text(" ", strip=True)
                n = _num(val)
                if n is not None:
                    candidates.append(n)
        if candidates:
            realistic = [x for x in candidates if 5 <= x <= 10000]
            if realistic:
                price = min(realistic)
        if price is None:
            vals = [_num(m.group(1)) for m in PRICE_RE.finditer(combined)]
            vals = [x for x in vals if x is not None and 5 <= x <= 10000]
            if vals:
                price = min(vals)

    pack_size = _pack_size(title + " " + visible[:8000])
    price_per_can = (price / pack_size) if (price is not None and pack_size > 0) else None

    in_stock = None
    alow = raw_avail.lower()
    if alow:
        if "instock" in alow or alow.endswith("/in_stock"):
            in_stock = True
        elif "outofstock" in alow or "soldout" in alow:
            in_stock = False
    if in_stock is None:
        in_stock = _text_stock(visible[:50000])

    cod = _text_cod(visible[:100000])

    confidence = 0.30
    if product_id: confidence += 0.20
    if price is not None: confidence += 0.18
    if structured_hit: confidence += 0.12
    if in_stock is not None: confidence += 0.08
    if cod is not None: confidence += 0.07
    if pack_size > 1: confidence += 0.05
    confidence = min(confidence, 1.0)

    return Offer(
        url=url,
        domain=urlparse(url).netloc.lower().removeprefix("www."),
        title=title[:300],
        product_id=product_id,
        price_total=price,
        units_in_offer=pack_size,
        price_per_can=price_per_can,
        currency=currency.upper(),
        in_stock=in_stock,
        cod=cod,
        confidence=confidence,
        source=source,
        raw_availability=raw_avail,
    )
