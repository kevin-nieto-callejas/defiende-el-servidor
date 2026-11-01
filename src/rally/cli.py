"""Línea de comandos de Autonomous Rally.

    rally ver            ver un episodio en vivo en la terminal
    rally evaluar        métricas de la ficha (seco vs. mojado)
    rally transiciones   comparar las 5 transiciones de la ficha con el ambiente
    rally mapa           dibujar la pista
    rally web            visor 3D en el navegador (three.js)
"""

import argparse
import sys
import time

import numpy as np
from rich import box
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from rally import policies, render, track
from rally.env import AutonomousRallyEnv
from rally.transitions import TRANSICIONES, ejecutar

console = Console()
MU_SECO, MU_MOJADO = 0.9, 0.5
HUD_ALTO = 22


def banner():
    t = Text()
    t.append("A U T O N O M O U S   R A L L Y\n", style="bold bright_white")
    t.append("MLOps Autonomous Lab · ambiente Gymnasium AutonomousRally-v0", style="grey62")
    return Panel(Align.center(t), border_style="bright_blue", box=box.HEAVY, padding=(0, 2))


# ----------------------------------------------------------------- layout

def _layout(escala):
    w, h = console.size
    if escala:
        lado = w >= escala * 100 + render.HUD_WIDTH + 2
        return escala, lado
    mapa_w = 2 * track.MAP_X
    mapa_h = 2 * track.MAP_Y / 2  # filas de texto por metro (2 píxeles por fila)
    lado = min((w - render.HUD_WIDTH - 2) / mapa_w, (h - 3) / mapa_h)
    arriba = min((w - 1) / mapa_w, (h - HUD_ALTO - 3) / mapa_h)
    sc = max(lado, arriba)
    sc = float(np.clip(sc, 0.12, 1.6))
    return sc, lado >= arriba


# -------------------------------------------------------------------- ver

def cmd_ver(args):
    mu = MU_MOJADO if args.lluvia else args.mu
    env = AutonomousRallyEnv(mu=mu)
    escala, lado = _layout(args.escala)
    rnd = render.TrackRenderer(env, escala)
    nombre = args.piloto
    resultados = []

    try:
        for ep in range(args.episodios):
            seed = args.semilla + ep
            pol = policies.crear(nombre, seed)
            obs, info = env.reset(seed=seed)
            rnd.reset_trail()
            rnd.add_trail(info)
            total, reward, action, paso, done = 0.0, 0.0, None, 0, False
            fps = 10 * args.velocidad
            pasos_por_frame = max(1, int(round(fps / 30)))
            pausa = pasos_por_frame / fps

            def dibujar():
                return render.frame(rnd, info, obs, action, reward, total,
                                    f"{nombre} · ep {ep + 1}/{args.episodios}", mu, paso, lado)

            if args.sin_animacion:
                while not done:
                    action = pol(obs, info)
                    obs, reward, term, trunc, info = env.step(action)
                    rnd.add_trail(info)
                    total += reward
                    paso += 1
                    done = term or trunc
            else:
                with Live(dibujar(), console=console, screen=True, auto_refresh=False) as live:
                    t_next = time.perf_counter()
                    while not done:
                        for _ in range(pasos_por_frame):
                            action = pol(obs, info)
                            obs, reward, term, trunc, info = env.step(action)
                            rnd.add_trail(info)
                            total += reward
                            paso += 1
                            done = term or trunc
                            if done:
                                break
                        live.update(dibujar(), refresh=True)
                        t_next += pausa
                        time.sleep(max(0.0, t_next - time.perf_counter()))
                    time.sleep(1.5)

            console.print(dibujar())
            console.print(render.resumen(info, total, nombre, mu))
            resultados.append((info, total))
    except KeyboardInterrupt:
        console.print("[yellow]Interrumpido.[/]")
        return 130

    if len(resultados) > 1:
        ok = sum(i["outcome"] == "exito" for i, _ in resultados)
        console.print(f"[bold]{ok}/{len(resultados)}[/] vueltas completas.")
    return 0


# ---------------------------------------------------------------- evaluar

def correr_episodios(nombre, mu, episodios, semilla, progress=None, task=None):
    env = AutonomousRallyEnv(mu=mu)
    filas = []
    for i in range(episodios):
        seed = semilla + i
        pol = policies.crear(nombre, seed)
        obs, info = env.reset(seed=seed)
        total, done = 0.0, False
        while not done:
            obs, r, term, trunc, info = env.step(pol(obs, info))
            total += r
            done = term or trunc
        filas.append({
            "outcome": info["outcome"],
            "t": info["t"],
            "incidentes": info["off_track_events"] + (info["outcome"] == "choque"),
            "retorno": total,
        })
        if progress is not None:
            progress.advance(task)
    return filas


def metricas(filas):
    exitos = [f for f in filas if f["outcome"] == "exito"]
    tiempos = np.array([f["t"] for f in exitos])
    return {
        "tasa": 100 * len(exitos) / len(filas),
        "t_med": float(np.median(tiempos)) if len(tiempos) else float("nan"),
        "t_p90": float(np.percentile(tiempos, 90)) if len(tiempos) else float("nan"),
        "incidentes": float(np.mean([f["incidentes"] for f in filas])),
        "retorno": float(np.mean([f["retorno"] for f in filas])),
        "fines": {k: sum(f["outcome"] == k for f in filas)
                  for k in ("exito", "salida", "choque", "estancado", "tiempo")},
    }


def cmd_evaluar(args):
    condiciones = {"seco": MU_SECO, "mojado": MU_MOJADO}
    conds = [c for c in args.condiciones]
    res = {}
    with Progress(TextColumn("[bold]{task.description}"), BarColumn(), MofNCompleteColumn(),
                  TimeElapsedColumn(), console=console, transient=True) as progress:
        for p in args.pilotos:
            for c in conds:
                task = progress.add_task(f"{p} · {c}", total=args.episodios)
                res[(p, c)] = metricas(correr_episodios(
                    p, condiciones[c], args.episodios, args.semilla, progress, task))

    tbl = Table(title=f"Evaluación · {args.episodios} episodios por fila · semillas "
                      f"{args.semilla}–{args.semilla + args.episodios - 1}",
                box=box.ROUNDED, header_style="bold bright_cyan", title_style="bold")
    for col, j in [("Piloto", "left"), ("Piso", "left"), ("① Vueltas completas", "right"),
                   ("② Tiempo mediano", "right"), ("p90", "right"),
                   ("③ Incidentes/ep", "right"), ("Recompensa media", "right"),
                   ("Fines", "left")]:
        tbl.add_column(col, justify=j)
    for (p, c), m in res.items():
        tasa_col = "green" if m["tasa"] >= 90 else ("yellow" if m["tasa"] >= 50 else "red")
        fines = " ".join(f"{k}:{v}" for k, v in m["fines"].items() if v)
        tbl.add_row(
            p, ("☀ " if c == "seco" else "☂ ") + c,
            f"[{tasa_col}]{m['tasa']:.0f} %[/]",
            "—" if np.isnan(m["t_med"]) else f"{m['t_med']:.1f} s",
            "—" if np.isnan(m["t_p90"]) else f"{m['t_p90']:.1f} s",
            f"{m['incidentes']:.2f}",
            f"{m['retorno']:+.1f}",
            fines,
        )
    console.print(tbl)

    if len(args.pilotos) >= 2 and set(conds) == {"seco", "mojado"}:
        veredicto(res, args.pilotos[0], args.pilotos[1])
    return 0


def veredicto(res, base, cand):
    """Criterio de aceptación de la ficha (sección Métricas e incidente)."""
    bs, bm = res[(base, "seco")], res[(base, "mojado")]
    cs, cm = res[(cand, "seco")], res[(cand, "mojado")]
    dt = (cs["t_med"] / bs["t_med"] - 1) * 100 if bs["t_med"] == bs["t_med"] else float("nan")
    criterios = [
        (f"En mojado completa más vueltas que {base}",
         f"{cm['tasa']:.0f} % vs {bm['tasa']:.0f} %", cm["tasa"] > bm["tasa"]),
        ("En seco no pierde más de 5 pp de vueltas",
         f"{cs['tasa'] - bs['tasa']:+.0f} pp", cs["tasa"] >= bs["tasa"] - 5),
        ("En seco el tiempo mediano no sube más de 5 %",
         f"{dt:+.1f} %", dt == dt and dt <= 5),
    ]
    t = Table.grid(padding=(0, 2))
    t.add_column()
    t.add_column()
    t.add_column(justify="right")
    for desc, val, ok in criterios:
        t.add_row("[bold green]✔[/]" if ok else "[bold red]✖[/]", desc, val)
    aceptado = all(ok for *_, ok in criterios)
    titulo = (f"[bold]Protocolo de la ficha · candidato [cyan]{cand}[/] vs base [cyan]{base}[/] → "
              + ("[bold black on green] ACEPTADO [/]" if aceptado else "[bold white on red] RECHAZADO [/]"))
    console.print(Panel(t, title=titulo, border_style="green" if aceptado else "red", expand=False))


# ---------------------------------------------------------- transiciones

def cmd_transiciones(args):
    env = AutonomousRallyEnv()
    tbl = Table(title="Ficha vs. ambiente (código)", box=box.ROUNDED,
                header_style="bold bright_cyan", title_style="bold")
    for col in ["", "Transición", "Acción", "Recompensa ficha", "Recompensa ambiente",
                "Velocidad", "Desvío", "Derrape", "Sig. CP", "Fin"]:
        tbl.add_column(col)
    todo_ok = True
    for tr in TRANSICIONES:
        _, r, info = ejecutar(env, tr)
        e = tr["esperado"]
        ok = (abs(r - e["recompensa"]) < 0.01 and info["next_cp"] == e["next_cp"]
              and info["outcome"] == e["fin"])
        todo_ok &= ok
        tbl.add_row(
            "[bold green]✔[/]" if ok else "[bold red]✖[/]",
            f"[bold]{tr['id']}[/] {tr['nombre']}",
            f"({tr['accion'][0]:+.2f}, {tr['accion'][1]:+.2f})",
            f"{e['recompensa']:+.3f}",
            f"[bold]{r:+.3f}[/]",
            f"{info['v']:.2f} m/s",
            f"{info['d']:+.2f} m",
            "[bold red]sí[/]" if info["skidding"] else "no",
            str(info["next_cp"]),
            info["outcome"] or "—",
        )
    console.print(tbl)
    console.print("[bold green]Las 5 transiciones coinciden con la ficha.[/]" if todo_ok
                  else "[bold red]Hay diferencias con la ficha.[/]")
    return 0 if todo_ok else 1


# ------------------------------------------------------------------- mapa

def cmd_mapa(args):
    env = AutonomousRallyEnv()
    if args.svg:
        with open(args.svg, "w", encoding="utf-8") as f:
            f.write(render.svg_mapa(env.cfg.track_width))
        console.print(f"[green]Mapa guardado en {args.svg}[/]")
        return 0
    escala, _ = _layout(args.escala)
    rnd = render.TrackRenderer(env, escala)
    obs, info = env.reset(seed=0)
    console.print(rnd.map_text(info, obs))
    console.print(render.leyenda())
    console.print(f"[grey62]Pista {track.LAP:.2f} m · ancho {env.cfg.track_width:.0f} m · "
                  f"{len(track.VERTICES)} curvas (la más cerrada de {track.R:.1f} m) · {len(track.GATES) - 1} checkpoints · 1 carácter = "
                  f"{1 / escala:.2f} m[/]")
    return 0


# ------------------------------------------------------------------- MLOps

def cmd_pipeline(args):
    import os

    from rally import pipeline

    vivo = args.vivo or os.environ.get("RALLY_VIVO") == "1"
    console.print(f"[bold bright_cyan]▶ Etapa: {args.etapa}[/]" + ("  [red]● en vivo[/]" if vivo else ""))
    etapas = {"datos": pipeline.etapa_datos, "evaluar": pipeline.etapa_evaluar,
              "registrar": pipeline.etapa_registrar,
              "qlearning": lambda: pipeline.etapa_qlearning(vivo),
              "ppo": lambda: pipeline.etapa_ppo(vivo),
              "generalizacion": lambda: __import__(
                  "rally.generalizacion", fromlist=["x"]).etapa_generalizacion()}
    etapas[args.etapa]()
    return 0


def cmd_publicar(args):
    from rally.publicar import publicar

    url, _ = publicar(args.repo, privado=not args.publico)
    console.print(f"[bold green]Modelo publicado:[/] [bright_cyan underline]{url}[/] "
                  f"({'público' if args.publico else 'privado'})")
    return 0


def cmd_sincronizar(args):
    from rally.sincronizar import sincronizar

    console.print("[bold]Copiando experimentos de MLflow a DagsHub…[/]")
    r = sincronizar(lambda m: console.print(m))
    if r:
        console.print(f"[bold green]{r['corridas_nuevas']} corridas y {r['modelos_nuevos']} versiones "
                      f"de modelo nuevas.[/] Ver: [bright_cyan underline]{r['url']}[/]")
    return 0


def cmd_mlflow(args):
    import subprocess

    from rally.agentes.seguimiento import TRACKING_URI

    console.print(f"[bold]MLflow[/] en [bright_cyan underline]http://localhost:{args.puerto}[/]  "
                  "(Ctrl+C para detener)")
    return subprocess.call(["mlflow", "ui", "--backend-store-uri", TRACKING_URI,
                            "--port", str(args.puerto), "--host", "127.0.0.1"])


# ------------------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(prog="rally", description="Autonomous Rally en la terminal.")
    sub = p.add_subparsers(dest="cmd")

    pilotos = list(policies.POLITICAS)
    v = sub.add_parser("ver", help="ver un episodio en vivo")
    v.add_argument("--piloto", choices=pilotos, default="experto")
    v.add_argument("--mu", type=float, default=MU_SECO, help="adherencia del asfalto")
    v.add_argument("--lluvia", action="store_true", help="atajo para --mu 0.5 (incidente)")
    v.add_argument("--semilla", type=int, default=0)
    v.add_argument("--episodios", type=int, default=1)
    v.add_argument("--velocidad", type=float, default=1.0, help="1 = tiempo real, 2 = doble…")
    v.add_argument("--escala", type=float, default=None, help="caracteres por metro (auto)")
    v.add_argument("--sin-animacion", action="store_true", help="solo el cuadro final")
    v.set_defaults(fn=cmd_ver)

    e = sub.add_parser("evaluar", help="métricas de la ficha sobre muchos episodios")
    e.add_argument("--pilotos", nargs="+", choices=pilotos, default=["experto", "prudente"])
    e.add_argument("--condiciones", nargs="+", choices=["seco", "mojado"],
                   default=["seco", "mojado"])
    e.add_argument("--episodios", type=int, default=100)
    e.add_argument("--semilla", type=int, default=0)
    e.set_defaults(fn=cmd_evaluar)

    t = sub.add_parser("transiciones", help="comparar las 5 transiciones de la ficha")
    t.set_defaults(fn=cmd_transiciones)

    m = sub.add_parser("mapa", help="dibujar la pista")
    m.add_argument("--escala", type=float, default=None)
    m.add_argument("--svg", metavar="ARCHIVO", help="guardar el mapa con medidas en SVG")
    m.set_defaults(fn=cmd_mapa)

    w = sub.add_parser("web", help="visor 3D en el navegador (three.js)")
    w.add_argument("--puerto", type=int, default=8765)
    w.set_defaults(fn=lambda a: __import__("rally.web", fromlist=["servir"]).servir(a.puerto))

    pl = sub.add_parser("pipeline", help="una etapa del pipeline de MLOps (la usa DVC)")
    pl.add_argument("etapa", choices=["datos", "qlearning", "ppo", "evaluar", "generalizacion",
                                      "registrar"])
    pl.add_argument("--vivo", action="store_true",
                    help="transmitir el entrenamiento al visor 3D (también con RALLY_VIVO=1)")
    pl.set_defaults(fn=cmd_pipeline)

    pu = sub.add_parser("publicar", help="subir el modelo PPO a Hugging Face Hub")
    pu.add_argument("--repo", required=True, help="usuario/nombre, p. ej. miguel/autonomous-rally-ppo")
    pu.add_argument("--publico", action="store_true", help="repositorio público (por defecto privado)")
    pu.set_defaults(fn=cmd_publicar)

    si = sub.add_parser("sincronizar", help="copiar los experimentos de MLflow a DagsHub")
    si.set_defaults(fn=cmd_sincronizar)

    ap = sub.add_parser("api", help="API de simulación para la web (FastAPI)")
    ap.add_argument("--puerto", type=int, default=8000)
    ap.set_defaults(fn=lambda args: (__import__("uvicorn").run("rally.api:app", host="0.0.0.0", port=args.puerto), 0)[1])

    ma = sub.add_parser("manifiesto", help="generar manifests/ desde las etiquetas de git")
    ma.set_defaults(fn=lambda args: (__import__("rally.manifiesto").manifiesto.generar(), 0)[1])

    ml = sub.add_parser("mlflow", help="abrir la interfaz de MLflow (experimentos y modelos)")
    ml.add_argument("--puerto", type=int, default=5001)
    ml.set_defaults(fn=cmd_mlflow)

    args = p.parse_args(argv)
    if not args.cmd:
        console.print(banner())
        p.print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
