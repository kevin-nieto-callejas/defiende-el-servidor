"""Enlaces de MLflow en DagsHub e intentos interrumpidos, para el catálogo de la web.

    python scripts/operacion/enlaces_dagshub.py      (después de `rally sincronizar` y `rally manifiesto`)

Los manifiestos guardan el run de origen (el MLflow local o el de GitHub Actions). `rally sincronizar` copia cada
run a DagsHub con otro id y la etiqueta `origen_run_id`. Este script lee DagsHub (no escribe nada) y deja dos archivos:

- manifests/enlaces_mlflow.json: {run de origen: {experimento, run en DagsHub}}, para que la web enlace directo a
  cada run sin consultar DagsHub.
- manifests/interrumpidos.json: los runs que terminaron como KILLED o FAILED, con su diagnóstico y el estado
  «sin checkpoint disponible», como pide el enunciado. Se conservan; ninguno produjo pesos utilizables.
"""

import json
from pathlib import Path

from mlflow import MlflowClient

from rally.sincronizar import DAGSHUB_URI, _credenciales

ENLACES = Path("manifests/enlaces_mlflow.json")
INTERRUMPIDOS = Path("manifests/interrumpidos.json")


def _fecha(ms):
    import datetime
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if ms else None


def main():
    _credenciales()
    cliente = MlflowClient(tracking_uri=DAGSHUB_URI)
    catalogo = json.loads(Path("manifests/catalogo.json").read_text(encoding="utf-8"))
    ids = {f["run_id"] for f in catalogo if f.get("run_id")}
    enlaces, interrumpidos = {}, []
    for exp in cliente.search_experiments():
        for r in cliente.search_runs([exp.experiment_id], max_results=5000, order_by=["attributes.start_time ASC"]):
            origen = r.data.tags.get("origen_run_id", r.info.run_id)
            destino = {"experimento": exp.experiment_id, "run": r.info.run_id}
            if origen in ids or r.info.run_id in ids:
                enlaces[origen if origen in ids else r.info.run_id] = destino
            if r.info.status in ("KILLED", "FAILED"):
                t = r.data.tags
                pasos = max((m for m in r.data.metrics if m.startswith("eval_") or m.startswith("episodio_")),
                            key=len, default=None)
                interrumpidos.append({
                    "run_id": origen, "nombre": r.info.run_name, "experimento": exp.name, "estado": r.info.status,
                    "inicio": _fecha(r.info.start_time),
                    "ambiente_version": t.get("ambiente_version"), "git_commit": t.get("git_commit"),
                    "semilla": r.data.params.get("semilla") or r.data.params.get("seed"),
                    "hipotesis": t.get("hipotesis") or r.data.params.get("hipotesis"),
                    "diagnostico": t.get("diagnostico") or (t.get("interrumpida") and f"Interrumpido: {t['interrumpida']}")
                    or t.get("mlflow.note.content") or "Interrumpido sin nota",
                    "checkpoint": "sin checkpoint disponible",
                    "metricas_registradas": len(r.data.metrics) if pasos else 0,
                    "dagshub": destino})
    ENLACES.write_text(json.dumps(dict(sorted(enlaces.items())), indent=2) + "\n", encoding="utf-8")
    INTERRUMPIDOS.write_text(json.dumps(interrumpidos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(enlaces)} de {len(ids)} runs del catálogo enlazados; sin copia en DagsHub: {sorted(ids - set(enlaces))}")
    print(f"{len(interrumpidos)} intentos interrumpidos en {INTERRUMPIDOS}")


if __name__ == "__main__":
    main()
