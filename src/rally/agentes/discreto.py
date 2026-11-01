"""Acciones discretas y discretización del estado (para Q-learning con tabla).

Q-learning con tabla necesita un número finito de estados y de acciones:
- Acciones: 6 de pedal × 9 de dirección = 54. Hacen falta niveles suaves (soltar el
  pedal, girar poquito): con solo "frenar / 30 % / a fondo" no se puede mantener la
  velocidad con lluvia y el carro llega pasado a las curvas.
- Estado: se agrupan en rangos (bins) las observaciones que más importan, incluida
  la señal de lluvia (sin ella la tabla no puede manejar distinto cuando llueve) y el
  margen de frenada: la tabla solo veía 50 m y con lluvia frenar pide más de 70.
- El pedal significa una aceleración en m/s², no un porcentaje: así la misma tabla
  sirve con cualquier aceleración máxima del carro.
"""

import itertools

import gymnasium as gym
import numpy as np

from rally.env import A_REF

A_TABLA = 4.0  # m/s²: el pedal a fondo de la tabla (aceleración base de la ficha)
PEDAL =(-1.0, -0.4, 0.0, 0.25, 0.6, 1.0)  # frenar fuerte ... acelerar a fondo
DIRECCION = (-1.0, -0.6, -0.3, -0.1, 0.0, 0.1, 0.3, 0.6, 1.0)  # derecha fuerte ... izquierda fuerte
ACCIONES = np.array(list(itertools.product(PEDAL, DIRECCION)), dtype=np.float32)
# Para estados nunca vistos: pedal suave y volante recto (no "frenar y girar a fondo")
NEUTRA = int(np.argmin(np.abs(ACCIONES - np.array([0.25, 0.0])).sum(1)))

# (índice en la observación, bordes de los rangos)
BINS = [
    (4, (-0.6, -0.3, -0.1, 0.1, 0.3, 0.6)),  # desvío del centro: 7 rangos
    (5, (-0.08, -0.04, -0.015, 0.015, 0.04, 0.08)),  # error de rumbo: 7 rangos
    (0, (0.2, 0.3, 0.4, 0.5, 0.6, 0.72, 0.85)),  # velocidad: 8 rangos
    (14, (-0.4, -0.12, 0.12, 0.4)),  # curvatura a 25 m: 5 rangos
    (13, (-0.4, -0.12, 0.12, 0.4)),  # curvatura a 10 m: 5 rangos
    (19, (0.5,)),  # lluvia: 2 rangos
]
MARGEN = (-0.2, -0.08, -0.02, 0.02, 0.08)  # velocidad menos velocidad segura: 6 rangos
FORMA = tuple(len(b) + 1 for _, b in BINS) + (len(MARGEN) + 1,)
N_ESTADOS = int(np.prod(FORMA))


def estado(obs):
    """Convierte la observación continua en un índice de la tabla Q."""
    idx = [int(np.digitize(obs[i], b)) for i, b in BINS]
    idx.append(int(np.digitize(obs[0] - obs[23], MARGEN)))
    return int(np.ravel_multi_index(idx, FORMA))


def a_mando(accion, obs):
    """Pasa la acción de la tabla a mandos del carro que hay ahora (acelerar en m/s²)."""
    u, d = accion
    return np.array([min(u * A_TABLA / (obs[21] * A_REF), 1.0) if u > 0 else u, d], dtype=np.float32)


def discreta(accion):
    """La acción discreta más parecida a una acción continua (para imitar al maestro)."""
    return int(np.argmin(((ACCIONES - np.asarray(accion)) ** 2).sum(1)))


class AccionesDiscretas(gym.ActionWrapper):
    """Expone las acciones discretas sobre el ambiente continuo."""

    def __init__(self, env):
        super().__init__(env)
        self.action_space = gym.spaces.Discrete(len(ACCIONES))

    def action(self, a):
        return ACCIONES[int(a)]
