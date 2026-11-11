"""¿Un cambio de código altera el entrenamiento de Q-learning? Entrena una versión recortada y
guarda la tabla, para comparar dos versiones del código en la misma máquina.

Usa la configuración de params.yaml con 2 iteraciones de DAgger y 30 episodios. Con el mismo
código y la misma semilla el entrenamiento es determinista: si dos versiones dan la misma
tabla byte a byte, el cambio no afecta a Q-learning.

Uso (desde la raíz del repositorio):
  git worktree add /tmp/rally-viejo <commit>
  (cd /tmp/rally-viejo && PYTHONPATH=src python $PWD/scripts/analisis/comparar_qlearning.py /tmp/q_viejo.npz /tmp/punto_viejo)
  PYTHONPATH=src python scripts/analisis/comparar_qlearning.py /tmp/q_nuevo.npz /tmp/punto_nuevo
  # imprime el SHA-256 de q y de visitas: deben coincidir

Cada corrida necesita su propia carpeta de punto de guardado, para que no retome la otra.
"""
import hashlib
import sys

import numpy as np
import yaml

import rally
from rally.agentes.qlearning import entrenar
from rally.env import AutonomousRallyEnv

salida, punto = sys.argv[1], sys.argv[2]
p = yaml.safe_load(open("params.yaml", encoding="utf-8"))
amb, pq = p["ambiente"], dict(p["qlearning"])
pq.update(dagger_iter=2, dagger_episodios=2, episodios=30)
ag, hist = entrenar(lambda: AutonomousRallyEnv(**amb), pq, carpeta_punto=punto)
ag.guardar(salida)
d = np.load(salida)
print(f"código: {rally.__file__}")
print({k: hashlib.sha256(d[k].tobytes()).hexdigest()[:16] for k in ("q", "visitas")}, "episodios", len(hist))
