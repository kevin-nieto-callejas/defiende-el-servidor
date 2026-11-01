"""Selección y rollback: decide con criterios fijados y conserva cada decisión.

`decidir` compara un candidato contra configs/seleccion.yaml y contra el recomendado actual.
`promover` cambia manifests/recomendado.json y anota en historial.json; registrar un candidato
no lo promueve. `volver` restaura la versión anterior del historial (rollback).
"""
import json
import time
from pathlib import Path

import yaml

CRITERIOS = Path("configs/seleccion.yaml")
RECOMENDADO = Path("manifests/recomendado.json")
HISTORIAL = Path("manifests/historial.json")


def _leer(ruta, defecto=None):
    ruta = Path(ruta)
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else defecto


def _escribir(ruta, datos):
    Path(ruta).write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")


def decidir(nombre, tipo, evaluacion, generalizacion, actual=None):
    """Devuelve el veredicto, criterio por criterio, sin promover nada."""
    c = yaml.safe_load(CRITERIOS.read_text(encoding="utf-8"))[tipo]
    r = evaluacion["resultados"][tipo]
    seco, mojado = r["seco"]["vueltas_pct"], r["mojado"]["vueltas_pct"]
    pruebas = generalizacion["resultados"][tipo]
    calificadas = [n for n, p in generalizacion["pruebas"].items() if p.get("referencia")]
    extremos = sum(pruebas[n]["vueltas_pct"] for n in calificadas) / len(calificadas)
    peor = min(calificadas, key=lambda n: pruebas[n]["vueltas_pct"])
    t = r["seco"]["tiempo_mediano_s"]
    criterios = {
        "seco": seco >= c["seco_min_pct"], "mojado": mojado >= c["mojado_min_pct"],
        "tiempo_seco": t is not None and t <= c["tiempo_seco_max_s"],
        "extremos": extremos >= c["extremos_min_pct"],
        "peor_prueba": pruebas[peor]["vueltas_pct"] >= c["prueba_min_pct"],
    }
    if actual and actual.get("resultados"):
        criterios["no_pierde_seco"] = seco >= actual["resultados"]["seco"]["vueltas_pct"] - c["perdida_max_puntos"]
        criterios["no_pierde_mojado"] = mojado >= actual["resultados"]["mojado"]["vueltas_pct"] - c["perdida_max_puntos"]
    return {"candidato": nombre, "aceptado": all(criterios.values()), "criterios": criterios,
            "valores": {"seco": seco, "mojado": mojado, "tiempo_seco_s": t, "extremos_pct": round(extremos, 1),
                        "peor_prueba": {peor: pruebas[peor]["vueltas_pct"]}}}


def promover(nombre, motivo, resultados=None):
    historial = _leer(HISTORIAL, [])
    entrada = {"modelo": nombre, "motivo": motivo, "resultados": resultados,
               "fecha": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    historial.append(entrada)
    _escribir(HISTORIAL, historial)
    _escribir(RECOMENDADO, entrada)
    return entrada


def volver(motivo):
    """Rollback: restaura la recomendación anterior; queda como un paso más del historial."""
    historial = _leer(HISTORIAL, [])
    if len(historial) < 2:
        raise ValueError("No hay una versión anterior a la cual volver")
    previa = historial[-2]
    return promover(previa["modelo"], f"rollback: {motivo}", previa.get("resultados"))
