"""Lógica PURA de decisão de rota do TinyAI Box.

Nenhuma função aqui tem efeito colateral: não chama rede, não lê disco.
Isso torna as regras 100% testáveis (ver tests/test_rotas.py).

Fluxo de referência (Scheduler Engineer):
    Prompt chegou
      → é voz?          → Whisper → LLM → Piper
      → é pequeno?      → TinyLlama (local)
      → é complexo?     → OpenRouter (remoto)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Rota(str, Enum):
    VOZ = "voz"                  # Whisper -> LLM -> Piper
    LOCAL = "llm_local"          # TinyLlama via llama.cpp
    REMOTA = "openrouter"        # API remota para prompts complexos


class TipoEntrada(str, Enum):
    TEXTO = "texto"
    AUDIO = "audio"


@dataclass(frozen=True)
class EstadoHardware:
    """Snapshot dos recursos, fornecido pela observabilidade (Embedded)."""
    ram_livre_mb: int = 1024
    cpu_percent: float = 0.0
    temperatura_c: float = 40.0


@dataclass(frozen=True)
class Requisicao:
    conteudo: str
    tipo: TipoEntrada = TipoEntrada.TEXTO
    latencia_maxima_s: float | None = None


@dataclass(frozen=True)
class Decisao:
    rota: Rota
    motivo: str
    fallback: Rota | None = None


# ---------------------------------------------------------------------------
# Heurísticas de complexidade (simples de propósito — ajustar com uso real)
# ---------------------------------------------------------------------------

PALAVRAS_COMPLEXAS: frozenset[str] = frozenset({
    "explique", "analise", "compare", "resuma", "traduza",
    "código", "programa", "matemática", "passo a passo",
    "por que", "detalhadamente",
})

LIMITE_PROMPT_PEQUENO_CHARS = 280      # até isso, TinyLlama dá conta
LIMITE_RAM_LOCAL_MB = 500              # abaixo disso, não subir LLM local
LIMITE_CPU_LOCAL = 90.0                # CPU sustentada acima disso -> remoto
LIMITE_TEMP_C = 75.0                   # proteção térmica


def estimar_complexidade(texto: str) -> str:
    """Retorna 'pequeno' ou 'complexo' com heurística barata."""
    t = texto.lower()
    if len(texto) > LIMITE_PROMPT_PEQUENO_CHARS:
        return "complexo"
    if any(p in t for p in PALAVRAS_COMPLEXAS):
        return "complexo"
    return "pequeno"


def hardware_suporta_local(hw: EstadoHardware) -> bool:
    return (
        hw.ram_livre_mb >= LIMITE_RAM_LOCAL_MB
        and hw.cpu_percent < LIMITE_CPU_LOCAL
        and hw.temperatura_c < LIMITE_TEMP_C
    )


def escolher_rota(
    req: Requisicao,
    hw: EstadoHardware,
    openrouter_disponivel: bool = True,
) -> Decisao:
    """Função pura central: (requisição, hardware) -> Decisão."""
    # 1. Áudio sempre entra pelo pipeline de voz.
    if req.tipo is TipoEntrada.AUDIO:
        return Decisao(
            rota=Rota.VOZ,
            motivo="entrada de áudio: Whisper -> LLM -> Piper",
            fallback=Rota.REMOTA if openrouter_disponivel else None,
        )

    complexidade = estimar_complexidade(req.conteudo)
    local_ok = hardware_suporta_local(hw)

    # 2. Prompt pequeno e hardware saudável -> local.
    if complexidade == "pequeno" and local_ok:
        return Decisao(
            rota=Rota.LOCAL,
            motivo="prompt pequeno e hardware dentro dos limites",
            fallback=Rota.REMOTA if openrouter_disponivel else None,
        )

    # 3. Complexo, ou hardware pressionado -> remoto (se houver).
    if openrouter_disponivel:
        motivo = (
            "prompt complexo" if complexidade == "complexo"
            else f"hardware pressionado (RAM={hw.ram_livre_mb}MB, "
                 f"CPU={hw.cpu_percent}%, T={hw.temperatura_c}°C)"
        )
        return Decisao(rota=Rota.REMOTA, motivo=motivo, fallback=None)

    # 4. Sem remoto configurado: tenta local mesmo assim (melhor esforço).
    return Decisao(
        rota=Rota.LOCAL,
        motivo="OpenRouter indisponível; melhor esforço no modelo local",
        fallback=None,
    )
