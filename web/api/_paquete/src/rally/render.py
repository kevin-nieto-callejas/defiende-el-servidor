"""Dibujo del ambiente en la terminal con colores (rich).

Cada carácter "▀" muestra dos píxeles: el de arriba con el color de letra y el
de abajo con el color de fondo. Así los píxeles quedan casi cuadrados.
Solo dibuja el estado del simulador: física ≠ decoración.
"""

import math

import numpy as np
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from rally import track
from rally.env import RAY_ANGLES

C = {
    "muro": (203, 213, 225),
    "ciudad1": (51, 49, 56),
    "ciudad2": (61, 58, 66),
    "cesped1": (86, 135, 52),
    "cesped2": (98, 148, 60),
    "asfalto": (58, 61, 66),
    "linea": (92, 96, 104),
    "pianito_r": (220, 38, 38),
    "pianito_b": (240, 240, 240),
    "bloque": (156, 163, 175),
    "puerta": (56, 189, 248),
    "puerta_sig": (250, 204, 21),
    "puerta_ok": (30, 64, 105),
    "meta_n": (20, 20, 20),
    "meta_b": (245, 245, 245),
    "estela": (192, 132, 252),
    "rayo": (125, 211, 252),
    "rayo_fin": (52, 211, 153),
    "carro": (249, 115, 22),
    "carro_frente": (254, 240, 138),
}

HUD_WIDTH = 46


def _hex(c):
    return "#%02x%02x%02x" % c


class TrackRenderer:
    def __init__(self, env, scale=1.0):
        self.env = env
        self.cfg = env.unwrapped.cfg
        self.scale = scale
        self.cols = int(round(2 * track.MAP_X * scale))
        self.prows = int(round(2 * track.MAP_Y * scale))
        self.prows += self.prows % 2  # número par de píxeles verticales
        self.trail = []
        self._bg = self._background()

    # ------------------------------------------------------------- fondo
    def _pixel_centers(self):
        xs = -track.MAP_X + (np.arange(self.cols) + 0.5) / self.scale
        ys = track.MAP_Y - (np.arange(self.prows) + 0.5) / self.scale
        return np.meshgrid(xs, ys)

    def _background(self):
        gx, gy = self._pixel_centers()
        hw = self.cfg.track_width / 2
        px = 1 / self.scale
        img = np.zeros(gx.shape + (3,), dtype=np.uint8)

        # Ciudad alrededor (manzanas), escape verde y muro del circuito urbano
        manzana = ((np.floor(gx / 14) + np.floor(gy / 14)) % 2).astype(bool)
        img[:] = C["ciudad1"]
        img[manzana] = C["ciudad2"]

        s, d = track.project_many(gx, gy)
        escape = np.abs(d) <= hw + track.RUNOFF
        stripes = (np.floor(s / 6) % 2).astype(bool)
        img[escape] = C["cesped1"]
        img[escape & stripes] = C["cesped2"]
        muro = (np.abs(d) > hw + track.RUNOFF) & (np.abs(d) <= hw + track.RUNOFF + max(0.8, px))
        img[muro] = C["muro"]
        on = np.abs(d) <= hw
        img[on] = C["asfalto"]
        curb = on & (np.abs(d) > hw - max(0.8, px))
        red = (np.floor(s / 2.0) % 2).astype(bool)
        img[curb & red] = C["pianito_r"]
        img[curb & ~red] = C["pianito_b"]

        center = on & (np.abs(d) <= px / 2 + 1e-6) & ((np.floor(s / 3.0) % 2) == 0)
        img[center] = C["linea"]

        self._gate_mask = []
        for i, (gs, _, _) in enumerate(track.GATES):
            ds = np.abs((s - gs + track.LAP / 2) % track.LAP - track.LAP / 2)
            mask = on & (ds < max(0.6, px * 0.75))
            self._gate_mask.append(mask)
            if i == len(track.GATES) - 1:  # meta a cuadros
                chk = ((np.floor(d / 1.0) + np.floor(s / 1.0)) % 2).astype(bool)
                meta = on & (ds < max(1.0, px))
                img[meta & chk] = C["meta_n"]
                img[meta & ~chk] = C["meta_b"]

        self._gx, self._gy = gx, gy
        return img

    # ------------------------------------------------------------- frame
    def _to_pixel(self, x, y):
        c = int((x + track.MAP_X) * self.scale)
        r = int((track.MAP_Y - y) * self.scale)
        if 0 <= c < self.cols and 0 <= r < self.prows:
            return r, c
        return None

    def reset_trail(self):
        self.trail = []

    def add_trail(self, info):
        """Guarda la posición; rellena el tramo desde la anterior para que la estela sea continua."""
        x, y = info["x"], info["y"]
        if self.trail:
            px, py = self.trail[-1]
            n = int(math.hypot(x - px, y - py) * self.scale * 2)
            for k in range(1, n):
                self.trail.append((px + (x - px) * k / n, py + (y - py) * k / n))
        self.trail.append((x, y))

    def map_text(self, info, obs=None):
        img = self._bg.copy()
        next_cp = info["next_cp"]
        for i, mask in enumerate(self._gate_mask[:-1]):
            color = C["puerta_ok"] if i + 1 < next_cp else (
                C["puerta_sig"] if i + 1 == next_cp else C["puerta"])
            img[mask] = color

        for x, y in self.trail[-2000:]:
            p = self._to_pixel(x, y)
            if p and tuple(img[p]) != C["bloque"]:
                img[p] = C["estela"]

        # Rayos de los sensores (los mismos que observa el agente)
        if obs is not None:
            rays = np.asarray(obs[6:13]) * self.cfg.r_max
            for a, dist in zip(RAY_ANGLES, rays):
                ang = info["psi"] + a
                for t in np.arange(1.2, dist, 0.6 / self.scale):
                    p = self._to_pixel(info["x"] + t * math.cos(ang), info["y"] + t * math.sin(ang))
                    if p:
                        img[p] = C["rayo"]
                if dist < self.cfg.r_max:
                    p = self._to_pixel(info["x"] + dist * math.cos(ang),
                                       info["y"] + dist * math.sin(ang))
                    if p:
                        img[p] = C["rayo_fin"]

        # Carro: rectángulo orientado (inflado medio píxel para que siempre se vea)
        cs, sn = math.cos(info["psi"]), math.sin(info["psi"])
        pad = 0.5 / self.scale
        L, W = self.cfg.car_length / 2 + pad, self.cfg.car_width / 2 + pad
        rx, ry = self._gx - info["x"], self._gy - info["y"]
        lx, ly = rx * cs + ry * sn, -rx * sn + ry * cs
        body = (np.abs(lx) <= L) & (np.abs(ly) <= W)
        img[body] = C["carro"]
        img[body & (lx > L * 0.45)] = C["carro_frente"]
        p = self._to_pixel(info["x"], info["y"])
        if p and not body.any():
            img[p] = C["carro"]

        return self._image_to_text(img)

    def _image_to_text(self, img):
        text = Text(no_wrap=True, overflow="crop")
        for r in range(0, self.prows, 2):
            top, bot = img[r], img[r + 1]
            run, prev = 0, None
            for c in range(self.cols):
                key = (tuple(top[c]), tuple(bot[c]))
                if key != prev and run:
                    text.append("▀" * run, style=f"{_hex(prev[0])} on {_hex(prev[1])}")
                    run = 0
                prev = key
                run += 1
            text.append("▀" * run, style=f"{_hex(prev[0])} on {_hex(prev[1])}")
            if r + 2 < self.prows:
                text.append("\n")
        return text


# ------------------------------------------------------------------ SVG

def svg_mapa(ancho=8.0, escala=3.0):
    """Mapa del circuito en SVG, generado desde la geometría real del ambiente."""
    mx, my = track.MAP_X, track.MAP_Y
    W, H = 2 * mx * escala, 2 * my * escala
    X = lambda x: (x + mx) * escala  # noqa: E731
    Y = lambda y: (my - y) * escala  # noqa: E731
    pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in zip(track.XS[::4], track.YS[::4]))
    poly = lambda color, w, extra="": (  # noqa: E731
        f'<polygon points="{pts}" fill="none" stroke="{color}" stroke-width="{w:.1f}" '
        f'stroke-linejoin="round" {extra}/>')
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H + 70:.0f}" '
         f'font-family="Segoe UI, Helvetica, Arial, sans-serif">',
         f'<rect width="{W:.0f}" height="{H + 70:.0f}" fill="#3b3a40"/>',
         f'<text x="16" y="28" font-size="20" font-weight="700" fill="#fff">Autonomous Rally · '
         f'Circuito inspirado en Mónaco · {track.LAP:.0f} m</text>',
         poly("#e5e7eb", (ancho + 2 * track.RUNOFF + 1) * escala),
         poly("#5b9a3c", (ancho + 2 * track.RUNOFF) * escala),
         poly("#2b2d31", ancho * escala),
         poly("#d4d4d8", 1.2, 'stroke-dasharray="8 8"')]
    for k, c in enumerate(track.CORNERS):
        idx = [i for i, n in enumerate(track.NAMES) if n == c["name"]]
        i = idx[len(idx) // 2]
        dy = -12 if k % 2 == 0 else 20  # alterna arriba/abajo para que no se monten
        o.append(f'<text x="{X(track.XS[i]):.0f}" y="{Y(track.YS[i]) + dy:.0f}" font-size="12" '
                 f'fill="#fde68a" text-anchor="middle">{c["name"]} · r {c["r"]:g} m</text>')
    for i, (s, x, y, n) in enumerate(track.GATES_NAMED):
        h = track.heading_at(s - 0.01)
        nx, ny = -math.sin(h) * ancho / 2, math.cos(h) * ancho / 2
        meta = i == len(track.GATES_NAMED) - 1
        color = "#f97316" if meta else "#22d3ee"
        etiqueta = "SALIDA / META" if meta else f"CP{i + 1}"
        o.append(f'<line x1="{X(x + nx):.1f}" y1="{Y(y + ny):.1f}" x2="{X(x - nx):.1f}" '
                 f'y2="{Y(y - ny):.1f}" stroke="{color}" stroke-width="5"/>')
        o.append(f'<text x="{X(x) + 10:.0f}" y="{Y(y) + 22:.0f}" font-size="14" font-weight="700" '
                 f'fill="{color}">{etiqueta} · s={s:.0f} m</text>')
    # Flecha de sentido en la salida y escala
    h = track.HS[40]
    x0, y0 = X(track.XS[40]), Y(track.YS[40])
    o.append(f'<path d="M {x0:.1f} {y0:.1f} l {28 * math.cos(h):.1f} {-28 * math.sin(h):.1f}" '
             f'stroke="#fff" stroke-width="3" marker-end="url(#f)"/>')
    o.insert(1, '<defs><marker id="f" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" '
                'markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
                'fill="#fff"/></marker></defs>')
    sx = 16
    o.append(f'<line x1="{sx}" y1="{H + 40:.0f}" x2="{sx + 50 * escala:.0f}" y2="{H + 40:.0f}" '
             f'stroke="#fff" stroke-width="3"/>')
    o.append(f'<text x="{sx}" y="{H + 60:.0f}" font-size="13" fill="#fff">50 m · ancho de pista '
             f'{ancho:g} m · escape {track.RUNOFF:g} m · muro a {ancho / 2 + track.RUNOFF:g} m del '
             f'centro · sentido antihorario · origen (0,0) en el centro del mapa</text>')
    o.append("</svg>")
    return "\n".join(o)


# ------------------------------------------------------------------ HUD

def bar(value, width=20, color="cyan", lo=0.0, hi=1.0):
    frac = 0.0 if hi == lo else (min(max(value, lo), hi) - lo) / (hi - lo)
    full = frac * width
    n = int(full)
    parts = " ▏▎▍▌▋▊▉"
    rem = parts[int((full - n) * 8)] if n < width else ""
    t = Text("█" * n + rem, style=color)
    t.append(" " * (width - n - len(rem)), style="on grey19")
    return t


def bipolar(value, width=21, pos="green", neg="red"):
    half = width // 2
    v = max(-1.0, min(1.0, value))
    n = int(round(abs(v) * half))
    left = " " * (half - n) + ("█" * n if v < 0 else "")
    right = ("█" * n if v > 0 else "") + " " * (half - n)
    t = Text(left[:half].rjust(half), style=f"{neg} on grey19")
    t.append("│", style="bold white")
    t.append(right[:half].ljust(half), style=f"{pos} on grey19")
    return t


def hud(info, obs, action, reward, total, politica, mu, cfg, paso):
    tbl = Table.grid(padding=(0, 1))
    tbl.add_column(style="bold grey70", width=11)
    tbl.add_column(width=HUD_WIDTH - 15)

    piso = "[bold cyan]SECO[/]" if mu >= 0.75 else "[bold blue]MOJADO[/]"
    tbl.add_row("Piloto", Text.from_markup(f"[bold]{politica}[/]"))
    tbl.add_row("Piso", Text.from_markup(f"{piso}  μ={mu:.2f}"))
    tbl.add_row("Tiempo", Text.from_markup(
        f"[bold]{info['t']:5.1f}[/] s / {cfg.max_steps * cfg.dt:.0f} s  · paso {paso}"))

    kmh = info["v"] * 3.6
    t = bar(info["v"], 18, "bold bright_cyan", 0, cfg.v_max)
    t.append(f" {info['v']:4.1f} m/s", style="bold")
    tbl.add_row("Velocidad", t)
    tbl.add_row("", Text(f"{kmh:5.1f} km/h", style="grey62"))

    if action is not None:
        a = bipolar(float(action[0]), 19, "bright_green", "bright_red")
        a.append(" acel" if action[0] >= 0 else " freno", style="grey62")
        tbl.add_row("Pedal", a)
        dtext = bipolar(-float(action[1]), 19, "bright_magenta", "bright_magenta")
        dtext.append(" izq" if action[1] > 0.02 else (" der" if action[1] < -0.02 else " —"),
                     style="grey62")
        tbl.add_row("Dirección", dtext)

    gu = info.get("grip_use", 0.0)
    gcolor = "bright_red" if info.get("skidding") else ("yellow" if gu > 0.8 else "green")
    g = bar(gu, 18, gcolor, 0, 1)
    g.append(" DERRAPE" if info.get("skidding") else f" {gu * 100:3.0f}%",
             style="bold bright_red" if info.get("skidding") else "")
    tbl.add_row("Agarre", g)

    hw = cfg.track_width / 2
    dv = info["d"] / hw
    dcol = "bright_red" if abs(dv) > 1 else "bright_white"
    dt = bipolar(-dv / 2, 19, dcol, dcol)
    dt.append(f" {info['d']:+.1f} m", style="bold bright_red" if abs(dv) > 1 else "")
    tbl.add_row("Desvío", dt)

    if obs is not None:
        blocks = " ▁▂▃▄▅▆▇█"
        rays = Text()
        for v in obs[6:13][::-1]:  # izquierda -> derecha en pantalla
            k = int(round(float(v) * 8))
            col = "bright_red" if v < 0.15 else ("yellow" if v < 0.35 else "bright_cyan")
            rays.append(blocks[k] * 2 + " ", style=col)
        tbl.add_row("Sensores", rays)
        tbl.add_row("", Text("izq ←  7 rayos  → der", style="grey50"))

    # Checkpoints y progreso de la vuelta
    cps = Text()
    n_gates = len(track.GATES)
    for i in range(1, n_gates + 1):
        n = "META" if i == n_gates else str(i)
        if i < info["next_cp"]:
            cps.append(f"✔{n} ", style="bold green")
        elif i == info["next_cp"]:
            cps.append(f"▶{n} ", style="bold black on yellow")
            cps.append(" ")
        else:
            cps.append(f"{n} ", style="grey50")
    tbl.add_row("Checkpoints", cps)
    prog = max(0.0, info["s_best"]) / track.LAP
    p = bar(prog, 18, "bold green", 0, 1)
    p.append(f" {prog * 100:3.0f}%", style="bold")
    tbl.add_row("Vuelta", p)

    rcol = "bright_green" if reward >= 0 else "bright_red"
    tbl.add_row("Recompensa", Text.from_markup(
        f"paso [{rcol}]{reward:+7.2f}[/]  total [bold {'green' if total >= 0 else 'red'}]{total:+7.1f}[/]"))

    estado = _estado(info, cfg)
    tbl.add_row("Estado", estado)
    return Panel(tbl, title="[bold]AUTONOMOUS RALLY[/]", border_style="bright_blue",
                 width=HUD_WIDTH, subtitle="[grey50]Ctrl+C para salir[/]")


def _estado(info, cfg):
    out = info.get("outcome")
    if out == "exito":
        return Text("🏁 ¡VUELTA COMPLETA!", style="bold black on bright_green")
    if out == "choque":
        return Text("💥 CHOQUE", style="bold white on red")
    if out == "salida":
        return Text("✖ SE SALIÓ DE LA PISTA", style="bold white on red")
    if out == "estancado":
        return Text("⏸ ESTANCADO", style="bold black on yellow")
    if out == "tiempo":
        return Text("⏱ SE ACABÓ EL TIEMPO", style="bold black on yellow")
    if abs(info["d"]) > cfg.track_width / 2:
        return Text(f"⚠ EN EL CÉSPED {info['off_steps'] * cfg.dt:.1f}/1.0 s",
                    style="bold black on yellow")
    return Text("● EN PISTA", style="bold green")


def leyenda():
    def sw(c, label):
        t = Text("██", style=_hex(c))
        t.append(f" {label}  ", style="grey70")
        return t

    t = Text()
    for c, label in [
        (C["carro"], "carro"), (C["estela"], "estela"), (C["rayo_fin"], "sensor"),
        (C["puerta_sig"], "próximo CP"), (C["puerta"], "CP"), (C["bloque"], "bloque"),
        (C["pianito_r"], "borde"),
    ]:
        t.append_text(sw(c, label))
    return t


def resumen(info, total, politica, mu):
    out = info["outcome"]
    ok = out == "exito"
    titulo = {
        "exito": "🏁 VUELTA COMPLETA",
        "choque": "💥 CHOQUE",
        "salida": "✖ SALIDA DE PISTA",
        "estancado": "⏸ ESTANCADO",
        "tiempo": "⏱ TIEMPO AGOTADO",
    }.get(out, str(out))
    tbl = Table.grid(padding=(0, 2))
    tbl.add_column(style="bold grey70")
    tbl.add_column()
    tbl.add_row("Piloto", politica)
    tbl.add_row("Piso", f"{'seco' if mu >= 0.75 else 'mojado'} (μ={mu:.2f})")
    tbl.add_row("Tiempo", f"{info['t']:.1f} s" + (" (tiempo de vuelta)" if ok else ""))
    tbl.add_row("Progreso", f"{max(0, info['s_best']):.1f} / {track.LAP:.1f} m "
                            f"({max(0, info['s_best']) / track.LAP * 100:.0f}%)")
    tbl.add_row("Salidas de pista", str(info["off_track_events"]))
    tbl.add_row("Recompensa total", Text(f"{total:+.2f}", style="bold green" if total >= 0 else "bold red"))
    return Panel(tbl, title=f"[bold]{titulo}[/]",
                 border_style="green" if ok else "red", expand=False)


def frame(renderer, info, obs, action, reward, total, politica, mu, paso, lado_a_lado):
    mapa = renderer.map_text(info, obs)
    panel = hud(info, obs, action, reward, total, politica, mu, renderer.cfg, paso)
    if lado_a_lado:
        grid = Table.grid(padding=(0, 1))
        grid.add_column()
        grid.add_column()
        grid.add_row(Group(mapa, leyenda()), panel)
        return grid
    return Group(mapa, leyenda(), panel)
