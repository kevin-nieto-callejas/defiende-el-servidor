"""Geometría de la pista de Autonomous Rally (ver docs/ambiente-v0.1.md).

Circuito inspirado en Mónaco. El trazado se define como un polígono de
vértices con un radio de curva en cada uno: entre vértices hay rectas y en
cada vértice un arco tangente a ambas rectas (como se diseñan los circuitos).
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


def _assemble():
    corners, errors = _build(VERTICES)
    if errors:
        raise ValueError("Trazado inválido:\n" + "\n".join(errors))
    xs, ys, hs, ks, names, seglen = _sample(corners, SAMPLE)

    # Centrar el trazado en el origen
    cx, cy = (xs.max() + xs.min()) / 2, (ys.max() + ys.min()) / 2
    xs, ys = xs - cx, ys - cy

    # La vuelta empieza en la línea de salida (recta Noghes -> Sainte Dévote)
    v0, v1 = np.array(VERTICES[0][1:3]) - (cx, cy), np.array(VERTICES[1][1:3]) - (cx, cy)
    start = v0 + START_FRACTION * (v1 - v0)
    i0 = int(np.argmin(np.hypot(xs - start[0], ys - start[1])))
    roll = lambda arr: np.roll(arr, -i0)  # noqa: E731
    xs, ys, hs, ks, seglen = map(roll, (xs, ys, hs, ks, seglen))
    names = names[i0:] + names[:i0]
    ss = np.concatenate([[0.0], np.cumsum(seglen)[:-1]])
    return xs, ys, hs, ks, names, ss, float(seglen.sum()), corners


XS, YS, HS, KS, NAMES, SS, LAP, CORNERS = _assemble()
_TREE = cKDTree(np.column_stack([XS, YS]))
_NX, _NY = -np.sin(HS), np.cos(HS)  # normal izquierda

MAP_X = float(np.abs(XS).max() + MARGIN)
MAP_Y = float(np.abs(YS).max() + MARGIN)
OBSTACLES = []  # en un circuito urbano el obstáculo es el muro


def _corner_range(name):
    idx = [i for i, n in enumerate(NAMES) if n == name]
    return SS[idx[0]], SS[idx[-1]]


def _gates():
    gates = []
    for name in GATE_CORNERS:
        _, s_end = _corner_range(name)
        s = s_end + 12.0  # 12 m después de la salida de la curva
        i = int(np.searchsorted(SS, s))
        gates.append((float(SS[i]), float(XS[i]), float(YS[i]), name))
    gates.sort()
    gates.append((LAP, float(XS[0]), float(YS[0]), "Meta"))
    return gates


GATES_NAMED = _gates()
GATES = [(s, x, y) for s, x, y, _ in GATES_NAMED]
GATE_NAMES = [n for *_, n in GATES_NAMED]
R = float(min(c["r"] for c in CORNERS))  # radio más cerrado (la horquilla)


# ------------------------------------------------------------- consultas

def lateral(x, y):
    """Desvío lateral d respecto a la línea central (+ = izquierda). Escalar o arreglo."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    _, i = _TREE.query(np.column_stack([x.ravel(), y.ravel()]))
    d = (x.ravel() - XS[i]) * _NX[i] + (y.ravel() - YS[i]) * _NY[i]
    return d.reshape(x.shape) if x.shape else float(d[0])


def project(x, y):
    """Proyecta un punto sobre la línea central: (s en [0, LAP), d, rumbo tangente)."""
    _, i = _TREE.query((x, y))
    dx, dy = x - XS[i], y - YS[i]
    along = dx * math.cos(HS[i]) + dy * math.sin(HS[i])
    d = dx * _NX[i] + dy * _NY[i]
    return float((SS[i] + along) % LAP), float(d), float(HS[i])


def project_many(x, y):
    """Versión vectorizada de project: devuelve arreglos (s, d)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    _, i = _TREE.query(np.column_stack([x.ravel(), y.ravel()]))
    dx, dy = x.ravel() - XS[i], y.ravel() - YS[i]
    s = (SS[i] + dx * np.cos(HS[i]) + dy * np.sin(HS[i])) % LAP
    d = dx * _NX[i] + dy * _NY[i]
    return s.reshape(x.shape), d.reshape(x.shape)


def _index(s):
    return int(np.searchsorted(SS, s % LAP, side="right") - 1)


def point_at(s):
    """Punto (x, y) de la línea central a la distancia s (con módulo LAP)."""
    i = _index(s)
    along = (s % LAP) - SS[i]
    return float(XS[i] + along * math.cos(HS[i])), float(YS[i] + along * math.sin(HS[i]))


def heading_at(s):
    return float(HS[_index(s)])


def curvature_at(s):
    """Curvatura con signo (1/m) en s: + izquierda, - derecha, 0 recta."""
    return float(KS[_index(s)])


def in_corner(s):
    return abs(curvature_at(s)) > 1e-9


def corner_name(s):
    return NAMES[_index(s)]


def in_obstacle(x, y):
    return np.zeros(np.shape(x), dtype=bool)


def outside_walls(x, y, half_width):
    """True más allá del muro: zona de escape superada o fuera del mapa."""
    beyond = abs_lateral_rapido(np.asarray(x, dtype=float), np.asarray(y, dtype=float)) > half_width + RUNOFF
    return beyond | (np.abs(x) >= MAP_X) | (np.abs(y) >= MAP_Y)


# ------------------------------------------------------------- grilla rápida
# Para los rayos se consulta |d| miles de veces por segundo. En vez del KD-tree
# se usa una grilla precalculada cada 0.25 m con interpolación bilineal.
GRID_RES = 0.25
_grid = None


def _cargar_grilla():
    global _grid
    import hashlib
    import os
    from pathlib import Path

    # La clave depende de la geometría ya muestreada: si cambia el trazado o el
    # algoritmo, cambia la clave y la grilla se recalcula.
    h = hashlib.sha1()
    for arr in (XS, YS, HS):
        h.update(np.ascontiguousarray(arr).tobytes())
    h.update(repr((GRID_RES, MAP_X, MAP_Y)).encode())
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "rally" / f"grilla-{h.hexdigest()[:16]}.npy"
    if cache.exists():
        try:
            _grid = np.load(cache)
            return _grid
        except (OSError, ValueError, EOFError):
            pass  # archivo dañado: se recalcula
    gx = np.arange(-MAP_X, MAP_X + GRID_RES, GRID_RES)
    gy = np.arange(-MAP_Y, MAP_Y + GRID_RES, GRID_RES)
    mx, my = np.meshgrid(gx, gy)
    _grid = np.abs(lateral(mx, my)).astype(np.float32)
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_name(f".{cache.stem}.{os.getpid()}.tmp.npy")
        np.save(tmp, _grid)
        os.replace(tmp, cache)  # escritura atómica: varios procesos pueden arrancar a la vez
    except OSError:
        pass
    return _grid


def abs_lateral_rapido(x, y):
    """|d| interpolado desde la grilla (error < 1 cm cerca de la pista)."""
    g = _grid if _grid is not None else _cargar_grilla()
    fx = (np.clip(x, -MAP_X, MAP_X - 1e-6) + MAP_X) / GRID_RES
    fy = (np.clip(y, -MAP_Y, MAP_Y - 1e-6) + MAP_Y) / GRID_RES
    ix, iy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    tx, ty = fx - ix, fy - iy
    return ((g[iy, ix] * (1 - tx) + g[iy, ix + 1] * tx) * (1 - ty)
            + (g[iy + 1, ix] * (1 - tx) + g[iy + 1, ix + 1] * tx) * ty)


def raycast(x, y, psi, angles, r_max, half_width, step=0.25, refine=7):
    """Distancia (m) de cada rayo al primer borde de pista o muro (r_max si no hay)."""
    origin_on = abs(float(lateral(x, y))) <= half_width

    def hits(px, py):
        d = abs_lateral_rapido(px, py)
        on = d <= half_width
        wall = (d > half_width + RUNOFF) | (np.abs(px) >= MAP_X) | (np.abs(py) >= MAP_Y)
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


_N_LARGO, _N_ANCHO = 9, 5  # puntos del contorno: cada 0.5 m en el largo, ~0.45 m en el ancho


def car_collides(x, y, psi, length, width, half_width):
    """True si algún punto del contorno del carro (muestreado cada ~0.5 m) pasa el muro."""
    lx = np.linspace(-length / 2, length / 2, _N_LARGO)
    ly = np.linspace(-width / 2, width / 2, _N_ANCHO)
    bx = np.concatenate([lx, lx, np.full(_N_ANCHO, -length / 2), np.full(_N_ANCHO, length / 2)])
    by = np.concatenate([np.full(_N_LARGO, -width / 2), np.full(_N_LARGO, width / 2), ly, ly])
    c, s = math.cos(psi), math.sin(psi)
    return bool(outside_walls(x + bx * c - by * s, y + bx * s + by * c, half_width).any())


def check_design(max_width=12.0):
    """Revisa el trazado: radios, rectas y separación entre tramos no vecinos."""
    report = {"largo": LAP, "radio_min": R, "curvas": len(VERTICES), "problemas": []}
    pts = np.column_stack([XS, YS])
    sep_min = max_width + 2 * RUNOFF + 2
    worst = (np.inf, None)
    for i in range(0, len(XS), 8):
        near = _TREE.query_ball_point(pts[i], sep_min)
        for j in near:
            gap = abs(SS[i] - SS[j])
            gap = min(gap, LAP - gap)
            if gap > 60:
                dist = float(np.hypot(*(pts[i] - pts[j])))
                if dist < worst[0]:
                    worst = (dist, (corner_name(SS[i]) or "recta", corner_name(SS[j]) or "recta"))
    if worst[1]:
        report["problemas"].append(
            f"Tramos a {worst[0]:.1f} m (< {sep_min:.0f} m): {worst[1][0]} / {worst[1][1]}")
    return report
