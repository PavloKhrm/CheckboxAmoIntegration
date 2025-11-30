import logging
from typing import Any, Dict, Optional

import requests

from config import (
    CHECKBOX_API_BASE,
    CHECKBOX_CASHIER_LOGIN,
    CHECKBOX_CASHIER_PASSWORD,
    CHECKBOX_LICENSE_KEY,
    CHECKBOX_CLIENT_NAME,
    CHECKBOX_CLIENT_VERSION,
    CHECKBOX_SEND_EMAIL,
)

logger = logging.getLogger("checkbox_api")


class CheckboxApiError(Exception):
    def __init__(self, status_code: int, message: str, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _base_headers() -> Dict[str, str]:
    return {
        "Accept": "application/json",
        "X-Client-Name": CHECKBOX_CLIENT_NAME,
        "X-Client-Version": CHECKBOX_CLIENT_VERSION,
    }


def _http(
    method: str,
    path: str,
    token: Optional[str] = None,
    json: Optional[Any] = None,
    use_license: bool = False,
) -> Any:
    url = f"{CHECKBOX_API_BASE}{path}"
    headers = _base_headers()
    if json is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if use_license:
        headers["X-License-Key"] = CHECKBOX_LICENSE_KEY
    logger.debug(
        "checkbox.http",
        extra={"method": method, "url": url, "use_license": use_license},
    )
    resp = requests.request(method, url, headers=headers, json=json, timeout=5)
    try:
        data = resp.json()
    except Exception:
        data = resp.text
    if resp.status_code >= 400:
        message = ""
        if isinstance(data, dict):
            message = str(data.get("message") or data)
        else:
            message = str(data)
        logger.error(
            "checkbox.error",
            extra={"status": resp.status_code, "message": message, "preview": str(data)[:500]},
        )
        raise CheckboxApiError(resp.status_code, message, data)
    return data


def sign_in() -> str:
    body = {"login": CHECKBOX_CASHIER_LOGIN, "password": CHECKBOX_CASHIER_PASSWORD}
    logger.debug("checkbox.signin.start")
    data = _http("POST", "/cashier/signin", json=body)
    token = ""
    if isinstance(data, dict):
        token = str(data.get("access_token") or data.get("token") or "")
    if not token:
        raise CheckboxApiError(500, "checkbox signin: no token in response", data)
    logger.debug("checkbox.signin.ok")
    return token


def open_shift(token: str) -> Any:
    data = _http("POST", "/shifts", token=token, json={}, use_license=True)
    return data


def ensure_shift(token: str) -> None:
    try:
        open_shift(token)
        return
    except CheckboxApiError as e:
        msg = str(e)
        msg_lower = msg.lower()
        if "already" in msg_lower or "вже працює" in msg_lower or "зайнята іншим касиром" in msg_lower:
            logger.debug("checkbox.ensure_shift.already_open")
            return
        raise


def create_sell_receipt(
    token: str,
    goods: Any,
    total_minor: int,
    discount_minor: int = 0,
    email: Optional[str] = None,
    payment_type: str = "CASHLESS",
) -> Any:
    payments_value = max(0, int(total_minor) - max(0, int(discount_minor)))
    payments = [
        {
            "type": payment_type,
            "value": payments_value,
            "label": "Оплата",
        }
    ]
    body: Dict[str, Any] = {
        "goods": goods,
        "payments": payments,
    }
    if discount_minor > 0:
        body["discounts"] = [
            {
                "type": "DISCOUNT",
                "mode": "VALUE",
                "value": int(discount_minor),
                "name": "Знижка з AmoCRM",
            }
        ]
    if CHECKBOX_SEND_EMAIL and email:
        body["delivery"] = {"emails": [email]}
    data = _http("POST", "/receipts/sell", token=token, json=body, use_license=True)
    return data
