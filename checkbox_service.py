import logging
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from config import MONEY_QUANT
from checkbox_api import (
    sign_in_for_profile,
    ensure_shift_for_profile,
    create_sell_receipt_for_profile,
)

logger = logging.getLogger("checkbox_service")


def to_minor(amount: Decimal) -> int:
    if amount is None:
        return 0
    try:
        value = Decimal(amount).quantize(MONEY_QUANT)
    except Exception:
        value = Decimal("0")
    return max(0, int(value * 100))


def line_total_minor(price_minor: int, quantity: Decimal) -> int:
    try:
        q = Decimal(quantity)
    except Exception:
        q = Decimal("0")
    if q <= 0:
        return 0
    q1000 = int((q * 1000).to_integral_value())
    return max(0, price_minor * q1000 // 1000)


def build_goods_and_sum(purchases: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    goods: List[Dict[str, Any]] = []
    total_minor = 0
    for idx, p in enumerate(purchases):
        name = p.get("name") or f"Товар {idx + 1}"
        quantity = p.get("quantity") or 1
        price = p.get("price") or Decimal("0")
        price_minor = to_minor(price)
        if price_minor <= 0 or quantity <= 0:
            continue
        sum_minor = line_total_minor(price_minor, Decimal(str(quantity)))
        total_minor += sum_minor
        goods.append(
            {
                "good": {
                    "code": str(idx + 1),
                    "name": name,
                    "price": price_minor,
                    "tax": [8],
                },
                "quantity": int((Decimal(str(quantity)) * 1000).to_integral_value()),
                "is_return": False,
            }
        )
    return goods, total_minor


def create_receipt_for_lead_data(lead_data: Dict[str, Any], profile_id: str) -> Dict[str, Any]:
    purchases = lead_data.get("purchases") or []
    email = lead_data.get("email")
    discount = lead_data.get("discount") or Decimal("0")
    goods, total_minor = build_goods_and_sum(purchases)
    if not goods or total_minor <= 0:
        return {"receipt_id": "", "receipt_number": "", "error": "no goods or zero total"}
    discount_minor = to_minor(discount)
    if discount_minor > total_minor:
        discount_minor = total_minor
    token = sign_in_for_profile(profile_id)
    ensure_shift_for_profile(token, profile_id)
    logger.debug(
        "checkbox.create_receipt.start",
        extra={
            "lead_id": lead_data.get("id"),
            "profile_id": profile_id,
            "total_minor": total_minor,
            "discount_minor": discount_minor,
        },
    )
    data = create_sell_receipt_for_profile(token, profile_id, goods, total_minor, discount_minor, email=email)
    if isinstance(data, dict):
        receipt_id = str(data.get("id") or data.get("receipt_id") or "")
        number = str(data.get("fiscal_code") or data.get("number") or "")
    else:
        receipt_id = ""
        number = ""
    logger.debug(
        "checkbox.create_receipt.done",
        extra={"lead_id": lead_data.get("id"), "profile_id": profile_id, "receipt_id": receipt_id, "number": number},
    )
    return {"receipt_id": receipt_id, "receipt_number": number, "raw": data}
