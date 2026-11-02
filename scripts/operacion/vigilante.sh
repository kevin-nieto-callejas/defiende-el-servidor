#!/bin/bash
# Vigilantes: cada minuto revisan la cola, los servicios, los errores, el avance y los recursos.
# Reinician lo que se cayó y anotan en runs/logs/alertas.log lo que necesita una decisión.
M=$HOME/code/defiende-el-servidor
cd "$M" || exit 1
E=runs/cola; L=runs/logs
mkdir -p "$E" "$L"
exec 8>"$E/candado-vigilante"
flock -n 8 || exit 0

hora() { date '+%F %T'; }
avisado=/tmp/rally-avisos; mkdir -p "$avisado"
una_vez() {  # avisa una sola vez por clave cada 30 minutos
  local f="$avisado/$1"; shift
  if [ ! -f "$f" ] || [ -n "$(find "$f" -mmin +30)" ]; then touch "$f"; echo "$(hora) ALERTA $*" >> "$L/alertas.log"; fi
}
arrancar() { setsid nohup "$@" < /dev/null & disown; }

vig_cola() {
  [ -f "$E/fin" ] || [ -f "$E/pausa" ] && return
  pgrep -f "runs/cola.sh" >/dev/null || { una_vez cola "la cola estaba caída: se relanza"; arrancar bash runs/cola.sh > /dev/null 2>&1; }
}

vig_servicio() {  # nombre patrón url comando...
  local n=$1 pat=$2 url=$3; shift 3
  curl -sf -m 20 -o /dev/null "$url" && return
  pgrep -f "$pat" >/dev/null && { una_vez "$n-lento" "$n no responde, proceso vivo"; return; }
  una_vez "$n" "$n caído: se relanza"
  arrancar "$@" >> "$L/$n.log" 2>&1
}

vig_errores() {  # busca trazas nuevas en los logs de la cola
  local pos=/tmp/rally-pos-errores
  touch "$pos"
  for f in "$L"/cola-*.log "$L"/repro-q5.log; do
    [ -f "$f" ] && [ "$f" -nt "$pos" ] || continue
    local t; t=$(tail -200 "$f" | grep -E "^(Traceback|ERROR|[A-Za-z.]*Error:)|Killed|MemoryError" | tail -1 | cut -c1-150)
    [ -n "$t" ] && una_vez "err-$(basename "$f")" "$(basename "$f"): $t"
  done
  touch "$pos"
}

vig_avance() {  # silencio no es éxito: un entrenamiento que no escribe en 25 min se reporta
  pgrep -f "dvc repro|rally semillas" >/dev/null || return
  local ultimo; ultimo=$(ls -t runs/ppo-punto/* runs/qlearning-punto/* runs/semillas/*/* mlflow.db 2>/dev/null | head -1)
  [ -n "$ultimo" ] && [ -n "$(find "$ultimo" -mmin +25)" ] && una_vez avance "sin avance hace 25 min: $ultimo"
}

vig_recursos() {
  local libre disco; libre=$(free -m | awk '/^Mem:/{print $7}'); disco=$(df --output=pcent / | tail -1 | tr -dc 0-9)
  [ "$libre" -lt 700 ] && una_vez ram "RAM disponible baja: $libre MB"
  [ "$disco" -gt 90 ] && una_vez disco "disco al $disco %"
  echo "$(hora) ram=${libre}MB disco=${disco}% carga=$(cut -d' ' -f1 /proc/loadavg) pasos=$(ls $E/*.ok 2>/dev/null | wc -l)" > "$L/vigilante-estado.txt"
}

while true; do
  vig_cola
  vig_servicio api "rally api" http://127.0.0.1:8000/api/salud taskset -c 7 .venv/bin/rally api --puerto 8000
  vig_servicio visor "rally web" http://127.0.0.1:8765/ runs/visor.sh
  vig_errores
  vig_avance
  vig_recursos
  sleep 60
done
