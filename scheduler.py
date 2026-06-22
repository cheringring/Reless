"""내장 스케줄러 — 매일 지정 시각에 main.run()을 자동 실행합니다.

사용법:
    python scheduler.py

프로세스를 계속 실행시켜 두어야 합니다. 서버 환경에서는
Docker 또는 systemd 서비스로 관리하는 것을 권장합니다.
"""
import logging
import sys
import time

import schedule

from config import config
from main import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _safe_run() -> None:
    try:
        run()
    except Exception as exc:
        logger.error("스케줄 실행 중 예외 발생: %s", exc, exc_info=True)


def main() -> None:
    schedule_time = config.SCHEDULE_TIME
    logger.info("스케줄러 시작 — 매일 %s에 실행됩니다.", schedule_time)

    schedule.every().day.at(schedule_time).do(_safe_run)

    logger.info("첫 번째 실행은 오늘 %s에 예정되어 있습니다.", schedule_time)
    logger.info("즉시 실행을 원하면 Ctrl+C 후 'python main.py'를 실행하세요.")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
