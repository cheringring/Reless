"""SMTP 연결 진단 스크립트 — 테스트 후 삭제해도 됩니다."""
import smtplib
import socket

HOST = "gwsmtp.ktbizoffice.com"
PASSWORD = "Rnjscpdms1289@"  # .env 파일의 SMTP_PASSWORD 값을 여기에 직접 입력하세요

# KT BizOffice는 username 형식에 민감할 수 있으므로 여러 형식 시도
USER_CANDIDATES = [
    "kwonc8814@datasolution.kr",   # 전체 이메일
    "kwonc8814",                    # 로컬 파트만
    "kwonc8814@ktbizoffice.com",    # BizOffice 도메인
    "datasolution\\kwonc8814",      # NTLM-style domain\\user
]

TESTS = [
    {"label": "[1] 포트 587 + STARTTLS", "port": 587, "ssl": False, "tls": True},
    {"label": "[2] 포트 465 + SSL",       "port": 465, "ssl": True,  "tls": False},
    {"label": "[3] 포트 25  + 평문",       "port": 25,  "ssl": False, "tls": False},
    {"label": "[4] 포트 587 + 평문",       "port": 587, "ssl": False, "tls": False},
]


def test_smtp(label, port, ssl, tls):
    print(f"\n{'='*50}")
    print(f"{label}")
    print(f"  Host: {HOST}:{port}  SSL={ssl}  TLS={tls}")
    try:
        if ssl:
            smtp = smtplib.SMTP_SSL(HOST, port, timeout=10)
        else:
            smtp = smtplib.SMTP(HOST, port, timeout=10)
            if tls:
                smtp.starttls()

        print(f"  ✅ 서버 연결 성공")
        print(f"  EHLO AUTH: {smtp.esmtp_features.get('auth', '(없음)')}")

        if PASSWORD:
            smtp.login(USER_CANDIDATES[0], PASSWORD)
            print(f"  ✅ 로그인 성공!")
            smtp.quit()
            return True
        else:
            print(f"  ⚠️  PASSWORD가 비어있어 로그인 테스트 건너뜀")
            smtp.quit()

    except smtplib.SMTPAuthenticationError as e:
        print(f"  ❌ 인증 실패: {e.smtp_code} {e.smtp_error}")
    except smtplib.SMTPException as e:
        print(f"  ❌ SMTP 오류: {e}")
    except socket.timeout:
        print(f"  ❌ 타임아웃 — 포트 차단 가능성")
    except ConnectionRefusedError:
        print(f"  ❌ 연결 거부 — 포트 닫혀 있음")
    except Exception as e:
        print(f"  ❌ 기타 오류: {type(e).__name__}: {e}")
    return False


def test_auth_formats():
    """포트 587+STARTTLS에서 username 형식별 인증 시도"""
    print(f"\n{'='*50}")
    print("[AUTH] 포트 587 + STARTTLS — username 형식 순차 시도")
    print(f"{'='*50}")
    for user in USER_CANDIDATES:
        try:
            smtp = smtplib.SMTP(HOST, 587, timeout=10)
            smtp.starttls()
            smtp.login(user, PASSWORD)
            print(f"  ✅ 성공! username = '{user}'")
            smtp.quit()
            return user
        except smtplib.SMTPAuthenticationError as e:
            print(f"  ❌ '{user}' → {e.smtp_code} {e.smtp_error}")
        except Exception as e:
            print(f"  ❌ '{user}' → {type(e).__name__}: {e}")
    print("  모든 username 형식 실패 — KT BizOffice 관리자에게 SMTP 계정 활성화 요청 필요")
    return None


if __name__ == "__main__":
    print("=" * 50)
    print("KT BizOffice SMTP 연결 진단")
    print("=" * 50)

    if not PASSWORD:
        print("\n⚠️  PASSWORD 변수에 비밀번호를 입력하세요 (이 파일 7번째 줄)")
        print("   (테스트 후 이 파일은 삭제하세요)\n")

    for t in TESTS:
        test_smtp(**t)

    if PASSWORD:
        test_auth_formats()

    print("\n" + "="*50)
    print("진단 완료")
