import logging
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request

from config import LOG_LEVEL, PORT
from amocrm_service import (
    load_lead_with_details,
    is_target_status,
    is_already_processed,
    set_checkbox_status,
)
from checkbox_service import create_receipt_for_lead_data

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("app")

app = Flask(__name__)


def _extract_lead_id_from_json(body: Dict[str, Any]) -> Optional[int]:
    leads = body.get("leads") or {}
    status_items = leads.get("status") or leads.get("status_leads") or []
    if isinstance(status_items, list) and status_items:
        first = status_items[0]
        lead_id = first.get("id")
        if lead_id:
            try:
                return int(lead_id)
            except Exception:
                return None
    if "lead_id" in body:
        try:
            return int(body["lead_id"])
        except Exception:
            return None
    return None


def _extract_lead_id_from_form(form: Dict[str, Any]) -> Optional[int]:
    for key, value in form.items():
        if key.endswith("[id]") and "leads[status]" in key:
            try:
                return int(value)
            except Exception:
                return None
    if "lead_id" in form:
        try:
            return int(form["lead_id"])
        except Exception:
            return None
    return None


@app.route("/health", methods=["GET"])
def health() -> Any:
    return jsonify({"status": "ok"}), 200


@app.route("/amocrm/webhook", methods=["POST"])
def amocrm_webhook() -> Any:
    lead_id: Optional[int] = None
    body: Dict[str, Any] = {}
    if request.is_json:
        try:
            body = request.get_json(force=True, silent=True) or {}
        except Exception:
            body = {}
        lead_id = _extract_lead_id_from_json(body)
    if lead_id is None:
        form = request.form or {}
        if form:
            lead_id = _extract_lead_id_from_form(form)
    if lead_id is None:
        return jsonify({"error": "lead_id not found"}), 400
    logger.info("webhook.received", extra={"lead_id": lead_id})
    try:
        lead_data = load_lead_with_details(lead_id)
    except Exception as e:
        logger.exception("lead.load.error")
        return jsonify({"error": str(e)}), 500
    if is_already_processed(lead_data):
        logger.info("lead.already_processed", extra={"lead_id": lead_id})
        return jsonify({"status": "already_processed"}), 200
    if not is_target_status(lead_data):
        logger.info(
            "lead.status.skip",
            extra={"lead_id": lead_id, "status_value": lead_data.get("status_value")},
        )
        return jsonify({"status": "skipped_by_status"}), 200
    try:
        result = create_receipt_for_lead_data(lead_data)
    except Exception as e:
        msg = str(e)
        logger.exception("checkbox.create.error")
        set_checkbox_status(lead_id, f"ERROR: {msg}")
        return jsonify({"error": msg}), 500
    receipt_id = result.get("receipt_id") or ""
    receipt_number = result.get("receipt_number") or ""
    error = result.get("error")
    if error:
        set_checkbox_status(lead_id, f"ERROR: {error}")
        return jsonify({"error": error, "receipt_id": receipt_id, "receipt_number": receipt_number}), 500
    text = f"OK: {receipt_number or '—'} (id: {receipt_id or '—'})"
    set_checkbox_status(lead_id, text)
    return jsonify(
        {
            "status": "ok",
            "lead_id": lead_id,
            "receipt_id": receipt_id,
            "receipt_number": receipt_number,
        }
    ), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
