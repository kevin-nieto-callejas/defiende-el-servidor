#!/bin/bash
# Cuando la cola termina las semillas: evaluación oficial de lo que falta, con todos los núcleos.
M=$HOME/code/defiende-el-servidor
export PATH="$M/.venv/bin:/usr/local/bin:/usr/bin:/bin"
export OMP_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$M"
until [ -f runs/cola/fin ]; do sleep 60; done
if taskset -c 0-5 dvc repro > runs/logs/repro-final.log 2>&1; then
  git add dvc.lock metrics
  git diff --cached --quiet || git commit -q -m "Evaluación oficial de Q-learning v8

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  echo "$(date '+%F %T') HITO evaluacion oficial q8" >> runs/logs/alertas.log
else
  echo "$(date '+%F %T') ALERTA dvc repro final falló; ver runs/logs/repro-final.log" >> runs/logs/alertas.log
fi
