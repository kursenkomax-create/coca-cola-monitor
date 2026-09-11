from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Offer:
    url: str
    domain: str
    title: str = ""
    product_id: Optional[str] = None
    price_total: Optional[float] = None
    units_in_offer: int = 1
    price_per_can: Optional[float] = None
    currency: str = "UAH"
    in_stock: Optional[bool] = None
    cod: Optional[bool] = None
    stock_quantity: Optional[int] = None
    confidence: float = 0.0
    source: str = ""
    raw_availability: str = ""

    def to_dict(self):
        return asdict(self)
