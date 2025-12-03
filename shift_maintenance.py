import logging
import sys
from datetime import datetime
import zoneinfo

from config import LOG_LEVEL, CHECKBOX_PROFILES
from checkbox_api import sign_in_for_profile, close_shift_for_profile, ensure_shift_for_profile

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("shift_maintenance")

TZ = zoneinfo.ZoneInfo("Europe/Kiev")


def close_all() -> None:
    now = datetime.now(TZ)
    logger.info("shift_maintenance.close_all.start", extra={"now": now.isoformat()})
    for profile_id in CHECKBOX_PROFILES.keys():
        try:
            token = sign_in_for_profile(profile_id)
            close_shift_for_profile(token, profile_id)
            logger.info("shift_maintenance.close_ok", extra={"profile_id": profile_id})
        except Exception as e:
            logger.error("shift_maintenance.close_error", extra={"profile_id": profile_id, "error": str(e)})


def open_all() -> None:
    now = datetime.now(TZ)
    logger.info("shift_maintenance.open_all.start", extra={"now": now.isoformat()})
    for profile_id in CHECKBOX_PROFILES.keys():
        try:
            token = sign_in_for_profile(profile_id)
            ensure_shift_for_profile(token, profile_id)
            logger.info("shift_maintenance.open_ok", extra={"profile_id": profile_id})
        except Exception as e:
            logger.error("shift_maintenance.open_error", extra={"profile_id": profile_id, "error": str(e)})


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "close":
        close_all()
    elif mode == "open":
        open_all()
    else:
        logger.error("shift_maintenance.invalid_mode", extra={"mode": mode})
