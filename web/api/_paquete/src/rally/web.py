"""Visor 3D (three.js) del ambiente: `rally web`.

El servidor corre los episodios con el ambiente de Python y le entrega al
navegador cada paso (posición, acción, rayos, recompensa...). El navegador solo
dibuja: la física y las reglas viven en el simulador.
"""

import json
import math
import mimetypes
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from rally import policies, track
from rally.env import RAY_ANGLES, RAYO_REF, AutonomousRallyEnv, RallyConfig

STATIC = Path(__file__).parent / "static"
VIVO = Path("runs/vivo")  # lo escribe el entrenamiento (rally pipeline ... --vivo)
console = Console()
mimetypes.add_type("application/javascript", ".js")


def _r(v, n=3):
    return round(float(v), n)


# Parámetros que se pueden variar por experimento: (mínimo, máximo, paso, base).
# Son los rangos de la ficha (docs/ambiente-v0.1.md, Variables y unidades).
RANGOS = {
    "ancho": (6.0, 12.0, 0.5, 8.0),  # track_width (m)
    "mu": (0.4, 1.0, 0.05, 0.9),  # adherencia del asfalto
    "a_max": (2.0, 6.0, 0.5, 4.0),  # m/s²
    "r_max": (10.0, 40.0, 1.0, 20.0),  # alcance de sensores (m)
}
CAMPO_CFG = {"ancho": "track_width", "mu": "mu", "a_max": "a_max", "r_max": "r_max"}
# Pistas que se pueden elegir en el visor. Las reservadas (la Sierra) no: correr modelos en
# ellas a voluntad las dejaría de ser una prueba (docs/experimentos/v6-pistas.md).
PISTAS_WEB = [n for n in track.PISTAS if n not in track.RESERVADAS]


class PistaNoDisponible(ValueError):
    """La pista no existe o está reservada para la prueba de generalización."""


def leer_pista(nombre):
    """Nombre de pista válido para el visor y la API (por defecto Mónaco)."""
    nombre = (nombre or "monaco").strip().lower()
    if nombre in track.RESERVADAS:
        raise PistaNoDisponible(f"La pista {nombre} está reservada para la prueba de generalización")
    if nombre not in PISTAS_WEB:
        raise PistaNoDisponible(f"Pista desconocida: {nombre}. Disponibles: {', '.join(PISTAS_WEB)}")
    return nombre
EXPERIMENTOS = []  # registro de la sesión (en memoria)


def leer_parametros(q):
    """Valida los parámetros del experimento y los recorta a los rangos de la ficha."""
    p = {}
    for k, (lo, hi, _, base) in RANGOS.items():
        try:
            p[k] = min(max(float(q.get(k, base)), lo), hi)
        except ValueError:
            p[k] = base
    return p


def datos_pista(pista="monaco"):
    cfg = RallyConfig()
    t = track.obtener(leer_pista(pista))
    centro = []
    s = 0.0
    while s < t.LAP:
        x, y = t.point_at(s)
        centro.append([_r(s, 2), _r(x), _r(y), _r(t.heading_at(s), 4),
                       _r(t.curvature_at(s), 4)])
        s += 0.5
    puertas = []
    n = len(t.GATES_NAMED)
    for i, (gs, gx, gy, curva) in enumerate(t.GATES_NAMED):
        puertas.append({"id": i + 1, "s": _r(gs), "x": gx, "y": gy,
                        "h": _r(t.heading_at(gs - 0.01), 4), "curva": curva,
                        "nombre": "META" if i == n - 1 else f"CP{i + 1}"})
    curvas = []
    for nombre, *_ in t.VERTICES:
        idx = [i for i, nm in enumerate(t.NAMES) if nm == nombre]
        mid = idx[len(idx) // 2]
        curvas.append({"nombre": nombre, "s": _r(t.SS[mid], 1),
                       "x": _r(t.XS[mid]), "y": _r(t.YS[mid]),
                       "radio": next(c["r"] for c in t.CORNERS if c["name"] == nombre)})
    return {
        "pista": t.nombre,
        "titulo": t.titulo,
        "descripcion": t.descripcion,
        "pistas": [{"nombre": n, "titulo": track.PISTAS[n].titulo, "descripcion": track.PISTAS[n].descripcion,
                    "largo": _r(track.PISTAS[n].LAP, 0)} for n in PISTAS_WEB],
        "largo": _r(t.LAP),
        "ancho": cfg.track_width,
        "escape": t.RUNOFF,
        "radio": t.R,
        "curvas": curvas,
        "mapa": [t.MAP_X, t.MAP_Y],
        "centro": centro,
        "puertas": puertas,
        "bloques": [list(o) for o in t.OBSTACLES],
        "carro": {"largo": cfg.car_length, "ancho": cfg.car_width, "ejes": cfg.wheelbase},
        "rayos": {"angulos": [_r(a, 4) for a in RAY_ANGLES], "alcance": cfg.r_max},
        "pilotos": {k: v[0] for k, v in policies.POLITICAS.items() if policies.disponible(k)},
        "dt": cfg.dt,
        "max_t": cfg.max_steps * cfg.dt,
        "delta_max": math.radians(cfg.delta_max_deg),
        "rangos": {k: {"min": lo, "max": hi, "paso": st, "base": b}
                   for k, (lo, hi, st, b) in RANGOS.items()},
    }


def correr_episodio(piloto="experto", semilla=0, politica=None, pista="monaco", **params):
    params = leer_parametros(params)
    pista = leer_pista(pista)
    env = AutonomousRallyEnv(**{CAMPO_CFG[k]: v for k, v in params.items()}, pista=pista)
    pol = politica or policies.crear(piloto, semilla)
    obs, info = env.reset(seed=semilla)
    total = 0.0
    frames = []

    def frame(obs, info, accion, r):
        return {
            "t": _r(info["t"], 2), "x": _r(info["x"]), "y": _r(info["y"]),
            "psi": _r(info["psi"], 4), "v": _r(info["v"]), "d": _r(info["d"]),
            "s": _r(max(info["s_best"], 0), 2), "cp": info["next_cp"],
            "agarre": _r(info["grip_use"]), "derrape": bool(info["skidding"]),
            "fuera": _r(info["off_steps"] * env.cfg.dt, 2),
            "rayos": [_r(v) for v in np.asarray(obs[6:13]) * RAYO_REF],
            "a": [_r(accion[0]), _r(accion[1])], "r": _r(r), "R": _r(total, 2),
            "fin": info["outcome"],
        }

    frames.append(frame(obs, info, (0.0, 0.0), 0.0))
    done = False
    while not done:
        accion = pol(obs, info)
        obs, r, term, trunc, info = env.step(accion)
        total += r
        frames.append(frame(obs, info, accion, r))
        done = term or trunc
    return {
        "piloto": piloto, "semilla": semilla, "params": params, "pista": pista,
        "modo": "evaluacion" if piloto in policies.MODELOS else "aleatorio" if piloto == "aleatoria" else "referencia",
        "resultado": info["outcome"], "tiempo": _r(info["t"], 2), "recompensa": _r(total, 2),
        "salidas": info["off_track_events"],
        "progreso": _r(max(info["s_best"], 0) / track.largo(info) * 100, 1),
        "frames": frames,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def log_message(self, fmt, *args):  # silencio: registramos solo los episodios
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, data, estado=200):
        body = json.dumps(data, separators=(",", ":")).encode()
        self.send_response(estado)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path in ("/api/pista", "/api/episodio"):   # la página misma se sirve con cualquier ?pista=
            try:
                pista = leer_pista(q.get("pista"))
            except PistaNoDisponible as e:
                return self._json({"detail": str(e)}, 403 if q.get("pista", "").lower() in track.RESERVADAS else 404)
        if url.path == "/api/pista":
            return self._json(datos_pista(pista))
        if url.path == "/api/episodio":
            piloto = q.get("piloto", "experto")
            if piloto not in policies.POLITICAS:
                self.send_error(400, "piloto desconocido")
                return
            try:
                semilla = int(q.get("semilla", 0))
            except ValueError:
                semilla = 0
            t0 = time.perf_counter()
            ep = correr_episodio(piloto, semilla, pista=pista, **{k: q[k] for k in RANGOS if k in q})
            ms = (time.perf_counter() - t0) * 1000
            p = ep["params"]
            ep["id"] = len(EXPERIMENTOS) + 1
            EXPERIMENTOS.append({k: v for k, v in ep.items() if k != "frames"})
            color = "green" if ep["resultado"] == "exito" else "red"
            console.print(
                f"[grey50]#{ep['id']:<3d}{time.strftime('%H:%M:%S')}[/]  [bold]{piloto:9s}[/] {pista:7s} "
                f"μ={p['mu']:.2f} ancho={p['ancho']:4.1f} m a={p['a_max']:.1f} sensor={p['r_max']:2.0f} m "
                f"semilla {semilla:<4d}→ [bold {color}]{ep['resultado']:9s}[/] {ep['tiempo']:5.1f} s  "
                f"recompensa {ep['recompensa']:+7.1f}  [grey50]({ms:.0f} ms)[/]"
            )
            return self._json(ep)
        if url.path == "/api/experimentos":
            return self._json(EXPERIMENTOS)
        if url.path in ("/api/vivo/curva", "/api/vivo/episodio"):
            archivo = VIVO / ("curva.json" if url.path.endswith("curva") else "episodio.json")
            if not archivo.exists():
                return self._json({"activo": False})
            body = archivo.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return None
        return super().do_GET()


def servir(puerto=8765, host="127.0.0.1"):
    try:
        server = ThreadingHTTPServer((host, puerto), partial(Handler))
    except OSError:
        console.print(f"[bold yellow]El puerto {puerto} ya está en uso.[/] Puede que ya haya un visor "
                      f"abierto en http://localhost:{puerto}. Usa otro con: [bold]rally web --puerto 8766[/]")
        return 1
    url = f"http://localhost:{puerto}"
    t = Text()
    t.append("AUTONOMOUS RALLY · visor 3D\n\n", style="bold bright_white")
    t.append("Abierto en  ", style="grey70")
    t.append(url + "\n\n", style="bold bright_cyan underline")
    t.append("Dentro de VS Code: ", style="grey70")
    t.append("Ctrl+Shift+P → Simple Browser: Show → " + url + "\n", style="bold")
    t.append("La física corre aquí en Python; el navegador solo dibuja.\n", style="grey62")
    t.append("Ctrl+C para detener.", style="grey50")
    console.print(Panel(t, border_style="bright_blue", padding=(1, 3)))
    console.print("[bold]Episodios[/]")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Servidor detenido.[/]")
    finally:
        server.server_close()
    return 0
