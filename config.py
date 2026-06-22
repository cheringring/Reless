import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "")
    EMAIL_TO: list[str] = [
        addr.strip()
        for addr in os.getenv("EMAIL_TO", "").split(",")
        if addr.strip()
    ]

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    TARGET_URL: str = os.getenv(
        "TARGET_URL",
        "https://doc.dataiku.com/dss/latest/release_notes/index.html",
    )

    SEND_NO_CHANGE_EMAIL: bool = (
        os.getenv("SEND_NO_CHANGE_EMAIL", "false").lower() == "true"
    )
    SCHEDULE_TIME: str = os.getenv("SCHEDULE_TIME", "09:00")

    DATA_DIR: str = os.path.join(os.path.dirname(__file__), "data")
    HASH_FILE: str = os.path.join(DATA_DIR, "last_hash.txt")
    VERSIONS_FILE: str = os.path.join(DATA_DIR, "last_versions.json")

    def validate(self) -> list[str]:
        """필수 설정값이 누락된 경우 경고 메시지를 반환합니다."""
        warnings = []
        if not self.SMTP_HOST:
            warnings.append("SMTP_HOST가 설정되지 않았습니다.")
        if not self.SMTP_USER:
            warnings.append("SMTP_USER가 설정되지 않았습니다.")
        if not self.SMTP_PASSWORD:
            warnings.append("SMTP_PASSWORD가 설정되지 않았습니다.")
        if not self.EMAIL_TO:
            warnings.append("EMAIL_TO가 설정되지 않았습니다.")
        if not self.OPENAI_API_KEY:
            warnings.append("OPENAI_API_KEY가 설정되지 않았습니다.")
        return warnings


config = Config()
