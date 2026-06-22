import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

BASE_URL = "https://doc.dataiku.com/dss/latest/release_notes/"

# DSS 버전 번호 패턴: X.Y 또는 X.Y.Z (단, 앞에 DSS/Version 키워드가 있거나 href 구조로 확인)
_DSS_VERSION_RE = re.compile(r"\b(\d{1,2}\.\d+(?:\.\d+)?)\b")
# href 앵커에서 버전 추출: version-14-7-0-june-18th-2026 → 14.7.0
_ANCHOR_VERSION_RE = re.compile(r"version-(\d+)-(\d+)-(\d+)-")


def _get_main_content(soup: BeautifulSoup) -> Tag:
    """릴리즈 노트 본문 영역을 반환합니다."""
    candidates = [
        soup.find("div", {"role": "main"}),
        soup.find("article"),
        soup.find("div", class_=re.compile(r"(body|content|main)", re.I)),
        soup.find("main"),
    ]
    for element in candidates:
        if element:
            return element
    logger.warning("본문 영역을 특정하지 못해 전체 문서를 사용합니다.")
    return soup


def extract_content(html: str) -> str:
    """변경 감지에 사용할 핵심 텍스트를 추출합니다."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "meta"]):
        tag.decompose()
    main = _get_main_content(soup)
    text = main.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_versions(html: str) -> list[dict]:
    """릴리즈 노트 인덱스 페이지에서 DSS 버전 목록을 추출합니다.

    앵커 href 패턴 `version-X-Y-Z-` 를 기준으로 정확한 버전만 추출합니다.

    Returns:
        [{"version": "14.7.0", "title": "Version 14.7.0 - June 18th, 2026",
          "url": "https://...14.html#version-14-7-0-june-18th-2026",
          "anchor": "version-14-7-0-june-18th-2026"}]
    """
    soup = BeautifulSoup(html, "lxml")
    main = _get_main_content(soup)
    versions = []
    seen = set()

    for a_tag in main.find_all("a", href=True):
        href = a_tag["href"]
        parsed = urlparse(href)
        anchor = parsed.fragment  # "version-14-7-0-june-18th-2026"

        m = _ANCHOR_VERSION_RE.match(anchor)
        if not m:
            continue

        version_str = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
        if version_str in seen:
            continue

        full_url = urljoin(BASE_URL, href) if not href.startswith("http") else href
        title = a_tag.get_text(strip=True) or f"Version {version_str}"

        versions.append({
            "version": version_str,
            "title": title,
            "url": full_url,
            "anchor": anchor,
        })
        seen.add(version_str)

    logger.info("추출된 DSS 버전 수: %d", len(versions))
    return versions


def extract_version_detail(html: str, version: str, anchor: str = "") -> str:
    """버전 상세 페이지에서 해당 버전 섹션만 추출합니다.

    anchor가 주어지면 해당 id를 가진 헤딩부터 다음 동급 헤딩까지만 추출합니다.
    예) anchor="version-14-7-0-june-18th-2026"
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    if anchor:
        section_text = _extract_anchor_section(soup, anchor)
        if section_text:
            logger.info("앵커 섹션 추출 성공: #%s (%d자)", anchor, len(section_text))
            return section_text[:8000] + ("\n...(이하 생략)" if len(section_text) > 8000 else "")

    logger.warning("앵커 섹션 미발견, 전체 본문 사용: %s", anchor)
    main = _get_main_content(soup)
    text = main.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    content = "\n".join(lines)
    return content[:8000] + ("\n...(이하 생략)" if len(content) > 8000 else "")


def _extract_anchor_section(soup: BeautifulSoup, anchor: str) -> str:
    """anchor id에 해당하는 헤딩 섹션의 텍스트를 추출합니다.

    해당 id를 가진 요소를 찾고, 동일 레벨의 다음 헤딩이 나올 때까지 수집합니다.
    """
    start_el = soup.find(id=anchor)
    if not start_el:
        return ""

    heading_tag = start_el if start_el.name in ("h1","h2","h3","h4") else start_el.find_parent(re.compile(r"^h[1-4]$"))
    if not heading_tag:
        heading_tag = start_el

    level = int(heading_tag.name[1]) if heading_tag.name and heading_tag.name[0] == "h" else 2
    stop_tags = {f"h{i}" for i in range(1, level + 1)}

    parts = [heading_tag.get_text(strip=True)]
    for sibling in heading_tag.find_next_siblings():
        if sibling.name in stop_tags:
            break
        text = sibling.get_text(separator="\n", strip=True)
        if text:
            parts.append(text)

    return "\n".join(parts)
