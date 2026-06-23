import logging
import re as _re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import config

logger = logging.getLogger(__name__)


def _build_connection() -> smtplib.SMTP:
    """SMTP 연결 객체를 생성하고 인증합니다.

    SMTP_USE_SSL=true  → SMTP_SSL (포트 465, 직접 SSL)
    SMTP_USE_TLS=true  → SMTP + STARTTLS (포트 587)
    둘 다 false        → 평문 SMTP
    """
    if config.SMTP_USE_SSL:
        logger.debug("SMTP SSL 모드 (포트 %d)", config.SMTP_PORT)
        smtp = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=30)
    else:
        smtp = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30)
        if config.SMTP_USE_TLS:
            logger.debug("SMTP STARTTLS 모드 (포트 %d)", config.SMTP_PORT)
            smtp.starttls()
    smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
    return smtp


def _send(subject: str, body_html: str) -> None:
    """이메일을 발송합니다."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_FROM
    msg["To"] = ", ".join(config.EMAIL_TO)

    msg.attach(MIMEText(body_html, "html", "utf-8"))

    with _build_connection() as smtp:
        smtp.sendmail(config.EMAIL_FROM, config.EMAIL_TO, msg.as_string())
    logger.info("메일 발송 완료: %s → %s", subject, config.EMAIL_TO)


def _format_versions_html(new_versions: list[dict]) -> str:
    rows = ""
    for v in new_versions:
        rows += (
            f'<tr>'
            f'<td style="padding:6px 12px;border-bottom:1px solid #eee;">'
            f'<strong>{v["title"]}</strong></td>'
            f'<td style="padding:6px 12px;border-bottom:1px solid #eee;">'
            f'<a href="{v["url"]}" style="color:#1a73e8;">릴리즈 노트 보기 →</a></td>'
            f'</tr>'
        )
    return rows


def _summary_to_subject(summary: str) -> str:
    """요약문에서 제목용 한 줄을 추출합니다 (최대 60자). ## 등 마크다운 기호 제거."""
    for line in summary.splitlines():
        line = line.strip().lstrip("#").strip().lstrip("-•* ")
        if len(line) > 5:
            return line[:60] + ("..." if len(line) > 60 else "")
    return "새 업데이트 감지"


_MD_LINK_RE = _re.compile(r'\[([^\]]+)\]\((https?://[^)]+)\)')


def _linkify(text: str) -> str:
    """[텍스트](url) 마크다운 링크를 HTML <a> 태그로 변환합니다."""
    return _MD_LINK_RE.sub(
        r'<a href="\2" style="color:#1a73e8;">\1</a>', text
    )


def _category_slug(name: str) -> str:
    """카테고리명을 Sphinx 앵커 슬러그로 변환합니다. 예: 'Agentic AI & RAG' → 'agentic-ai-rag'"""
    slug = _re.sub(r'[^a-zA-Z0-9\s]', '', name.lower())
    slug = _re.sub(r'\s+', '-', slug.strip())
    return _re.sub(r'-+', '-', slug)


def _summary_to_html(summary: str, version_urls: dict | None = None) -> str:
    """마크다운 요약문을 버전별 변경사항 나열 HTML로 변환합니다."""
    version_urls = version_urls or {}
    lines = summary.splitlines()
    html_parts = []
    in_list = False
    current_base_url: str = ""

    for line in lines:
        line = line.strip()
        if not line:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        if _re.fullmatch(r'-{2,}', line):
            continue

        if line.startswith("### "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            feature = _linkify(line[4:].strip())
            html_parts.append(
                f'<div style="margin-top:16px;padding:12px 16px;'
                f'background:#F0FDF4;border:1px solid #86EFAC;'
                f'border-left:4px solid #16A34A;border-radius:4px;">'
                f'<strong style="color:#15803D;font-size:14px;">{feature}</strong>'
                f'</div>'
            )
        elif line.startswith("## ") or line.startswith("# "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            heading = line.lstrip("#").strip()
            url = version_urls.get(heading)
            if url:
                current_base_url = url.split("#")[0]
                heading_html = (
                    f'<a href="{url}" style="color:#1565C0;text-decoration:none;">'
                    f'{heading} &rarr;</a>'
                )
            else:
                heading_html = heading
            html_parts.append(
                f'<div style="margin-top:18px;padding:8px 14px;'
                f'background:#EFF6FF;border-left:4px solid #1565C0;'
                f'border-radius:0 4px 4px 0;">'
                f'<strong style="font-size:14px;">{heading_html}</strong></div>'
            )
        elif line.startswith("**") and line.endswith("**"):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            cat = line.strip("*").strip()
            if current_base_url:
                slug = _category_slug(cat)
                cat_html = (
                    f'<a href="{current_base_url}#{slug}" '
                    f'style="color:#374151;text-decoration:none;">{cat} &rarr;</a>'
                )
            else:
                cat_html = cat
            html_parts.append(
                f'<p style="margin:12px 0 2px;font-size:13px;'
                f'color:#374151;font-weight:bold;">{cat_html}</p>'
            )
        elif line.startswith("- ") or line.startswith("• ") or line.startswith("* "):
            if not in_list:
                html_parts.append(
                    '<ul style="margin:6px 0 6px 0;padding-left:20px;line-height:1.9;font-size:14px;">'
                )
                in_list = True
            item = _linkify(line.lstrip("-•*").strip())
            html_parts.append(f"<li style='margin-bottom:4px;'>{item}</li>")
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(
                f'<p style="margin:6px 0;line-height:1.7;font-size:14px;">{_linkify(line)}</p>'
            )

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


_FOOTER = (
    "이 메일은 Dataiku Release Monitor가 자동 발송한 메일입니다.<br>"
    "문의: AIE 팀 권체은 "
    "(<a href='mailto:kwonc8814@datasolution.kr' style='color:#999;'>"
    "kwonc8814@datasolution.kr</a>)"
)


def send_change_notification(
    new_versions: list[dict],
    summary: str,
    index_url: str,
) -> None:
    """신규 버전/변경 감지 시 알림 이메일을 발송합니다."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    subject = f"[Dataiku] Release notes 변경사항: {_summary_to_subject(summary)}"

    versions_html = _format_versions_html(new_versions)
    version_urls = {v["title"]: v["url"] for v in new_versions}
    summary_html = _summary_to_html(summary, version_urls)

    body_html = f"""
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;color:#333;max-width:700px;margin:auto;padding:20px;">
  <div style="background:#1565C0;padding:18px 24px;border-radius:6px 6px 0 0;">
    <h2 style="color:#fff;margin:0;font-size:20px;">Dataiku DSS 릴리즈 노트 업데이트</h2>
    <p style="color:#bbdefb;margin:6px 0 0;font-size:13px;">감지 시각: {now}</p>
  </div>
  <div style="border:1px solid #ddd;border-top:none;padding:24px;border-radius:0 0 6px 6px;">

    <p style="color:#555;margin-top:0;font-size:14px;">
      Dataiku DSS에서 새롭게 추가된 릴리즈 노트를 확인해 보세요.
    </p>

    <h3 style="color:#1565C0;border-bottom:2px solid #E3F2FD;padding-bottom:6px;font-size:15px;margin-bottom:12px;">
      신규 릴리즈 버전
    </h3>
    <table style="width:100%;border-collapse:collapse;margin-bottom:24px;">
      <tbody>
        {versions_html}
      </tbody>
    </table>

    <h3 style="color:#1565C0;border-bottom:2px solid #E3F2FD;padding-bottom:6px;font-size:15px;margin-bottom:4px;">
      Release note 변경 요약
    </h3>
    <div style="color:#333;">
      {summary_html}
    </div>

    <div style="margin-top:28px;text-align:center;">
      <a href="{index_url}"
         style="background:#1565C0;color:#fff;padding:12px 28px;border-radius:4px;
                text-decoration:none;font-weight:bold;display:inline-block;font-size:14px;">
        전체 릴리즈 노트 보기 →
      </a>
    </div>

    <hr style="border:none;border-top:1px solid #eee;margin:28px 0 16px;">
    <p style="font-size:12px;color:#999;margin:0;">
      {_FOOTER}
    </p>
  </div>
</body>
</html>
"""
    _send(subject, body_html)


def send_no_change_notification(index_url: str) -> None:
    """변경 없음 일일 상태 이메일을 발송합니다."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    subject = "[Dataiku] Release notes 변경사항 없습니다."

    body_html = f"""
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;color:#333;max-width:700px;margin:auto;padding:20px;">
  <div style="background:#546E7A;padding:18px 24px;border-radius:6px 6px 0 0;">
    <h2 style="color:#fff;margin:0;font-size:20px;">
      ✅ Dataiku DSS 릴리즈 노트 — 변경 없음
    </h2>
  </div>
  <div style="border:1px solid #ddd;border-top:none;padding:24px;border-radius:0 0 6px 6px;">
    <p>확인 시각: <strong>{now}</strong></p>
    <p>
      오늘 <a href="{index_url}">Dataiku DSS 릴리즈 노트</a>에
      새로운 변경사항이 없습니다.
    </p>
    <hr style="border:none;border-top:1px solid #eee;margin:20px 0 12px;">
    <p style="font-size:12px;color:#999;margin:0;">
      {_FOOTER}
    </p>
  </div>
</body>
</html>
"""
    _send(subject, body_html)


def send_error_notification(error_message: str) -> None:
    """실행 중 오류 발생 시 알림 이메일을 발송합니다."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    subject = f"[Dataiku Release Monitor] 실행 오류 발생 — {now}"

    body_html = f"""
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;color:#333;max-width:700px;margin:auto;padding:20px;">
  <div style="background:#C62828;padding:18px 24px;border-radius:6px 6px 0 0;">
    <h2 style="color:#fff;margin:0;font-size:20px;">
      ⚠️ Dataiku Release Monitor 오류
    </h2>
  </div>
  <div style="border:1px solid #ddd;border-top:none;padding:24px;border-radius:0 0 6px 6px;">
    <p>발생 시각: <strong>{now}</strong></p>
    <pre style="background:#fff3f3;padding:14px;border-radius:4px;overflow-x:auto;
                font-size:13px;border:1px solid #ffcdd2;">{error_message}</pre>
    <hr style="border:none;border-top:1px solid #eee;margin:20px 0 12px;">
    <p style="font-size:12px;color:#999;margin:0;">
      {_FOOTER}
    </p>
  </div>
</body>
</html>
"""
    _send(subject, body_html)
