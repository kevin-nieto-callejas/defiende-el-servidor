"""Selección y rollback: decide con criterios fijados y conserva cada decisión.

`decidir` compara un candidato contra configs/seleccion.yaml y contra el recomendado actual.
`promover` cambia manifests/recomendado.json y anota en historial.json; registrar un candidato
no lo promueve. `volver` restaura la versión anterior del historial (rollback).
`anotar` guarda cada veredicto, aceptado o rechazado, en decisiones.json. Va aparte del historial
porque el rollback vuelve a la entrada anterior de historial.json, que solo tiene promociones.
"""
import json
import time
from pathlib import Path

import yaml

CRITERIOS = Path("configs/seleccion.yaml")
RECOMENDADO = Path("manifests/recomendado.json")
HISTORIAL = Path("manifests/historial.json")
DECISIONES = Path("manifests/decisiones.json")


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


def evaluar_candidato(nombre, tipo, semilla=None):
    actual = _leer(RECOMENDADO)
    if actual and not actual["modelo"].startswith(f"{tipo}-"):
        actual = None   # el recomendado es de otro agente: solo aplican los criterios fijados
    evaluacion, generalizacion = _leer("metrics/evaluacion.json"), _leer("metrics/generalizacion.json")
    if semilla is not None:   # otra semilla: mismas pruebas, con sus resultados
        res = _leer("metrics/semillas.json" if tipo == "ppo" else "metrics/semillas-qlearning.json")[f"{tipo}-s{semilla}"]
        evaluacion = {"resultados": {tipo: res}}
        generalizacion = {"pruebas": generalizacion["pruebas"], "resultados": {tipo: res}}
    return {**decidir(nombre, tipo, evaluacion, generalizacion, actual), "tipo": tipo}


def anotar(veredicto):
    """Guarda el veredicto en decisiones.json; repetir la misma evaluación no agrega otra entrada."""
    decisiones = _leer(DECISIONES, [])
    entrada = {k: veredicto[k] for k in ("candidato", "tipo", "aceptado", "criterios", "valores")}
    previas = [d for d in decisiones if d["candidato"] == entrada["candidato"]]
    if previas and all(previas[-1][k] == entrada[k] for k in entrada):
        return previas[-1]
    entrada |= {"criterios_de": str(CRITERIOS), "fecha": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    decisiones.append(entrada)
    _escribir(DECISIONES, decisiones)
    return entrada


def promover(nombre, motivo, resultados=None):
    historial = _leer(HISTORIAL, [])
    if historial and historial[-1]["modelo"] == nombre:   # repetir el pipeline no cuenta como cambio
        return historial[-1]
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
