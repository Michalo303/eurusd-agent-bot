from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


class LLMClient:
    """Thin future integration point for JSON-only agent calls."""

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        provider = os.getenv("EURUSD_BOT_LLM_PROVIDER", "none").lower()
        if provider == "openai":
            return self._openai(system, user)
        raise RuntimeError("No LLM provider configured. Use deterministic agents or set EURUSD_BOT_LLM_PROVIDER.")

    def _openai(self, system: str, user: str) -> dict[str, Any]:
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("EURUSD_BOT_OPENAI_MODEL", "gpt-5.1")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        payload = {
            "model": model,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "text": {"format": {"type": "json_object"}},
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = data["output"][0]["content"][0]["text"]
        return json.loads(text)

