from pathlib import Path
import json
import structlog

LOGGER = structlog.get_logger(__name__)

CONFIG_PATH = Path(__file__).parent / "domain_config.json"


def load_domain_config() -> dict:
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        LOGGER.warning("domain-config-load-failed", error=str(exc))
        return {}
