import logging
from typing import Any, Dict, Optional

import requests

from config import (
    CHECKBOX_API_BASE,
    CHECKBOX_CLIENT_NAME,
    CHECKBOX_CLIENT_VERSION,
    CHECKBOX_SEND_EMAIL,
    CHECKBOX_PROFILES,
    CheckboxProfile,
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
    license_key: Optional[str] = None,
) -> Any:
    url = f"{CHECKBOX_API_BASE}{path}"
    headers = _base_headers()
    if json is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if license_key:
        headers["X-License-Key"] = license_key
    logger.debug("checkbox.http", extra={"method": method, "url": url})
    resp = requests.request(method, url, headers=headers, json=json, timeout=5)
    try:
        data = resp.json()
    except Exception:
        data = resp.text
    if resp.status_code >= 400:
        msg_text = ""
        if isinstance(data, dict):
            msg_text = str(data.get("message") or data)
        else:
            msg_text = str(data)
        logger.error(
            "checkbox.error",
            extra={
                "status_code": resp.status_code,
                "api_message": msg_text,
                "api_preview": str(data)[:500],
                "url": url,
            },
        )
        raise CheckboxApiError(resp.status_code, msg_text, data)
    return data


def get_profile(profile_id: str) -> CheckboxProfile:
    profile = CHECKBOX_PROFILES.get(profile_id)
    if not profile:
        raise CheckboxApiError(500, f"Unknown checkbox profile {profile_id}", None)
    return profile


def sign_in_for_profile(profile_id: str) -> str:
    profile = get_profile(profile_id)
    body = {"login": profile.login, "password": profile.password}
    logger.debug("checkbox.signin.start", extra={"profile_id": profile_id})
    data = _http("POST", "/cashier/signin", json=body)
    token = ""
    if isinstance(data, dict):
        token = str(data.get("access_token") or data.get("token") or "")
    if not token:
        raise CheckboxApiError(500, "checkbox signin: no token in response", data)
    logger.debug("checkbox.signin.ok", extra={"profile_id": profile_id})
    return token


def open_shift_for_profile(token: str, profile_id: str) -> Any:
    profile = get_profile(profile_id)
    data = _http("POST", "/shifts", token=token, json={}, license_key=profile.license_key)
    return data


def close_shift_for_profile(token: str, profile_id: str) -> Any:
    profile = get_profile(profile_id)
    data = _http("POST", "/shifts/close", token=token, json={}, license_key=profile.license_key)
    return data


def ensure_shift_for_profile(token: str, profile_id: str) -> None:
    try:
        open_shift_for_profile(token, profile_id)
        return
    except CheckboxApiError as e:
        msg_lower = str(e).lower()
        if (
            "вже працює" in msg_lower
            or "already" in msg_lower
            or "відкрито зміну" in msg_lower
            or "зайнята іншим касиром" in msg_lower
        ):
            logger.debug("checkbox.ensure_shift.already_open", extra={"profile_id": profile_id})
            return
        raise


def create_sell_receipt_for_profile(
    token: str,
    profile_id: str,
    goods: Any,
    total_minor: int,
    discount_minor: int = 0,
    email: Optional[str] = None,
    payment_type: str = "CASHLESS",
) -> Any:
    profile = get_profile(profile_id)
    email = "pasha.kharaman@gmail.com"
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
    data = _http("POST", "/receipts/sell", token=token, json=body, license_key=profile.license_key)
    return data
