#!/bin/bash
# Test final reservado, con los modelos ya elegidos, y subida de los pesos finalistas.
M=$HOME/code/defiende-el-servidor
export PATH="$M/.venv/bin:/usr/local/bin:/usr/bin:/bin"
export OMP_NUM_THREADS=1 PYTHONUNBUFFERED=1
cd "$M"
if taskset -c 0-6 rally test-final --ppo finalistas/ppo-s1/modelo.zip --qlearning finalistas/qlearning-s1/q_table.npz > runs/logs/test-final.log 2>&1; then
  echo "$(date '+%F %T') HITO test final terminado" >> runs/logs/alertas.log
else
  echo "$(date '+%F %T') ALERTA test final falló; ver runs/logs/test-final.log" >> runs/logs/alertas.log
fi
dvc push -r almacen > runs/logs/subir-almacen.log 2>&1 && echo "$(date '+%F %T') HITO finalistas en almacen" >> runs/logs/alertas.log
for i in $(seq 1 30); do
  if dvc push -r dagshub > runs/logs/subir-dagshub.log 2>&1; then
    echo "$(date '+%F %T') HITO finalistas en DagsHub" >> runs/logs/alertas.log
    exit 0
  fi
  sleep 300
done
echo "$(date '+%F %T') ALERTA la subida de finalistas a DagsHub sigue fallando" >> runs/logs/alertas.log
