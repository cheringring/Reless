# Dataiku Release Monitor

매일 [Dataiku DSS 릴리즈 노트](https://doc.dataiku.com/dss/latest/release_notes/index.html) 페이지를 감시하여,  
새로운 버전이나 변경이 감지되면 OpenAI로 요약 후 AIE 팀 메일로 자동 발송하는 Python 자동화 프로그램입니다.

---

## 실행 흐름

```
매일 실행
  → 페이지 스크래핑 (requests)
  → 변경 감지 (SHA-256 해시 비교)
    → 변경 없음: 종료 (또는 "변경 없음" 메일)
    → 변경 있음:
        → 신규 버전 파싱 (BeautifulSoup4)
        → 상세 페이지 스크래핑 (최대 3개)
        → OpenAI 요약 (gpt-4o-mini)
        → 회사 SMTP 메일 발송
        → 해시/버전 정보 저장
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
