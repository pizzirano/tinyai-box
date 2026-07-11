"""Testes das regras puras de decisão do Scheduler (sem rede, sem mocks pesados)."""

from scheduler.rotas import (
    Decisao,
    EstadoHardware,
    Requisicao,
    Rota,
    TipoEntrada,
    escolher_rota,
    estimar_complexidade,
    hardware_suporta_local,
)

HW_SAUDAVEL = EstadoHardware(ram_livre_mb=900, cpu_percent=30.0, temperatura_c=50.0)
HW_SEM_RAM = EstadoHardware(ram_livre_mb=200, cpu_percent=30.0, temperatura_c=50.0)
HW_QUENTE = EstadoHardware(ram_livre_mb=900, cpu_percent=30.0, temperatura_c=80.0)
HW_CPU_ALTA = EstadoHardware(ram_livre_mb=900, cpu_percent=95.0, temperatura_c=50.0)


# --- complexidade -----------------------------------------------------------

def test_prompt_curto_e_pequeno():
    assert estimar_complexidade("qual a capital do brasil?") == "pequeno"


def test_prompt_longo_e_complexo():
    assert estimar_complexidade("x" * 300) == "complexo"


def test_palavra_chave_torna_complexo():
    assert estimar_complexidade("explique a teoria da relatividade") == "complexo"


# --- limites de hardware ----------------------------------------------------

def test_hardware_saudavel_suporta_local():
    assert hardware_suporta_local(HW_SAUDAVEL)


def test_pouca_ram_bloqueia_local():
    assert not hardware_suporta_local(HW_SEM_RAM)


def test_temperatura_alta_bloqueia_local():
    assert not hardware_suporta_local(HW_QUENTE)


def test_cpu_alta_bloqueia_local():
    assert not hardware_suporta_local(HW_CPU_ALTA)


# --- roteamento -------------------------------------------------------------

def _req(texto: str, tipo=TipoEntrada.TEXTO) -> Requisicao:
    return Requisicao(conteudo=texto, tipo=tipo)


def test_audio_vai_para_pipeline_de_voz():
    d = escolher_rota(_req("", TipoEntrada.AUDIO), HW_SAUDAVEL)
    assert d.rota is Rota.VOZ


def test_pequeno_com_hardware_ok_vai_local():
    d = escolher_rota(_req("oi, tudo bem?"), HW_SAUDAVEL)
    assert d.rota is Rota.LOCAL
    assert d.fallback is Rota.REMOTA


def test_complexo_vai_para_openrouter():
    d = escolher_rota(_req("explique passo a passo como funciona docker"), HW_SAUDAVEL)
    assert d.rota is Rota.REMOTA


def test_hardware_pressionado_empurra_para_remoto():
    d = escolher_rota(_req("oi"), HW_SEM_RAM)
    assert d.rota is Rota.REMOTA
    assert "hardware pressionado" in d.motivo


def test_sem_openrouter_faz_melhor_esforco_local():
    d = escolher_rota(_req("explique tudo detalhadamente"), HW_SAUDAVEL,
                      openrouter_disponivel=False)
    assert d.rota is Rota.LOCAL
    assert d.fallback is None


def test_decisao_e_imutavel():
    d = escolher_rota(_req("oi"), HW_SAUDAVEL)
    assert isinstance(d, Decisao)
    try:
        d.rota = Rota.REMOTA  # type: ignore[misc]
        assert False, "Decisao deveria ser frozen"
    except AttributeError:
        pass
