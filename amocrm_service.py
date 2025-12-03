import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

import requests

from config import (
    AMO_BASE_URL,
    AMO_ACCESS_TOKEN,
    AMO_FIELD_DISCOUNT,
    AMO_FIELD_STATUS,
    AMO_FIELD_CHECKBOX_STATUS,
    AMO_STATUS_TARGET,
    AMO_FIELD_TTN,
    AMO_PURCHASES_CATALOG_ID,
    AMO_PURCHASE_ITEMS_FIELD_ID,
    AMO_PURCHASE_TOTAL_FIELD_ID,
)
from amocrm_client import (
    AmoApiError,
    get_contact,
    get_lead,
    update_lead_custom_field,
)

logger = logging.getLogger("amocrm_service")


def _amo_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {AMO_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _find_cf_value_by_id(entity: Dict[str, Any], field_id: int) -> Optional[Any]:
    for cf in entity.get("custom_fields_values") or []:
        if cf.get("field_id") == field_id:
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


def _fetch_purchase_element_ids_for_lead(lead_id: int) -> List[int]:
    url = f"{AMO_BASE_URL}/api/v4/leads/{lead_id}/links"
    logger.info(f"amo.purchases.links.get start lead_id={lead_id} url={url}")
    resp = requests.get(url, headers=_amo_headers(), params={"limit": 250}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    links = (data.get("_embedded") or {}).get("links") or []
    ids: List[int] = []
    for link in links:
        if link.get("to_entity_type") != "catalog_elements":
            continue
        md = link.get("metadata") or {}
        catalog_id = md.get("catalog_id")
        try:
            catalog_id_int = int(catalog_id)
        except Exception:
            catalog_id_int = 0
        if catalog_id_int != AMO_PURCHASES_CATALOG_ID:
            continue
        eid = link.get("to_entity_id")
        if not eid:
            continue
        try:
            ids.append(int(eid))
        except Exception:
            continue
    logger.info(f"amo.purchases.links.done lead_id={lead_id} ids={ids}")
    return ids


def _fetch_catalog_elements(ids: List[int]) -> List[Dict[str, Any]]:
    if not ids:
        return []
    elements: List[Dict[str, Any]] = []
    url = f"{AMO_BASE_URL}/api/v4/catalogs/{AMO_PURCHASES_CATALOG_ID}/elements"
    chunk_size = 40
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        params = [("filter[id][]", str(x)) for x in chunk]
        logger.info(f"amo.purchases.elements.get chunk ids={chunk}")
        resp = requests.get(url, headers=_amo_headers(), params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        els = (data.get("_embedded") or {}).get("elements") or []
        logger.info(f"amo.purchases.elements.chunk_done count={len(els)}")
        elements.extend(els)
    logger.info(f"amo.purchases.elements.total count={len(elements)}")
    return elements


def _extract_items_from_catalog_element(element: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    cfs = element.get("custom_fields_values") or []
    block = None
    for cf in cfs:
        if cf.get("field_id") == AMO_PURCHASE_ITEMS_FIELD_ID:
            block = cf
            break
    if not block:
        logger.info(
            f"amo.purchases.element.no_items_field element_id={element.get('id')} "
            f"items_field_id={AMO_PURCHASE_ITEMS_FIELD_ID}"
        )
        return items
    values = block.get("values") or []
    logger.info(
        f"amo.purchases.element.items_field element_id={element.get('id')} raw_values_len={len(values)}"
    )
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
        logger.info(
            f"amo.purchases.element.item_raw element_id={element.get('id')} idx={idx} "
            f"name={name} unit_price={unit_price} quantity={quantity} price_dec={price_dec} qty_dec={qty_dec}"
        )
        if price_dec <= 0 or qty_dec <= 0:
            continue
        items.append(
            {
                "name": name,
                "quantity": qty_dec,
                "price": price_dec,
            }
        )
    logger.info(
        f"amo.purchases.element.items_parsed element_id={element.get('id')} count={len(items)}"
    )
    return items


def _fetch_purchases_for_lead(lead_id: int) -> List[Dict[str, Any]]:
    try:
        ids = _fetch_purchase_element_ids_for_lead(lead_id)
    except Exception as e:
        logger.error(f"amo.purchases.links.error lead_id={lead_id} error={e}")
        return []
    if not ids:
        logger.info(f"amo.purchases.links.empty lead_id={lead_id}")
        return []
    try:
        elements = _fetch_catalog_elements(ids)
    except Exception as e:
        logger.error(f"amo.purchases.elements.error lead_id={lead_id} error={e}")
        return []
    purchases: List[Dict[str, Any]] = []
    for el in elements:
        items = _extract_items_from_catalog_element(el)
        purchases.extend(items)
    logger.info(
        f"amo.purchases.total_parsed lead_id={lead_id} elements={len(elements)} items={len(purchases)}"
    )
    return purchases


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
    purchases = _fetch_purchases_for_lead(lead_id)
    logger.info(
        "amocrm.load_lead done "
        f"lead_id={lead_id} status_value={status_value} discount={discount} "
        f"checkbox_status={checkbox_status_value} email={email} ttn={ttn_value} "
        f"purchases_flat={len(purchases)}"
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
