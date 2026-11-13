"""Vehículos del proyecto: el carro (rally.env) y la moto MotoGP (rally.moto).

Todo lo que depende del vehículo pasa por aquí: el ambiente, su versión, dónde viven sus modelos,
sus métricas y su experimento de MLflow. El carro conserva todas sus rutas de siempre (models/,
metrics/, data/processed/), así nada de lo ya versionado cambia de lugar. La moto vive en
subcarpetas `moto/` y en su propia sección `moto:` de params.yaml.
"""
from pathlib import Path

from rally import env as _carro
from rally import moto as _moto

VEHICULOS = ("carro", "moto")
TITULOS = {"carro": "Carro de rally", "moto": "Moto MotoGP"}


def validar(vehiculo):
    v = (vehiculo or "carro").strip().lower()
    if v not in VEHICULOS:
        raise ValueError(f"Vehículo desconocido: {vehiculo!r}. Disponibles: {', '.join(VEHICULOS)}")
    return v


def clase(vehiculo="carro"):
    return _moto.MotoGPEnv if validar(vehiculo) == "moto" else _carro.AutonomousRallyEnv


def config(vehiculo="carro"):
    return _moto.MotoConfig() if validar(vehiculo) == "moto" else _carro.RallyConfig()


def crear_env(vehiculo="carro", **kw):
    return clase(vehiculo)(**kw)


def version(vehiculo="carro"):
    return _moto.VERSION if validar(vehiculo) == "moto" else _carro.VERSION


def n_obs(vehiculo="carro"):
    return _moto.OBS_DIM if validar(vehiculo) == "moto" else _carro.OBS_DIM


def de_version(environment_version):
    """Vehículo de un modelo según la versión del ambiente de su manifiesto."""
    return "moto" if str(environment_version or "").startswith("moto") else "carro"


def carpeta(base, vehiculo="carro"):
    """models/ → models/moto/ (y lo mismo con metrics/ y data/processed/)."""
    base = Path(base)
    return base if validar(vehiculo) == "carro" else base / "moto"


def prefijo(vehiculo="carro"):
    """Prefijo de nombres (runs, modelos registrados, manifiestos): '' o 'moto-'."""
    return "" if validar(vehiculo) == "carro" else "moto-"
