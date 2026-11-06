"""Función de Vercel: la API de simulación (FastAPI) en el mismo dominio que la web.

Python sigue siendo la autoridad del mundo: corre el mismo ambiente del entrenamiento. Lo que
cambia frente al contenedor es que las redes de PPO corren en numpy (una función no puede cargar
PyTorch). El código, los manifiestos y los modelos vienen de `_paquete/`, que arma
`deploy/api/empaquetar.py web/api/_paquete --vercel` y comprueba `--verificar`.
"""
import os
import sys
from pathlib import Path

PAQUETE = Path(__file__).resolve().parent / "_paquete"


def _crear():
    if (PAQUETE / "paquete.json").exists():
        sys.path.insert(0, str(PAQUETE / "src"))
        os.chdir(PAQUETE)                                    # la API lee manifests/ y paquete.json desde aquí
        os.environ.setdefault("RALLY_MODELOS", str(PAQUETE / "pesos"))
        os.environ.setdefault("XDG_CACHE_HOME", "/tmp")      # la grilla de la pista se guarda donde se puede escribir
        os.environ.setdefault("RALLY_ORIGENES", "*")
        from rally.api import app as api
        return api
    # Sin paquete se responde un error claro: la web lo muestra y entra en replay
    from fastapi import FastAPI, HTTPException

    api = FastAPI(title="Autonomous Rally API (sin paquete)")

    @api.get("/api/{ruta:path}")
    def sin_paquete(ruta: str):
        raise HTTPException(503, "Falta web/api/_paquete: corre deploy/api/empaquetar.py web/api/_paquete --vercel")

    return api


# Vercel reconoce la función leyendo el archivo: `app` tiene que quedar al nivel del módulo
app = _crear()
