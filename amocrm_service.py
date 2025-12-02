import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from config import (
    AMO_FIELD_DISCOUNT,
    AMO_FIELD_STATUS,
    AMO_FIELD_CHECKBOX_STATUS,
    AMO_STATUS_TARGET,
    AMO_PURCHASE_PRICE_FIELD_ID,
    AMO_FIELD_TTN,
)
from amocrm_client import (
    AmoApiError,
    get_contact,
    get_lead,
    get_purchases_for_lead,
    update_lead_custom_field,
)

logger = logging.getLogger("amocrm_service")


def _find_cf_value_by_id(entity: Dict[str, Any], field_id: int) -> Optional[Any]:
    for cf in entity.get("custom_fields_values") or []:
        if cf.get("field_id") == field_id:
            values = cf.get("values") or []
            if values:
                return values[0].get("value")
    return None


def _find_cf_value_by_code(entity: Dict[str, Any], code: str) -> Optional[Any]:
    code_lower = code.lower()
    for cf in entity.get("custom_fields_values") or []:
        field_code = str(cf.get("field_code") or "").lower()
        if field_code == code_lower:
            values = cf.get("values") or []
            if values:
                return values[0].get("value")
    return None


def _extract_email_from_contact(contact: Dict[str, Any]) -> Optional[str]:
    for cf in contact.get("custom_fields_values") or []:
        field_code = str(cf.get("field_code") or "").lower()
        if field_code == "email":
            values = cf.get("values") or []
            if values:
                email = values[0].get("value")
                if email:
                    return str(email)
    return None


def _extract_email_from_lead(lead: Dict[str, Any]) -> Optional[str]:
    embedded = lead.get("_embedded") or {}
    contacts = embedded.get("contacts") or []
    if not contacts:
        return None
    contact_id = contacts[0].get("id")
    if not contact_id:
        return None
    try:
        contact = get_contact(contact_id)
    except AmoApiError as e:
        logger.error("amo.contact.error", extra={"contact_id": contact_id, "error": str(e)})
        return None
    return _extract_email_from_contact(contact)


def _extract_price_from_purchase(raw_element: Dict[str, Any]) -> Decimal:
    if AMO_PURCHASE_PRICE_FIELD_ID:
        v = _find_cf_value_by_id(raw_element, AMO_PURCHASE_PRICE_FIELD_ID)
        if v is not None:
            try:
                return Decimal(str(v).replace(",", "."))
            except Exception:
                return Decimal("0")
    for code in ("PRICE", "price"):
        v = _find_cf_value_by_code(raw_element, code)
        if v is not None:
            try:
                return Decimal(str(v).replace(",", "."))
            except Exception:
                return Decimal("0")
    return Decimal("0")


def load_lead_with_details(lead_id: int) -> Dict[str, Any]:
    lead = get_lead(lead_id)
    status_value = _find_cf_value_by_id(lead, AMO_FIELD_STATUS)
    discount_raw = _find_cf_value_by_id(lead, AMO_FIELD_DISCOUNT)
    checkbox_status_value = None
    if AMO_FIELD_CHECKBOX_STATUS:
        checkbox_status_value = _find_cf_value_by_id(lead, AMO_FIELD_CHECKBOX_STATUS)
    ttn_value = _find_cf_value_by_id(lead, AMO_FIELD_TTN)
    discount = Decimal("0")
    if discount_raw not in (None, ""):
        try:
            discount = Decimal(str(discount_raw).replace(",", "."))
        except Exception:
            discount = Decimal("0")
    email = _extract_email_from_lead(lead)
    purchases_raw = get_purchases_for_lead(lead_id)
    purchases: List[Dict[str, Any]] = []
    for p in purchases_raw:
        raw_element = p.get("raw_element") or {}
        price = _extract_price_from_purchase(raw_element)
        qty = p.get("quantity") or 1
        purchases.append(
            {
                "name": p.get("name") or "Товар",
                "quantity": qty,
                "price": price,
            }
        )
    return {
        "id": lead_id,
        "lead": lead,
        "status_value": status_value,
        "discount": discount,
        "checkbox_status": checkbox_status_value,
        "email": email,
        "purchases": purchases,
        "ttn": ttn_value,
    }


def is_target_status(lead_data: Dict[str, Any]) -> bool:
    value = lead_data.get("status_value")
    if value is None:
        return False
    return str(value).strip() == AMO_STATUS_TARGET


def is_already_processed(lead_data: Dict[str, Any]) -> bool:
    if not AMO_FIELD_CHECKBOX_STATUS:
        return False
    value = lead_data.get("checkbox_status") or ""
    if not isinstance(value, str):
        value = str(value)
    value_lower = value.lower()
    return value_lower.startswith("ok:") or value_lower.startswith("error:")


def set_checkbox_status(lead_id: int, text: str) -> None:
    if not AMO_FIELD_CHECKBOX_STATUS:
        return
    try:
        update_lead_custom_field(lead_id, AMO_FIELD_CHECKBOX_STATUS, text)
    except AmoApiError as e:
        logger.error(
            "amo.checkbox_status.error",
            extra={"lead_id": lead_id, "error": str(e), "text": text},
        )
