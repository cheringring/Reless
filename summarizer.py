import logging

from openai import OpenAI

from config import config

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


SYSTEM_PROMPT = """당신은 소프트웨어 릴리즈 노트 요약 전문가입니다.
Dataiku DSS 릴리즈 노트를 분석하여 한국어로 버전별 변경사항을 정리합니다.

반드시 아래 형식을 지켜 작성하세요:

## [버전 제목]

### 주요 신규 기능: [기능명](링크_url_만_있으면)
기능에 대한 핵심 내용을 다음 순서로 요약:
1. 한 줄 요약 (이 기능이 무엇인지)
2. 주요 기능/할 수 있는 것 목록 (bullet)
3. 사용 방법이나 접근 경로 (있을 경우)
링크된 문서가 제공된 경우 그 내용을 최대한 활용해 상세히 작성

### 버그 수정 및 개선

**[카테고리명 - 원본 섹션명 그대로 (Agentic AI & RAG, Charts, Datasets 등)]**
- 수정 또는 개선 항목

규칙:
- 주요 신규 기능이 없으면 ### 주요 신규 기능 항목 생략
- 카테고리명은 원본 릴리즈 노트의 실제 섹션명 그대로 사용 (임의로 번역하거나 변경 금지)
- 여러 버전이 있으면 버전마다 위 형식 반복
- 원문의 [텍스트](링크) 형태 링크는 반드시 보존"""

NEW_VERSION_PROMPT_TEMPLATE = """아래는 Dataiku DSS 새 릴리즈 노트 목록과 내용입니다.
각 버전의 변경 내용을 한국어로 요약해주세요.

{content}

위 내용을 바탕으로 핵심 변경사항만 간결하게 요약하세요."""

INDEX_CHANGE_PROMPT_TEMPLATE = """아래는 Dataiku DSS 릴리즈 노트 페이지에서 감지된 변경 내용입니다.
어떤 변화가 있었는지 한국어로 요약해주세요.

{content}

위 내용을 바탕으로 핵심 변경사항을 3~5줄로 요약하세요."""


def summarize_new_versions(
    new_versions: list[dict],
    detail_texts: dict[str, str],
    linked_pages: dict[str, str] | None = None,
) -> str:
    """신규 버전 목록과 상세 내용을 요약합니다.

    Args:
        new_versions: 신규 버전 딕셔너리 목록 [{"version", "title", "url"}]
        detail_texts: 버전별 상세 텍스트 {"version": "content"}
        linked_pages: 릴리즈 노트에서 링크된 페이지 내용 {label: content}

    Returns:
        한국어 요약 문자열
    """
    content_parts = []
    for v in new_versions:
        detail = detail_texts.get(v["version"], "")
        content_parts.append(
            f"## {v['title']}\n링크: {v['url']}\n\n{detail}"
        )

    combined = "\n\n---\n\n".join(content_parts)

    if linked_pages:
        linked_section = "\n\n--- 링크된 도큰먼트 내용 ---\n"
        for label, content in linked_pages.items():
            linked_section += f"\n[{label} 문서]\n{content}\n"
        combined += linked_section

    MAX_INPUT = 14000
    if len(combined) > MAX_INPUT:
        combined = combined[:MAX_INPUT] + "\n...(이하 생략)"

    prompt = NEW_VERSION_PROMPT_TEMPLATE.format(content=combined)
    return _call_openai(prompt)


def summarize_content_change(changed_content: str) -> str:
    """버전 변경 없이 콘텐츠만 변경된 경우 요약합니다."""
    MAX_INPUT = 12000
    if len(changed_content) > MAX_INPUT:
        changed_content = changed_content[:MAX_INPUT] + "\n...(이하 생략)"

    prompt = INDEX_CHANGE_PROMPT_TEMPLATE.format(content=changed_content)
    return _call_openai(prompt)


def _call_openai(user_prompt: str) -> str:
    """OpenAI API를 호출하여 요약 결과를 반환합니다."""
    try:
        client = _get_client()
        logger.info("OpenAI API 요약 요청 중 (모델: %s)", config.OPENAI_MODEL)
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        summary = response.choices[0].message.content.strip()
        logger.info("OpenAI 요약 완료 (%d자)", len(summary))
        return summary
    except Exception as exc:
        logger.error("OpenAI API 호출 실패: %s", exc)
        return f"(요약 실패: {exc})\n자세한 내용은 위 릴리즈 노트 링크를 확인하세요."
