import os
from decimal import Decimal
from typing import Dict, NamedTuple


def getenv_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing env var {name}")
    return value


class CheckboxProfile(NamedTuple):
    login: str
    password: str
    license_key: str


AMO_BASE_URL = getenv_required("AMO_BASE_URL").rstrip("/")
AMO_ACCESS_TOKEN = getenv_required("AMO_ACCESS_TOKEN")

AMO_PURCHASES_CATALOG_ID = int(getenv_required("AMO_PURCHASES_CATALOG_ID"))
AMO_FIELD_STATUS = int(os.getenv("AMO_FIELD_STATUS", "459279"))
AMO_FIELD_DISCOUNT = int(os.getenv("AMO_FIELD_DISCOUNT", "825281"))
AMO_FIELD_CHECKBOX_STATUS = int(os.getenv("AMO_FIELD_CHECKBOX_STATUS", "0"))
AMO_STATUS_TARGET = os.getenv("AMO_STATUS_TARGET", "Контроль оплаты")
AMO_PURCHASE_PRICE_FIELD_ID = int(os.getenv("AMO_PURCHASE_PRICE_FIELD_ID", "0"))

AMO_PURCHASE_ITEMS_FIELD_ID = int(os.getenv("AMO_PURCHASE_ITEMS_FIELD_ID", "0"))
AMO_PURCHASE_TOTAL_FIELD_ID = int(os.getenv("AMO_PURCHASE_TOTAL_FIELD_ID", "0"))

AMO_FIELD_TTN = int(os.getenv("AMO_FIELD_TTN", "603103"))

CHECKBOX_API_BASE = os.getenv("CHECKBOX_API_BASE", "https://api.checkbox.in.ua/api/v1").rstrip("/")
CHECKBOX_CLIENT_NAME = os.getenv("CHECKBOX_CLIENT_NAME", "amo-checkbox-python")
CHECKBOX_CLIENT_VERSION = os.getenv("CHECKBOX_CLIENT_VERSION", "1.0.0")
CHECKBOX_SEND_EMAIL = os.getenv("CHECKBOX_SEND_EMAIL", "true").lower() == "true"


def _load_profile(prefix: str) -> CheckboxProfile | None:
    login = os.getenv(f"{prefix}_CASHIER_LOGIN") or ""
    password = os.getenv(f"{prefix}_CASHIER_PASSWORD") or ""
    license_key = os.getenv(f"{prefix}_LICENSE_KEY") or ""
    if not (login and password and license_key):
        return None
    return CheckboxProfile(login=login, password=password, license_key=license_key)


CHECKBOX_PROFILES: Dict[str, CheckboxProfile] = {}

for idx in ("1", "2"):
    profile = _load_profile(f"CHECKBOX{idx}")
    if profile:
        CHECKBOX_PROFILES[idx] = profile

default_profile = _load_profile("CHECKBOX")
if default_profile and "default" not in CHECKBOX_PROFILES:
    CHECKBOX_PROFILES["default"] = default_profile

NP_API_KEY_1 = os.getenv("NP_API_KEY_1", "")
NP_API_KEY_2 = os.getenv("NP_API_KEY_2", "")

NP_SENDER_NAME_1 = (os.getenv("NP_SENDER_NAME_1") or "").strip()
NP_SENDER_NAME_2 = (os.getenv("NP_SENDER_NAME_2") or "").strip()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
PORT = int(os.getenv("PORT", "8080"))

MONEY_QUANT = Decimal("0.01")
