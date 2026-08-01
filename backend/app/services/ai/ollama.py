"""Provedor Ollama (servidor local)."""
from __future__ import annotations

import json
from typing import Any

import httpx

from app.services.ai.base import LLMProvider, strip_json


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _chat(self, messages: list[dict], temperature: float, fmt: str | None) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if fmt:
            payload["format"] = fmt
        with httpx.Client(timeout=1800) as client:
            r = client.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
            return data.get("message", {}).get("content", "")

    def chat_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        json_schema_hint: str | None = None,
    ) -> dict[str, Any]:
        fmt = "json" if json_schema_hint else None
        content = self._chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature,
            fmt,
        )
        return json.loads(strip_json(content))

    def chat_text(self, system: str, user: str, temperature: float = 0.5) -> str:
        return self._chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature,
            None,
        )

    def available(self) -> tuple[bool, str]:
        try:
            with httpx.Client(timeout=3) as client:
                r = client.get(f"{self.base_url}/api/tags")
                if r.status_code != 200:
                    return False, f"Ollama respondeu {r.status_code}"
                models = [m.get("name", "") for m in r.json().get("models", [])]
                base = self.model.split(":")[0]
                if not any(m.startswith(base) for m in models):
                    return (
                        False,
                        f"Modelo '{self.model}' não encontrado no Ollama. Modelos disponíveis: {', '.join(models[:8]) or 'nenhum'}",
                    )
                return True, ""
        except Exception as e:
            return False, f"Ollama não está acessível em {self.base_url} ({e}). Inicie com: ollama serve"


class OpenAICompatProvider(LLMProvider):
    """Qualquer servidor compatível com a API OpenAI (LM Studio, llama.cpp, etc.)."""

    name = "openai_compat"

    def __init__(self, base_url: str = "http://localhost:1234/v1", model: str = "local", api_key: str = "local") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    def _chat(self, messages: list[dict], temperature: float) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        with httpx.Client(timeout=1800) as client:
            r = client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    def chat_json(self, system, user, temperature=0.3, json_schema_hint=None):
        content = self._chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature,
        )
        return json.loads(strip_json(content))

    def chat_text(self, system, user, temperature=0.5):
        return self._chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature,
        )

    def available(self) -> tuple[bool, str]:
        try:
            with httpx.Client(timeout=3) as client:
                r = client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if r.status_code != 200:
                    return False, f"Servidor respondeu {r.status_code}"
                models = [m.get("id", "") for m in r.json().get("data", [])]
                if self.model not in models:
                    return False, f"Modelo '{self.model}' não listado. Disponíveis: {', '.join(models[:8]) or 'nenhum'}"
                return True, ""
        except Exception as e:
            return False, f"Servidor OpenAI-compat não acessível em {self.base_url} ({e})"
