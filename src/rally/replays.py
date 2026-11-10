"""Datos estáticos para la web sin API: catálogo y vueltas ya simuladas, marcadas como replay.

Mientras no haya una API pública, la URL muestra evidencia real en vez de un error. Son episodios
de la semilla 0 en la condición base, seco y lluvia. No sustituyen la evaluación en vivo.
"""
import json
from pathlib import Path

from rally import api, historicos
from rally.web import correr_episodio

SALIDA = Path("web/public/datos")
CONDICIONES = {"seco": 0.9, "lluvia": 0.5}


def _guardar(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def generar():
    _guardar(SALIDA / "pista.json", api.pista())
    _guardar(SALIDA / "modelos.json", api.modelos())
    _guardar(SALIDA / "salud.json", {"estado": "replay", "ambiente": api.VERSION, "commit": api.commit_servido(),
                                     "recomendado": api.recomendado(), "episodios": 0, "errores": 0,
                                     "latencia_paso_ms": None})
    versiones = [f["nombre"] for f in historicos.catalogo() if f["ejecutable"]]
    for nombre in list(api.MODOS) + versiones:
        crear = api._politica(nombre)[0]
        for clima, mu in CONDICIONES.items():
            ep = correr_episodio(nombre, 0, politica=crear(0), mu=mu)
            ep.update(modo="replay", modelo=nombre, id=f"replay {clima}")
            ep["aviso"] = "Replay grabado: semilla 0 y parámetros base. Correr en vivo requiere la API."
            _guardar(SALIDA / "replays" / f"{nombre}-{clima}.json", ep)
            print(f"  {nombre} {clima}: {ep['resultado']} {ep['tiempo']} s")
