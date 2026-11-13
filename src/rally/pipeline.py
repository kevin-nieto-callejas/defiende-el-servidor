"""Etapas del pipeline de MLOps (las ejecuta DVC según dvc.yaml).

    datos       → data/processed/demos.npz, data/processed/escenarios.json
    qlearning   → models/qlearning/   (registrado en MLflow como rally-qlearning)
    ppo         → models/ppo/         (registrado en MLflow como rally-ppo)
    evaluar     → metrics/evaluacion.json   (protocolo de la ficha: seco vs. mojado)
    registrar   → metrics/registro.json     (alias champion/challenger en MLflow)

Cada etapa lee sus parámetros de params.yaml, así DVC sabe qué rehacer cuando
cambia un parámetro, el código o los datos.

Con `vehiculo="moto"` (`rally pipeline <etapa> --vehiculo moto`) las mismas etapas trabajan con
la moto MotoGP: leen la sección `moto:` de params.yaml encima de la del carro y escriben en
data/processed/moto/, models/moto/ y metrics/moto/, con su propio experimento de MLflow.
"""

import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import mlflow
import numpy as np
import yaml

from rally import policies, track, vehiculos
from rally.agentes import seguimiento
from rally.env import VERSION, AutonomousRallyEnv

DEMOS = Path("data/processed/demos.npz")
ESCENARIOS = Path("data/processed/escenarios.json")
METRICAS = Path("metrics")


def _crear_env(vehiculo="carro", **kw):
    """Ambiente del vehículo (el del carro se busca aquí en tiempo de llamada: las pruebas lo espían)."""
    return AutonomousRallyEnv(**kw) if vehiculos.validar(vehiculo) == "carro" else vehiculos.crear_env(vehiculo, **kw)


def params(vehiculo="carro"):
    """params.yaml; para la moto, su sección `moto:` reemplaza clave por clave a la del carro.

    RALLY_PARAMS permite pruebas rápidas con otro archivo sin tocar params.yaml.
    """
    ruta = Path(os.environ.get("RALLY_PARAMS", "params.yaml"))
    p = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    if vehiculos.validar(vehiculo) == "carro":
        return p
    propios = p.get("moto") or {}
    out = {k: v for k, v in p.items() if k != "moto"}
    for seccion, valores in propios.items():
        out[seccion] = {**out.get(seccion, {}), **valores} if isinstance(valores, dict) else valores
    for seccion in ("qlearning", "ppo"):   # los agentes eligen ambiente y maestro con esta clave
        out[seccion] = {**out[seccion], "vehiculo": "moto"}
    return out


def rutas(vehiculo="carro"):
    """Dónde lee y escribe cada etapa: el carro conserva sus rutas; la moto usa subcarpetas moto/."""
    datos = vehiculos.carpeta("data/processed", vehiculo)
    return {"demos": datos / "demos.npz", "escenarios": datos / "escenarios.json",
            "metricas": vehiculos.carpeta(METRICAS, vehiculo),
            "modelos": vehiculos.carpeta("models", vehiculo),
            "runs": Path("runs") / ("moto" if vehiculo == "moto" else "")}


def _escribir_json(ruta, datos):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")


def _config_ambiente(vehiculo="carro"):
    """Configuración completa del ambiente (params.yaml + valores por defecto) y su huella."""
    import dataclasses
    import hashlib

    cfg = dataclasses.asdict(_crear_env(vehiculo, **params(vehiculo)["ambiente"]).cfg)
    h = hashlib.sha1(json.dumps(cfg, sort_keys=True).encode())
    for arr in (track.XS, track.YS):
        h.update(np.ascontiguousarray(arr).tobytes())
    return cfg, h.hexdigest()[:12]


def _run(nombre, p_etapa, extra_tags=None, vehiculo="carro"):
    seguimiento.iniciar(vehiculo)
    run = mlflow.start_run(run_name=vehiculos.prefijo(vehiculo) + nombre)
    cfg, huella = _config_ambiente(vehiculo)
    mlflow.set_tags({"etapa": nombre, "vehiculo": vehiculo, "ambiente_version": vehiculos.version(vehiculo),
                     "ambiente_huella": huella,
                     **seguimiento.etiquetas_git(), **(extra_tags or {})})
    # Parámetros de la etapa + toda la configuración del ambiente (física, recompensa, límites)
    mlflow.log_params({**seguimiento.aplanar(p_etapa), **seguimiento.aplanar(cfg, "env.")})
    return run


def _dataset_mlflow(vehiculo="carro"):
    demos = rutas(vehiculo)["demos"]
    d = np.load(demos)
    return mlflow.data.from_numpy(d["obs"], targets=d["acciones"], source=str(demos),
                                  name=f"demos-experto-monaco{'-moto' if vehiculo == 'moto' else ''}")


# ----------------------------------------------------------------- datos

def etapa_datos(vehiculo="carro"):
    p = params(vehiculo)
    r_ = rutas(vehiculo)
    amb, pd = p["ambiente"], p["datos"]
    obs_l, act_l, rew_l, ep_l, mu_l = [], [], [], [], []
    resumen = []
    ep = 0
    for piloto, mu in (("experto", amb["mu"]), ("prudente", p["evaluacion"]["mu_mojado"])):
        env = _crear_env(vehiculo, **{**amb, "mu": mu})
        for k in range(pd["demos_episodios"]):
            pol = policies.crear(piloto, pd["semilla"] + k, vehiculo)
            obs, info = env.reset(seed=pd["semilla"] + k)
            done = False
            while not done:
                a = pol(obs, info)
                obs_l.append(obs)
                act_l.append(a)
                obs, r, term, trunc, info = env.step(a)
                rew_l.append(r)
                ep_l.append(ep)
                mu_l.append(mu)
                done = term or trunc
            resumen.append({"piloto": piloto, "mu": mu, "resultado": info["outcome"],
                            "tiempo": info["t"]})
            ep += 1
    r_["demos"].parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(r_["demos"], obs=np.array(obs_l, dtype=np.float32),
                        acciones=np.array(act_l, dtype=np.float32),
                        recompensas=np.array(rew_l, dtype=np.float32),
                        episodio=np.array(ep_l, dtype=np.int32), mu=np.array(mu_l, dtype=np.float32))
    pe = p["evaluacion"]
    _escribir_json(r_["escenarios"], {
        "descripcion": "Escenarios fijos del protocolo de evaluación (no se usan para entrenar)",
        "semillas": list(range(pe["semilla_inicial"], pe["semilla_inicial"] + pe["episodios"])),
        "condiciones": {"seco": pe["mu_seco"], "mojado": pe["mu_mojado"]},
        "ambiente": amb, "ambiente_version": vehiculos.version(vehiculo), "vehiculo": vehiculo,
        "pista_m": round(track.LAP, 2),
    })
    exitos = sum(r["resultado"] == "exito" for r in resumen)
    metricas = {"transiciones": len(obs_l), "episodios": ep, "episodios_exitosos": exitos}
    _escribir_json(r_["metricas"] / "datos.json", metricas)
    with _run("datos", pd, vehiculo=vehiculo):
        mlflow.log_input(_dataset_mlflow(vehiculo), context="demostraciones")
        mlflow.log_metrics(metricas)
        mlflow.log_artifact(str(r_["escenarios"]))
    print(f"Dataset: {len(obs_l)} transiciones de {ep} episodios ({exitos} exitosos) → {r_['demos']}")


# ----------------------------------------------------------------- modelos en MLflow

class _PilotoPyfunc(mlflow.pyfunc.PythonModel):
    """Envoltura MLflow: recibe observaciones (N×24 el carro, N×26 la moto) y devuelve acciones (N×2)."""

    def __init__(self, tipo):
        self.tipo = tipo

    def load_context(self, context):
        ruta = context.artifacts["modelo"]
        if self.tipo == "ppo":
            from rally.agentes.ppo import PilotoPPO
            self.piloto = PilotoPPO(ruta)
        else:
            from rally.agentes.qlearning import AgenteQ
            self.piloto = AgenteQ.cargar(ruta)

    def predict(self, context, model_input, params=None):
        obs = np.asarray(model_input, dtype=np.float32)
        return np.array([self.piloto(o, None) for o in obs], dtype=np.float32)


def _registrar_modelo(tipo, archivo, ejemplo, vehiculo="carro"):
    info = mlflow.pyfunc.log_model(
        name="modelo", python_model=_PilotoPyfunc(tipo), artifacts={"modelo": str(archivo)},
        input_example=ejemplo, registered_model_name=seguimiento.modelos(vehiculo)[tipo],
        # El paquete no está en PyPI: se instala desde el repositorio del grupo
        pip_requirements=["autonomous-rally @ git+https://github.com/melo11miguel/defiende-el-servidor.git",
                          "stable-baselines3", "torch", "numpy", "scipy", "gymnasium"],
    )
    return info.registered_model_version


def _ejemplo_obs(vehiculo="carro"):
    return np.zeros((1, vehiculos.n_obs(vehiculo)), dtype=np.float32)


def _evaluador_rapido(ambiente, pe, n=5, pistas=None, vehiculo="carro"):
    """Evaluación corta durante el entrenamiento: seco, mojado y extremos de los deslizadores.

    Con varias pistas de entrenamiento, seco y mojado corren `n` vueltas en cada una y los
    extremos se reparten entre ellas. Nunca usa una pista reservada: elegir el mejor punto
    del entrenamiento mirándola sería ajustar el modelo a la prueba.
    """
    pistas = track.validar_entrenamiento(pistas)
    ms, mm = pe["mu_seco"], pe["mu_mojado"]
    extremos = [{"mu": 0.4}, {"mu": 0.75}, {"mu": ms, "track_width": 12.0}, {"mu": mm, "track_width": 6.0},
                {"mu": mm, "track_width": 12.0}, {"mu": ms, "r_max": 10.0}, {"mu": mm, "r_max": 40.0},
                {"mu": mm, "a_max": 6.0}, {"mu": ms, "a_max": 2.0}]

    def correr(modelo, cond, veces, pista="monaco"):
        env = _crear_env(vehiculo, **{**ambiente, **cond}, pista=pista)
        ok, prog, tiempos = 0, 0.0, []
        for k in range(veces):
            obs, info = env.reset(seed=pe["semilla_eval_rapida"] + k)
            done = False
            while not done:
                a, _ = modelo.predict(obs, deterministic=True)
                obs, _, term, trunc, info = env.step(a)
                done = term or trunc
            ok += info["outcome"] == "exito"
            prog += info["s_best"] / track.largo(info)
            if info["outcome"] == "exito":
                tiempos.append(info["t"])
        return ok, prog, tiempos

    def correr_pistas(modelo, cond, veces):
        ok, prog, tiempos = 0, 0.0, []
        for pista in pistas:
            o, p_, t = correr(modelo, cond, veces, pista)
            ok, prog, tiempos = ok + o, prog + p_, tiempos + t
        return ok, prog, tiempos

    def evaluar(modelo):
        res = {}
        for nombre, mu in (("seco", ms), ("mojado", mm)):
            ok, prog, tiempos = correr_pistas(modelo, {"mu": mu}, n)
            total = n * len(pistas)
            res[f"{nombre}_vueltas_pct"] = 100 * ok / total
            res[f"{nombre}_progreso_pct"] = 100 * prog / total
            res[f"{nombre}_tiempo_s"] = round(float(np.mean(tiempos)), 2) if tiempos else None
        res["robusto_vueltas_pct"] = round(float(np.mean(
            [100 * correr(modelo, c, 2, pistas[i % len(pistas)])[0] / 2 for i, c in enumerate(extremos)])), 1)
        return res
    return evaluar


# ----------------------------------------------------------------- Q-learning

def etapa_qlearning(vivo=False, vehiculo="carro"):
    from rally.agentes.qlearning import entrenar
    from rally.agentes.vivo import Grabador

    p = params(vehiculo)
    r_ = rutas(vehiculo)
    amb, pq = p["ambiente"], p["qlearning"]
    salida = r_["modelos"] / "qlearning"
    grabador = Grabador("qlearning", amb) if vivo else None
    t0 = time.time()
    with _run("qlearning", pq, {"algoritmo": "Q-learning", "hipotesis": pq["hipotesis"]}, vehiculo) as run:
        mlflow.log_input(_dataset_mlflow(vehiculo), context="demostraciones")
        ventana = []

        def al_terminar(res, ag):
            ventana.append(res)
            if res["episodio"] % 10 == 0:
                v = ventana[-50:]
                mlflow.log_metrics({
                    "episodio_recompensa": float(np.mean([e["recompensa"] for e in v])),
                    "episodio_vueltas_pct": 100 * float(np.mean([e["resultado"] == "exito" for e in v])),
                    "episodio_progreso_m": float(np.mean([e["progreso"] for e in v])),
                    "epsilon": res["epsilon"],
                    "estados_visitados": int((ag.visitas > 0).sum()),
                }, step=res["episodio"])
            if res["episodio"] % 100 == 0:
                print(f"  episodio {res['episodio']:5d}  ε={res['epsilon']:.2f}  "
                      f"recompensa media {np.mean([e['recompensa'] for e in ventana[-100:]]):+8.1f}  "
                      f"progreso {np.mean([e['progreso'] for e in ventana[-100:]]):6.1f} m")

        ag, hist = entrenar(lambda: _crear_env(vehiculo, **amb), pq, grabador, al_terminar,
                            carpeta_punto=str(r_["runs"] / "qlearning-punto"))
        salida.mkdir(parents=True, exist_ok=True)
        ag.guardar(salida / "q_table.npz")
        nombre = seguimiento.modelos(vehiculo)["qlearning"]
        version = _registrar_modelo("qlearning", salida / "q_table.npz", _ejemplo_obs(vehiculo), vehiculo)
        _escribir_json(salida / "info.json", {
            "algoritmo": "Q-learning", "vehiculo": vehiculo, "episodios": len(hist),
            "pasos": int(hist[-1]["pasos"]) if hist else 0, "mlflow_run_id": run.info.run_id,
            "mlflow_modelo": nombre, "mlflow_version": version,
            "ambiente_version": vehiculos.version(vehiculo), "ambiente_huella": _config_ambiente(vehiculo)[1],
            "estados_visitados": int((ag.visitas > 0).sum()), "segundos": round(time.time() - t0, 1),
        })
    print(f"Q-learning listo: {salida} (MLflow {nombre} v{version})")


# ----------------------------------------------------------------- PPO

def etapa_ppo(vivo=False, vehiculo="carro"):
    from rally.agentes import ppo
    from rally.agentes.vivo import Grabador

    p = params(vehiculo)
    r_ = rutas(vehiculo)
    amb, pp = p["ambiente"], p["ppo"]
    salida = r_["modelos"] / "ppo"
    grabador = Grabador("ppo", amb) if vivo else None
    t0 = time.time()
    pistas = track.validar_entrenamiento(pp.get("pistas"))
    with _run("ppo", pp, {"algoritmo": "PPO", "hipotesis": pp["hipotesis"],
                          "pistas_entrenamiento": ",".join(pistas)}, vehiculo) as run:
        mlflow.log_input(_dataset_mlflow(vehiculo), context="demostraciones")
        # Punto de guardado: si el computador se apaga, el próximo `dvc repro` sigue donde quedó.
        # La huella junta parámetros, versión del ambiente y dataset: si algo cambia, empieza de cero.
        import hashlib
        huella = hashlib.sha1(json.dumps([amb, pp, vehiculos.version(vehiculo), _config_ambiente(vehiculo)[1]],
                                         sort_keys=True).encode() + r_["demos"].read_bytes()).hexdigest()[:16]
        punto = ppo.PuntoGuardado(r_["runs"] / "ppo-punto", huella)
        _, n_ep = ppo.entrenar(amb, pp, r_["demos"], salida, grabador,
                               _evaluador_rapido(amb, p["evaluacion"], pistas=pistas, vehiculo=vehiculo), punto)
        nombre = seguimiento.modelos(vehiculo)["ppo"]
        version = _registrar_modelo("ppo", salida / "modelo.zip", _ejemplo_obs(vehiculo), vehiculo)
        info = json.loads((salida / "info.json").read_text(encoding="utf-8"))
        info.update({"mlflow_run_id": run.info.run_id, "mlflow_modelo": nombre, "vehiculo": vehiculo,
                     "ambiente_version": vehiculos.version(vehiculo), "ambiente_huella": _config_ambiente(vehiculo)[1],
                     "mlflow_version": version, "segundos": round(time.time() - t0, 1),
                     "pistas_entrenamiento": pistas})
        _escribir_json(salida / "info.json", info)
    print(f"PPO listo: {salida} ({n_ep} episodios, MLflow {nombre} v{version})")


# ----------------------------------------------------------------- evaluación

def _evaluar_lote(args):
    piloto, ambiente, mu, semillas, *resto = args
    vehiculo = resto[0] if resto else "carro"
    env = _crear_env(vehiculo, **{**ambiente, "mu": mu})
    out = []
    for s in semillas:
        pol = policies.crear(piloto, s, vehiculo)
        obs, info = env.reset(seed=s)
        total, done = 0.0, False
        while not done:
            obs, r, term, trunc, info = env.step(pol(obs, info))
            total += r
            done = term or trunc
        out.append({"ok": info["outcome"] == "exito", "t": info["t"], "r": total,
                    "inc": info["off_track_events"] + (info["outcome"] in ("choque", "caida")),
                    "fin": info["outcome"], "prog": info["s_best"] / track.largo(info)})
    return piloto, mu, out


def _metricas(filas):
    t = [f["t"] for f in filas if f["ok"]]
    return {
        "vueltas_pct": round(100 * float(np.mean([f["ok"] for f in filas])), 1),
        "tiempo_mediano_s": round(float(np.median(t)), 2) if t else None,
        "tiempo_p90_s": round(float(np.percentile(t, 90)), 2) if t else None,
        "incidentes_ep": round(float(np.mean([f["inc"] for f in filas])), 3),
        "recompensa_media": round(float(np.mean([f["r"] for f in filas])), 2),
        "progreso_pct": round(100 * float(np.mean([f["prog"] for f in filas])), 1),
    }


def veredicto(base, cand):
    """Protocolo de la ficha: ¿el candidato mejora en mojado sin perder en seco?"""
    bs, bm, cs, cm = base["seco"], base["mojado"], cand["seco"], cand["mojado"]
    sube_t = None
    if bs["tiempo_mediano_s"] and cs["tiempo_mediano_s"]:
        sube_t = round(100 * (cs["tiempo_mediano_s"] / bs["tiempo_mediano_s"] - 1), 1)
    criterios = {
        "mejora_en_mojado": cm["vueltas_pct"] > bm["vueltas_pct"],
        "no_pierde_vueltas_en_seco": cs["vueltas_pct"] >= bs["vueltas_pct"] - 5,
        "tiempo_seco_maximo_5pct": sube_t is not None and sube_t <= 5,
    }
    return {"criterios": criterios, "tiempo_seco_cambio_pct": sube_t,
            "aceptado": all(criterios.values())}


def etapa_evaluar(vehiculo="carro"):
    p = params(vehiculo)
    r_ = rutas(vehiculo)
    amb, pe = p["ambiente"], p["evaluacion"]
    esc = json.loads(r_["escenarios"].read_text(encoding="utf-8"))
    pilotos = [x for x in pe["pilotos"] if policies.disponible(x, vehiculo)]
    tareas = []
    for piloto in pilotos:
        for mu in esc["condiciones"].values():
            sem = esc["semillas"]
            for i in range(0, len(sem), 10):
                tareas.append((piloto, amb, mu, sem[i:i + 10], vehiculo))
    filas = {}
    with ProcessPoolExecutor() as ex:
        for piloto, mu, out in ex.map(_evaluar_lote, tareas):
            filas.setdefault((piloto, mu), []).extend(out)
    res = {}
    for piloto in pilotos:
        res[piloto] = {c: _metricas(filas[(piloto, mu)]) for c, mu in esc["condiciones"].items()}
    base = pe["base"]
    veredictos = {c: veredicto(res[base], res[c]) for c in pilotos if c != base}
    salida = {"episodios_por_condicion": len(esc["semillas"]), "base": base, "vehiculo": vehiculo,
              "ambiente_version": vehiculos.version(vehiculo), "resultados": res, "veredictos": veredictos}
    _escribir_json(r_["metricas"] / "evaluacion.json", salida)
    with _run("evaluacion", pe, vehiculo=vehiculo):
        for piloto, cond in res.items():
            for c, m in cond.items():
                mlflow.log_metrics({f"{piloto}.{c}.{k}": v for k, v in m.items() if v is not None})
        mlflow.log_artifact(str(r_["metricas"] / "evaluacion.json"))
    for piloto, cond in res.items():
        print(f"  {piloto:10s} seco {cond['seco']['vueltas_pct']:5.1f}% "
              f"{cond['seco']['tiempo_mediano_s'] or '—'} s · mojado {cond['mojado']['vueltas_pct']:5.1f}%")


# ----------------------------------------------------------------- registro

def etapa_registrar(vehiculo="carro"):
    """Marca cada versión nueva como champion (si gana el protocolo) o challenger."""
    from mlflow import MlflowClient

    seguimiento.iniciar(vehiculo)
    r_ = rutas(vehiculo)
    cliente = MlflowClient()
    ev = json.loads((r_["metricas"] / "evaluacion.json").read_text(encoding="utf-8"))
    registro = {}
    for tipo, nombre in seguimiento.modelos(vehiculo).items():
        info_path = r_["modelos"] / tipo / "info.json"
        if not info_path.exists() or tipo not in ev["resultados"]:
            continue
        info = json.loads(info_path.read_text(encoding="utf-8"))
        # mlflow.db no se versiona: la versión se busca por el run_id guardado en info.json
        # (que sí está en DVC). Si no existe en este MLflow, no se puede etiquetar.
        encontradas = cliente.search_model_versions(f"run_id='{info['mlflow_run_id']}'")
        if not encontradas:
            print(f"  {nombre}: la corrida {info['mlflow_run_id']} no está en este MLflow; se omite")
            continue
        version = str(encontradas[0].version)
        m = ev["resultados"][tipo]
        ver = ev["veredictos"].get(tipo, {})
        for c, met in m.items():
            for k, v in met.items():
                if v is not None:
                    cliente.set_model_version_tag(nombre, version, f"{c}.{k}", str(v))
        cliente.set_model_version_tag(nombre, version, "protocolo_aceptado", str(ver.get("aceptado")))
        # Champion: la versión con más vueltas completas (seco + mojado); empate → menor tiempo
        puntaje = m["seco"]["vueltas_pct"] + m["mojado"]["vueltas_pct"]
        t_nuevo = m["seco"]["tiempo_mediano_s"] or float("inf")
        try:
            actual = cliente.get_model_version_by_alias(nombre, "champion")
            p_actual = float(actual.tags.get("seco.vueltas_pct", 0)) + float(actual.tags.get("mojado.vueltas_pct", 0))
            t_actual = float(actual.tags.get("seco.tiempo_mediano_s", "inf"))
        except Exception:
            actual, p_actual, t_actual = None, -1, float("inf")
        gana = puntaje > p_actual or (puntaje == p_actual and t_nuevo < t_actual)
        alias = "champion" if (actual is None or str(actual.version) == version or gana) else "challenger"
        cliente.set_registered_model_alias(nombre, alias, version)
        registro[tipo] = {"modelo": nombre, "version": version, "alias": alias, "puntaje": puntaje,
                          "protocolo_aceptado": ver.get("aceptado")}
        print(f"  {nombre} v{version} → @{alias} (puntaje {puntaje:.0f})")
    _escribir_json(r_["metricas"] / "registro.json", registro)
