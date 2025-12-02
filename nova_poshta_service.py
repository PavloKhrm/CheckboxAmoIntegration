import logging
from typing import Optional

import requests

from config import NP_API_KEY_1, NP_API_KEY_2

logger = logging.getLogger("nova_poshta_service")

NP_API_URL = "https://api.novaposhta.ua/v2.0/json/"


def _check_ttn_with_key(api_key: str, ttn: str) -> bool:
    if not api_key:
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
    logger.debug("np.check_ttn.request", extra={"ttn": ttn})
    try:
        resp = requests.post(NP_API_URL, json=body, timeout=10)
    except requests.RequestException as e:
        logger.error("np.check_ttn.http_error", extra={"ttn": ttn, "error": str(e)})
        return False
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
    logger.info("np.check_ttn.match", extra={"ttn": ttn, "docs_len": len(docs)})
    return True


def detect_profile_for_ttn(ttn: str) -> Optional[str]:
    ttn = (ttn or "").strip()
    if not ttn:
        return None
    if _check_ttn_with_key(NP_API_KEY_1, ttn):
        return "1"
    if _check_ttn_with_key(NP_API_KEY_2, ttn):
        return "2"
    return None
