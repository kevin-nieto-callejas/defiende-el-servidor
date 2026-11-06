"""Copia los experimentos de MLflow locales (mlflow.db) al MLflow de DagsHub.

    rally sincronizar

Copia cada corrida con sus parámetros, etiquetas, historial completo de métricas
y artefactos, y después los modelos registrados (versiones, etiquetas y alias).
Es idempotente: cada corrida copiada lleva la etiqueta `origen_run_id`, así que
volver a correrlo solo sube lo nuevo.

Credenciales: DAGSHUB_TOKEN en el archivo .env (no se sube a git).
"""

import os
import tempfile
from pathlib import Path

import mlflow.artifacts
from mlflow import MlflowClient
from mlflow.entities import Metric, Param, RunTag

from rally.agentes.seguimiento import EXPERIMENTO, MODELOS, TRACKING_URI

DAGSHUB_USUARIO = "kevin-nieto-callejas"
DAGSHUB_REPO = "autonomous-rally"
DAGSHUB_URI = f"https://dagshub.com/{DAGSHUB_USUARIO}/{DAGSHUB_REPO}.mlflow"


def leer_env(clave):
    if os.environ.get(clave):
        return os.environ[clave]
    env = Path(".env")
    if env.exists():
        for linea in env.read_text(encoding="utf-8").splitlines():
            if linea.strip().startswith(f"{clave}="):
                return linea.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _credenciales():
    token = leer_env("DAGSHUB_TOKEN")
    if not token:
        raise SystemExit("Falta DAGSHUB_TOKEN en el archivo .env")
    os.environ["MLFLOW_TRACKING_USERNAME"] = DAGSHUB_USUARIO
    os.environ["MLFLOW_TRACKING_PASSWORD"] = token


def _en_lotes(items, n):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def sincronizar(log=print):
    _credenciales()
    origen = MlflowClient(tracking_uri=TRACKING_URI)
    destino = MlflowClient(tracking_uri=DAGSHUB_URI)

    exp_o = origen.get_experiment_by_name(EXPERIMENTO)
    if exp_o is None:
        log("No hay experimentos locales todavía.")
        return {}
    exp_d = destino.get_experiment_by_name(EXPERIMENTO)
    exp_d_id = exp_d.experiment_id if exp_d else destino.create_experiment(EXPERIMENTO)

    # Corridas ya copiadas: origen_run_id -> run_id en DagsHub
    copiadas = {r.data.tags["origen_run_id"]: r.info.run_id
                for r in destino.search_runs([exp_d_id], max_results=5000)
                if "origen_run_id" in r.data.tags}

    corridas = origen.search_runs([exp_o.experiment_id], max_results=5000,
                                  order_by=["attributes.start_time ASC"])
    nuevas = 0
    for run in corridas:
        rid = run.info.run_id
        if rid in copiadas:
            continue
        if run.info.status == "RUNNING":
            log(f"  · {run.info.run_name}: sigue corriendo, se copia la próxima vez")
            continue
        tags = {k: v for k, v in run.data.tags.items() if not k.startswith("mlflow.log-model")}
        tags["origen_run_id"] = rid
        nuevo = destino.create_run(exp_d_id, start_time=run.info.start_time, tags=tags,
                                   run_name=run.info.run_name)
        nid = nuevo.info.run_id
        params = [Param(k, str(v)[:6000]) for k, v in run.data.params.items()]
        for lote in _en_lotes(params, 100):
            destino.log_batch(nid, params=lote)
        metricas = []
        for clave in run.data.metrics:
            metricas += [Metric(m.key, m.value, m.timestamp, m.step)
                         for m in origen.get_metric_history(rid, clave)]
        for lote in _en_lotes(metricas, 1000):
            destino.log_batch(nid, metrics=lote)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = origen.download_artifacts(rid, "", tmp)
            if any(Path(ruta).iterdir()):
                destino.log_artifacts(nid, ruta)
        destino.set_terminated(nid, status=run.info.status, end_time=run.info.end_time)
        copiadas[rid] = nid
        nuevas += 1
        log(f"  ✔ {run.info.run_name} ({len(params)} parámetros, {len(metricas)} puntos de métricas)")

    # Modelos registrados: misma versión, etiquetas y alias
    modelos = 0
    for nombre in MODELOS.values():
        try:
            versiones = origen.search_model_versions(f"name='{nombre}'")
        except Exception:
            continue
        if not versiones:
            continue
        try:
            destino.get_registered_model(nombre)
        except Exception:
            destino.create_registered_model(nombre)
        ya = {v.tags.get("origen_run_id") for v in destino.search_model_versions(f"name='{nombre}'")}
        for v in sorted(versiones, key=lambda x: int(x.version)):
            if v.run_id not in copiadas:
                continue
            # En MLflow 3 los archivos del modelo viven aparte de la corrida (LoggedModel):
            # se descargan y se suben a la carpeta "modelo" de la corrida copiada.
            if not destino.list_artifacts(copiadas[v.run_id], "modelo"):
                with tempfile.TemporaryDirectory() as tmp:
                    ruta = mlflow.artifacts.download_artifacts(artifact_uri=v.source, dst_path=tmp,
                                                               tracking_uri=TRACKING_URI)
                    destino.log_artifacts(copiadas[v.run_id], ruta, "modelo")
                log(f"  ✔ archivos del modelo {nombre} v{v.version}")
            if v.run_id in ya:
                continue
            nv = destino.create_model_version(nombre, source=f"runs:/{copiadas[v.run_id]}/modelo",
                                              run_id=copiadas[v.run_id],
                                              tags={**v.tags, "origen_run_id": v.run_id,
                                                    "origen_version": v.version})
            modelos += 1
            log(f"  ✔ modelo {nombre} v{v.version} → DagsHub v{nv.version}")
        # search_model_versions no trae los alias: se piden versión por versión
        alias = {a: v for v in versiones
                 for a in (origen.get_model_version(nombre, v.version).aliases or [])}
        dest_por_origen = {x.tags.get("origen_run_id"): x.version
                           for x in destino.search_model_versions(f"name='{nombre}'")}
        for a, v in alias.items():
            if v.run_id in dest_por_origen:
                try:
                    destino.set_registered_model_alias(nombre, a, dest_por_origen[v.run_id])
                except Exception as e:  # el servidor puede no soportar alias
                    log(f"  · alias @{a} no se pudo copiar: {e}")
    return {"corridas_nuevas": nuevas, "modelos_nuevos": modelos,
            "url": f"https://dagshub.com/{DAGSHUB_USUARIO}/{DAGSHUB_REPO}/experiments"}
