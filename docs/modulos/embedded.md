# Módulo: Embedded / Linux

Alvo: TV Box ARMv7 com Armbian/Debian.

**Instalação na box:**

```bash
sudo cp -r tinyai-box /opt/tinyai-box
sudo cp /opt/tinyai-box/systemd/*.service /opt/tinyai-box/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tinyai.service tinyai-monitor.timer
```

**Monitoramento** (`scripts/monitor.sh`, a cada 5min via timer):

| Métrica | Limite | Ação recomendada |
|---|---|---|
| RAM livre | < 300MB | trocar para modelo menor / adiar tarefa |
| Temperatura | > 75°C | reduzir carga (pausar LLM local) |
| CPU sustentada | > 90% | rotear prompts para OpenRouter |

Logs: `journalctl -t tinyai-monitor` e `journalctl -u tinyai.service`.
Diagnóstico manual: `free -h`, `htop`, `swapon --summary`, `cat /sys/class/thermal/thermal_zone0/temp`.
