import time
from datetime import datetime, timedelta

from feishu_bug_alert import main


def _next_run_time():
    now = datetime.now()
    next_run = now.replace(hour=15, minute=40, second=0, microsecond=0)
    while next_run <= now or next_run.weekday() >= 5:
        next_run += timedelta(days=1)
    return next_run


if __name__ == "__main__":
    try:
        while True:
            next_run = _next_run_time()
            time.sleep((next_run - datetime.now()).total_seconds())
            main()
    except KeyboardInterrupt:
        pass
