import logging
from typing import Any, Dict, List, Optional

import requests

from config import AMO_BASE_URL, AMO_ACCESS_TOKEN, AMO_PURCHASES_CATALOG_ID

logger = logging.getLogger("amocrm_client")


class AmoApiError(Exception):
    def __init__(self, status_code: int, message: str, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {AMO_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _http(
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Any] = None,
) -> Any:
    url = f"{AMO_BASE_URL}{path}"
    logger.debug("amo.http", extra={"method": method, "url": url, "params": params})
    resp = requests.request(method, url, headers=_headers(), params=params, json=json, timeout=10)
    try:
        data = resp.json()
    except Exception:
        data = resp.text
    if resp.status_code >= 400:
        message = ""
        if isinstance(data, dict):
            message = str(data.get("title") or data.get("message") or data)
        else:
            message = str(data)
        logger.error(
            "amo.error",
            extra={"status": resp.status_code, "message": message, "preview": str(data)[:500]},
        )
        raise AmoApiError(resp.status_code, message, data)
    return data


def get_lead(lead_id: int) -> Dict[str, Any]:
    return _http("GET", f"/api/v4/leads/{lead_id}", params={"with": "contacts"})


def get_contact(contact_id: int) -> Dict[str, Any]:
    return _http("GET", f"/api/v4/contacts/{contact_id}")


def get_lead_links(lead_id: int) -> List[Dict[str, Any]]:
    data = _http("GET", f"/api/v4/leads/{lead_id}/links", params={"limit": 250})
    embedded = data.get("_embedded") or {}
    links = embedded.get("links") or []
    return links


def get_catalog_element(catalog_id: int, element_id: int) -> Dict[str, Any]:
    return _http("GET", f"/api/v4/catalogs/{catalog_id}/elements/{element_id}")


def update_lead_custom_field(lead_id: int, field_id: int, value: str) -> Dict[str, Any]:
    body = {
        "custom_fields_values": [
            {
                "field_id": field_id,
                "values": [{"value": value}],
            }
        ]
    }
    return _http("PATCH", f"/api/v4/leads/{lead_id}", json=body)


def get_purchases_for_lead(lead_id: int) -> List[Dict[str, Any]]:
    links = get_lead_links(lead_id)
    result: List[Dict[str, Any]] = []
    by_element_id: Dict[int, Dict[str, Any]] = {}
    for link in links:
        if link.get("to_entity_type") != "catalog_elements":
            continue
        to_catalog_id = link.get("to_catalog_id")
        if to_catalog_id != AMO_PURCHASES_CATALOG_ID:
            continue
        element_id = link.get("to_entity_id")
        if not element_id:
            continue
        quantity = link.get("quantity") or 1
        if element_id in by_element_id:
            by_element_id[element_id]["quantity"] += quantity
        else:
            by_element_id[element_id] = {"element_id": element_id, "quantity": quantity}
    for element_id, info in by_element_id.items():
        try:
            element = get_catalog_element(AMO_PURCHASES_CATALOG_ID, element_id)
        except AmoApiError as e:
            logger.error(
                "amo.purchase.element_error",
                extra={"element_id": element_id, "error": str(e)},
            )
            continue
        result.append(
            {
                "id": element_id,
                "name": element.get("name") or "Товар",
                "quantity": info.get("quantity") or 1,
                "raw_element": element,
            }
        )
    return result
