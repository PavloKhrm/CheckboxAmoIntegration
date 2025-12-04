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
from nova_poshta_service import detect_profile_for_ttn
from telegram_notify import send_telegram, resolve_sender_name

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
        logger.error("webhook.lead_id_not_found")
        send_telegram("❌ Вебхук AmoCRM: не удалось получить ID сделки")
        return jsonify({"error": "lead_id not found"}), 400
    logger.info(f"webhook.received lead_id={lead_id}")
    try:
        lead_data = load_lead_with_details(lead_id)
    except Exception as e:
        msg = str(e)
        logger.exception(f"lead.load.error lead_id={lead_id} error={msg}")
        send_telegram(f"❌ Сделка <b>{lead_id}</b>: ошибка загрузки сделки\n<code>{msg}</code>")
        return jsonify({"error": msg}), 500
    if is_already_processed(lead_data):
        logger.info(f"lead.already_processed lead_id={lead_id}")
        return jsonify({"status": "already_processed"}), 200
    if not is_target_status(lead_data):
        logger.info(
            f"lead.status.skip lead_id={lead_id} status_value={lead_data.get('status_value')}"
        )
        return jsonify({"status": "skipped_by_status"}), 200
    ttn = lead_data.get("ttn") or ""
    if not ttn:
        msg = "no TTN in deal"
        logger.warning(f"lead.no_ttn lead_id={lead_id}")
        set_checkbox_status(lead_id, f"ERROR: {msg}")
        send_telegram(f"❌ Сделка <b>{lead_id}</b>: нет ТТН в сделке")
        return jsonify({"error": msg}), 400
    profile_id = detect_profile_for_ttn(str(ttn))
    if not profile_id:
        msg = "TTN does not belong to known Nova Poshta accounts"
        logger.warning(f"lead.ttn_profile_not_found lead_id={lead_id} ttn={ttn}")
        set_checkbox_status(lead_id, f"ERROR: {msg}")
        send_telegram(
            f"❌ Сделка <b>{lead_id}</b>: ТТН <code>{ttn}</code> не относится ни к одному аккаунту НП"
        )
        return jsonify({"error": msg}), 400
    try:
        result = create_receipt_for_lead_data(lead_data, profile_id)
    except Exception as e:
        msg = str(e)
        logger.exception(f"checkbox.create.error lead_id={lead_id} profile_id={profile_id} error={msg}")
        set_checkbox_status(lead_id, f"ERROR: {msg}")
        sender_name = resolve_sender_name(str(profile_id))
        send_telegram(
            f"❌ Сделка <b>{lead_id}</b>: ошибка при создании чека ({sender_name})\n<code>{msg}</code>",
            str(profile_id),
        )
        return jsonify({"error": msg}), 500
    receipt_id = result.get("receipt_id") or ""
    receipt_number = result.get("receipt_number") or ""
    error = result.get("error")
    if error:
        logger.error(
            f"checkbox.create.result_error lead_id={lead_id} profile_id={profile_id} error={error}"
        )
        set_checkbox_status(lead_id, f"ERROR: {error}")
        sender_name = resolve_sender_name(str(profile_id))
        send_telegram(
            f"❌ Сделка <b>{lead_id}</b>: ошибка создания чека ({sender_name})\n<code>{error}</code>",
            str(profile_id),
        )
        return jsonify(
            {
                "error": error,
                "receipt_id": receipt_id,
                "receipt_number": receipt_number,
                "profile_id": profile_id,
            }
        ), 500
    text = f"OK: {receipt_number or '—'} (id: {receipt_id or '—'})"
    set_checkbox_status(lead_id, text)
    logger.info(
        f"checkbox.create.ok lead_id={lead_id} profile_id={profile_id} "
        f"receipt_id={receipt_id} receipt_number={receipt_number}"
    )
    sender_name = resolve_sender_name(str(profile_id))
    send_telegram(
        f"✅ Сделка <b>{lead_id}</b>: чек выдан успешно ({sender_name})\n"
        f"ID: <code>{receipt_id or '—'}</code>\nНомер: <code>{receipt_number or '—'}</code>",
        str(profile_id),
    )
    return jsonify(
        {
            "status": "ok",
            "lead_id": lead_id,
            "profile_id": profile_id,
            "receipt_id": receipt_id,
            "receipt_number": receipt_number,
        }
    ), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
