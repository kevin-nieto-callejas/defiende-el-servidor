"""Selección y rollback: decide con criterios fijados y conserva cada decisión.

`decidir` compara un candidato contra configs/seleccion.yaml y contra el recomendado actual.
`promover` cambia manifests/recomendado.json y anota en historial.json; registrar un candidato
no lo promueve. `volver` restaura la versión anterior del historial (rollback).
`anotar` guarda cada veredicto, aceptado o rechazado, en decisiones.json. Va aparte del historial
porque el rollback vuelve a la entrada anterior de historial.json, que solo tiene promociones.

La moto lleva su propia selección: criterios en la sección `moto:` de configs/seleccion.yaml y
recomendado, historial y decisiones en manifests/moto/. Un modelo de un vehículo nunca reemplaza
al recomendado del otro: corren en ambientes distintos.
"""
import json
import time
from pathlib import Path

import yaml

CRITERIOS = Path("configs/seleccion.yaml")
RECOMENDADO = Path("manifests/recomendado.json")
HISTORIAL = Path("manifests/historial.json")
DECISIONES = Path("manifests/decisiones.json")


def archivos(vehiculo="carro"):
    """(recomendado, historial, decisiones) del vehículo."""
    if vehiculo == "moto":
        base = Path("manifests/moto")
        return base / "recomendado.json", base / "historial.json", base / "decisiones.json"
    return RECOMENDADO, HISTORIAL, DECISIONES


def _criterios(tipo, vehiculo="carro"):
    todos = yaml.safe_load(CRITERIOS.read_text(encoding="utf-8"))
    return (todos["moto"] if vehiculo == "moto" else todos)[tipo]


def _leer(ruta, defecto=None):
    ruta = Path(ruta)
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else defecto


def _escribir(ruta, datos):
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")


def decidir(nombre, tipo, evaluacion, generalizacion, actual=None, vehiculo="carro"):
    """Devuelve el veredicto, criterio por criterio, sin promover nada."""
    c = _criterios(tipo, vehiculo)
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


def evaluar_candidato(nombre, tipo, semilla=None, vehiculo="carro"):
    recomendado, *_ = archivos(vehiculo)
    metricas = Path("metrics/moto") if vehiculo == "moto" else Path("metrics")
    actual = _leer(recomendado)
    if actual and not actual["modelo"].startswith(f"{tipo}-"):
        actual = None   # el recomendado es de otro agente: solo aplican los criterios fijados
    evaluacion, generalizacion = _leer(metricas / "evaluacion.json"), _leer(metricas / "generalizacion.json")
    if semilla is not None:   # otra semilla: mismas pruebas, con sus resultados
        res = _leer(metricas / ("semillas.json" if tipo == "ppo" else "semillas-qlearning.json"))[f"{tipo}-s{semilla}"]
        evaluacion = {"resultados": {tipo: res}}
        generalizacion = {"pruebas": generalizacion["pruebas"], "resultados": {tipo: res}}
    return {**decidir(nombre, tipo, evaluacion, generalizacion, actual, vehiculo), "tipo": tipo, "vehiculo": vehiculo}


def anotar(veredicto):
    """Guarda el veredicto en decisiones.json; repetir la misma evaluación no agrega otra entrada."""
    *_, ruta_decisiones = archivos(veredicto.get("vehiculo", "carro"))
    decisiones = _leer(ruta_decisiones, [])
    entrada = {k: veredicto[k] for k in ("candidato", "tipo", "aceptado", "criterios", "valores")}
    previas = [d for d in decisiones if d["candidato"] == entrada["candidato"]]
    if previas and all(previas[-1][k] == entrada[k] for k in entrada):
        return previas[-1]
    entrada |= {"criterios_de": str(CRITERIOS), "fecha": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    decisiones.append(entrada)
    _escribir(ruta_decisiones, decisiones)
    return entrada


def promover(nombre, motivo, resultados=None, vehiculo="carro"):
    ruta_recomendado, ruta_historial, _ = archivos(vehiculo)
    historial = _leer(ruta_historial, [])
    if historial and historial[-1]["modelo"] == nombre:   # repetir el pipeline no cuenta como cambio
        return historial[-1]
    entrada = {"modelo": nombre, "motivo": motivo, "resultados": resultados,
               "fecha": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    historial.append(entrada)
    _escribir(ruta_historial, historial)
    _escribir(ruta_recomendado, entrada)
    return entrada


def volver(motivo, vehiculo="carro"):
    """Rollback: restaura la recomendación anterior; queda como un paso más del historial."""
    _, ruta_historial, _ = archivos(vehiculo)
    historial = _leer(ruta_historial, [])
    if len(historial) < 2:
        raise ValueError("No hay una versión anterior a la cual volver")
    previa = historial[-2]
    return promover(previa["modelo"], f"rollback: {motivo}", previa.get("resultados"), vehiculo)
