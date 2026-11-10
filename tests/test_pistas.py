"""Pistas adicionales (Bosque y Puerto): geometría válida, Mónaco intacto y pilotos que completan."""

import math

import numpy as np
import pytest

from rally import policies, track
from rally.env import AutonomousRallyEnv


@pytest.mark.parametrize("nombre", list(track.PISTAS))
def test_trazado_cerrado_y_sin_tramos_pegados(nombre):
    p = track.obtener(nombre)
    giro = sum(math.degrees(c["theta"]) for c in p.CORNERS)
    assert abs(abs(giro) - 360) < 1e-6  # una sola vuelta, sin lazos
    assert p.check_design()["problemas"] == []
    assert len(p.GATES) == 7 and p.GATES[-1][0] == p.LAP
    assert all(a[0] < b[0] for a, b in zip(p.GATES, p.GATES[1:]))  # puertas en orden


def test_bosque_gira_en_sentido_horario():
    assert sum(c["theta"] for c in track.BOSQUE.CORNERS) < 0
    assert sum(c["theta"] for c in track.MONACO.CORNERS) > 0


def test_nombres_del_modulo_siguen_siendo_monaco():
    assert track.obtener() is track.MONACO
    assert track.LAP == track.MONACO.LAP and track.XS is track.MONACO.XS
    with pytest.raises(ValueError, match="Pista desconocida"):
        track.obtener("spa")


def test_ambiente_por_defecto_no_cambia():
    a, b = AutonomousRallyEnv(), AutonomousRallyEnv(pista="monaco")
    oa, _ = a.reset(seed=3)
    ob, info = b.reset(seed=3)
    assert np.array_equal(oa, ob) and info["pista"] == "monaco"


def test_reset_puede_elegir_o_sortear_la_pista():
    env = AutonomousRallyEnv(pista=["monaco", "bosque", "puerto"])
    vistas = {env.reset(seed=s)[1]["pista"] for s in range(30)}
    assert vistas == {"monaco", "bosque", "puerto"}
    _, info = env.reset(seed=0, options={"pista": "puerto"})
    assert info["pista"] == "puerto"
    x, y = track.PUERTO.XS[0], track.PUERTO.YS[0]
    assert math.hypot(info["x"] - x, info["y"] - y) < 1.0  # arranca en la meta del Puerto


@pytest.mark.parametrize("nombre", ["bosque", "puerto", "sierra"])
@pytest.mark.parametrize("piloto,mu", [("experto", 0.9), ("maestro", 0.5)])
def test_los_pilotos_de_referencia_completan(nombre, piloto, mu):
    env = AutonomousRallyEnv(pista=nombre, mu=mu)
    for s in range(3):
        pol = policies.crear(piloto, s)
        obs, info = env.reset(seed=1000 + s)
        done = False
        while not done:
            obs, _, term, trunc, info = env.step(pol(obs, info))
            done = term or trunc
        assert info["outcome"] == "exito", (nombre, piloto, s, info["outcome"], info["next_cp"])


def test_sierra_reservada_no_se_puede_entrenar():
    assert track.validar_entrenamiento(None) == ["monaco"]
    assert track.validar_entrenamiento(["monaco", "bosque", "puerto"]) == ["monaco", "bosque", "puerto"]
    with pytest.raises(ValueError, match="reservadas"):
        track.validar_entrenamiento(["monaco", "sierra"])
    with pytest.raises(ValueError, match="Pista desconocida"):
        track.validar_entrenamiento(["monacco"])


def test_sierra_no_tiene_curvas_mas_cerradas_que_las_que_mide_el_sensor():
    from rally.env import R_NOTA
    assert track.SIERRA.R >= R_NOTA


def test_entrenamiento_ppo_sortea_solo_las_pistas_pedidas():
    pytest.importorskip("stable_baselines3")
    from rally.agentes.ppo import crear_env
    env = crear_env({}, {"semilla": 0, "pistas": ["bosque", "puerto"]}, 0)()
    vistas = {env.reset()[1]["pista"] for _ in range(20)}
    assert vistas == {"bosque", "puerto"}
    assert crear_env({}, {"semilla": 0}, 0)().reset()[1]["pista"] == "monaco"  # versiones anteriores
    with pytest.raises(ValueError, match="reservadas"):
        crear_env({}, {"semilla": 0, "pistas": ["sierra"]}, 0)


def test_progreso_usa_el_largo_de_la_pista_del_episodio():
    assert track.largo({"pista": "bosque"}) == track.BOSQUE.LAP != track.MONACO.LAP
    assert track.largo({}) == track.MONACO.LAP


def test_evaluador_rapido_recorre_las_pistas_de_entrenamiento(monkeypatch):
    pytest.importorskip("mlflow")
    from rally import pipeline
    vistas = []
    real = pipeline.AutonomousRallyEnv

    def espia(*a, pista=None, **kw):
        vistas.append(pista)
        return real(*a, pista=pista, **kw)

    monkeypatch.setattr(pipeline, "AutonomousRallyEnv", espia)

    class Quieto:
        def predict(self, obs, deterministic=True):
            return np.zeros(2, dtype=np.float32), None

    pe = {"mu_seco": 0.9, "mu_mojado": 0.5, "semilla_eval_rapida": 10000}
    m = pipeline._evaluador_rapido({}, pe, n=1, pistas=["monaco", "bosque"])(Quieto())
    assert set(vistas) == {"monaco", "bosque"} and m["seco_vueltas_pct"] == 0
    with pytest.raises(ValueError, match="reservadas"):
        pipeline._evaluador_rapido({}, pe, pistas=["sierra"])
