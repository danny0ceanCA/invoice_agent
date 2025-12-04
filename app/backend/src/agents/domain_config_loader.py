import json
import os
from functools import lru_cache


@lru_cache()
def load_domain_config() -> dict:
    """Load and cache domain_config.json from the agents folder."""
    here = os.path.dirname(__file__)
    config_path = os.path.join(here, "domain_config.json")
    with open(config_path, "r") as f:
        return json.load(f)
