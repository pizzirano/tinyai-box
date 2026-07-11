"""API do Scheduler — ponto de entrada HTTP do TinyAI Box.

Endpoints:
  POST /prompt   {"texto": "..."}          -> resposta em texto
  POST /voz      (multipart, campo audio)  -> resposta em áudio WAV
  GET  /saude                              -> estado do hardware + config

Cada decisão gera um log estruturado: rota, motivo, latência, fallback usado.
"""

from __future__ import annotations

import json
import logging
import time

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from . import adaptadores as adp
from .hardware import ler_estado
from .rotas import Decisao, Requisicao, Rota, TipoEntrada, escolher_rota

logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","nivel":"%(levelname)s","mod":"%(name)s","msg":%(message)s}',
)
log = logging.getLogger("tinyai.scheduler")

app = FastAPI(title="TinyAI Box — Scheduler", version="1.0.0")


class PromptIn(BaseModel):
    texto: str
    max_tokens: int = 256


def _log_decisao(decisao: Decisao, latencia_s: float, usou_fallback: bool) -> None:
    log.info(json.dumps({
        "evento": "decisao",
        "rota": decisao.rota.value,
        "motivo": decisao.motivo,
        "latencia_s": round(latencia_s, 2),
        "fallback_usado": usou_fallback,
    }, ensure_ascii=False))


def _executar_texto(prompt: str, decisao: Decisao, max_tokens: int) -> tuple[str, bool]:
    """Executa a rota decidida; em falha do local, cai para o fallback."""
    try:
        if decisao.rota is Rota.LOCAL:
            return adp.completar_local(prompt, max_tokens), False
        return adp.completar_remoto(prompt, max_tokens), False
    except adp.AdaptadorErro as exc:
        if decisao.fallback is Rota.REMOTA:
            log.warning(json.dumps({"evento": "fallback", "de": decisao.rota.value,
                                    "para": "openrouter", "erro": str(exc)}, ensure_ascii=False))
            return adp.completar_remoto(prompt, max_tokens), True
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/prompt")
def prompt(body: PromptIn):
    inicio = time.monotonic()
    hw = ler_estado()
    decisao = escolher_rota(
        Requisicao(conteudo=body.texto, tipo=TipoEntrada.TEXTO),
        hw,
        openrouter_disponivel=adp.openrouter_configurado(),
    )
    resposta, usou_fb = _executar_texto(body.texto, decisao, body.max_tokens)
    _log_decisao(decisao, time.monotonic() - inicio, usou_fb)
    return {"resposta": resposta, "rota": decisao.rota.value, "motivo": decisao.motivo}


@app.post("/voz")
async def voz(audio: UploadFile):
    inicio = time.monotonic()
    hw = ler_estado()
    decisao = escolher_rota(
        Requisicao(conteudo="", tipo=TipoEntrada.AUDIO),
        hw,
        openrouter_disponivel=adp.openrouter_configurado(),
    )
    audio_bytes = await audio.read()
    try:
        texto = adp.transcrever_audio(audio_bytes)
    except adp.AdaptadorErro as exc:
        raise HTTPException(status_code=502, detail=f"whisper: {exc}") from exc

    # Após transcrever, o texto passa pela mesma régua de complexidade.
    decisao_llm = escolher_rota(
        Requisicao(conteudo=texto, tipo=TipoEntrada.TEXTO),
        hw,
        openrouter_disponivel=adp.openrouter_configurado(),
    )
    resposta, usou_fb = _executar_texto(texto, decisao_llm, max_tokens=200)

    try:
        wav = adp.sintetizar_fala(resposta)
    except adp.AdaptadorErro as exc:
        raise HTTPException(status_code=502, detail=f"piper: {exc}") from exc

    _log_decisao(decisao, time.monotonic() - inicio, usou_fb)
    return Response(content=wav, media_type="audio/wav",
                    headers={"X-Transcricao": texto[:200], "X-Rota-LLM": decisao_llm.rota.value})


@app.get("/saude")
def saude():
    hw = ler_estado()
    return {
        "status": "ok",
        "hardware": {"ram_livre_mb": hw.ram_livre_mb,
                     "cpu_percent": hw.cpu_percent,
                     "temperatura_c": hw.temperatura_c},
        "openrouter_configurado": adp.openrouter_configurado(),
    }
