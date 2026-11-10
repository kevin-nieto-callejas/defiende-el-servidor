"""Geometría de las pistas de Autonomous Rally (ver docs/ambiente-v0.1.md).

Cada pista es un objeto `Pista`; `obtener(nombre)` la busca en `PISTAS`.
Mónaco es la pista por defecto y los nombres del módulo (`XS`, `project`...)
siguen apuntando a ella.

Cada trazado se define como un polígono de vértices con un radio de curva en
cada uno: entre vértices hay rectas y en cada vértice un arco tangente a ambas
rectas (como se diseñan los circuitos).
Así cada curva tiene un radio exacto y conocido.

La línea central se muestrea cada 0.25 m. Para proyectar un punto se busca la
muestra más cercana con un KD-tree (rápido incluso para miles de puntos).
A cada lado de la pista hay una zona de escape corta y luego el muro (Armco),
como en un circuito urbano.
"""

import math

import numpy as np
from scipy.spatial import cKDTree

# (nombre de la curva, x, y, radio de la curva en m). Sentido antihorario.
VERTICES = [
    ("Anthony Noghes", -40.0, 0.0, 16.0),
    ("Sainte Dévote", 150.0, 0.0, 13.0),
    ("Beau Rivage", 168.0, 95.0, 90.0),
    ("Massenet", 138.0, 178.0, 38.0),
    ("Casino", 82.0, 172.0, 28.0),
    ("Casino salida", 45.0, 196.0, 24.0),
    ("Mirabeau Haute", -18.0, 192.0, 13.0),
    ("Fairmont", -14.0, 126.0, 9.5),  # horquilla: dos curvas cerradas a la derecha
    ("Fairmont salida", -40.0, 126.0, 9.5),
    ("Mirabeau Bas", -40.0, 166.0, 12.0),
    ("Portier", -85.0, 168.0, 14.0),
    ("Túnel", -170.0, 150.0, 120.0),
    ("Nouvelle Chicane", -200.0, 72.0, 11.0),
    ("Nouvelle Chicane salida", -182.0, 60.0, 11.0),
    ("Tabac", -192.0, 24.0, 15.0),
    ("Piscine", -128.0, 34.0, 13.0),
    ("Piscine salida", -112.0, 22.0, 13.0),
    ("Rascasse", -70.0, 34.0, 10.0),
]
START_FRACTION = 0.35  # la salida está a este porcentaje de la recta Noghes -> Sainte Dévote
SAMPLE = 0.25  # m entre muestras de la línea central
RUNOFF = 2.0  # m de escape entre el borde de la pista y el muro
MARGIN = 25.0  # m entre el trazado y el borde del mapa

# Puertas (checkpoints): nombre de la curva tras la cual se ubica cada puerta
GATE_CORNERS = ["Beau Rivage", "Casino salida", "Fairmont salida", "Túnel",
                "Nouvelle Chicane salida", "Piscine salida"]


def wrap_angle(a):
    """Lleva un ángulo a (-pi, pi]."""
    return (a + math.pi) % (2 * math.pi) - math.pi


# ------------------------------------------------------------- construcción

def _build(vertices):
    """Devuelve las piezas (rectas y arcos) del trazado cerrado y errores de diseño."""
    pts = np.array([(x, y) for _, x, y, _ in vertices])
    radii = [r for *_, r in vertices]
    n = len(pts)
    corners, errors = [], []
    for i in range(n):
        p, v, q = pts[i - 1], pts[i], pts[(i + 1) % n]
        d_in = (v - p) / np.linalg.norm(v - p)
        d_out = (q - v) / np.linalg.norm(q - v)
        cross = d_in[0] * d_out[1] - d_in[1] * d_out[0]
        theta = math.atan2(cross, float(np.dot(d_in, d_out)))  # + = izquierda
        t = radii[i] * math.tan(abs(theta) / 2)
        a, b = v - t * d_in, v + t * d_out
        normal = np.array([-d_in[1], d_in[0]]) * (1 if theta > 0 else -1)
        center = a + radii[i] * normal
        corners.append({"name": vertices[i][0], "a": a, "b": b, "theta": theta, "t": t,
                        "r": radii[i], "center": center})
    for i in range(n):
        seg = np.linalg.norm(pts[(i + 1) % n] - pts[i])
        room = seg - corners[i]["t"] - corners[(i + 1) % n]["t"]
        if room < 0:
            errors.append(f"No caben las curvas {corners[i]['name']} y "
                          f"{corners[(i + 1) % n]['name']}: faltan {-room:.1f} m")
    return corners, errors


def _sample(corners, step):
    """Muestrea la línea central: arcos y rectas alternados, cada `step` m."""
    xs, ys, hs, ks, names = [], [], [], [], []
    n = len(corners)
    for i, c in enumerate(corners):
        # Arco de la curva i
        a0 = math.atan2(c["a"][1] - c["center"][1], c["a"][0] - c["center"][0])
        arc = abs(c["theta"]) * c["r"]
        m = max(1, int(round(arc / step)))
        sgn = 1 if c["theta"] > 0 else -1
        for k in range(m):
            ang = a0 + sgn * (k / m) * abs(c["theta"])
            xs.append(c["center"][0] + c["r"] * math.cos(ang))
            ys.append(c["center"][1] + c["r"] * math.sin(ang))
            hs.append(ang + sgn * math.pi / 2)
            ks.append(sgn / c["r"])
            names.append(c["name"])
        # Recta hasta la siguiente curva
        b, a_next = c["b"], corners[(i + 1) % n]["a"]
        seg = a_next - b
        length = float(np.linalg.norm(seg))
        m = int(round(length / step))
        h = math.atan2(seg[1], seg[0])
        for k in range(m):
            p = b + seg * (k / max(m, 1))
            xs.append(p[0])
            ys.append(p[1])
            hs.append(h)
            ks.append(0.0)
            names.append("")
    xs, ys = np.array(xs), np.array(ys)
    seglen = np.hypot(np.diff(xs, append=xs[0]), np.diff(ys, append=ys[0]))
    return xs, ys, np.array([wrap_angle(h) for h in hs]), np.array(ks), names, seglen


class Pista:
    """Un circuito cerrado: geometría muestreada, puertas y consultas.

    `sentido` solo documenta el trazado (antihorario u horario); la geometría sale
    del orden de los vértices.
    """

    def __init__(self, nombre, vertices, gate_corners, start_fraction=0.35, descripcion="",
                 sentido="antihorario", titulo=None):
        self.nombre = nombre
        self.titulo = titulo or nombre.capitalize()  # nombre para mostrar en la web
        self.descripcion = descripcion
        self.sentido = sentido
        self.VERTICES = list(vertices)
        self.GATE_CORNERS = list(gate_corners)
        self.START_FRACTION = start_fraction
        self.RUNOFF = RUNOFF
        (self.XS, self.YS, self.HS, self.KS, self.NAMES, self.SS, self.LAP,
         self.CORNERS) = self._assemble()
        self._TREE = cKDTree(np.column_stack([self.XS, self.YS]))
        self._NX, self._NY = -np.sin(self.HS), np.cos(self.HS)  # normal izquierda
        self.MAP_X = float(np.abs(self.XS).max() + MARGIN)
        self.MAP_Y = float(np.abs(self.YS).max() + MARGIN)
        self.OBSTACLES = []  # en un circuito urbano el obstáculo es el muro
        self.GATES_NAMED = self._gates()
        self.GATES = [(s, x, y) for s, x, y, _ in self.GATES_NAMED]
        self.GATE_NAMES = [n for *_, n in self.GATES_NAMED]
        self.R = float(min(c["r"] for c in self.CORNERS))  # radio más cerrado
        self._grid = None

    def __repr__(self):
        return f"Pista({self.nombre!r}, {self.LAP:.0f} m, {len(self.VERTICES)} curvas)"

    # --------------------------------------------------------- construcción

    def _assemble(self):
        corners, errors = _build(self.VERTICES)
        if errors:
            raise ValueError(f"Trazado inválido ({self.nombre}):\n" + "\n".join(errors))
        xs, ys, hs, ks, names, seglen = _sample(corners, SAMPLE)

        # Centrar el trazado en el origen
        cx, cy = (xs.max() + xs.min()) / 2, (ys.max() + ys.min()) / 2
        xs, ys = xs - cx, ys - cy

        # La vuelta empieza en la línea de salida (recta entre los dos primeros vértices)
        v0 = np.array(self.VERTICES[0][1:3]) - (cx, cy)
        v1 = np.array(self.VERTICES[1][1:3]) - (cx, cy)
        start = v0 + self.START_FRACTION * (v1 - v0)
        i0 = int(np.argmin(np.hypot(xs - start[0], ys - start[1])))
        roll = lambda arr: np.roll(arr, -i0)  # noqa: E731
        xs, ys, hs, ks, seglen = map(roll, (xs, ys, hs, ks, seglen))
        names = names[i0:] + names[:i0]
        ss = np.concatenate([[0.0], np.cumsum(seglen)[:-1]])
        return xs, ys, hs, ks, names, ss, float(seglen.sum()), corners

    def _corner_range(self, name):
        idx = [i for i, n in enumerate(self.NAMES) if n == name]
        return self.SS[idx[0]], self.SS[idx[-1]]

    def _gates(self):
        gates = []
        for name in self.GATE_CORNERS:
            _, s_end = self._corner_range(name)
            s = s_end + 12.0  # 12 m después de la salida de la curva
            i = int(np.searchsorted(self.SS, s))
            gates.append((float(self.SS[i]), float(self.XS[i]), float(self.YS[i]), name))
        gates.sort()
        gates.append((self.LAP, float(self.XS[0]), float(self.YS[0]), "Meta"))
        return gates

    # ------------------------------------------------------------ consultas

    def lateral(self, x, y):
        """Desvío lateral d respecto a la línea central (+ = izquierda). Escalar o arreglo."""
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        _, i = self._TREE.query(np.column_stack([x.ravel(), y.ravel()]))
        d = (x.ravel() - self.XS[i]) * self._NX[i] + (y.ravel() - self.YS[i]) * self._NY[i]
        return d.reshape(x.shape) if x.shape else float(d[0])

    def project(self, x, y):
        """Proyecta un punto sobre la línea central: (s en [0, LAP), d, rumbo tangente)."""
        _, i = self._TREE.query((x, y))
        dx, dy = x - self.XS[i], y - self.YS[i]
        along = dx * math.cos(self.HS[i]) + dy * math.sin(self.HS[i])
        d = dx * self._NX[i] + dy * self._NY[i]
        return float((self.SS[i] + along) % self.LAP), float(d), float(self.HS[i])

    def project_many(self, x, y):
        """Versión vectorizada de project: devuelve arreglos (s, d)."""
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        _, i = self._TREE.query(np.column_stack([x.ravel(), y.ravel()]))
        dx, dy = x.ravel() - self.XS[i], y.ravel() - self.YS[i]
        s = (self.SS[i] + dx * np.cos(self.HS[i]) + dy * np.sin(self.HS[i])) % self.LAP
        d = dx * self._NX[i] + dy * self._NY[i]
        return s.reshape(x.shape), d.reshape(x.shape)

    def _index(self, s):
        return int(np.searchsorted(self.SS, s % self.LAP, side="right") - 1)

    def point_at(self, s):
        """Punto (x, y) de la línea central a la distancia s (con módulo LAP)."""
        i = self._index(s)
        along = (s % self.LAP) - self.SS[i]
        return (float(self.XS[i] + along * math.cos(self.HS[i])),
                float(self.YS[i] + along * math.sin(self.HS[i])))

    def heading_at(self, s):
        return float(self.HS[self._index(s)])

    def curvature_at(self, s):
        """Curvatura con signo (1/m) en s: + izquierda, - derecha, 0 recta."""
        return float(self.KS[self._index(s)])

    def in_corner(self, s):
        return abs(self.curvature_at(s)) > 1e-9

    def corner_name(self, s):
        return self.NAMES[self._index(s)]

    def in_obstacle(self, x, y):
        return np.zeros(np.shape(x), dtype=bool)

    def outside_walls(self, x, y, half_width):
        """True más allá del muro: zona de escape superada o fuera del mapa."""
        beyond = self.abs_lateral_rapido(np.asarray(x, dtype=float),
                                         np.asarray(y, dtype=float)) > half_width + RUNOFF
        return beyond | (np.abs(x) >= self.MAP_X) | (np.abs(y) >= self.MAP_Y)

    # --------------------------------------------------------- grilla rápida
    # Para los rayos se consulta |d| miles de veces por segundo. En vez del KD-tree
    # se usa una grilla precalculada cada 0.25 m con interpolación bilineal.

    def _cargar_grilla(self):
        import hashlib
        import os
        from pathlib import Path

        # La clave depende de la geometría ya muestreada: si cambia el trazado o el
        # algoritmo, cambia la clave y la grilla se recalcula.
        h = hashlib.sha1()
        for arr in (self.XS, self.YS, self.HS):
            h.update(np.ascontiguousarray(arr).tobytes())
        h.update(repr((GRID_RES, self.MAP_X, self.MAP_Y)).encode())
        cache = (Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "rally"
                 / f"grilla-{h.hexdigest()[:16]}.npy")
        if cache.exists():
            try:
                self._grid = np.load(cache)
                return self._grid
            except (OSError, ValueError, EOFError):
                pass  # archivo dañado: se recalcula
        gx = np.arange(-self.MAP_X, self.MAP_X + GRID_RES, GRID_RES)
        gy = np.arange(-self.MAP_Y, self.MAP_Y + GRID_RES, GRID_RES)
        mx, my = np.meshgrid(gx, gy)
        self._grid = np.abs(self.lateral(mx, my)).astype(np.float32)
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache.with_name(f".{cache.stem}.{os.getpid()}.tmp.npy")
            np.save(tmp, self._grid)
            os.replace(tmp, cache)  # escritura atómica: varios procesos pueden arrancar a la vez
        except OSError:
            pass
        return self._grid

    def abs_lateral_rapido(self, x, y):
        """|d| interpolado desde la grilla (error < 1 cm cerca de la pista)."""
        g = self._grid if self._grid is not None else self._cargar_grilla()
        fx = (np.clip(x, -self.MAP_X, self.MAP_X - 1e-6) + self.MAP_X) / GRID_RES
        fy = (np.clip(y, -self.MAP_Y, self.MAP_Y - 1e-6) + self.MAP_Y) / GRID_RES
        ix, iy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
        tx, ty = fx - ix, fy - iy
        return ((g[iy, ix] * (1 - tx) + g[iy, ix + 1] * tx) * (1 - ty)
                + (g[iy + 1, ix] * (1 - tx) + g[iy + 1, ix + 1] * tx) * ty)

    def raycast(self, x, y, psi, angles, r_max, half_width, step=0.25, refine=7):
        """Distancia (m) de cada rayo al primer borde de pista o muro (r_max si no hay)."""
        origin_on = abs(float(self.lateral(x, y))) <= half_width

        def hits(px, py):
            d = self.abs_lateral_rapido(px, py)
            on = d <= half_width
            wall = (d > half_width + RUNOFF) | (np.abs(px) >= self.MAP_X) | (np.abs(py) >= self.MAP_Y)
            return (on != origin_on) | wall

        ang = psi + np.asarray(angles)
        dx, dy = np.cos(ang), np.sin(ang)
        ts = np.arange(step, r_max + 1e-9, step)
        h = hits(x + np.outer(dx, ts), y + np.outer(dy, ts))
        any_hit = h.any(axis=1)
        idx = np.argmax(h, axis=1)
        hi = ts[idx]
        lo = np.where(idx > 0, ts[np.maximum(idx - 1, 0)], 0.0)
        for _ in range(refine):
            mid = (lo + hi) / 2
            hm = hits(x + mid * dx, y + mid * dy)
            hi = np.where(hm, mid, hi)
            lo = np.where(hm, lo, mid)
        return np.where(any_hit, hi, r_max)

    def car_collides(self, x, y, psi, length, width, half_width):
        """True si algún punto del contorno del carro (muestreado cada ~0.5 m) pasa el muro."""
        lx = np.linspace(-length / 2, length / 2, _N_LARGO)
        ly = np.linspace(-width / 2, width / 2, _N_ANCHO)
        bx = np.concatenate([lx, lx, np.full(_N_ANCHO, -length / 2), np.full(_N_ANCHO, length / 2)])
        by = np.concatenate([np.full(_N_LARGO, -width / 2), np.full(_N_LARGO, width / 2), ly, ly])
        c, s = math.cos(psi), math.sin(psi)
        return bool(self.outside_walls(x + bx * c - by * s, y + bx * s + by * c, half_width).any())

    def check_design(self, max_width=12.0):
        """Revisa el trazado: radios, rectas y separación entre tramos no vecinos."""
        report = {"pista": self.nombre, "largo": self.LAP, "radio_min": self.R,
                  "curvas": len(self.VERTICES), "problemas": []}
        pts = np.column_stack([self.XS, self.YS])
        sep_min = max_width + 2 * RUNOFF + 2
        worst = (np.inf, None)
        for i in range(0, len(self.XS), 8):
            near = self._TREE.query_ball_point(pts[i], sep_min)
            for j in near:
                gap = abs(self.SS[i] - self.SS[j])
                gap = min(gap, self.LAP - gap)
                if gap > 60:
                    dist = float(np.hypot(*(pts[i] - pts[j])))
                    if dist < worst[0]:
                        worst = (dist, (self.corner_name(self.SS[i]) or "recta",
                                        self.corner_name(self.SS[j]) or "recta"))
        if worst[1]:
            report["problemas"].append(
                f"Tramos a {worst[0]:.1f} m (< {sep_min:.0f} m): {worst[1][0]} / {worst[1][1]}")
        return report


GRID_RES = 0.25
_N_LARGO, _N_ANCHO = 9, 5  # puntos del contorno: cada 0.5 m en el largo, ~0.45 m en el ancho

# ------------------------------------------------------------- pistas

MONACO = Pista("monaco", VERTICES, GATE_CORNERS, START_FRACTION,
               descripcion="Circuito urbano inspirado en Mónaco: horquilla, túnel y chicanas", titulo="Mónaco")

# Pistas para medir si el agente aprendió a manejar o solo memorizó Mónaco. Se diseñaron
# distintas a propósito: el Bosque es rápido y gira en sentido HORARIO (Mónaco gira sobre
# todo a la izquierda); el Puerto es técnico, con chicanes y horquillas más cerradas.
# Antes de aceptarlas, los cuatro pilotos de referencia completaron 10/10 vueltas en seco y
# con lluvia (tests/test_pistas.py lo vuelve a revisar).
BOSQUE = Pista(
    "bosque",
    [
        ("Horquilla del Lago", -200.0, 110.0, 14.0),
        ("Curva Larga", 120.0, 110.0, 60.0),
        ("Pinos", 200.0, 30.0, 35.0),
        ("Ese del Río", 150.0, -30.0, 28.0),
        ("Ese del Río salida", 190.0, -95.0, 28.0),
        ("Valle", 110.0, -135.0, 45.0),
        ("Rápida del Bosque", -70.0, -110.0, 80.0),
        ("Mirador", -130.0, -30.0, 18.0),
        ("Cascada", -210.0, -50.0, 15.0),
    ],
    ["Curva Larga", "Ese del Río salida", "Valle", "Rápida del Bosque", "Mirador", "Cascada"],
    descripcion="Circuito rápido de curvas largas, en sentido horario",
    sentido="horario",
)

PUERTO = Pista(
    "puerto",
    [
        ("Muelle", -150.0, -90.0, 11.0),
        ("Chicane del Muelle", -30.0, -90.0, 9.0),
        ("Chicane del Muelle salida", -5.0, -72.0, 9.0),
        ("Faro", 120.0, -72.0, 10.0),
        ("Grúas", 130.0, 10.0, 15.0),
        ("Aduana", 50.0, 25.0, 9.0),
        ("Aduana salida", 50.0, 70.0, 9.0),
        ("Lonja", 140.0, 90.0, 14.0),
        ("Capitanía", 110.0, 160.0, 11.0),
        ("Dique", -60.0, 150.0, 22.0),
        ("Contenedores", -70.0, 60.0, 8.5),
        ("Contenedores salida", -110.0, 60.0, 8.5),
        ("Rompeolas", -170.0, 20.0, 12.0),
        ("Varadero", -130.0, -20.0, 10.0),
        ("Varadero salida", -175.0, -45.0, 10.0),
    ],
    ["Chicane del Muelle salida", "Aduana salida", "Capitanía", "Dique", "Contenedores salida",
     "Varadero salida"],
    descripcion="Circuito portuario técnico: chicanes y horquillas cerradas",
)

# Pista RESERVADA para la prueba final de generalización: ningún modelo entrena en ella y no
# se usa para elegir hiperparámetros ni el mejor punto del entrenamiento (rally.agentes.ppo
# se niega a entrenar con ella). Su curva más cerrada (11 m) está dentro de lo que miden las
# notas de curvatura (radio de Mónaco, 9.5 m): si un modelo falla aquí, no es por el sensor.
SIERRA = Pista(
    "sierra",
    [
        ("Puente", -170.0, -80.0, 15.0),
        ("Molino", 60.0, -100.0, 30.0),
        ("Mirador Alto", 170.0, -40.0, 18.0),
        ("Paso", 120.0, 30.0, 12.0),
        ("Paso salida", 170.0, 90.0, 12.0),
        ("Cumbre", 100.0, 150.0, 25.0),
        ("Bajada", -20.0, 120.0, 40.0),
        ("Laguna", -60.0, 160.0, 11.0),
        ("Laguna salida", -130.0, 150.0, 14.0),
        ("Cañón", -110.0, 40.0, 20.0),
        ("Refugio", -180.0, 10.0, 12.0),
    ],
    ["Mirador Alto", "Paso salida", "Bajada", "Laguna salida", "Cañón", "Refugio"],
    descripcion="Circuito de montaña de curvas mixtas; reservado para la prueba de generalización",
)

PISTAS = {"monaco": MONACO, "bosque": BOSQUE, "puerto": PUERTO, "sierra": SIERRA}
RESERVADAS = {"sierra"}


def validar_entrenamiento(pistas):
    """Lista de pistas para entrenar (None = Mónaco); falla si incluye una reservada."""
    nombres = ["monaco"] if pistas is None else ([pistas] if isinstance(pistas, str) else list(pistas))
    for n in nombres:
        obtener(n)
    prohibidas = RESERVADAS & set(nombres)
    if prohibidas:
        raise ValueError(f"No se puede entrenar con pistas reservadas para la prueba: {sorted(prohibidas)}")
    return nombres


def registrar(pista):
    PISTAS[pista.nombre] = pista
    return pista


def largo(info):
    """Largo de la pista en la que va el episodio (para expresar el progreso en %)."""
    return obtener(info.get("pista")).LAP


def obtener(nombre=None):
    """Pista por nombre (None = Mónaco). Acepta también un objeto Pista."""
    if nombre is None:
        return MONACO
    if isinstance(nombre, Pista):
        return nombre
    try:
        return PISTAS[nombre]
    except KeyError:
        raise ValueError(f"Pista desconocida: {nombre!r}. Disponibles: {', '.join(PISTAS)}") from None


# Compatibilidad: el resto del código y los modelos históricos usan `track.XS`,
# `track.project(...)`, etc. Esos nombres siguen apuntando a Mónaco.
(XS, YS, HS, KS, NAMES, SS, LAP, CORNERS) = (MONACO.XS, MONACO.YS, MONACO.HS, MONACO.KS,
                                              MONACO.NAMES, MONACO.SS, MONACO.LAP, MONACO.CORNERS)
_TREE = MONACO._TREE
MAP_X, MAP_Y = MONACO.MAP_X, MONACO.MAP_Y
OBSTACLES = MONACO.OBSTACLES
GATES_NAMED, GATES, GATE_NAMES = MONACO.GATES_NAMED, MONACO.GATES, MONACO.GATE_NAMES
R = MONACO.R
lateral, project, project_many = MONACO.lateral, MONACO.project, MONACO.project_many
point_at, heading_at, curvature_at = MONACO.point_at, MONACO.heading_at, MONACO.curvature_at
in_corner, corner_name, in_obstacle = MONACO.in_corner, MONACO.corner_name, MONACO.in_obstacle
outside_walls, abs_lateral_rapido = MONACO.outside_walls, MONACO.abs_lateral_rapido
raycast, car_collides, check_design = MONACO.raycast, MONACO.car_collides, MONACO.check_design
