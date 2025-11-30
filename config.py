import os
from decimal import Decimal

def getenv_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing env var {name}")
    return value

AMO_BASE_URL = getenv_required("AMO_BASE_URL").rstrip("/")
AMO_ACCESS_TOKEN = getenv_required("AMO_ACCESS_TOKEN")

AMO_PURCHASES_CATALOG_ID = int(getenv_required("AMO_PURCHASES_CATALOG_ID"))
AMO_FIELD_STATUS = int(os.getenv("AMO_FIELD_STATUS", "459279"))
AMO_FIELD_DISCOUNT = int(os.getenv("AMO_FIELD_DISCOUNT", "825281"))
AMO_FIELD_CHECKBOX_STATUS = int(os.getenv("AMO_FIELD_CHECKBOX_STATUS", "0"))
AMO_STATUS_TARGET = os.getenv("AMO_STATUS_TARGET", "Контроль оплаты")
AMO_PURCHASE_PRICE_FIELD_ID = int(os.getenv("AMO_PURCHASE_PRICE_FIELD_ID", "0"))

CHECKBOX_API_BASE = os.getenv("CHECKBOX_API_BASE", "https://api.checkbox.in.ua/api/v1").rstrip("/")
CHECKBOX_CASHIER_LOGIN = getenv_required("CHECKBOX_CASHIER_LOGIN")
CHECKBOX_CASHIER_PASSWORD = getenv_required("CHECKBOX_CASHIER_PASSWORD")
CHECKBOX_LICENSE_KEY = getenv_required("CHECKBOX_LICENSE_KEY")
CHECKBOX_SEND_EMAIL = os.getenv("CHECKBOX_SEND_EMAIL", "true").lower() == "true"
CHECKBOX_CLIENT_NAME = os.getenv("CHECKBOX_CLIENT_NAME", "amo-checkbox-python")
CHECKBOX_CLIENT_VERSION = os.getenv("CHECKBOX_CLIENT_VERSION", "1.0.0")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
PORT = int(os.getenv("PORT", "8080"))

MONEY_QUANT = Decimal("0.01")
