import hashlib
import json
import logging
import os

from config import config

logger = logging.getLogger(__name__)


def _ensure_data_dir() -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)


def compute_hash(content: str) -> str:
    """텍스트 콘텐츠의 SHA-256 해시값을 반환합니다."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_last_hash() -> str | None:
    """마지막으로 저장된 해시값을 반환합니다. 파일이 없으면 None."""
    if not os.path.exists(config.HASH_FILE):
        return None
    with open(config.HASH_FILE, "r", encoding="utf-8") as f:
        return f.read().strip() or None


def save_hash(new_hash: str) -> None:
    """새 해시값을 파일에 저장합니다."""
    _ensure_data_dir()
    with open(config.HASH_FILE, "w", encoding="utf-8") as f:
        f.write(new_hash)
    logger.debug("해시값 저장 완료: %s", new_hash[:16] + "...")


def has_changed(new_hash: str) -> bool:
    """현재 해시값이 저장된 해시값과 다른지 확인합니다.

    최초 실행(저장값 없음)은 변경으로 간주합니다.
    """
    last = load_last_hash()
    if last is None:
        logger.info("최초 실행: 해시 파일 없음. 변경으로 처리합니다.")
        return True
    changed = last != new_hash
    if changed:
        logger.info("해시값 변경 감지: %s → %s", last[:16] + "...", new_hash[:16] + "...")
    else:
        logger.info("해시값 동일 — 변경 없음.")
    return changed


def load_last_versions() -> list[dict]:
    """마지막으로 저장된 버전 목록을 반환합니다."""
    if not os.path.exists(config.VERSIONS_FILE):
        return []
    with open(config.VERSIONS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_versions(versions: list[dict]) -> None:
    """현재 버전 목록을 파일에 저장합니다."""
    _ensure_data_dir()
    with open(config.VERSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(versions, f, ensure_ascii=False, indent=2)
    logger.debug("버전 목록 저장 완료 (%d개)", len(versions))


def find_new_versions(
    current_versions: list[dict],
    last_versions: list[dict],
) -> list[dict]:
    """현재 버전 목록에서 이전에 없던 새 버전을 반환합니다."""
    last_version_strs = {v["version"] for v in last_versions}

    if not last_version_strs:
        logger.info("이전 버전 기록 없음(최초 실행) — 상위 3개를 신규로 처리합니다.")
        return current_versions[:3]

    new_versions = [
        v for v in current_versions if v["version"] not in last_version_strs
    ]
    logger.info("신규 버전 수: %d", len(new_versions))
    return new_versions
