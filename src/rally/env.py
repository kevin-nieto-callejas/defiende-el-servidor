"""Ambiente Gymnasium de Autonomous Rally (diseño: docs/ambiente-v0.1.md).

Circuito urbano inspirado en Mónaco: una vuelta pasando los checkpoints en
orden. A cada lado de la pista hay una zona de escape corta y luego el muro.
"""

import math
from dataclasses import dataclass, replace

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from rally import track

G = 9.81
RAY_ANGLES = np.radians([-90, -60, -30, 0, 30, 60, 90])
NOTAS_M = (10.0, 25.0, 50.0)  # "notas del copiloto": curvatura a estas distancias
MU_EST_MAX = 1.2  # tope del agarre estimado (más que el asfalto más adherente)
LLUVIA_MU = 0.75  # por debajo de esta adherencia se considera piso mojado (se ve llover)
# Topes de los rangos de la ficha. Los rayos se miden contra un tope fijo: si se dividieran
# por r_max, cambiar el alcance cambiaría lo que significa cada lectura (falló en v4).
ANCHO_REF, A_REF, RAYO_REF = 12.0, 6.0, 40.0
OBS_DIM = 24
VERSION = "0.4-monaco-configurable"

# Velocidad segura según la pista que viene: v² = μ · F(s), con la misma regla de los pilotos
# de referencia (curvas a 85 % del agarre y frenada a 6.67 · μ m/s²), mirando 100 m adelante.
_A_LAT, _FRENO, VISTA_M = 0.85 * G, 6.0 / 0.9, 100
MU_NOTA_SECO, MU_NOTA_LLUVIA = 0.8, 0.45  # agarre que supone la nota según el clima


def _tabla_frenada():
    n = int(track.LAP) + 1
    kappa = np.array([abs(track.curvature_at(float(i))) for i in range(n)])
    curva = np.where(kappa > 1e-6, _A_LAT / np.maximum(kappa, 1e-6), np.inf)
    return np.min([np.roll(curva, -k) + 2 * _FRENO * max(k - 2, 0) for k in range(0, VISTA_M + 1, 2)], axis=0)


_FRENADA = _tabla_frenada()


@dataclass
class RallyConfig:
    # Parámetros del escenario
    track_width: float = 8.0  # w (m)
    mu: float = 0.9  # adherencia del asfalto
    mu_grass: float = 0.35  # adherencia en la zona de escape
    a_max: float = 4.0  # m/s²
    b_max: float = 8.0  # m/s²
    r_max: float = 20.0  # alcance de sensores (m)
    v_max: float = 25.0  # m/s
    delta_max_deg: float = 30.0  # dirección máxima (°)
    dt: float = 0.1  # s
    drag: float = 0.05  # 1/s
    # Carro
    wheelbase: float = 2.5
    car_length: float = 4.0
    car_width: float = 1.8
    # Episodio
    max_steps: int = 1800  # 180 s (~2.3 veces una vuelta experta)
    off_track_limit: int = 10  # pasos seguidos fuera de pista (1 s)
    stall_limit: int = 100  # pasos sin mejorar s_best (10 s)
    start_lateral_noise: float = 0.5  # m
    start_heading_noise_deg: float = 5.0
    # Recompensa
    w_progress: float = 0.1  # por metro
    r_checkpoint: float = 10.0
    r_lap: float = 50.0
    r_time: float = -0.05  # por paso
    r_off_track: float = -1.0  # por paso
    w_steer_change: float = 0.2
    w_throttle_change: float = 0.05
    r_fail: float = -50.0


class AutonomousRallyEnv(gym.Env):
    """Una vuelta al circuito pasando los checkpoints en orden hasta la meta.

    Observación (24): [v, ω, sinφ, cosφ, d, eψ, 7 rayos, 3 notas de curvatura,
    agarre usado, derrape, agarre estimado, lluvia, ancho, aceleración máxima,
    alcance de sensores, velocidad segura].
    Acción (2): [u_acel, u_dir] en [-1, 1].
    """

    metadata = {"render_modes": ["ansi"], "render_fps": 10}

    def __init__(self, config: RallyConfig | None = None, render_mode=None, **overrides):
        self.cfg = replace(config or RallyConfig())
        for k, v in overrides.items():
            if not hasattr(self.cfg, k):  # un error de tipeo en params.yaml no pasa en silencio
                raise TypeError(f"Parámetro desconocido del ambiente: {k}")
            setattr(self.cfg, k, v)
        self.render_mode = render_mode
        self.delta_max = math.radians(self.cfg.delta_max_deg)

        low = np.array([0, -1, -1, -1, -2, -1] + [0] * 7 + [-1] * 3 + [0] * 8, dtype=np.float32)
        high = np.array([1, 1, 1, 1, 2, 1] + [1] * 7 + [1] * 3 + [1] * 8, dtype=np.float32)
        self.observation_space = spaces.Box(low, high, dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(2,), dtype=np.float32)

    # ------------------------------------------------------------------ API

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        cfg = self.cfg
        state = (options or {}).get("state")
        if state is None:
            # Salida en la línea de meta, mirando en el sentido de la pista, con ruido.
            lat = self.np_random.uniform(-cfg.start_lateral_noise, cfg.start_lateral_noise)
            dpsi = math.radians(
                self.np_random.uniform(-cfg.start_heading_noise_deg, cfg.start_heading_noise_deg)
            )
            h = float(track.HS[0])
            state = {"x": float(track.XS[0]) - lat * math.sin(h),
                     "y": float(track.YS[0]) + lat * math.cos(h), "psi": h + dpsi}

        self.x = float(state["x"])
        self.y = float(state["y"])
        self.psi = float(state["psi"])
        self.v = float(state.get("v", 0.0))
        self.omega = float(state.get("omega", 0.0))
        self.next_cp = int(state.get("next_cp", 1))
        self.steps = int(round(state.get("t", 0.0) / cfg.dt))
        self.off_steps = int(state.get("off_steps", 0))
        self.prev_action = np.array(state.get("prev_action", (0.0, 0.0)), dtype=np.float64)

        s_raw, self.d, _ = track.project(self.x, self.y)
        default_cum = s_raw if s_raw <= track.LAP / 2 else s_raw - track.LAP
        self.s_raw = s_raw
        self.s_cum = float(state.get("s_cum", default_cum))
        self.s_best = float(state.get("s_best", max(self.s_cum, 0.0)))
        self.stall_steps = 0
        self.off_track_events = 0
        self.outcome = None
        self.grip_use = 0.0
        self.skidding = False
        # Agarre estimado (como el control de tracción de un carro real): empieza
        # en el máximo posible y baja la primera vez que las llantas se saturan.
        self.mu_est = MU_EST_MAX

        return self._obs(), self._info()

    def step(self, action):
        cfg = self.cfg
        u = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        u_acel, u_dir = float(u[0]), float(u[1])

        # 1-5. Mandos -> aceleraciones, limitadas por el círculo de fricción.
        # La fuerza de las llantas se recorta por el agarre; la resistencia (drag)
        # no es fuerza de las llantas y se aplica después.
        delta = u_dir * self.delta_max
        mu = cfg.mu if abs(self.d) <= cfg.track_width / 2 else cfg.mu_grass
        grip = mu * G
        a_llanta = u_acel * (cfg.a_max if u_acel >= 0 else cfg.b_max)
        sat_long = abs(a_llanta) > grip
        a_llanta = max(-grip, min(grip, a_llanta))
        a_long = a_llanta - cfg.drag * self.v
        v_new = min(max(self.v + a_long * cfg.dt, 0.0), cfg.v_max)
        tan_d = math.tan(delta)
        a_lat = 0.0
        self.skidding = sat_long
        if v_new > 0:
            # El giro se integra con v_new, así que el límite lateral se revisa con v_new
            a_lat = v_new**2 * abs(tan_d) / cfg.wheelbase
            a_lat_max = math.sqrt(max(grip**2 - a_llanta**2, 0.0))
            if a_lat > a_lat_max:  # subviraje: gira menos de lo pedido
                tan_d = math.copysign(a_lat_max * cfg.wheelbase / v_new**2, tan_d)
                a_lat = a_lat_max
                self.skidding = True
        self.grip_use = math.hypot(a_llanta, a_lat) / grip
        if self.skidding:  # las llantas están en el límite: se mide el agarre real
            self.mu_est = min(self.mu_est, math.hypot(a_llanta, a_lat) / G)

        # 6-8. Integración (bicicleta cinemática)
        dpsi = v_new * tan_d / cfg.wheelbase * cfg.dt
        self.psi = track.wrap_angle(self.psi + dpsi)
        self.omega = dpsi / cfg.dt
        self.v = v_new
        self.x += v_new * math.cos(self.psi) * cfg.dt
        self.y += v_new * math.sin(self.psi) * cfg.dt
        self.steps += 1

        # 9. Proyección sobre la pista; s acumulado sin módulo.
        # Un salto mayor a lo que se puede recorrer en un paso es una proyección
        # sobre otro tramo cercano (p. ej. la horquilla): no cuenta como avance.
        s_raw, self.d, _ = track.project(self.x, self.y)
        ds = (s_raw - self.s_raw + track.LAP / 2) % track.LAP - track.LAP / 2
        if abs(ds) > 2 * cfg.v_max * cfg.dt + 1.0:
            ds = 0.0
        self.s_cum += ds
        self.s_raw = s_raw
        on_track = abs(self.d) <= cfg.track_width / 2

        # 10. Reglas
        reward = cfg.r_time
        reward -= cfg.w_steer_change * abs(u_dir - self.prev_action[1])
        reward -= cfg.w_throttle_change * abs(u_acel - self.prev_action[0])
        self.prev_action = u

        terminated = False
        n_gates = len(track.GATES)
        # La puerta cuenta en cuanto el carro esté en el asfalto y la haya pasado, aunque
        # el cruce exacto haya sido pisando el escape. Solo si la pasó hace poco (lo que
        # se recorre en el tiempo máximo fuera de pista): llegar mucho más adelante es un
        # atajo, no un cruce. next_cp nunca retrocede, así que no se cobra dos veces.
        margen = cfg.v_max * cfg.dt * cfg.off_track_limit + 5.0
        if self.next_cp <= n_gates and on_track:
            gate_s = track.GATES[self.next_cp - 1][0]
            if gate_s <= self.s_cum < gate_s + margen:
                if self.next_cp == n_gates:
                    reward += cfg.r_lap
                    terminated, self.outcome = True, "exito"
                else:
                    reward += cfg.r_checkpoint
                self.next_cp += 1

        if on_track:
            # Se paga el nuevo máximo de progreso, pero nunca más de lo que el carro
            # avanzó en este paso ni más allá de la próxima puerta sin cruzarla.
            cap = track.GATES[min(self.next_cp, n_gates) - 1][0]
            gain = min(max(min(self.s_cum, cap) - self.s_best, 0.0), max(ds, 0.0))
            new_best = self.s_best + gain
            reward += cfg.w_progress * gain
            self.s_best = new_best
            self.off_steps = 0
        else:
            gain = 0.0
            if self.off_steps == 0:
                self.off_track_events += 1
            self.off_steps += 1
            reward += cfg.r_off_track
        self.stall_steps = 0 if gain > 1e-9 else self.stall_steps + 1

        if not terminated:
            if track.car_collides(self.x, self.y, self.psi, cfg.car_length, cfg.car_width,
                                  cfg.track_width / 2):
                terminated, self.outcome = True, "choque"
                reward += cfg.r_fail
            elif self.off_steps >= cfg.off_track_limit:
                terminated, self.outcome = True, "salida"
                reward += cfg.r_fail
            elif self.stall_steps >= cfg.stall_limit:
                # Quedarse quieto cuesta lo mismo que chocar: si no, el agente aprende a
                # detenerse antes de las curvas difíciles (lo encontró la revisión).
                terminated, self.outcome = True, "estancado"
                reward += cfg.r_fail

        truncated = not terminated and self.steps >= cfg.max_steps
        if truncated:
            self.outcome = "tiempo"

        return self._obs(), float(reward), terminated, truncated, self._info()

    def render(self):
        if self.render_mode == "ansi":
            return self._ascii()
        return None

    # ------------------------------------------------------------ Internos

    def _obs(self):
        cfg = self.cfg
        s_raw, d, tangent = track.project(self.x, self.y)
        cp = track.GATES[min(self.next_cp, len(track.GATES)) - 1]
        phi = track.wrap_angle(math.atan2(cp[2] - self.y, cp[1] - self.x) - self.psi)
        e_psi = track.wrap_angle(self.psi - tangent)
        rays = track.raycast(
            self.x, self.y, self.psi, RAY_ANGLES, cfg.r_max, cfg.track_width / 2
        )
        notas = [np.clip(track.curvature_at(s_raw + k) * track.R, -1, 1) for k in NOTAS_M]
        lluvia = cfg.mu < LLUVIA_MU
        mu_nota = MU_NOTA_LLUVIA if lluvia else MU_NOTA_SECO
        v_segura = math.sqrt(mu_nota * _FRENADA[int(s_raw) % len(_FRENADA)])
        obs = [
            self.v / cfg.v_max,
            np.clip(self.omega / 2.0, -1, 1),
            math.sin(phi),
            math.cos(phi),
            np.clip(d / (cfg.track_width / 2), -2, 2),
            e_psi / math.pi,
            *(rays / RAYO_REF),
            *notas,
            # Sensor de agarre (v0.2): cuánto agarre se está usando, si las llantas
            # derrapan y el agarre estimado del piso (1 = no se ha medido un límite aún)
            min(self.grip_use, 1.0),
            float(self.skidding),
            self.mu_est / MU_EST_MAX,
            # Sensor de lluvia (v0.3): el piloto VE que llueve (cámara/limpiaparabrisas),
            # pero no sabe la adherencia exacta.
            1.0 if lluvia else 0.0,
            # Configuración del carro (v0.4): el piloto conoce su propio carro y el ancho
            cfg.track_width / ANCHO_REF,
            cfg.a_max / A_REF,
            cfg.r_max / RAYO_REF,
            # Nota de frenada (v0.4): a cuánto se puede ir para llegar bien a lo que viene
            min(v_segura, cfg.v_max) / cfg.v_max,
        ]
        return np.array(obs, dtype=np.float32)

    def _info(self):
        return {
            "x": self.x,
            "y": self.y,
            "psi": self.psi,
            "v": self.v,
            "d": self.d,
            "s": self.s_cum,
            "s_best": self.s_best,
            "next_cp": self.next_cp,
            "t": self.steps * self.cfg.dt,
            "off_track_events": self.off_track_events,
            "off_steps": self.off_steps,
            "grip_use": self.grip_use,
            "skidding": self.skidding,
            "mu_est": self.mu_est,
            "outcome": self.outcome,
        }

    def _ascii(self, cols=80, rows=24):
        """Mapa en texto: '#' pista, '|' muro, números CP, 'M' meta, '@' carro."""
        xs = np.linspace(-track.MAP_X, track.MAP_X, cols)
        ys = np.linspace(track.MAP_Y, -track.MAP_Y, rows)
        gx, gy = np.meshgrid(xs, ys)
        d = np.abs(track.lateral(gx, gy))
        hw = self.cfg.track_width / 2
        grid = np.full(gx.shape, " ", dtype="<U1")
        grid[d <= hw + track.RUNOFF + 2] = "|"
        grid[d <= hw] = "#"

        def cell(x, y):
            c = int(round((x + track.MAP_X) / (2 * track.MAP_X) * (cols - 1)))
            r = int(round((track.MAP_Y - y) / (2 * track.MAP_Y) * (rows - 1)))
            return min(max(r, 0), rows - 1), min(max(c, 0), cols - 1)

        for i, (_, gx_, gy_) in enumerate(track.GATES):
            grid[cell(gx_, gy_)] = "M" if i == len(track.GATES) - 1 else str(i + 1)
        grid[cell(self.x, self.y)] = "@"
        status = (
            f"t={self.steps * self.cfg.dt:5.1f}s v={self.v:5.2f}m/s s={self.s_cum:7.2f}m "
            f"d={self.d:+.2f}m sig.CP={self.next_cp}"
        )
        return "\n".join("".join(r) for r in grid) + "\n" + status
