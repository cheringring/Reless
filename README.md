# Dataiku Release Monitor

매일 [Dataiku DSS 릴리즈 노트](https://doc.dataiku.com/dss/latest/release_notes/index.html) 페이지를 감시하여,  
신규 버전 또는 변경이 감지되면 OpenAI(GPT-4o)로 요약 후 AIE 팀 메일로 자동 발송하는 Python 자동화 프로그램입니다.

---

## 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                          main.py  (오케스트레이터)                    │
│                                                                     │
│  run()                                                              │
│   │                                                                 │
│   ├─1─▶ scraper.fetch_page(TARGET_URL)                              │
│   │       └─ requests.get → HTML 반환                               │
│   │                                                                 │
│   ├─2─▶ parser.extract_content(html)                                │
│   │       └─ BeautifulSoup4로 동적 요소 제거 후 텍스트 추출          │
│   │                                                                 │
│   ├─3─▶ detector.compute_hash(content)                              │
│   │       └─ SHA-256 해시 계산                                      │
│   │                                                                 │
│   ├─4─▶ detector.has_changed(hash)                                  │
│   │       ├─ 변경 없음 → (선택) 변경없음 메일 발송 → 종료            │
│   │       └─ 변경 있음 → 계속                                       │
│   │                                                                 │
│   ├─5─▶ parser.extract_versions(html)                               │
│   │       └─ <a href="#version-X-Y-Z-..."> 앵커 파싱               │
│   │                                                                 │
│   ├─6─▶ detector.find_new_versions(current, last)                   │
│   │       └─ 이전 기록과 비교 → 신규 버전 목록 반환                  │
│   │                                                                 │
│   ├─7─▶ _fetch_version_details(new_versions)                        │
│   │       └─ 각 버전의 상세 페이지 스크래핑 (최대 3개)               │
│   │           └─ parser.extract_version_detail(html, version, anchor)│
│   │               └─ Sphinx <section id="..."> 앵커 섹션 추출       │
│   │               └─ <a href> 링크 → [text](url) 마크다운 보존      │
│   │                                                                 │
│   ├─8─▶ _fetch_linked_pages(detail_texts)                           │
│   │       └─ detail_texts에서 doc.dataiku.com 링크 감지             │
│   │           └─ 링크 페이지 fetch → 내용 추출 (최대 4000자)         │
│   │                                                                 │
│   ├─9─▶ summarizer.summarize_new_versions(versions, details, links) │
│   │       └─ OpenAI GPT-4o 호출                                     │
│   │           └─ SYSTEM_PROMPT: 버전별 구조화 + 카테고리별 분류      │
│   │           └─ 출력 형식: ## 버전 / ### 기능 / **카테고리** / -항목│
│   │                                                                 │
│   ├─10▶ mailer.send_change_notification(versions, summary, url)     │
│   │       └─ _summary_to_html() → 마크다운 → HTML 변환              │
│   │           ├─ ## 버전 제목 → 파란 박스 + 릴리즈 노트 링크         │
│   │           ├─ ### 기능 → 초록 박스 + 기능 문서 링크               │
│   │           ├─ **카테고리** → 굵은 제목 + 릴리즈 노트 섹션 앵커 링크│
│   │           ├─ - 항목 → 불릿 리스트                               │
│   │           └─ [text](url) → <a href> 클릭 가능 링크              │
│   │       └─ smtplib SMTP 발송                                      │
│   │                                                                 │
│   └─11▶ detector.save_hash / save_versions                          │
│           └─ data/last_hash.txt, data/last_versions.json 저장       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 모듈별 상세 설명

### `config.py` — 환경변수 로더
- `.env` 파일을 읽어 `Config` 클래스로 노출
- 누락된 필수 항목(`SMTP_HOST`, `OPENAI_API_KEY` 등)을 검사하고 경고 반환
- `SMTP_USE_SSL` / `SMTP_USE_TLS` 구분 지원 (포트 465 SSL vs 587 STARTTLS)

### `scraper.py` — 웹 스크래핑
- `requests.get()`으로 HTML 다운로드
- `User-Agent` 헤더 설정으로 차단 방지
- 연결 실패 시 예외 발생 (main에서 오류 메일 발송)

### `parser.py` — HTML 파싱 ★ 핵심 모듈
| 함수 | 역할 |
|------|------|
| `extract_content(html)` | 변경 감지용 텍스트 추출 (script/style/nav 제거) |
| `extract_versions(html)` | `#version-X-Y-Z-...` 앵커 파싱 → 버전 목록 반환 |
| `extract_version_detail(html, version, anchor)` | 특정 버전 섹션만 추출 |
| `_extract_anchor_section(soup, anchor)` | Sphinx `<section id="...">` 구조 지원 |

**링크 보존 로직** (`_extract_anchor_section` 내부):
```
<a href="/dss/latest/ai-assistants/cobuild.html">Cobuild</a>
    → [Cobuild](https://doc.dataiku.com/dss/latest/ai-assistants/cobuild.html)
```
- `headerlink` 앵커(`¶` 기호)는 제거
- 외부 링크는 절대 URL로 변환하여 마크다운 형식으로 보존
- 이후 OpenAI가 링크를 인식하여 요약에 포함

### `detector.py` — 변경 감지
| 함수 | 역할 |
|------|------|
| `compute_hash(text)` | SHA-256 해시 계산 |
| `has_changed(hash)` | `data/last_hash.txt`와 비교 |
| `find_new_versions(current, last)` | 이전에 없던 버전만 반환 |
| `load_last_versions()` | `data/last_versions.json` 로드 |
| `save_versions(versions)` | 버전 목록 저장 |

> **최초 실행 시**: 이전 기록이 없으므로 최신 3개 버전을 신규로 처리합니다.

### `summarizer.py` — OpenAI 요약

**요약 입력 구성**:
```
[릴리즈 노트 내용]
## Version 14.7.0 - June 18th, 2026
링크: https://...
(버전 상세 텍스트 — 링크 포함)

--- 링크된 도큐먼트 내용 ---
[Cobuild 문서]
(Cobuild 페이지 전체 내용 최대 4000자)
```

**출력 형식 (SYSTEM_PROMPT 강제)**:
```markdown
## Version 14.7.0 - June 18th, 2026

### 주요 신규 기능: [Cobuild](https://doc.dataiku.com/.../cobuild.html)
한 줄 요약
- 주요 기능 bullet 1
- 주요 기능 bullet 2
- 접근 방법

### 버그 수정 및 개선

**Agentic AI & RAG**
- 문서 스크린샷 속도 개선

**Charts**
- 색상 팔레트 이름 오류 수정
```

### `mailer.py` — 이메일 생성 및 발송

**HTML 렌더링 규칙** (`_summary_to_html()`):

| 마크다운 | HTML 결과 |
|---------|-----------|
| `## Version X.Y.Z` | 파란 박스, 릴리즈 노트 링크 연결 (`→`) |
| `### 주요 신규 기능: [명칭](url)` | 초록 박스, 기능 문서 링크 연결 |
| `**카테고리명**` | 굵은 소제목, 릴리즈 노트 해당 섹션 앵커 자동 링크 |
| `- 항목` | 불릿 리스트 |
| `[텍스트](url)` | 클릭 가능한 `<a>` 태그 |

**카테고리 앵커 자동 생성** (`_category_slug()`):
```
"Agentic AI & RAG" → #agentic-ai-rag
"Charts"           → #charts
"Coding & API"     → #coding-api
```

**SMTP 연결 방식**:
- `SMTP_USE_SSL=true` + 포트 465 → `smtplib.SMTP_SSL`
- `SMTP_USE_TLS=true` + 포트 587 → `smtplib.SMTP` + `starttls()`

### `scheduler.py` — 내장 스케줄러
- `schedule` 라이브러리 사용
- `SCHEDULE_TIME` 환경변수 기준으로 매일 1회 `main.run()` 호출

---

## 실행 흐름 요약

```
실행
  → 페이지 fetch
  → 해시 비교
    ├─ 변경 없음 → (옵션) 변경없음 메일 → 종료
    └─ 변경 있음
        → 신규 버전 추출 (앵커 파싱)
        → 버전 상세 페이지 fetch (최대 3개)
            → 링크된 기능 문서 fetch (Cobuild 등)
        → OpenAI GPT-4o 요약 (버전별 구조화)
        → HTML 이메일 생성 (링크 연결 포함)
        → SMTP 발송
        → 해시 + 버전 저장
```

---

## 설치

### 요구사항
- Python 3.11+
- 회사 SMTP 서버 접근 권한
- OpenAI API 키

### 의존성 설치

```bash
pip install -r requirements.txt
```

---

## 설정 (.env)

`.env.example`을 복사하여 `.env`를 생성하고 값을 채워주세요.

```bash
cp .env.example .env
```

| 항목 | 설명 | 예시 |
|------|------|------|
| `SMTP_HOST` | 회사 SMTP 서버 주소 | `mail.company.com` |
| `SMTP_PORT` | SMTP 포트 (TLS: 587, SSL: 465) | `587` |
| `SMTP_USER` | 발신 이메일 계정 | `aie-team@company.com` |
| `SMTP_PASSWORD` | SMTP 계정 비밀번호 | `your_password` |
| `SMTP_USE_TLS` | STARTTLS 사용 여부 | `true` |
| `EMAIL_FROM` | 발신자 주소 | `aie-team@company.com` |
| `EMAIL_TO` | 수신자 주소 (쉼표로 여러 명) | `team@company.com` |
| `OPENAI_API_KEY` | OpenAI API 키 | `sk-...` |
| `OPENAI_MODEL` | 사용할 모델 | `gpt-4o-mini` |
| `TARGET_URL` | 모니터링할 URL | `https://doc.dataiku.com/...` |
| `SEND_NO_CHANGE_EMAIL` | 변경 없을 때도 메일 발송 | `false` |
| `SCHEDULE_TIME` | 스케줄러 실행 시각 (HH:MM) | `09:00` |

---

## 실행 방법

### 방법 1: 즉시 1회 실행

```bash
python main.py
```

### 방법 2: 내장 스케줄러 (매일 자동 실행)

프로세스를 유지하면서 매일 지정 시각에 자동 실행됩니다.

```bash
python scheduler.py
```

### 방법 3: Windows 작업 스케줄러

1. `win_task_setup.bat`을 관리자 권한으로 실행하거나,  
   작업 스케줄러에서 직접 등록:

   - **프로그램**: `python`
   - **인수**: `C:\...\Reless\main.py`
   - **시작 위치**: `C:\...\Reless`
   - **트리거**: 매일 오전 9:00

```powershell
schtasks /create /tn "DataikuReleaseMonitor" /tr "python C:\Users\gksmf\Desktop\Reless\main.py" /sc daily /st 09:00 /f
```

### 방법 4: Docker (권장 — 서버 환경)

```bash
# 이미지 빌드 및 백그라운드 실행
docker-compose up -d --build

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down
```

Docker 컨테이너는 매일 오전 9시(UTC)에 자동 실행됩니다.  
시간대 변경이 필요하면 `docker-cron` 파일의 cron 표현식을 수정하세요.

---

## 파일 구조

```
Reless/
├── main.py              # 진입점 & 오케스트레이터
├── scraper.py           # 웹 스크래핑 (requests)
├── parser.py            # HTML 파싱 (BeautifulSoup4)
├── detector.py          # 해시 비교 & 버전 변경 감지
├── summarizer.py        # OpenAI API 요약
├── mailer.py            # 회사 SMTP 메일 발송
├── config.py            # 환경변수 로더
├── scheduler.py         # 내장 스케줄러
├── Dockerfile           # Docker 이미지 정의
├── docker-compose.yml   # Docker Compose 설정
├── docker-cron          # Docker용 cron 스케줄
├── requirements.txt     # Python 의존성
├── .env.example         # 환경변수 템플릿 (커밋용)
├── .env                 # 실제 시크릿 (gitignore)
└── data/                # 런타임 데이터 (gitignore)
    ├── last_hash.txt    # 마지막 해시값
    └── last_versions.json  # 마지막 버전 목록
```

---

## 이메일 예시

### 변경 감지 시
- **제목**: `[Dataiku DSS] 릴리즈 노트 업데이트 감지 — DSS 13.2.1`
- **본문**: 신규 버전 목록 + AI 요약 + 릴리즈 노트 링크

### 변경 없음 (SEND_NO_CHANGE_EMAIL=true 시)
- **제목**: `[Dataiku DSS] 릴리즈 노트 변경 없음 — 2026-06-22`

### 실행 오류 시
- **제목**: `[Dataiku Release Monitor] 실행 오류 발생`

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `SMTP 연결 실패` | SMTP 호스트/포트 오류 | `.env`의 `SMTP_HOST`, `SMTP_PORT` 확인 |
| `OpenAI API 오류` | API 키 잘못됨/한도 초과 | `OPENAI_API_KEY` 확인 및 OpenAI 대시보드 확인 |
| `변경이 없는데 매번 메일 발송` | 동적 요소로 인한 해시 변동 | `parser.py`의 `extract_content()`에서 추가 동적 요소 제거 |
| `버전이 파싱되지 않음` | 사이트 HTML 구조 변경 | `parser.py`의 `VERSION_PATTERN` 및 CSS 셀렉터 수정 |
