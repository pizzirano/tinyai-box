"""Adaptadores do Scheduler — aqui vivem TODOS os efeitos colaterais.

Cada adaptador fala com um serviço do docker-compose via HTTP.
Credenciais e URLs vêm SEMPRE de variáveis de ambiente (nunca hardcoded).
"""

from __future__ import annotations

import os
import time
import logging

import httpx

log = logging.getLogger("tinyai.adaptadores")

# URLs internas da rede do compose (defaults batem com docker-compose.yml)
WHISPER_URL = os.getenv("WHISPER_URL", "http://whisper:9000")
LLM_LOCAL_URL = os.getenv("LLM_LOCAL_URL", "http://llm-local:8080")
PIPER_URL = os.getenv("PIPER_URL", "http://piper:5000")
OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")

TIMEOUT_LOCAL_S = float(os.getenv("TIMEOUT_LOCAL_S", "60"))
TIMEOUT_REMOTO_S = float(os.getenv("TIMEOUT_REMOTO_S", "45"))


class AdaptadorErro(RuntimeError):
    """Falha em um serviço downstream — o Scheduler decide o fallback."""


def _cronometrado(nome: str):
    """Decorator: loga latência e erros de cada chamada externa."""
    def deco(fn):
        def wrapper(*args, **kwargs):
            inicio = time.monotonic()
            try:
                resultado = fn(*args, **kwargs)
                log.info("%s ok em %.2fs", nome, time.monotonic() - inicio)
                return resultado
            except httpx.HTTPError as exc:
                log.error("%s falhou em %.2fs: %s", nome, time.monotonic() - inicio, exc)
                raise AdaptadorErro(f"{nome}: {exc}") from exc
        return wrapper
    return deco


@_cronometrado("whisper")
def transcrever_audio(audio_bytes: bytes) -> str:
    """Envia áudio ao serviço Whisper e retorna o texto transcrito."""
    with httpx.Client(timeout=TIMEOUT_LOCAL_S) as c:
        r = c.post(
            f"{WHISPER_URL}/asr",
            files={"audio_file": ("audio.wav", audio_bytes, "audio/wav")},
            params={"output": "txt", "language": "pt"},
        )
        r.raise_for_status()
        return r.text.strip()


@_cronometrado("llm_local")
def completar_local(prompt: str, max_tokens: int = 256) -> str:
    """Chama o llama.cpp server (TinyLlama) rodando no container llm-local."""
    with httpx.Client(timeout=TIMEOUT_LOCAL_S) as c:
        r = c.post(
            f"{LLM_LOCAL_URL}/completion",
            json={
                "prompt": prompt,
                "n_predict": max_tokens,
                "temperature": 0.7,
                "stop": ["</s>", "Usuário:"],
            },
        )
        r.raise_for_status()
        return r.json().get("content", "").strip()


@_cronometrado("openrouter")
def completar_remoto(prompt: str, max_tokens: int = 512) -> str:
    """Chama a API do OpenRouter para prompts complexos."""
    if not OPENROUTER_API_KEY:
        raise AdaptadorErro("openrouter: OPENROUTER_API_KEY não configurada")
    with httpx.Client(timeout=TIMEOUT_REMOTO_S) as c:
        r = c.post(
            f"{OPENROUTER_URL}/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={
                "model": OPENROUTER_MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()


@_cronometrado("piper")
def sintetizar_fala(texto: str) -> bytes:
    """Converte texto em áudio WAV via serviço Piper."""
    with httpx.Client(timeout=TIMEOUT_LOCAL_S) as c:
        r = c.post(f"{PIPER_URL}/api/tts", json={"text": texto})
        r.raise_for_status()
        return r.content


def openrouter_configurado() -> bool:
    return bool(OPENROUTER_API_KEY)
