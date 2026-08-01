"""Interface comum dos provedores de IA (LLM)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Provedor abstrato — novos modelos podem ser adicionados sem alterar o pipeline."""

    name: str = "base"

    @abstractmethod
    def chat_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        json_schema_hint: str | None = None,
    ) -> dict[str, Any]:
        """Retorna a resposta do modelo como JSON."""
        raise NotImplementedError

    @abstractmethod
    def chat_text(self, system: str, user: str, temperature: float = 0.5) -> str:
        raise NotImplementedError

    def available(self) -> tuple[bool, str]:
        """Verifica se o provedor está acessível. Retorna (ok, mensagem)."""
        return True, ""


def strip_json(text: str) -> str:
    """Extrai o primeiro objeto/array JSON de um texto de resposta."""
    text = text.strip()
    start = text.find("{")
    if start == -1:
        start = text.find("[")
    if start == -1:
        return "{}"
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return "{}"
