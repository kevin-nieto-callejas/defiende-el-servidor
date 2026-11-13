"""Datos estáticos para la web sin API: catálogo y vueltas ya simuladas, marcadas como replay.

Mientras no haya una API pública, la URL muestra evidencia real en vez de un error. Son episodios
de la semilla 0 en la condición base, seco y lluvia. No sustituyen la evaluación en vivo.
La moto tiene su propia pista (`pista-moto.json`, con sus medidas y pilotos) y sus vueltas en
`replays/moto/`.
"""
import json
from pathlib import Path

from rally import api, historicos, vehiculos
from rally.web import correr_episodio

SALIDA = Path("web/public/datos")
CONDICIONES = {"seco": 0.9, "lluvia": 0.5}


def _guardar(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def generar(vehiculos_=vehiculos.VEHICULOS):
    _guardar(SALIDA / "modelos.json", api.modelos())
    _guardar(SALIDA / "salud.json", {"estado": "replay", "ambiente": api.VERSION, "commit": api.commit_servido(),
                                     "recomendado": api.recomendado(), "episodios": 0, "errores": 0,
                                     "latencia_paso_ms": None})
    for vehiculo in vehiculos_:
        moto = vehiculo == "moto"
        _guardar(SALIDA / ("pista-moto.json" if moto else "pista.json"), api.pista(vehiculo=vehiculo))
        carpeta = SALIDA / "replays" / ("moto" if moto else "")
        versiones = [f["nombre"] for f in historicos.catalogo() if f["ejecutable"] and f["vehiculo"] == vehiculo]
        for nombre in list(api.MODOS) + versiones:
            crear = api._politica(nombre, vehiculo)[0]
            for clima, mu in CONDICIONES.items():
                ep = correr_episodio(nombre, 0, politica=crear(0), mu=mu, vehiculo=vehiculo)
                ep.update(modo="replay", modelo=nombre, id=f"replay {clima}")
                ep["aviso"] = "Replay grabado: semilla 0 y parámetros base. Correr en vivo requiere la API."
                _guardar(carpeta / f"{nombre}-{clima}.json", ep)
                print(f"  {vehiculo} {nombre} {clima}: {ep['resultado']} {ep['tiempo']} s")
