"""Test reservado (como `rally test-final`) para un modelo exportado a numpy, una sola vez.

Mismo procedimiento que rally.testfinal: 100 semillas secretas, seco, lluvia y las pruebas de
generalización de params.yaml, y solo se publica el SHA-256 de la semilla. Corre la red con
agentes/red_numpy.py (exportación verificada contra PyTorch), así que sirve en equipos donde el
.zip no se puede cargar. La semilla vive en .env (no se sube a git) bajo la clave indicada; si no
existe, se genera al azar y se guarda ahí sin mostrarla. Se niega a correr si la salida ya existe.

Uso:
  python scripts/analisis/test_final_npz.py --modelo ppo-modelo-v6-pistas-s1=models/semillas-v6/v6-s1/modelo.npz \\
      --clave RALLY_SEMILLA_RESERVADA_V6S1 --salida metrics/test-final-v6-s1.json
"""
import argparse
import hashlib
import json
import os
import platform
import secrets
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from generalizacion_modelos import _lote  # noqa: E402  (mismo episodio que la etapa generalizacion)

from rally.pipeline import _metricas  # noqa: E402

N = 100
ENV = Path(".env")


def semilla(clave):
    """Lee la semilla de .env; si no está, la crea al azar y la guarda sin imprimirla."""
    if ENV.exists():
        for linea in ENV.read_text(encoding="utf-8").splitlines():
            if linea.startswith(f"{clave}="):
                return int(linea.split("=", 1)[1]), False
    base = 2_000_000 + secrets.randbelow(898_000_000)
    with ENV.open("a", encoding="utf-8") as f:
        f.write(f"{clave}={base}\n")
    os.chmod(ENV, 0o600)
    return base, True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", required=True, metavar="NOMBRE=RUTA.npz")
    ap.add_argument("--clave", required=True, help="nombre de la variable de .env con la semilla")
    ap.add_argument("--salida", required=True)
    a = ap.parse_args(argv)
    if Path(a.salida).exists():
        raise SystemExit(f"El test reservado ya se corrió ({a.salida}): no se repite")
    nombre, ruta = a.modelo.split("=", 1)
    base, nueva = semilla(a.clave)
    semillas = list(range(base, base + N))
    p = yaml.safe_load(Path("params.yaml").read_text(encoding="utf-8"))
    amb, pe, pg = p["ambiente"], p["evaluacion"], p["generalizacion"]
    pruebas = [{"nombre": "seco", "ambiente": {"mu": pe["mu_seco"]}},
               {"nombre": "mojado", "ambiente": {"mu": pe["mu_mojado"]}}] + pg["pruebas"]
    tareas = [(ruta, amb, pr, semillas[i:i + 10]) for pr in pruebas for i in range(0, N, 10)]
    filas = {}
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 1)) as ex:
        for _, prueba, out in ex.map(_lote, tareas):
            filas.setdefault(prueba, []).extend(out)
    with np.load(ruta, allow_pickle=False) as z:
        fuente, dif = str(z["fuente_sha256"]), float(z["max_diferencia"])
    res = {
        "episodios": N, "semillas_sha256": hashlib.sha256(str(base).encode()).hexdigest(),
        "semilla_en": f".env ({a.clave}), fuera del repositorio", "semilla_nueva": nueva,
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "corridas": 1,
        "modelo": {"nombre": nombre, "model_sha256": fuente, "motor": "numpy", "max_diferencia_con_pytorch": dif},
        "plataforma": f"{platform.system()} {platform.machine()}, Python {platform.python_version()}",
        "segundos": round(time.time() - t0, 1),
        "resultados": {nombre: {pr["nombre"]: _metricas(filas[pr["nombre"]]) for pr in pruebas}},
    }
    Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(a.salida).write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    r = res["resultados"][nombre]
    calificadas = [pr["nombre"] for pr in pg["pruebas"] if pr.get("referencia")]
    print(f"semillas sha256 {res['semillas_sha256']}  ({res['segundos']} s)")
    print(f"seco {r['seco']['vueltas_pct']} % ({r['seco']['tiempo_mediano_s']} s) · lluvia {r['mojado']['vueltas_pct']} %"
          f" · extremos {sum(r[n]['vueltas_pct'] for n in calificadas) / len(calificadas):.1f} %"
          f" · peor {min(calificadas, key=lambda n: r[n]['vueltas_pct'])}")


if __name__ == "__main__":
    main()
