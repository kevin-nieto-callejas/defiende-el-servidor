"""Pruebas del ambiente: ficha, física, reglas y trampas de recompensa."""

import math

import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from rally import AutonomousRallyEnv, policies, track
from rally.transitions import TRANSICIONES, ejecutar, _en_pista


@pytest.fixture
def env():
    return AutonomousRallyEnv()


def correr(env, piloto, seed=0):
    pol = policies.crear(piloto, seed)
    obs, info = env.reset(seed=seed)
    total, done = 0.0, False
    while not done:
        obs, r, term, trunc, info = env.step(pol(obs, info))
        total += r
        done = term or trunc
    return info, total


# ------------------------------------------------------------------ diseño

def test_trazado_valido():
    rep = track.check_design()
    assert rep["problemas"] == []
    giro = sum(math.degrees(c["theta"]) for c in track.CORNERS)
    assert giro == pytest.approx(360.0, abs=1e-6)  # una sola vuelta, sin cruces
    assert 900 < track.LAP < 1300


def test_gymnasium_check_env(env):
    check_env(env, skip_render_check=True)


@pytest.mark.parametrize("tr", TRANSICIONES, ids=[t["id"] for t in TRANSICIONES])
def test_transiciones_de_la_ficha(env, tr):
    _, r, info = ejecutar(env, tr)
    e = tr["esperado"]
    assert r == pytest.approx(e["recompensa"], abs=0.01)
    assert info["next_cp"] == e["next_cp"]
    assert info["outcome"] == e["fin"]


def test_reproducible():
    a, b = AutonomousRallyEnv(), AutonomousRallyEnv()
    ia, ra = correr(a, "aleatoria", seed=3)
    ib, rb = correr(b, "aleatoria", seed=3)
    assert ra == rb and ia["x"] == ib["x"] and ia["t"] == ib["t"]


# ------------------------------------------------------------------ física

def test_sin_reversa(env):
    env.reset(seed=0)
    for _ in range(5):
        _, _, _, _, info = env.step([-1.0, 0.0])
    assert info["v"] == 0.0


def test_subviraje_en_horquilla(env):
    tr = next(t for t in TRANSICIONES if t["id"] == "T3")
    _, _, info = ejecutar(env, tr)
    assert info["skidding"]


def test_experto_completa_en_seco():
    info, total = correr(AutonomousRallyEnv(mu=0.9), "experto")
    assert info["outcome"] == "exito"
    assert total > 100


def test_experto_falla_con_lluvia_y_prudente_no():
    assert correr(AutonomousRallyEnv(mu=0.5), "experto")[0]["outcome"] != "exito"
    assert correr(AutonomousRallyEnv(mu=0.5), "prudente")[0]["outcome"] == "exito"


# ------------------------------------------------------------------ trampas

def test_checkpoint_no_paga_dos_veces(env):
    """Cruzar de nuevo una puerta ya pasada no da los +10."""
    s = track.GATES[0][0]
    env.reset(options={"state": {**_en_pista(s - 1.0), "v": 20.0, "next_cp": 2,
                                 "s_cum": s - 1.0, "s_best": s}})
    _, r, _, _, info = env.step([0.0, 0.0])
    assert r < 1 and info["next_cp"] == 2


def test_atajo_no_paga(env):
    """Llegar a una puerta posterior sin pasar las anteriores no da puntos ni progreso."""
    s = track.GATES[2][0]
    env.reset(options={"state": {**_en_pista(s - 1.0), "v": 20.0, "next_cp": 1,
                                 "s_cum": s - 1.0, "s_best": 0.0}})
    _, r, _, _, info = env.step([0.0, 0.0])
    assert info["next_cp"] == 1
    assert info["s_best"] <= track.GATES[0][0]
    assert r < 0.5


def test_ir_y_volver_no_acumula(env):
    """El progreso se paga sobre el máximo alcanzado: volver al mismo sitio no paga."""
    env.reset(options={"state": {**_en_pista(50.0), "v": 10.0, "s_cum": 50.0, "s_best": 60.0}})
    _, r, _, _, info = env.step([0.0, 0.0])
    assert info["s_best"] == 60.0
    assert r < 0


def test_quedarse_quieto_termina_estancado(env):
    env.reset(seed=0)
    for _ in range(200):
        _, _, term, _, info = env.step([0.0, 0.0])
        if term:
            break
    assert info["outcome"] == "estancado"


def test_estancarse_no_es_salida_barata(env):
    """Quedarse quieto cuesta al menos lo mismo que chocar (si no, el agente se detiene
    antes de las curvas difíciles: lo encontró la revisión en el Q-learning v1)."""
    env.reset(seed=0)
    total, done = 0.0, False
    while not done:
        _, r, term, trunc, info = env.step([0.0, 0.0])
        total += r
        done = term or trunc
    assert info["outcome"] == "estancado"
    assert total <= env.cfg.r_fail


def test_puerta_cruzada_en_el_escape_cuenta_al_volver(env):
    """Cruzar la puerta pisando la zona de escape no la pierde: cuenta al volver al asfalto."""
    s = track.GATES[0][0]
    env.reset(options={"state": {**_en_pista(s - 0.5, d=4.2, dpsi_deg=-8), "v": 10.0,
                                 "s_cum": s - 0.5}})
    pol = policies.crear("experto")
    obs, info = env.observation_space.sample(), env._info()
    for _ in range(40):
        obs, _, term, trunc, info = env.step(pol(obs, info))
        if term or trunc:
            break
    assert info["next_cp"] == 2
    assert info["outcome"] is None


def test_sensor_de_agarre_detecta_lluvia():
    """Frenar fuerte con lluvia satura las llantas y el agarre estimado baja a ~μ."""
    seco, mojado = AutonomousRallyEnv(mu=0.9), AutonomousRallyEnv(mu=0.5)
    for e in (seco, mojado):
        e.reset(options={"state": {**_en_pista(50.0), "v": 20.0, "s_cum": 50.0}})
        e.step([-1.0, 0.0])
    assert mojado.mu_est == pytest.approx(0.5, abs=0.02)
    assert seco.mu_est > 1.0  # en seco el freno no satura: sigue sin medirse un límite
    obs = mojado._obs()
    assert obs.shape == (24,) and obs[17] == 1.0 and obs[19] == 1.0   # derrape y lluvia


def test_rayos_no_cambian_de_significado_con_el_alcance():
    """La misma pared se lee igual con cualquier alcance (v4 chocaba al mover ese deslizador)."""
    corto, largo = AutonomousRallyEnv(r_max=20.0), AutonomousRallyEnv(r_max=40.0)
    o1, o2 = corto.reset(seed=0)[0], largo.reset(seed=0)[0]
    assert o1[6] == pytest.approx(o2[6], abs=1e-3)   # rayo lateral: la pared está cerca
    assert o1[22] == pytest.approx(0.5) and o2[22] == pytest.approx(1.0)


def test_observacion_dentro_de_su_espacio_en_los_extremos():
    for ajustes in ({"track_width": 12.0, "a_max": 6.0, "r_max": 40.0}, {"track_width": 6.0, "a_max": 2.0, "r_max": 10.0}):
        e = AutonomousRallyEnv(**ajustes)
        assert e.observation_space.contains(e.reset(seed=0)[0])


def test_nota_de_frenada_baja_antes_de_la_curva_cerrada():
    """Antes de la curva más cerrada la velocidad segura baja, y más con lluvia."""
    s = float(track.SS[int(np.argmax(np.abs(track.KS)))])
    seco, mojado = AutonomousRallyEnv(mu=0.9), AutonomousRallyEnv(mu=0.5)
    o1, o2 = (e.reset(options={"state": {**_en_pista(s - 20.0), "s_cum": s - 20.0}})[0] for e in (seco, mojado))
    assert o2[23] < o1[23] < 1.0


@pytest.mark.parametrize("ajustes", [{"mu": 0.4}, {"mu": 0.5, "a_max": 6.0}, {"mu": 0.75}, {"mu": 0.5, "track_width": 6.0}])
def test_maestro_con_traccion_completa_los_extremos(ajustes):
    """Sin control de tracción, μ 0.4 y a_max 6 con lluvia no se completaban."""
    e = AutonomousRallyEnv(**ajustes)
    pol = policies.crear("maestro")
    obs, info = e.reset(seed=0)
    done = False
    while not done:
        obs, _, term, trunc, info = e.step(pol(obs, info))
        done = term or trunc
    assert info["outcome"] == "exito"


def test_dominio_aleatorio_cubre_los_rangos_y_conserva_la_base():
    from rally.agentes.ppo import DominioAleatorio
    p = {"prob_lluvia": 0.5, "lluvia_min": 0.4, "lluvia_max": 0.75, "mu_min": 0.75, "mu_max": 1.0,
         "prob_base": 0.3, "rangos": {"track_width": [6.0, 12.0], "r_max": [10.0, 40.0]}}
    env = DominioAleatorio(AutonomousRallyEnv(), p)
    env.reset(seed=0)
    vistos = []
    for _ in range(200):
        env.reset()
        c = env.unwrapped.cfg
        vistos.append((c.mu, c.track_width, c.r_max))
    mus, anchos, alcances = zip(*vistos)
    assert min(mus) < 0.5 and max(mus) > 0.9
    assert min(anchos) >= 6.0 and max(anchos) <= 12.0 and 8.0 in anchos
    assert min(alcances) >= 10.0 and max(alcances) <= 40.0 and 20.0 in alcances


def test_ruido_no_toca_lluvia_ni_configuracion():
    from rally.agentes.ppo import RuidoSensores
    env = RuidoSensores(AutonomousRallyEnv(mu=0.5), 0.05)
    obs, _ = env.reset(seed=0)
    assert obs[19] == 1.0 and obs[20] == pytest.approx(8 / 12)
    assert env.observation_space.contains(obs)


def test_adaptador_familia_0_3_devuelve_rayos_por_alcance():
    """Un modelo de 20 observaciones recibe los rayos como en su ambiente original."""
    from unittest.mock import MagicMock
    from rally.agentes.ppo import PilotoPPO
    pol = PilotoPPO.__new__(PilotoPPO)
    pol.n_obs = 20
    pol.model = MagicMock()
    pol.model.predict.return_value = (np.zeros(2), None)
    obs = AutonomousRallyEnv(r_max=20.0).reset(seed=0)[0]
    pol(obs, None)
    enviado = pol.model.predict.call_args[0][0]
    assert enviado.shape == (20,)
    assert enviado[6] == pytest.approx(obs[6] * 2)


def test_tabla_mide_el_pedal_en_m_s2():
    from rally.agentes.discreto import a_mando
    obs = AutonomousRallyEnv(a_max=6.0).reset(seed=0)[0]
    assert a_mando((1.0, 0.0), obs)[0] == pytest.approx(4 / 6)
    assert a_mando((-1.0, 0.0), obs)[0] == -1.0


def test_parametro_desconocido_falla():
    with pytest.raises(TypeError):
        AutonomousRallyEnv(track_widht=10)


def test_qlearning_evaluacion_determinista():
    from rally.agentes.qlearning import AgenteQ
    ag = AgenteQ(seed=0)  # tabla en cero: todo empata
    obs = AutonomousRallyEnv().reset(seed=0)[0]
    assert all((ag(obs, None) == ag(obs, None)).all() for _ in range(5))


def test_qlearning_sin_experiencia_no_frena_y_gira_a_fondo():
    from rally.agentes.discreto import ACCIONES, NEUTRA
    from rally.agentes.qlearning import AgenteQ
    ag = AgenteQ(seed=0)
    assert ag.mejor(0) == NEUTRA                  # estado nunca visto
    ag.q[0, 3] = -5.0
    assert ag.mejor(0) == NEUTRA                  # lo único probado salió mal
    ag.q[0, 3] = 5.0
    assert ag.mejor(0) == 3
    assert abs(ACCIONES[NEUTRA][1]) < 1e-6        # volante recto


def test_tabla_distingue_la_lluvia():
    from rally.agentes.discreto import estado
    seco, mojado = AutonomousRallyEnv(mu=0.9), AutonomousRallyEnv(mu=0.5)
    obs_s, obs_m = seco.reset(seed=0)[0], mojado.reset(seed=0)[0]
    assert estado(obs_s) != estado(obs_m)


def test_accion_discreta_es_la_mas_parecida():
    from rally.agentes.discreto import ACCIONES, discreta
    assert (ACCIONES[discreta([0.0, 0.0])] == [0.0, 0.0]).all()
    assert (ACCIONES[discreta([0.95, -0.93])] == [1.0, -1.0]).all()


def test_punto_de_guardado_q(tmp_path):
    from rally.agentes.qlearning import PuntoQ
    PuntoQ(tmp_path, "a").guardar({"it": 7}, q=np.ones(3))
    d = PuntoQ(tmp_path, "a").cargar()
    assert d["estado"]["it"] == 7 and (d["q"] == 1).all()
    assert PuntoQ(tmp_path, "otra-huella").cargar() is None   # otros parámetros: empieza de cero
    PuntoQ(tmp_path, "a").borrar()
    assert PuntoQ(tmp_path, "a").cargar() is None


def test_maestro_qlearning_completa_en_seco_y_lluvia():
    import yaml
    from rally.agentes.qlearning import maestro
    pol = maestro(yaml.safe_load(open("params.yaml"))["qlearning"])
    for mu in (0.75, 0.45):
        env = AutonomousRallyEnv(mu=mu)
        obs, info = env.reset(seed=0)
        done = False
        while not done:
            obs, _, term, trunc, info = env.step(pol(obs, info))
            done = term or trunc
        assert info["outcome"] == "exito", mu


def test_salto_de_proyeccion_no_es_avance(env):
    """Si el carro aparece cerca de otro tramo (la horquilla), s no salta."""
    env.reset(seed=0)
    s0 = env.s_cum
    env.x, env.y = track.point_at(track.LAP / 2)  # teletransporte (no físico)
    env.step([0.0, 0.0])
    assert abs(env.s_cum - s0) < 5
