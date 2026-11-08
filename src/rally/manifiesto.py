"""Manifiestos: lo necesario para recuperar y evaluar un modelo, sin depender de la memoria.

Cada versión marcada con una etiqueta de git produce manifests/<tipo>-<etiqueta>.json con los
pesos y su SHA-256, el contrato de observaciones y acciones, el ambiente compatible, la
configuración, el run y los resultados. Todo se lee de git y de la caché de DVC, así que
también sirve para versiones viejas. `catalogo.json` es lo que muestra la web.
"""
import hashlib
import json
import re
import subprocess
from pathlib import Path

import yaml

CACHE = Path(".dvc/cache/files/md5")
SALIDA = Path("manifests")
ARCHIVO = {"ppo": "modelo.zip", "qlearning": "q_table.npz"}
SUITE = "ficha-100-semillas-0-99"
OBS_0_4 = ["v/25 m/s", "ω/2 rad/s", "sin φ", "cos φ", "d/(w/2)", "eψ/π rad"]
OBS_0_4 += [f"rayo {a}°/40 m" for a in (-90, -60, -30, 0, 30, 60, 90)]
OBS_0_4 += [f"curvatura a {k} m·R" for k in (10, 25, 50)]
OBS_0_4 += ["agarre usado", "derrape", "μ estimado/1.2", "lluvia", "ancho/12 m", "a_max/6 m/s²",
            "r_max/40 m", "velocidad segura/25 m/s"]
ACCIONES = ["u_acel [-1, 1]", "u_dir [-1, 1]"]
# Nivel y decisión de cada versión. Los intentos fallidos se conservan como rechazados.
VERSIONES = {
    "modelo-v1": ("N1", "reemplazado", "Primer modelo: entrenado solo en seco"),
    "modelo-v2": ("N1", "reemplazado", "Un sensor de agarre debería ayudar con lluvia: no ayudó"),
    "experimento-v3": ("N2", "rechazado", "Practicar 50 % con lluvia e imitar vueltas perfectas: falló en ambos pisos"),
    "modelo-v4": ("N2", "aceptado", "DAgger corrige los estados a los que llega la red al equivocarse"),
    "modelo-qlearning-v6": ("N2", "reemplazado", "DAgger tabular y bin de lluvia: mejora la tabla de 0 % a 60/15"),
    "modelo-v5": ("N3", "candidato", None),
    "modelo-qlearning-v7": ("N3", "reemplazado", None),
    "modelo-qlearning-v8": ("N3", "candidato", None),
    "modelo-v6-pistas": ("N3", "candidato", None),
}
# Dónde se entrenó cada versión cuando no fue en el PC de siempre: la huella del ambiente
# (ambiente_huella) cambia entre Linux y macOS por el redondeo del último bit en la geometría.
PLATAFORMAS = {
    "modelo-v6-pistas": {"maquina": "MacBook de Miguel, Intel Core i3-1000NG4 (x86_64), 8 GB",
                         "sistema": "macOS 15.8", "python": "3.12.14", "torch": "2.2.2",
                         "stable_baselines3": "2.4.1", "numpy": "1.26.4"},
}
# Versiones que no salen de `dvc repro` completo (la etapa evaluar también necesita la tabla Q):
# sus resultados con la suite de la ficha están en este archivo, en el commit de la etiqueta.
RESULTADOS = {"modelo-v6-pistas": "metrics/v6-ficha.json"}
FINALISTAS = Path("finalistas")   # semillas 1 y 2: DVC las versiona con finalistas.dvc
FAMILIA = {"ppo": "modelo-v5", "qlearning": "modelo-qlearning-v8"}
METRICAS = {"ppo": Path("metrics/semillas.json"), "qlearning": Path("metrics/semillas-qlearning.json")}
ELEGIDA = {"ppo": 1, "qlearning": 1}   # por configs/seleccion.yaml: más vueltas y luego menor tiempo


def _git(*a):
    return subprocess.check_output(["git", *a], text=True, stderr=subprocess.DEVNULL)


def _cache(md5):
    return CACHE / md5[:2] / md5[2:]


def _sha256(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def _salidas(lock, etapa, ruta):
    """md5 de la carpeta que produjo la etapa según dvc.lock."""
    for o in lock["stages"][etapa]["outs"]:
        if o["path"] == ruta:
            return o["md5"]
    raise KeyError(ruta)


def manifiesto(rev, tipo):
    commit = _git("rev-parse", f"{rev}^{{commit}}").strip()
    lock = yaml.safe_load(_git("show", f"{commit}:dvc.lock"))
    texto_params = _git("show", f"{commit}:params.yaml")
    params = yaml.safe_load(texto_params)
    env = _git("show", f"{commit}:src/rally/env.py")
    version_env = re.search(r'^VERSION = "(.+)"', env, re.M).group(1)
    n_obs = int(re.search(r"Observación \((\d+)\)", env).group(1))
    md5 = _salidas(lock, tipo, f"models/{tipo}")
    hijos = {e["relpath"]: e["md5"] for e in json.loads(_cache(md5).read_text())}
    pesos = _cache(hijos[ARCHIVO[tipo]])
    info = json.loads(_cache(hijos["info.json"]).read_text())
    try:
        if rev in RESULTADOS:
            ev = json.loads(_git("show", f"{commit}:{RESULTADOS[rev]}"))["resultados"]
        else:
            ev = json.loads(_git("show", f"{commit}:metrics/evaluacion.json"))["resultados"].get(tipo)
    except (subprocess.CalledProcessError, ValueError):
        ev = None
    nivel, decision, hipotesis = VERSIONES.get(rev, (None, None, None))
    if tipo == "qlearning" and "qlearning" not in rev:   # esas etiquetas hablan del PPO
        if rev == "modelo-v5":
            raise KeyError("la tabla de esta versión tiene su propia etiqueta")
        decision, hipotesis = "rechazado", "Tabla entrenada junto a esta versión"
    p = params.get(tipo, {})
    return {
        "nombre": f"{tipo}-{rev}", "tipo": tipo, "etiqueta_git": rev,
        "run_id": info.get("mlflow_run_id"), "level_id": nivel,
        "decision": decision, "hipotesis": p.get("hipotesis") or hipotesis,
        "environment_version": version_env, "ambiente_huella": info.get("ambiente_huella"),
        "git_commit": commit, "config_sha256": hashlib.sha256(texto_params.encode()).hexdigest(),
        "model_uri": f"dvc://models/{tipo}/{ARCHIVO[tipo]}@{commit}",
        "model_md5_dvc": hijos[ARCHIVO[tipo]], "model_sha256": _sha256(pesos),
        "mlflow_modelo": info.get("mlflow_modelo"), "mlflow_version": info.get("mlflow_version"),
        "normalization_uri": None,   # sin VecNormalize: el ambiente ya entrega valores escalados
        "runtime_ref": f"requirements.txt y pyproject.toml en {commit}",
        "evaluation_suite_id": SUITE, "seed": p.get("semilla"), "parent_run_id": None,
        "origen": "desde cero con imitación" if p.get("dagger_iter") else "desde cero",
        "presupuesto": {k: v for k, v in info.items() if k in ("pasos", "episodios", "segundos")},
        "contrato": {"observaciones": n_obs, "orden": OBS_0_4 if n_obs == 24 else f"ver src/rally/env.py en {commit}",
                     "acciones": ACCIONES, "clipping": "[-1, 1]", "paso_s": 0.1},
        "resultados": ev,
        "pistas_entrenamiento": info.get("pistas_entrenamiento", ["monaco"]),
        "entrenamiento_plataforma": PLATAFORMAS.get(rev),
    }


def _run_de_semilla(tipo, s):
    """Run terminado de esa semilla: de ahí salen su id y el commit que la entrenó."""
    from mlflow import MlflowClient

    from rally.agentes.seguimiento import EXPERIMENTO, TRACKING_URI
    c = MlflowClient(tracking_uri=TRACKING_URI)
    exp = c.get_experiment_by_name(EXPERIMENTO)
    filtro = f"attributes.run_name = '{tipo}-semilla-{s}' and attributes.status = 'FINISHED'"
    return c.search_runs([exp.experiment_id], filtro, max_results=1)[0]


def manifiesto_finalista(tipo, s):
    """Otra semilla del mismo experimento: comparte contrato y configuración con su familia."""
    pesos = FINALISTAS / f"{tipo}-s{s}" / ARCHIVO[tipo]
    familia = FAMILIA[tipo]
    run = _run_de_semilla(tipo, s)
    res = json.loads(METRICAS[tipo].read_text(encoding="utf-8"))[f"{tipo}-s{s}"]
    datos = pesos.read_bytes()
    return {**manifiesto(familia, tipo), "nombre": f"{tipo}-{familia}-s{s}", "etiqueta_git": f"{familia}-s{s}",
            "run_id": run.info.run_id, "git_commit": run.data.tags["git_commit"], "seed": s,
            "decision": "aceptado" if ELEGIDA[tipo] == s else "candidato", "model_uri": f"dvc://{pesos}", "model_md5_dvc": hashlib.md5(datos).hexdigest(),
            "model_sha256": hashlib.sha256(datos).hexdigest(), "mlflow_modelo": None, "mlflow_version": None,
            "presupuesto": {}, "resultados": {"seco": res["seco"], "mojado": res["mojado"]}}


def generar(revisiones=None):
    revisiones = revisiones or [t for t in _git("tag", "-l").split() if t in VERSIONES]
    SALIDA.mkdir(exist_ok=True)
    catalogo = []

    def agregar(m):
        ruta = SALIDA / f"{m['nombre']}.json"
        ruta.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
        catalogo.append({k: m[k] for k in ("nombre", "tipo", "etiqueta_git", "level_id", "decision", "hipotesis",
                                           "environment_version", "git_commit", "model_sha256", "resultados")})
        print(f"  {ruta}  {m['model_sha256'][:12]}")

    for rev in revisiones:
        for tipo in ARCHIVO:
            if "qlearning" in rev and tipo != "qlearning":
                continue
            try:
                agregar(manifiesto(rev, tipo))
            except (KeyError, FileNotFoundError, subprocess.CalledProcessError) as e:
                print(f"  {tipo} {rev}: sin manifiesto ({e})")
    for carpeta in sorted(FINALISTAS.glob("*-s*")):
        tipo, s = carpeta.name.rsplit("-s", 1)
        agregar(manifiesto_finalista(tipo, int(s)))
    (SALIDA / "catalogo.json").write_text(json.dumps(catalogo, indent=2, ensure_ascii=False), encoding="utf-8")
    return catalogo
