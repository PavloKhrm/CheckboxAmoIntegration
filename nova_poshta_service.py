import logging
from typing import Optional

import requests

from config import NP_API_KEY_1, NP_API_KEY_2, NP_SENDER_NAME_1, NP_SENDER_NAME_2

logger = logging.getLogger("nova_poshta_service")

NP_API_URL = "https://api.novaposhta.ua/v2.0/json/"


def _normalize_name(value: str) -> str:
    return value.strip().lower() if value else ""


def _check_ttn_with_key(api_key: str, ttn: str, expected_sender_name: str) -> bool:
    if not api_key:
        return False
    if not expected_sender_name:
        logger.warning("np.check_ttn.no_expected_sender_name", extra={"ttn": ttn, "api_key": api_key[:4]})
        return False
    body = {
        "apiKey": api_key,
        "modelName": "TrackingDocument",
        "calledMethod": "getStatusDocuments",
        "methodProperties": {
            "Documents": [
                {
                    "DocumentNumber": ttn,
                    "Phone": "",
                }
            ]
        },
    }
    logger.debug("np.check_ttn.request", extra={"ttn": ttn, "api_key": api_key[:4]})
    try:
        resp = requests.post(NP_API_URL, json=body, timeout=10)
    except requests.RequestException as e:
        logger.error("np.check_ttn.http_error", extra={"ttn": ttn, "error": str(e)})
        return False
    logger.info(
        "np.raw_response",
        extra={
            "ttn": ttn,
            "status_code": resp.status_code,
            "raw": resp.text[:2000],
        },
    )
    try:
        data = resp.json()
    except Exception:
        logger.error("np.check_ttn.bad_json", extra={"ttn": ttn, "status": resp.status_code})
        return False
    success = bool(data.get("success"))
    docs = data.get("data") or []
    errors = data.get("errors") or []
    if not success or errors or not docs:
        logger.info(
            "np.check_ttn.no_match",
            extra={"ttn": ttn, "success": success, "errors": errors, "docs_len": len(docs)},
        )
        return False
    doc = docs[0]
    sender_name = str(doc.get("CounterpartySenderDescription") or "")
    logger.info(
        "np.check_ttn.sender_name",
        extra={"ttn": ttn, "sender_name": sender_name},
    )
    if _normalize_name(sender_name) != _normalize_name(expected_sender_name):
        logger.info(
            "np.check_ttn.sender_mismatch",
            extra={
                "ttn": ttn,
                "sender_name": sender_name,
                "expected_sender_name": expected_sender_name,
            },
        )
        return False
    logger.info(
        "np.check_ttn.match",
        extra={"ttn": ttn, "sender_name": sender_name},
    )
    return True


def detect_profile_for_ttn(ttn: str) -> Optional[str]:
    ttn = (ttn or "").strip()
    if not ttn:
        return None
    if _check_ttn_with_key(NP_API_KEY_1, ttn, NP_SENDER_NAME_1):
        return "1"
    if _check_ttn_with_key(NP_API_KEY_2, ttn, NP_SENDER_NAME_2):
        return "2"
    return None
