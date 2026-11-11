"""Pruebas de la moto MotoGP: contrato, física de inclinación y caída, pilotos, pipeline y API."""

import json
import math

import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from rally import AutonomousRallyEnv, MotoGPEnv, policies, vehiculos
from rally.moto import OBS_DIM, MotoConfig
from rally.transitions import TRANSICIONES_MOTO, _en_pista, ejecutar


def correr(env, piloto, seed=0):
    pol = policies.crear(piloto, seed, "moto")
    obs, info = env.reset(seed=seed)
    total, done = 0.0, False
    while not done:
        obs, r, term, trunc, info = env.step(pol(obs, info))
        total += r
        done = term or trunc
    return info, total


# ------------------------------------------------------------------ contrato

def test_gymnasium_check_env():
    check_env(MotoGPEnv(), skip_render_check=True)


def test_observacion_extiende_la_del_carro_sin_cambiar_su_orden():
    """Las 24 primeras significan lo mismo que en el carro; la 25 y la 26 son de la moto."""
    obs, _ = MotoGPEnv().reset(seed=0)
    carro, _ = AutonomousRallyEnv().reset(seed=0)
    assert obs.shape == (OBS_DIM,) == (26,) and carro.shape == (24,)
    assert np.allclose(obs[2:21], carro[2:21])   # rumbo, desvío, rayos, notas, agarre, lluvia, ancho
    assert obs[21] == pytest.approx(5.0 / 6.0) and carro[21] == pytest.approx(4.0 / 6.0)   # a_max/6 de cada uno
    assert obs[22] == carro[22]
    assert obs[24] == 0.0 and obs[25] == 0.0     # sale derecha y sin patinar


def test_registro_de_vehiculos():
    assert vehiculos.VEHICULOS == ("carro", "moto")
    assert isinstance(vehiculos.crear_env("moto"), MotoGPEnv)
    assert vehiculos.version("moto").startswith("moto") and vehiculos.n_obs("moto") == 26
    assert vehiculos.de_version("moto-0.1") == "moto" and vehiculos.de_version("0.4-monaco-configurable") == "carro"
    with pytest.raises(ValueError):
        vehiculos.validar("camion")


def test_el_carro_no_cambia():
    """Agregar la moto no toca al carro: su configuración base es la de siempre."""
    env = AutonomousRallyEnv()
    assert env.cfg.a_max == 4.0 and env.cfg.v_max == 25.0 and env.observation_space.shape == (24,)
    assert env._falla_vehiculo() is None


@pytest.mark.parametrize("tr", TRANSICIONES_MOTO, ids=[t["id"] for t in TRANSICIONES_MOTO])
def test_transiciones_de_la_ficha_moto(tr):
    env = MotoGPEnv(**tr.get("ambiente", {}))
    _, r, info = ejecutar(env, tr)
    e = tr["esperado"]
    assert r == pytest.approx(e["recompensa"], abs=0.01)
    assert info["next_cp"] == e["next_cp"] and info["outcome"] == e["fin"]
    assert math.degrees(info["inclinacion"]) == pytest.approx(e["inclinacion_deg"], abs=0.01)


# ------------------------------------------------------------------ física

def test_la_inclinacion_tarda_en_llegar():
    env = MotoGPEnv()
    env.reset(options={"state": {**_en_pista(100.0), "v": 15.0, "s_cum": 100.0}})
    grados = []
    for _ in range(4):
        _, _, _, _, info = env.step((0.0, 1.0))
        grados.append(round(math.degrees(info["inclinacion"]), 3))
    assert grados == [8.0, 16.0, 24.0, 32.0]


def test_girar_es_inclinarse():
    """Inclinada a la izquierda gira a la izquierda: tan φ = v² κ / g."""
    env = MotoGPEnv()
    env.reset(options={"state": {**_en_pista(100.0), "v": 15.0, "s_cum": 100.0, "phi": math.radians(20)}})
    psi0 = env.psi
    env.step((0.0, 20 / 60))
    assert env.psi > psi0
    kappa = 9.81 * math.tan(math.radians(20)) / env.v**2
    assert env.omega == pytest.approx(env.v * kappa, rel=1e-6)


def test_pasarse_del_agarre_tira_la_moto_y_el_carro_solo_subvira():
    estado = {**_en_pista(100.0), "v": 15.0, "s_cum": 100.0, "phi": math.radians(45)}
    moto = MotoGPEnv(mu=0.5)
    moto.reset(options={"state": estado})
    fines = [moto.step((0.0, 45 / 60))[4]["outcome"] for _ in range(3)]
    assert fines == [None, None, "caida"]
    carro = AutonomousRallyEnv(mu=0.5)
    carro.reset(options={"state": {k: v for k, v in estado.items() if k != "phi"}})
    for _ in range(3):
        *_, info = carro.step((0.0, 1.0))
    assert info["outcome"] is None and info["skidding"]


def test_frenar_inclinada_deja_sin_agarre_lateral():
    """Círculo de fricción: frenar a fondo inclinada con lluvia la tira aunque la inclinación aguante."""
    estado = {**_en_pista(100.0), "v": 15.0, "s_cum": 100.0, "phi": math.radians(20)}
    env = MotoGPEnv(mu=0.5)
    env.reset(options={"state": estado})
    for _ in range(3):
        *_, info = env.step((-1.0, 20 / 60))
    assert info["outcome"] == "caida"
    env.reset(options={"state": estado})
    *_, info = env.step((0.0, 20 / 60))
    assert info["patinando_pasos"] == 0


def test_parada_no_se_inclina():
    env = MotoGPEnv()
    env.reset(options={"state": {**_en_pista(100.0), "v": 0.0, "s_cum": 100.0}})
    *_, info = env.step((0.0, 1.0))
    assert info["inclinacion"] == 0.0


def test_reproducible():
    ia, ra = correr(MotoGPEnv(), "aleatoria", seed=3)
    ib, rb = correr(MotoGPEnv(), "aleatoria", seed=3)
    assert ra == rb and ia["x"] == ib["x"]


def test_config_moto_y_sobrescrituras():
    env = MotoGPEnv(mu=0.6, a_max=3.0)
    assert isinstance(env.cfg, MotoConfig) and env.cfg.mu == 0.6 and env.cfg.a_max == 3.0
    with pytest.raises(TypeError):
        MotoGPEnv(no_existe=1)


# ------------------------------------------------------------------ pilotos

def test_pilotos_de_referencia_de_la_moto():
    """El escenario del carro se repite: el experto se cae con lluvia, el maestro completa ambos pisos."""
    seco, mojado = MotoGPEnv(mu=0.9), MotoGPEnv(mu=0.5)
    assert correr(seco, "experto")[0]["outcome"] == "exito"
    assert correr(mojado, "experto")[0]["outcome"] == "caida"
    assert correr(seco, "maestro")[0]["outcome"] == "exito"
    assert correr(mojado, "maestro")[0]["outcome"] == "exito"


def test_maestro_de_moto_completa_el_minimo_de_agarre():
    assert correr(MotoGPEnv(mu=0.4), "maestro")[0]["outcome"] == "exito"


def test_las_politicas_de_moto_no_cambian_las_del_carro():
    assert set(policies.politicas("moto")) == set(policies.POLITICAS)
    assert isinstance(policies.crear("experto", 0, "moto"), policies.PurePursuitMoto)
    assert type(policies.crear("experto", 0)) is policies.PurePursuit


# ------------------------------------------------------------------ pipeline y API

def test_params_de_la_moto_heredan_y_reemplazan():
    from rally.pipeline import params, rutas
    p, c = params("moto"), params()
    assert p["ambiente"]["a_max"] == 5.0 and c["ambiente"]["a_max"] == 4.0
    assert p["ppo"]["vehiculo"] == "moto" and "vehiculo" not in c["ppo"]
    assert p["ppo"]["capas"] == c["ppo"]["capas"]   # heredado del carro
    assert rutas("moto")["modelos"].as_posix() == "models/moto" and rutas()["modelos"].as_posix() == "models"


def _cliente():
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from rally.api import app
    return TestClient(app)


def test_api_pista_y_episodio_de_la_moto():
    c = _cliente()
    p = c.get("/api/pista", params={"vehiculo": "moto"}).json()
    assert p["vehiculo"] == "moto" and p["carro"]["largo"] == 2.1 and p["rangos"]["a_max"]["base"] == 5.0
    assert {"experto", "maestro"} <= set(p["pilotos"])
    ep = c.get("/api/episodio", params={"piloto": "maestro", "vehiculo": "moto"}).json()
    assert ep["vehiculo"] == "moto" and ep["resultado"] == "exito" and ep["ambiente_servido"].startswith("moto")
    assert "incl" in ep["frames"][10] and ep["params"]["a_max"] == 5.0


def test_api_evalua_la_moto_y_rechaza_vehiculos_desconocidos():
    c = _cliente()
    r = c.post("/api/evaluar", json={"modelo": "experto", "episodios": 2, "mu": 0.5, "vehiculo": "moto"}).json()
    assert r["vehiculo"] == "moto" and r["fallos_por_causa"] == {"caida": 2}
    assert c.get("/api/pista", params={"vehiculo": "camion"}).status_code == 404


def test_un_modelo_del_carro_no_corre_en_la_moto():
    from rally import historicos
    if not historicos.SALIDA.joinpath("catalogo.json").exists():
        pytest.skip("sin manifiestos")
    c = _cliente()
    assert c.get("/api/episodio", params={"piloto": "ppo-modelo-v5-s1", "vehiculo": "moto"}).status_code == 409
    filas = c.get("/api/modelos", params={"vehiculo": "carro"}).json()["modelos"]
    assert filas and all(f["vehiculo"] == "carro" for f in filas)


# ------------------------------------------------------------------ manifiestos

def test_el_catalogo_conserva_la_moto_si_no_se_pueden_regenerar_sus_manifiestos(tmp_path, monkeypatch):
    """En un clon sin `dvc pull` los pesos no están en la caché y no hay manifiesto que regenerar.

    Regenerar entonces no debe dejar el catálogo sin la moto: la web y la API la leen de ahí, así
    que perderla la borraría de la entrega sin ningún aviso.
    """
    from rally import manifiesto

    salida = tmp_path / "manifests"
    salida.mkdir()
    catalogo = [{"nombre": "ppo-modelo-v5-s1", "tipo": "ppo"},
                {"nombre": "ppo-moto-v1", "tipo": "ppo", "vehiculo": "moto"},
                {"nombre": "qlearning-moto-v1", "tipo": "qlearning", "vehiculo": "moto"}]
    (salida / "catalogo.json").write_text(json.dumps(catalogo), encoding="utf-8")

    def sin_pesos(tipo, rev="moto-v1"):
        raise FileNotFoundError("los pesos no están en la caché de DVC")

    monkeypatch.setattr(manifiesto, "SALIDA", salida)
    monkeypatch.setattr(manifiesto, "manifiesto_moto", sin_pesos)

    resultado = manifiesto.generar_moto()

    assert resultado == catalogo
    assert json.loads((salida / "catalogo.json").read_text(encoding="utf-8")) == catalogo
