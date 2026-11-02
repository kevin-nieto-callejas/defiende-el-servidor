#!/bin/bash
# Semillas de Q-learning en paralelo con las de PPO: núcleos y archivo de resultados aparte.
M=$HOME/code/defiende-el-servidor
export PATH="$M/.venv/bin:/usr/local/bin:/usr/bin:/bin"
export OMP_NUM_THREADS=1 PYTHONUNBUFFERED=1 RALLY_SEMILLAS=metrics/semillas-qlearning.json
cd "$M"
for i in 1 2 3; do
  if taskset -c 6 rally semillas qlearning 1 2 >> runs/logs/semillas-q.log 2>&1; then
    echo "$(date '+%F %T') HITO semillas de Q-learning terminadas" >> runs/logs/alertas.log
    exit 0
  fi
  sleep 60
done
echo "$(date '+%F %T') ALERTA semillas de Q-learning fallaron; ver runs/logs/semillas-q.log" >> runs/logs/alertas.log
