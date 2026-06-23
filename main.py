import logging
import re
import sys

import detector
import mailer
import parser
import scraper
import summarizer
from config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def run() -> None:
    """메인 실행 함수 — 스크래핑 → 변경 감지 → 요약 → 메일 발송."""
    logger.info("=" * 60)
    logger.info("Dataiku Release Monitor 시작")
    logger.info("대상 URL: %s", config.TARGET_URL)

    warnings = config.validate()
    for w in warnings:
        logger.warning("설정 경고: %s", w)

    try:
        html = scraper.fetch_page(config.TARGET_URL)
    except Exception as exc:
        logger.error("페이지 스크래핑 실패: %s", exc)
        _try_send_error(str(exc))
        sys.exit(1)

    content = parser.extract_content(html)
    current_hash = detector.compute_hash(content)

    if not detector.has_changed(current_hash):
        logger.info("변경사항 없음.")
        if config.SEND_NO_CHANGE_EMAIL:
            mailer.send_no_change_notification(config.TARGET_URL)
        logger.info("Dataiku Release Monitor 종료 (변경 없음)")
        return

    logger.info("변경사항 감지 — 버전 목록 파싱 중...")
    current_versions = parser.extract_versions(html)
    last_versions = detector.load_last_versions()
    new_versions = detector.find_new_versions(current_versions, last_versions)

    if new_versions:
        logger.info(
            "신규 버전 %d개 발견: %s",
            len(new_versions),
            [v["version"] for v in new_versions],
        )
        detail_texts = _fetch_version_details(new_versions)
        linked_pages = _fetch_linked_pages(detail_texts)
        summary = summarizer.summarize_new_versions(new_versions, detail_texts, linked_pages)
        mailer.send_change_notification(new_versions, summary, config.TARGET_URL)
    else:
        logger.info("버전 목록 변경 없음 (페이지 내용 수정 감지)")
        summary = summarizer.summarize_content_change(content[:8000])
        first_version = current_versions[:1] if current_versions else []
        mailer.send_change_notification(
            first_version or [{"version": "업데이트", "title": "릴리즈 노트 내용 변경", "url": config.TARGET_URL}],
            summary,
            config.TARGET_URL,
        )

    detector.save_hash(current_hash)
    detector.save_versions(current_versions)
    logger.info("해시 및 버전 정보 저장 완료.")
    logger.info("Dataiku Release Monitor 종료 (변경 처리 완료)")


def _fetch_version_details(versions: list[dict]) -> dict[str, str]:
    """각 신규 버전 페이지의 상세 텍스트를 수집합니다.

    같은 페이지(예: 14.html)를 가리키는 버전이 여럿이면 한 번만 다운로드합니다.
    """
    detail_texts: dict[str, str] = {}
    MAX_DETAIL_PAGES = 3
    page_cache: dict[str, str] = {}

    for v in versions[:MAX_DETAIL_PAGES]:
        try:
            page_url = v["url"].split("#")[0]
            anchor = v.get("anchor", "")
            logger.info("버전 상세 스크래핑: %s (anchor: %s)", page_url, anchor)

            if page_url not in page_cache:
                page_cache[page_url] = scraper.fetch_page(page_url)

            detail_texts[v["version"]] = parser.extract_version_detail(
                page_cache[page_url], v["version"], anchor
            )
        except Exception as exc:
            logger.warning("버전 %s 상세 페이지 스크래핑 실패: %s", v["version"], exc)
            detail_texts[v["version"]] = f"(상세 페이지 로드 실패: {exc})"

    return detail_texts


_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\((https://doc\.dataiku\.com/[^)]+)\)')


def _fetch_linked_pages(detail_texts: dict[str, str]) -> dict[str, str]:
    """detail_texts 내 doc.dataiku.com 링크를 fetch하여 {label: content} 반환."""
    linked: dict[str, str] = {}
    seen: set[str] = set()
    for text in detail_texts.values():
        for label, url in _MD_LINK_RE.findall(text):
            if "release_notes" in url or url in seen:
                continue
            seen.add(url)
            try:
                logger.info("링크 페이지 fetch: [%s] %s", label, url)
                page_html = scraper.fetch_page(url)
                content = parser.extract_content(page_html)
                linked[label] = content[:4000]
            except Exception as exc:
                logger.warning("링크 페이지 로드 실패 %s: %s", url, exc)
    return linked


def _try_send_error(error_message: str) -> None:
    """오류 알림 메일 발송을 시도합니다 (SMTP 설정이 있는 경우에만)."""
    if config.SMTP_HOST and config.EMAIL_TO:
        try:
            mailer.send_error_notification(error_message)
        except Exception as mail_exc:
            logger.error("오류 알림 메일 발송 실패: %s", mail_exc)


if __name__ == "__main__":
    run()
