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


@pytest.mark.parametrize("nombre", ["bosque", "puerto"])
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
