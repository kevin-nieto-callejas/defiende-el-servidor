"""Lleva los experimentos de MLflow de la moto de un equipo a DagsHub sin copiar mlflow.db.

La base de MLflow guarda rutas absolutas del equipo donde se entrenó y su esquema depende de la
versión de MLflow, así que no se puede abrir en otro computador. Este script la pasa a archivos
simples y luego los sube:

    # En el equipo donde se entrenó:
    python scripts/operacion/mlflow_moto.py exportar entrega/mlflow-moto
    # En cualquier equipo con el repositorio, DAGSHUB_TOKEN en .env:
    python scripts/operacion/mlflow_moto.py subir entrega/mlflow-moto

`subir` es idempotente igual que `rally sincronizar`: cada corrida lleva la etiqueta `origen_run_id`
y no se sube dos veces. También crea las versiones de los modelos registrados con sus alias.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

import mlflow.artifacts
from mlflow import MlflowClient
from mlflow.entities import Metric, Param

from rally.agentes.seguimiento import EXPERIMENTO_MOTO, MODELOS_MOTO, TRACKING_URI


def exportar(destino):
    destino = Path(destino)
    origen = MlflowClient(tracking_uri=TRACKING_URI)
    exp = origen.get_experiment_by_name(EXPERIMENTO_MOTO)
    if exp is None:
        raise SystemExit(f"No hay corridas de {EXPERIMENTO_MOTO} en este equipo")
    corridas = origen.search_runs([exp.experiment_id], max_results=5000, order_by=["attributes.start_time ASC"])
    for run in corridas:
        rid = run.info.run_id
        d = destino / "corridas" / rid
        d.mkdir(parents=True, exist_ok=True)
        metricas = []
        for clave in run.data.metrics:
            metricas += [[m.key, m.value, m.timestamp, m.step] for m in origen.get_metric_history(rid, clave)]
        (d / "corrida.json").write_text(json.dumps({
            "run_id": rid, "nombre": run.info.run_name, "estado": run.info.status,
            "inicio": run.info.start_time, "fin": run.info.end_time,
            "params": run.data.params,
            "tags": {k: v for k, v in run.data.tags.items() if not k.startswith("mlflow.log-model")},
            "metricas": metricas,
        }, ensure_ascii=False), encoding="utf-8")
        ruta = origen.download_artifacts(rid, "", str(d / "artefactos"))
        print(f"  {run.info.run_name}: {len(metricas)} puntos, artefactos en {ruta}")
    modelos = []
    for nombre in MODELOS_MOTO.values():
        for v in origen.search_model_versions(f"name='{nombre}'"):
            carpeta = destino / "modelos" / f"{nombre}-v{v.version}"
            mlflow.artifacts.download_artifacts(artifact_uri=v.source, dst_path=str(carpeta), tracking_uri=TRACKING_URI)
            alias = origen.get_model_version(nombre, v.version).aliases or []
            modelos.append({"nombre": nombre, "version": v.version, "run_id": v.run_id, "tags": v.tags,
                            "alias": list(alias), "carpeta": carpeta.name})
            print(f"  modelo {nombre} v{v.version} {list(alias)}")
    (destino / "modelos.json").write_text(json.dumps(modelos, indent=2, ensure_ascii=False), encoding="utf-8")


def subir(carpeta):
    from rally.sincronizar import DAGSHUB_URI, _credenciales, _en_lotes

    carpeta = Path(carpeta)
    _credenciales()
    destino = MlflowClient(tracking_uri=DAGSHUB_URI)
    exp = destino.get_experiment_by_name(EXPERIMENTO_MOTO)
    exp_id = exp.experiment_id if exp else destino.create_experiment(EXPERIMENTO_MOTO)
    copiadas = {r.data.tags["origen_run_id"]: r.info.run_id
                for r in destino.search_runs([exp_id], max_results=5000) if "origen_run_id" in r.data.tags}
    for archivo in sorted((carpeta / "corridas").glob("*/corrida.json")):
        c = json.loads(archivo.read_text(encoding="utf-8"))
        if c["run_id"] in copiadas:
            continue
        nuevo = destino.create_run(exp_id, start_time=c["inicio"], run_name=c["nombre"],
                                   tags={**c["tags"], "origen_run_id": c["run_id"]})
        nid = nuevo.info.run_id
        for lote in _en_lotes([Param(k, str(v)[:6000]) for k, v in c["params"].items()], 100):
            destino.log_batch(nid, params=lote)
        for lote in _en_lotes([Metric(*m) for m in c["metricas"]], 1000):
            destino.log_batch(nid, metrics=lote)
        artefactos = archivo.parent / "artefactos"
        if artefactos.exists() and any(artefactos.iterdir()):
            destino.log_artifacts(nid, str(artefactos))
        destino.set_terminated(nid, status=c["estado"], end_time=c["fin"])
        copiadas[c["run_id"]] = nid
        print(f"  ✔ {c['nombre']}")
    for m in json.loads((carpeta / "modelos.json").read_text(encoding="utf-8")):
        nid = copiadas.get(m["run_id"])
        if nid is None:
            continue
        try:
            destino.get_registered_model(m["nombre"])
        except Exception:
            destino.create_registered_model(m["nombre"])
        ya = {v.tags.get("origen_run_id") for v in destino.search_model_versions(f"name='{m['nombre']}'")}
        if m["run_id"] in ya:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(carpeta / "modelos" / m["carpeta"], Path(tmp) / "modelo")
            destino.log_artifacts(nid, str(Path(tmp) / "modelo"), "modelo")
        nv = destino.create_model_version(m["nombre"], source=f"runs:/{nid}/modelo", run_id=nid,
                                          tags={**m["tags"], "origen_run_id": m["run_id"], "origen_version": m["version"]})
        for a in m["alias"]:
            try:
                destino.set_registered_model_alias(m["nombre"], a, nv.version)
            except Exception as e:
                print(f"  · alias @{a}: {e}")
        print(f"  ✔ modelo {m['nombre']} v{m['version']} → DagsHub v{nv.version}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("exportar", "subir"):
        raise SystemExit(__doc__)
    (exportar if sys.argv[1] == "exportar" else subir)(sys.argv[2])
