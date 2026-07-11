#!/bin/sh
# monitor.sh — diagnóstico de recursos do TinyAI Box (ARMv7 / Armbian).
# Thresholds (Embedded Engineer): CPU > 90%, temperatura > 75°C, RAM livre < 300MB.
# Uso: ./scripts/monitor.sh   (ou via systemd timer tinyai-monitor.timer)

set -eu

LIMITE_RAM_MB=300
LIMITE_TEMP_C=75
LIMITE_CPU=90

ram_livre_mb=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)

temp_raw=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0)
temp_c=$((temp_raw / 1000))

# CPU: duas amostras de /proc/stat com 1s de intervalo (POSIX, sem bashisms)
amostra1=$(grep '^cpu ' /proc/stat)
sleep 1
amostra2=$(grep '^cpu ' /proc/stat)
cpu_pct=$(printf '%s\n%s\n' "$amostra1" "$amostra2" | awk '
  NR==1 {t1=$2+$3+$4+$5+$6+$7+$8; i1=$5}
  NR==2 {t2=$2+$3+$4+$5+$6+$7+$8; i2=$5;
         dt=t2-t1; di=i2-i1;
         if (dt>0) printf "%d", 100*(dt-di)/dt; else printf "0"}')

swap_uso=$(swapon --summary --noheadings 2>/dev/null | awk '{print $4}' | head -1)

echo "RAM livre: ${ram_livre_mb}MB | CPU: ${cpu_pct}% | Temp: ${temp_c}°C | Swap usado: ${swap_uso:-0}kB"

alerta=0
[ "$ram_livre_mb" -lt "$LIMITE_RAM_MB" ] && { echo "ALERTA: RAM livre < ${LIMITE_RAM_MB}MB -> considerar modelo menor ou adiar tarefa"; alerta=1; }
[ "$temp_c" -gt "$LIMITE_TEMP_C" ]       && { echo "ALERTA: temperatura > ${LIMITE_TEMP_C}°C -> reduzir carga (pausar LLM local)"; alerta=1; }
[ "$cpu_pct" -gt "$LIMITE_CPU" ]         && { echo "ALERTA: CPU > ${LIMITE_CPU}% sustentado -> rotear prompts para OpenRouter"; alerta=1; }

# Log estruturado para journalctl
logger -t tinyai-monitor "ram_livre_mb=${ram_livre_mb} cpu_pct=${cpu_pct} temp_c=${temp_c} alerta=${alerta}"

exit 0
