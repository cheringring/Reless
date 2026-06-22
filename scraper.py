import logging
import time

import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 5


def fetch_page(url: str) -> str:
    """지정한 URL의 HTML 소스를 반환합니다.

    Args:
        url: 스크래핑할 웹 페이지 URL

    Returns:
        HTML 소스 문자열

    Raises:
        requests.HTTPError: HTTP 오류 응답 시
        requests.ConnectionError: 네트워크 연결 실패 시
        requests.Timeout: 타임아웃 초과 시
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("페이지 요청 중 (시도 %d/%d): %s", attempt, MAX_RETRIES, url)
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            logger.info("페이지 수신 완료 (%d bytes)", len(response.content))
            return response.text
        except (requests.ConnectionError, requests.Timeout) as exc:
            logger.warning("요청 실패 (시도 %d/%d): %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                raise
        except requests.HTTPError as exc:
            logger.error("HTTP 오류: %s", exc)
            raise
