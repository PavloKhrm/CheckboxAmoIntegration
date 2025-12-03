from datetime import datetime, time
import zoneinfo

TZ = zoneinfo.ZoneInfo("Europe/Kiev")
CLOSE_TIME = time(23, 45)
OPEN_TIME = time(0, 1)

def is_receipt_allowed_now() -> bool:
    now = datetime.now(TZ).time()
    if CLOSE_TIME <= now or now < OPEN_TIME:
        return False
    return True
