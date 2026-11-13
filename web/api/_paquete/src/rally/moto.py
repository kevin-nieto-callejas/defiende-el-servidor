"""Ambiente MotoGP: las mismas pistas, puertas y recompensa del carro con física de moto.

Ficha: docs/ambiente-moto.md. Lo que cambia frente al carro (rally.env):

- **El mando de dirección pide una inclinación**, no un ángulo de volante. La moto gira por
  inclinarse: a_lat = g · tan φ, y la curvatura es a_lat / v². La inclinación no cambia de golpe:
  sube o baja a lo sumo `roll_rate_deg` por segundo. El agente tiene que empezar a tumbar la moto
  antes de la curva (la decisión nueva de este vehículo).
- **Pasarse del agarre tira la moto.** El carro subvira (gira menos y sigue); la moto que pide más
  agarre lateral del que hay patina, y si patina `slide_limit` pasos seguidos se cae: fin del
  episodio con resultado "caida" y la misma penalización que un choque.
- **Equilibrio a baja velocidad.** Parada no se puede inclinar: a velocidad v la inclinación máxima
  es la que corresponde al giro más cerrado del manubrio, atan(v² · tan δ_max / (L · g)).
- Más liviana y más rápida: v_max 32 m/s, a_max 5 m/s², b_max 9 m/s², 2.1 m × 0.8 m.

Observación (26): las 24 del carro, con el mismo orden y divisores (la velocidad se divide por
el v_max de la moto), más [24] inclinación φ/φ_max y [25] riesgo de caída (pasos patinando /
slide_limit). Acción (2): [u_acel, u_dir] en [-1, 1]; u_dir = inclinación pedida / φ_max.
"""

import math
from dataclasses import dataclass

import numpy as np
from gymnasium import spaces

from rally import track
from rally.env import G, AutonomousRallyEnv, RallyConfig

VERSION = "moto-0.1"
OBS_DIM = 26
VEHICULO = "moto"


@dataclass
class MotoConfig(RallyConfig):
    a_max: float = 5.0  # m/s²
    b_max: float = 9.0  # m/s²
    v_max: float = 32.0  # m/s
    drag: float = 0.04  # 1/s
    delta_max_deg: float = 30.0  # tope del manubrio: solo limita el giro a muy baja velocidad
    wheelbase: float = 1.45
    car_length: float = 2.1  # largo de la moto (m)
    car_width: float = 0.8  # ancho con el piloto (m)
    phi_max_deg: float = 60.0  # inclinación máxima que puede pedir el piloto
    roll_rate_deg: float = 80.0  # °/s: qué tan rápido cambia la inclinación
    slide_limit: int = 3  # pasos seguidos patinando (0.3 s) antes de caerse


class MotoGPEnv(AutonomousRallyEnv):
    """Una vuelta en moto pasando los checkpoints en orden (ver el docstring del módulo)."""

    vehiculo = VEHICULO

    def __init__(self, config: MotoConfig | None = None, render_mode=None, pista=None, **overrides):
        super().__init__(config or MotoConfig(), render_mode, pista, **overrides)
        if not isinstance(self.cfg, MotoConfig):
            raise TypeError("MotoGPEnv necesita un MotoConfig")
        low = np.concatenate([self.observation_space.low, np.array([-1, 0], dtype=np.float32)])
        high = np.concatenate([self.observation_space.high, np.array([1, 1], dtype=np.float32)])
        self.observation_space = spaces.Box(low, high, dtype=np.float32)

    @property
    def phi_max(self):
        return math.radians(self.cfg.phi_max_deg)

    def reset(self, *, seed=None, options=None):
        state = (options or {}).get("state") or {}
        self.phi = float(state.get("phi", 0.0))
        self.slide_steps = int(state.get("slide_steps", 0))
        return super().reset(seed=seed, options=options)

    # ------------------------------------------------------------ física

    def _fisica(self, u_acel, u_dir):
        cfg = self.cfg
        # 1. Inclinación: el mando pide un ángulo y la moto llega a él a lo sumo a roll_rate
        paso = math.radians(cfg.roll_rate_deg) * cfg.dt
        self.phi += max(-paso, min(paso, u_dir * self.phi_max - self.phi))

        # 2-3. Pedal: igual que el carro, recortado por el agarre (círculo de fricción)
        mu = cfg.mu if abs(self.d) <= cfg.track_width / 2 else cfg.mu_grass
        grip = mu * G
        a_llanta = u_acel * (cfg.a_max if u_acel >= 0 else cfg.b_max)
        sat_long = abs(a_llanta) > grip
        a_llanta = max(-grip, min(grip, a_llanta))
        v_new = min(max(self.v + (a_llanta - cfg.drag * self.v) * cfg.dt, 0.0), cfg.v_max)

        # 4. Equilibrio: a esta velocidad la moto solo se sostiene hasta el giro más cerrado
        kappa_max = math.tan(self.delta_max) / cfg.wheelbase
        phi_eq = math.atan(v_new**2 * kappa_max / G)
        self.phi = max(-phi_eq, min(phi_eq, self.phi))

        # 5. Giro por inclinación y límite de agarre: pasarse no subvira, patina
        a_lat = G * math.tan(abs(self.phi))
        a_lat_max = math.sqrt(max(grip**2 - a_llanta**2, 0.0))
        self.skidding = sat_long
        if a_lat > a_lat_max:
            a_lat = a_lat_max
            self.skidding = True
            self.slide_steps += 1
        else:
            self.slide_steps = 0
        kappa = math.copysign(a_lat / v_new**2, self.phi) if v_new > 0 else 0.0
        self.grip_use = math.hypot(a_llanta, a_lat) / grip
        if self.skidding:
            self.mu_est = min(self.mu_est, math.hypot(a_llanta, a_lat) / G)

        # 6-8. Integración: el mismo modelo de una sola huella del carro
        dpsi = v_new * kappa * cfg.dt
        self.psi = track.wrap_angle(self.psi + dpsi)
        self.omega = dpsi / cfg.dt
        self.v = v_new
        self.x += v_new * math.cos(self.psi) * cfg.dt
        self.y += v_new * math.sin(self.psi) * cfg.dt
        self.steps += 1

    def _falla_vehiculo(self):
        return "caida" if self.slide_steps >= self.cfg.slide_limit else None

    # ------------------------------------------------------------ observación

    def _obs(self):
        base = super()._obs()
        extra = [self.phi / self.phi_max, min(self.slide_steps / self.cfg.slide_limit, 1.0)]
        return np.concatenate([base, np.array(extra, dtype=np.float32)])

    def _info(self):
        return {**super()._info(), "inclinacion": self.phi, "patinando_pasos": self.slide_steps,
                "vehiculo": VEHICULO}
