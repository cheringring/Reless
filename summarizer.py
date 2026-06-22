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
Dataiku DSS 릴리즈 노트 내용을 분석하여 한국어로 간결하게 요약합니다.
다음 형식을 따르세요:
- 새로운 주요 기능 (있는 경우)
- 버그 수정 및 개선사항 (있는 경우)
- 주의사항 또는 Breaking changes (있는 경우)
각 항목은 3~5줄 이내로 간략히 작성하세요."""

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
) -> str:
    """신규 버전 목록과 상세 내용을 요약합니다.

    Args:
        new_versions: 신규 버전 딕셔너리 목록 [{"version", "title", "url"}]
        detail_texts: 버전별 상세 텍스트 {"version": "content"}

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
    MAX_INPUT = 12000
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
