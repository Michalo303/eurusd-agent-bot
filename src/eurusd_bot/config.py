from __future__ import annotations

import json
from pathlib import Path

from .models import BotConfig


def load_config(path: str | None) -> BotConfig:
    if not path:
        return BotConfig()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return BotConfig.from_mapping(data)

