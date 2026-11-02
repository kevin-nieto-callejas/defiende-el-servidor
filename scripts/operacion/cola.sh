#!/bin/bash
# Cola nocturna: corre los pasos en orden y recuerda cuáles terminó (runs/cola/*.ok).
# Si la cortan, al relanzarla sigue donde iba; PPO y Q-learning reanudan desde su punto de guardado.
M=$HOME/code/defiende-el-servidor
export PATH="$M/.venv/bin:/usr/local/bin:/usr/bin:/bin"
export OMP_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$M" || exit 1
E=runs/cola; L=runs/logs
mkdir -p "$E" "$L"
exec 9>"$E/candado"
flock -n 9 || exit 0   # una sola cola a la vez

hora() { date '+%F %T'; }
nota() { echo "$(hora) $*" >> "$L/cola.log"; }
alerta() { echo "$(hora) ALERTA $*" >> "$L/alertas.log"; nota "ALERTA $*"; }

paso() {  # paso NOMBRE INTENTOS comando...
  local n=$1 intentos=$2; shift 2
  [ -f "$E/$n.ok" ] && return 0
  for i in $(seq 1 "$intentos"); do
    nota "INICIO $n (intento $i)"
    if "$@" >> "$L/cola-$n.log" 2>&1; then
      touch "$E/$n.ok"; nota "FIN $n"; echo "$(hora) HITO $n terminado" >> "$L/alertas.log"
      return 0
    fi
    nota "FALLO $n (intento $i)"
    sleep 60
  done
  alerta "$n falló $intentos veces; ver $L/cola-$n.log"
  touch "$E/pausa"
  exit 1
}

esperar_dvc() { while pgrep -f "^$M/.venv/bin/python3 $M/.venv/bin/dvc repro" >/dev/null; do sleep 30; done; }
reproducir() { taskset -c 0-5 env RALLY_VIVO=1 dvc repro; }
empujar() { dvc push -r almacen && dvc push -r dagshub; }

guardar() {
  git add dvc.lock metrics
  git diff --cached --quiet || git commit -q -m "$1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
}

compuerta() {  # Solo gasta horas en más semillas si el candidato cumple los criterios fijados
  .venv/bin/rally seleccionar ppo-modelo-v5 --tipo ppo 2>/dev/null | tail -1 > "$E/veredicto-ppo.json"
  .venv/bin/rally seleccionar qlearning-modelo-v7 --tipo qlearning 2>/dev/null | tail -1 > "$E/veredicto-qlearning.json"
  python3 -c "import json,sys; v=json.load(open('$E/veredicto-ppo.json')); print(v); sys.exit(0 if v['aceptado'] else 1)"
}

paso esperar-q 1 esperar_dvc
paso repro 3 reproducir
paso guardar-repro 1 guardar "Resultados de la familia 0.4: Q-learning y PPO v5"
paso subir-modelos 5 empujar
if ! paso_ok=$(compuerta); then
  alerta "PPO v5 no cumple los criterios: se detiene antes de las semillas. $paso_ok"
  touch "$E/pausa"
  exit 1
fi
echo "$(hora) HITO compuerta aprobada: $paso_ok" >> "$L/alertas.log"
paso semillas-ppo 3 taskset -c 0-5 .venv/bin/rally semillas ppo 1 2
paso semillas-q 3 taskset -c 0-5 .venv/bin/rally semillas qlearning 1 2
paso guardar-semillas 1 guardar "Resultados de las 3 semillas de los finalistas"
touch "$E/fin"
echo "$(hora) HITO cola completa" >> "$L/alertas.log"
