"""La API publicada corre PPO en numpy: debe decidir lo mismo que PyTorch y conservar la identidad."""
import json
from pathlib import Path

import numpy as np
import pytest

from rally import historicos
from rally.agentes.red_numpy import RedNumpy, sha256

RAIZ = Path(__file__).resolve().parents[1]
PAQUETE_VERCEL = RAIZ / "web/api/_paquete"


def _modelo_sb3(tmp_path, n_obs=24, capas=(64, 64), semilla=0):
    pytest.importorskip("stable_baselines3")
    import gymnasium as gym
    from stable_baselines3 import PPO

    class Caja(gym.Env):
        observation_space = gym.spaces.Box(-np.inf, np.inf, (n_obs,), np.float32)
        action_space = gym.spaces.Box(-1.0, 1.0, (2,), np.float32)

    m = PPO("MlpPolicy", Caja(), policy_kwargs={"net_arch": dict(pi=list(capas), vf=list(capas))},
            seed=semilla, device="cpu")
    with __import__("torch").no_grad():   # salida grande: que el recorte a [-1, 1] también se pruebe
        m.policy.action_net.weight.mul_(20)
    ruta = tmp_path / f"modelo-{n_obs}.zip"
    m.save(ruta)
    return ruta


@pytest.mark.parametrize("n_obs", [24, 20])
def test_numpy_decide_lo_mismo_que_pytorch(tmp_path, n_obs):
    from rally.agentes.red_numpy import exportar
    ruta = _modelo_sb3(tmp_path, n_obs)
    info = exportar(ruta, tmp_path / "red.npz", n_aleatorias=2000)
    assert info["max_diferencia"] < 1e-5 and info["fuente_sha256"] == sha256(ruta)
    red = RedNumpy(tmp_path / "red.npz")
    assert red.n_obs == n_obs and red.fuente_sha256 == sha256(ruta)


def _npz_sintetico(destino, fuente, n_obs=24, semilla=0):
    """Red aleatoria con la forma de PPO; solo para probar la carga y la identidad, no para manejar."""
    rng = np.random.default_rng(semilla)
    capas = [(64, n_obs), (64, 64), (2, 64)]
    datos = {f"w{i}": rng.normal(0, 0.1, f).astype(np.float32) for i, f in enumerate(capas)}
    datos |= {f"b{i}": np.zeros(f[0], np.float32) for i, f in enumerate(capas)}
    np.savez(destino, **datos, n_capas=np.int64(3), activacion=np.str_("Tanh"), n_obs=np.int64(n_obs),
             low=-np.ones(2, np.float32), high=np.ones(2, np.float32), fuente_sha256=np.str_(fuente),
             max_diferencia=np.float64(0.0))


def test_api_usa_la_red_numpy_y_lo_dice(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from rally.api import app

    m = historicos.manifiesto("ppo-modelo-v5-s1")
    _npz_sintetico(tmp_path / f"{m['model_sha256']}.npz", m["model_sha256"])
    monkeypatch.setenv("RALLY_MODELOS", str(tmp_path))
    monkeypatch.setattr(historicos, "_pilotos", {})
    r = TestClient(app).post("/api/evaluar", json={"modelo": "ppo-modelo-v5-s1", "episodios": 1})
    assert r.status_code == 200
    e = r.json()
    assert e["motor"] == "numpy" and e["model_sha256"] == m["model_sha256"] and len(e["casos"]) == 1


def test_npz_de_otro_modelo_es_error_y_no_una_evaluacion(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from rally.api import app

    m = historicos.manifiesto("ppo-modelo-v5-s1")
    _npz_sintetico(tmp_path / f"{m['model_sha256']}.npz", "0" * 64)
    monkeypatch.setenv("RALLY_MODELOS", str(tmp_path))
    monkeypatch.setattr(historicos, "_pilotos", {})
    r = TestClient(app).get("/api/episodio", params={"piloto": "ppo-modelo-v5-s1"})
    assert r.status_code == 503 and "no se exportó" in r.json()["detail"]


@pytest.mark.skipif(not PAQUETE_VERCEL.joinpath("paquete.json").exists(), reason="sin paquete de Vercel")
def test_paquete_de_vercel_al_dia_con_el_repositorio():
    """Si alguien cambia src/ o manifests/ sin volver a empaquetar, la web publicaría otra versión."""
    import sys
    sys.path.insert(0, str(RAIZ / "deploy/api"))
    from empaquetar import verificar
    assert verificar(PAQUETE_VERCEL) == []
    paquete = json.loads(PAQUETE_VERCEL.joinpath("paquete.json").read_text(encoding="utf-8"))
    assert all(i.get("max_diferencia", 0) < 1e-5 for i in paquete["modelos"].values())
