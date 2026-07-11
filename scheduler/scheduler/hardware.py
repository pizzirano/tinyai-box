"""Leitura do estado real do hardware (ARMv7) para alimentar o Scheduler.

Fontes: /proc/meminfo, /proc/stat e /sys/class/thermal.
Se algo não existir (ex.: rodando em dev x86), retorna valores neutros.
"""

from __future__ import annotations

import logging
import time

from .rotas import EstadoHardware

log = logging.getLogger("tinyai.hardware")

_THERMAL = "/sys/class/thermal/thermal_zone0/temp"


def _ram_livre_mb() -> int:
    try:
        with open("/proc/meminfo") as f:
            info = dict(
                (linha.split(":")[0], linha.split()[1])
                for linha in f
                if ":" in linha
            )
        return int(info.get("MemAvailable", info.get("MemFree", "0"))) // 1024
    except OSError:
        return 1024


def _cpu_percent(intervalo_s: float = 0.2) -> float:
    def snapshot():
        with open("/proc/stat") as f:
            campos = f.readline().split()[1:]
        valores = list(map(int, campos))
        return sum(valores), valores[3]  # total, idle

    try:
        t1, i1 = snapshot()
        time.sleep(intervalo_s)
        t2, i2 = snapshot()
        dt, di = t2 - t1, i2 - i1
        return 0.0 if dt == 0 else round(100.0 * (dt - di) / dt, 1)
    except OSError:
        return 0.0


def _temperatura_c() -> float:
    try:
        with open(_THERMAL) as f:
            return int(f.read().strip()) / 1000.0
    except OSError:
        return 40.0


def ler_estado() -> EstadoHardware:
    estado = EstadoHardware(
        ram_livre_mb=_ram_livre_mb(),
        cpu_percent=_cpu_percent(),
        temperatura_c=_temperatura_c(),
    )
    log.debug("hardware: %s", estado)
    return estado
