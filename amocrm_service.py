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
    AMO_PURCHASE_ITEMS_FIELD_ID,
    AMO_PURCHASE_TOTAL_FIELD_ID,
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


def _find_cf_block_by_id(entity: Dict[str, Any], field_id: int) -> Optional[Dict[str, Any]]:
    for cf in entity.get("custom_fields_values") or []:
        if cf.get("field_id") == field_id:
            return cf
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
        logger.error(f"amo.contact.error contact_id={contact_id} error={e}")
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


def _extract_items_from_purchase_element(raw_element: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not AMO_PURCHASE_ITEMS_FIELD_ID:
        return items
    block = _find_cf_block_by_id(raw_element, AMO_PURCHASE_ITEMS_FIELD_ID)
    if not block:
        return items
    values = block.get("values") or []
    for idx, v in enumerate(values):
        obj = v.get("value") or {}
        name = obj.get("description") or f"Товар {idx + 1}"
        unit_price = obj.get("unit_price")
        quantity = obj.get("quantity") or 1
        try:
            price_dec = Decimal(str(unit_price).replace(",", "."))
        except Exception:
            price_dec = Decimal("0")
        try:
            qty_dec = Decimal(str(quantity))
        except Exception:
            qty_dec = Decimal("1")
        if price_dec <= 0 or qty_dec <= 0:
            continue
        items.append(
            {
                "name": name,
                "quantity": qty_dec,
                "price": price_dec,
            }
        )
    return items


def load_lead_with_details(lead_id: int) -> Dict[str, Any]:
    logger.info(f"amocrm.load_lead start lead_id={lead_id}")
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
        items = _extract_items_from_purchase_element(raw_element)
        if items:
            purchases.extend(items)
        else:
            price = _extract_price_from_purchase(raw_element)
            qty = p.get("quantity") or 1
            try:
                qty_dec = Decimal(str(qty))
            except Exception:
                qty_dec = Decimal("1")
            purchases.append(
                {
                    "name": p.get("name") or "Товар",
                    "quantity": qty_dec,
                    "price": price,
                }
            )
    logger.info(
        "amocrm.load_lead done "
        f"lead_id={lead_id} status_value={status_value} discount={discount} "
        f"checkbox_status={checkbox_status_value} email={email} ttn={ttn_value} "
        f"purchases_elements={len(purchases_raw)} purchases_flat={len(purchases)}"
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
    logger.info(f"amocrm.status.check status_value={value} target={AMO_STATUS_TARGET}")
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
    logger.info(f"amocrm.checkbox_status.check value={value_lower}")
    return value_lower.startswith("ok:") or value_lower.startswith("error:")


def set_checkbox_status(lead_id: int, text: str) -> None:
    if not AMO_FIELD_CHECKBOX_STATUS:
        return
    logger.info(f"amocrm.checkbox_status.set lead_id={lead_id} text={text}")
    try:
        update_lead_custom_field(lead_id, AMO_FIELD_CHECKBOX_STATUS, text)
    except AmoApiError as e:
        logger.error(f"amocrm.checkbox_status.error lead_id={lead_id} error={e} text={text}")
