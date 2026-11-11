"""Pilotos de referencia para probar el ambiente mientras no hay agente entrenado.

No son el agente: "experto" y "prudente" leen el estado interno (info) del
simulador, información que el agente no ve. Sirven como línea base.
"""

import math
from pathlib import Path

import numpy as np

from rally import track
from rally.env import A_REF

G = 9.81


class PurePursuit:
    """Sigue la línea central mirando un punto adelante y frena antes de las curvas.

    `mu_supuesto` es la adherencia que el piloto CREE que hay. No conoce la real:
    si cree que está seco y llueve, entra demasiado rápido a las curvas.
    """

    def __init__(self, mu_supuesto=0.9, margen=0.85, v_recta=22.0, freno=6.0,
                 wheelbase=2.5, delta_max_deg=30.0, traccion=None, b_max=8.0):
        self.a_lat = margen * mu_supuesto * G  # aceleración lateral que se permite
        self.v_recta = v_recta
        self.freno = freno * mu_supuesto / 0.9
        # Control de tracción: fracción del agarre que puede gastar el pedal. Si el pedal
        # pide todo el agarre, la física deja cero para girar y el carro sigue derecho.
        self.tope = None if traccion is None else traccion * mu_supuesto * G
        self.b_max = b_max
        self.wheelbase = wheelbase
        self.vista_m = 60  # metros que mira adelante para planear la frenada
        self.delta_max = math.radians(delta_max_deg)

    def v_curva(self, kappa):
        """Velocidad máxima en una curva de curvatura kappa: v² · |κ| <= a_lat."""
        return math.sqrt(self.a_lat / abs(kappa)) if kappa else self.v_recta

    def __call__(self, obs, info):
        x, y, psi, v = info["x"], info["y"], info["psi"], info["v"]
        s = info["s"]
        pista = track.obtener(info.get("pista"))

        u_dir = self._direccion(pista, x, y, psi, v, s)

        # Velocidad objetivo: la que permita frenar a tiempo para cada curva que viene
        v_obj = self.v_recta
        for k in range(0, self.vista_m + 1, 2):
            vc = self.v_curva(pista.curvature_at(s + k))
            v_obj = min(v_obj, math.sqrt(vc**2 + 2 * self.freno * max(k - 2, 0)))
        u_acel = float(np.clip(0.8 * (v_obj - v), -1, 1))
        if self.tope is not None:
            a_max = obs[21] * A_REF
            a = u_acel * (a_max if u_acel >= 0 else self.b_max)
            a = max(-self.tope, min(self.tope, a))
            u_acel = a / (a_max if a >= 0 else self.b_max)
        return np.array([u_acel, u_dir], dtype=np.float32)

    def _direccion(self, pista, x, y, psi, v, s):
        """Pure pursuit sobre la línea central: ángulo de volante normalizado."""
        ld = min(max(4.0 + 0.5 * v, 5.0), 14.0)
        tx, ty = pista.point_at(s + ld)
        alpha = track.wrap_angle(math.atan2(ty - y, tx - x) - psi)
        delta = math.atan2(2 * self.wheelbase * math.sin(alpha), ld)
        return float(np.clip(delta / self.delta_max, -1, 1))


class PurePursuitMoto(PurePursuit):
    """Pure pursuit para la moto: convierte la curvatura deseada en una inclinación.

    La moto gira por inclinarse: para seguir una curvatura κ a velocidad v necesita
    tan φ = v² · κ / g. Como la inclinación tarda en llegar (roll_rate), mira más adelante
    que el carro. Usa margen 0.8: en la moto pasarse del agarre no subvira, tira la moto.
    Por lo mismo trae control de tracción y ABS por defecto (`traccion` = 0.8 del agarre supuesto):
    frenar a fondo inclinado deja sin agarre lateral y la moto se cae.
    """

    def __init__(self, mu_supuesto=0.9, margen=0.8, v_recta=28.0, freno=6.0, traccion=0.8,
                 b_max=9.0, phi_max_deg=60.0, anticipo_s=0.25):
        super().__init__(mu_supuesto, margen, v_recta, freno, wheelbase=1.45, traccion=traccion, b_max=b_max)
        self.phi_max = math.radians(phi_max_deg)
        self.anticipo_s = anticipo_s
        # Nunca pide más inclinación de la que cree que aguanta el piso: tan φ <= 0.95 · μ supuesto
        self.phi_tope = math.atan(0.95 * mu_supuesto)
        self.agarre = 0.9 * mu_supuesto * G  # agarre total que se permite gastar
        self.vista_m = 120  # va más rápido: a 28 m/s y con lluvia frenar pide más de 60 m

    def __call__(self, obs, info):
        u_acel, u_dir = super().__call__(obs, info)
        # Círculo de fricción: con la moto inclinada queda menos agarre para acelerar o frenar
        a_lat = G * math.tan(abs(float(obs[24])) * self.phi_max) if len(obs) > 24 else 0.0
        resto = math.sqrt(max(self.agarre**2 - a_lat**2, 0.0))
        a_max = obs[21] * A_REF
        a = u_acel * (a_max if u_acel >= 0 else self.b_max)
        a = max(-resto, min(resto, a))
        return np.array([a / (a_max if a >= 0 else self.b_max), u_dir], dtype=np.float32)

    def _direccion(self, pista, x, y, psi, v, s):
        ld = min(max(4.0 + 0.5 * v, 5.0), 16.0) + self.anticipo_s * v
        tx, ty = pista.point_at(s + ld)
        alpha = track.wrap_angle(math.atan2(ty - y, tx - x) - psi)
        kappa = 2 * math.sin(alpha) / ld
        phi = math.atan(max(v, 1.0) ** 2 * kappa / G)
        phi = max(-self.phi_tope, min(self.phi_tope, phi))
        return float(np.clip(phi / self.phi_max, -1, 1))


class Maestro:
    """El profesor del PPO: mira la señal de lluvia (obs[19]) y maneja según el clima.

    En seco supone μ = 0.8 y con lluvia μ = 0.45. Con el control de tracción completa
    toda la zona de los deslizadores, incluso μ = 0.4 (runs/maestros.py lo midió).
    """

    def __init__(self, mu_seco=0.8, mu_lluvia=0.45, traccion_seco=0.8, traccion_lluvia=0.7):
        self.seco = PurePursuit(mu_seco, traccion=traccion_seco)
        self.lluvia = PurePursuit(mu_lluvia, traccion=traccion_lluvia)

    def __call__(self, obs, info):
        return (self.lluvia if obs[19] > 0.5 else self.seco)(obs, info)


class MaestroMoto(Maestro):
    """El profesor de los agentes de la moto: misma regla del clima con el piloto de moto.

    Con lluvia supone μ = 0.42 (el carro 0.45): en la moto pasarse no subvira, tira la moto, y así
    completa toda la zona de los deslizadores, incluso μ = 0.4.
    """

    def __init__(self, mu_seco=0.8, mu_lluvia=0.42, traccion_seco=0.8, traccion_lluvia=0.7, v_recta_lluvia=28.0):
        self.seco = PurePursuitMoto(mu_seco, traccion=traccion_seco)
        self.lluvia = PurePursuitMoto(mu_lluvia, v_recta=v_recta_lluvia, traccion=traccion_lluvia)


class Aleatoria:
    """Acciones al azar: sirve para ver que el ambiente no regala puntos."""

    def __init__(self, seed=None):
        self.rng = np.random.default_rng(seed)

    def __call__(self, obs, info):
        return self.rng.uniform(-1, 1, size=2).astype(np.float32)


MODELOS = {"qlearning": Path("models/qlearning/q_table.npz"), "ppo": Path("models/ppo/modelo.zip")}
MODELOS_MOTO = {"qlearning": Path("models/moto/qlearning/q_table.npz"), "ppo": Path("models/moto/ppo/modelo.zip")}
_cache = {}


def _modelo(nombre, vehiculo="carro"):
    """Carga una sola vez el modelo entrenado (models/ o models/moto/, versionados con DVC)."""
    rutas = MODELOS_MOTO if vehiculo == "moto" else MODELOS
    clave = (vehiculo, nombre)
    if clave not in _cache:
        if nombre == "ppo":
            from rally.agentes.ppo import PilotoPPO
            _cache[clave] = PilotoPPO(rutas[nombre])
        else:
            from rally.agentes.qlearning import AgenteQ
            _cache[clave] = AgenteQ.cargar(rutas[nombre])
    return _cache[clave]


POLITICAS = {
    "experto": ("Pure pursuit, asume piso seco (μ=0.9)", lambda seed: PurePursuit(0.9)),
    "prudente": ("Pure pursuit, asume lluvia (μ=0.5)", lambda seed: PurePursuit(0.5)),
    "maestro": ("Pure pursuit que mira la señal de lluvia (profesor del PPO)", lambda seed: Maestro()),
    "aleatoria": ("Acciones al azar", lambda seed: Aleatoria(seed)),
    "qlearning": ("Agente Q-learning entrenado (tabla)", lambda seed: _modelo("qlearning")),
    "ppo": ("Agente PPO entrenado (red neuronal)", lambda seed: _modelo("ppo")),
}
# Los mismos pilotos para la moto: giran pidiendo inclinación y sus modelos están en models/moto/
POLITICAS_MOTO = {
    "experto": ("Pure pursuit de moto, asume piso seco (μ=0.9)", lambda seed: PurePursuitMoto(0.9)),
    "prudente": ("Pure pursuit de moto, asume lluvia (μ=0.5)", lambda seed: PurePursuitMoto(0.5)),
    "maestro": ("Pure pursuit de moto que mira la señal de lluvia (profesor de sus agentes)",
                lambda seed: MaestroMoto()),
    "aleatoria": ("Acciones al azar", lambda seed: Aleatoria(seed)),
    "qlearning": ("Agente Q-learning de la moto (tabla)", lambda seed: _modelo("qlearning", "moto")),
    "ppo": ("Agente PPO de la moto (red neuronal)", lambda seed: _modelo("ppo", "moto")),
}


def politicas(vehiculo="carro"):
    return POLITICAS_MOTO if vehiculo == "moto" else POLITICAS


def disponible(nombre, vehiculo="carro"):
    rutas = MODELOS_MOTO if vehiculo == "moto" else MODELOS
    return nombre in politicas(vehiculo) and (nombre not in rutas or rutas[nombre].exists())


def crear(nombre, seed=None, vehiculo="carro"):
    if not disponible(nombre, vehiculo):
        extra = " --vehiculo moto" if vehiculo == "moto" else ""
        raise FileNotFoundError(f"El modelo '{nombre}' no está entrenado todavía: "
                                f"corre `dvc repro` o `rally pipeline {nombre}{extra}`")
    return politicas(vehiculo)[nombre][1](seed)
