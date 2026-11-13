"""Agente con red neuronal: PPO (Stable-Baselines3 + PyTorch).

1. Preentrenamiento por imitación con DAgger: la red maneja y el piloto maestro
   (policies.Maestro) le dice qué habría hecho en cada estado que visitó. Copiar
   vueltas perfectas no basta (behavior cloning, v1–v3): al primer error la red
   llega a estados que nunca vio y choca en Sainte Dévote.
2. Aprendizaje por refuerzo con PPO en varias simulaciones en paralelo: la red
   mejora sola con prueba y error, a partir de la recompensa.
3. Dominio aleatorio (opcional): en cada episodio se sortean adherencia, ancho,
   aceleración y alcance de sensores dentro de los rangos de la ficha, y los sensores
   llevan ruido, para que el modelo maneje bien en cualquier experimento del visor.
   Con `pistas` en params.yaml también se sortea la pista (nunca una reservada).
4. Se guarda el mejor modelo de las evaluaciones rápidas: si PPO empeora la red,
   el resultado final nunca queda peor que lo mejor que se vio.
"""

import json
from pathlib import Path

import gymnasium as gym
import mlflow
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import SubprocVecEnv

from rally import track, vehiculos
from rally.env import RAYO_REF


class DominioAleatorio(gym.Wrapper):
    """En cada reset sortea las condiciones del experimento (el agente no ve el μ exacto).

    `prob_lluvia` de los episodios son con lluvia (μ en [lluvia_min, lluvia_max]) y el resto
    en seco (μ en [mu_min, mu_max]). Así no aprende solo a ir rápido en seco (le pasó a la v2).
    `rangos` sortea otros parámetros del ambiente; con `prob_base` conservan el valor base,
    para que la condición de la ficha no quede menos practicada que los extremos.
    """

    def __init__(self, env, p):
        super().__init__(env)
        self.p = p
        cfg = env.unwrapped.cfg
        self.base = {k: getattr(cfg, k) for k in p.get("rangos", {})}

    def reset(self, **kw):
        r, p, cfg = self.np_random, self.p, self.env.unwrapped.cfg
        if r.random() < p["prob_lluvia"]:
            cfg.mu = float(r.uniform(p["lluvia_min"], p["lluvia_max"]))
        else:
            cfg.mu = float(r.uniform(p["mu_min"], p["mu_max"]))
        sortear = r.random() >= p.get("prob_base", 0.0)
        for k, (lo, hi) in p.get("rangos", {}).items():
            setattr(cfg, k, float(r.uniform(lo, hi)) if sortear else self.base[k])
        return self.env.reset(**kw)


class RuidoSensores(gym.ObservationWrapper):
    """Sensores imperfectos: cada episodio sortea cuánto ruido hay (v4 falló con ruido y lluvia)."""

    def __init__(self, env, ruido_max):
        super().__init__(env)
        self.ruido_max, self.ruido = ruido_max, 0.0

    def reset(self, **kw):
        self.ruido = float(self.np_random.uniform(0.0, self.ruido_max))
        return super().reset(**kw)

    def observation(self, obs):
        o = obs + self.np_random.normal(0.0, self.ruido, obs.shape)
        o[19:23] = obs[19:23]   # lluvia y configuración no son lecturas ruidosas
        return np.clip(o, self.observation_space.low, self.observation_space.high).astype(np.float32)


def crear_env(ambiente, ppo_params, rank):
    # `pistas` (opcional): cada episodio sortea una de estas pistas. Sin la clave, solo Mónaco,
    # igual que todas las versiones anteriores.
    pistas = track.validar_entrenamiento(ppo_params.get("pistas"))

    def _f():
        env = vehiculos.crear_env(ppo_params.get("vehiculo", "carro"), **ambiente, pista=pistas)
        if ppo_params.get("dominio_aleatorio"):
            env = DominioAleatorio(env, ppo_params)
        if ppo_params.get("ruido_sensores"):
            env = RuidoSensores(env, ppo_params["ruido_sensores"])
        env.reset(seed=200_000 + ppo_params["semilla"] * 1000 + rank)  # lejos de las semillas de evaluación
        return env
    return _f


def imitar(model, demos_path, epocas, lr=1e-3, batch=1024):
    """Behavior cloning: maximiza la probabilidad de las acciones del experto."""
    datos = np.load(demos_path)
    obs = torch.as_tensor(datos["obs"], dtype=torch.float32)
    acts = torch.as_tensor(np.clip(datos["acciones"], -0.999, 0.999), dtype=torch.float32)
    pol = model.policy
    opt = torch.optim.Adam(pol.parameters(), lr=lr)
    n = len(obs)
    perdidas = []
    for ep in range(epocas):
        perm = torch.randperm(n)
        total = 0.0
        for i in range(0, n, batch):
            idx = perm[i:i + batch]
            _, log_prob, entropia = pol.evaluate_actions(obs[idx], acts[idx])
            loss = -log_prob.mean() - 1e-3 * entropia.mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(idx)
        perdidas.append(total / n)
        mlflow.log_metric("bc_perdida", perdidas[-1], step=ep)
    return perdidas


def _media(pol, obs):
    return pol.get_distribution(obs).distribution.mean


def dagger(model, ambiente, p, evaluador=None):
    """DAgger: la red maneja, el maestro etiqueta cada estado visitado y la red se reentrena.

    Iteración 0: solo maneja el maestro. Después, con probabilidad beta (que baja a 0)
    maneja el maestro y si no la red; todos los datos se acumulan.
    """
    from rally.policies import Maestro, MaestroMoto

    clase = MaestroMoto if p.get("vehiculo") == "moto" else Maestro
    maestro = clase(p["maestro_mu_seco"], p["maestro_mu_lluvia"],
                    p["maestro_traccion_seco"], p["maestro_traccion_lluvia"])
    env = crear_env(ambiente, p, 99)()
    rng = np.random.default_rng(p["semilla"])
    pol = model.policy
    opt = torch.optim.Adam(pol.parameters(), lr=1e-3)
    O, A, perdidas = [], [], []
    for it in range(p["dagger_iter"]):
        beta = 1.0 if it == 0 else max(0.0, 0.5 - 0.1 * (it - 1))
        for _ in range(p["dagger_episodios"]):
            obs, info = env.reset()
            done = False
            while not done:
                a_m = maestro(obs, info)
                O.append(obs)
                A.append(a_m)
                if rng.random() >= beta:
                    with torch.no_grad():
                        a_m = _media(pol, torch.as_tensor(obs[None])).numpy()[0]
                obs, _, term, trunc, info = env.step(np.clip(a_m, -1, 1))
                done = term or trunc
        o = torch.as_tensor(np.array(O), dtype=torch.float32)
        a = torch.as_tensor(np.array(A), dtype=torch.float32)
        for _ in range(p["dagger_epocas"]):
            perm = torch.randperm(len(o))
            for i in range(0, len(o), 512):
                idx = perm[i:i + 512]
                loss = ((_media(pol, o[idx]) - a[idx]) ** 2).mean()
                opt.zero_grad()
                loss.backward()
                opt.step()
        perdidas.append(loss.item())
        mlflow.log_metrics({"dagger_perdida": perdidas[-1], "dagger_datos": len(O)}, step=it)
        if evaluador:
            m = evaluador(model)
            mlflow.log_metrics({f"dagger_{k}": v for k, v in m.items() if v is not None}, step=it)
            print(f"  DAgger {it + 1}/{p['dagger_iter']}: seco {m['seco_vueltas_pct']:.0f}% · "
                  f"mojado {m['mojado_vueltas_pct']:.0f}% ({len(O):,} estados)", flush=True)
    env.close()
    return perdidas


def puntaje(m):
    """Orden de las evaluaciones rápidas: vueltas, luego avance, luego tiempo."""
    tiempo = (m.get("seco_tiempo_s") or 999) + (m.get("mojado_tiempo_s") or 999)
    return (m["seco_vueltas_pct"] + m["mojado_vueltas_pct"] + m.get("robusto_vueltas_pct", 0),
            m["seco_progreso_pct"] + m["mojado_progreso_pct"], -tiempo)


class MejorModelo:
    """Guarda el modelo con el mejor puntaje de las evaluaciones rápidas (sobrevive apagones)."""

    def __init__(self, carpeta):
        self.carpeta = Path(carpeta)
        self.ruta = self.carpeta / "mejor.zip"
        try:
            est = json.loads((self.carpeta / "mejor.json").read_text(encoding="utf-8"))
            self.puntaje, self.metricas, self.paso = tuple(est["puntaje"]), est["metricas"], est["paso"]
        except (OSError, ValueError, KeyError):
            self.puntaje, self.metricas, self.paso = None, None, None

    def revisar(self, model, m, paso):
        if self.puntaje is not None and puntaje(m) <= self.puntaje:
            return False
        self.carpeta.mkdir(parents=True, exist_ok=True)
        tmp = self.carpeta / "mejor.tmp.zip"
        model.save(tmp)
        tmp.replace(self.ruta)
        self.puntaje, self.metricas, self.paso = puntaje(m), m, int(paso)
        (self.carpeta / "mejor.json").write_text(json.dumps(
            {"puntaje": self.puntaje, "metricas": m, "paso": self.paso}), encoding="utf-8")
        return True

    def borrar(self):
        for f in ("mejor.zip", "mejor.json"):
            (self.carpeta / f).unlink(missing_ok=True)


class Seguimiento(BaseCallback):
    """Registra cada episodio en MLflow y transmite el episodio del env 0 al visor."""

    def __init__(self, grabador, evaluador, eval_cada, n_envs, punto=None, pasos_iniciales=0,
                 episodios_iniciales=0, mejor=None):
        super().__init__()
        self.mejor = mejor
        self.grabador = grabador
        self.evaluador = evaluador
        self.eval_cada = eval_cada
        self.totales = np.zeros(n_envs)
        self.recientes = []
        self.n_ep = episodios_iniciales
        self.prox_eval = (pasos_iniciales // eval_cada + 1) * eval_cada
        self.punto = punto
        self.prox_punto = (pasos_iniciales // PUNTO_CADA + 1) * PUNTO_CADA

    def _on_step(self):
        infos, dones = self.locals["infos"], self.locals["dones"]
        rewards, actions = self.locals["rewards"], self.locals["actions"]
        self.totales += rewards
        if self.grabador is not None:
            obs0 = infos[0].get("terminal_observation", self.locals["new_obs"][0])
            self.grabador.paso(obs0, infos[0], np.clip(actions[0], -1, 1), float(rewards[0]))
        for i, d in enumerate(dones):
            if not d:
                continue
            info = infos[i]
            self.n_ep += 1
            self.recientes.append({"r": self.totales[i], "ok": info["outcome"] == "exito",
                                   "t": info["t"], "s": info["s_best"]})
            self.recientes = self.recientes[-50:]
            self.totales[i] = 0.0
            if i == 0 and self.grabador is not None:
                self.grabador.fin(info, self.num_timesteps)
            if self.n_ep % 10 == 0:
                rec = self.recientes
                mlflow.log_metrics({
                    "episodio_recompensa": float(np.mean([e["r"] for e in rec])),
                    "episodio_vueltas_pct": 100 * float(np.mean([e["ok"] for e in rec])),
                    "episodio_progreso_m": float(np.mean([e["s"] for e in rec])),
                    "episodios": self.n_ep,
                }, step=self.num_timesteps)
        if self.evaluador and self.num_timesteps >= self.prox_eval:
            self.prox_eval += self.eval_cada
            m = self.evaluador(self.model)
            mlflow.log_metrics({f"eval_{k}": v for k, v in m.items() if v is not None},
                               step=self.num_timesteps)
            if self.mejor:
                self.mejor.revisar(self.model, m, self.num_timesteps)
        if self.punto and self.num_timesteps >= self.prox_punto:
            self.prox_punto += PUNTO_CADA
            self.punto.guardar(self.model, self.n_ep)
        return True


PUNTO_CADA = 200_000   # pasos entre puntos de guardado


class PuntoGuardado:
    """Guarda el entrenamiento a medias para seguir si el computador se apaga.

    Vive en runs/ (fuera de DVC, que borra models/ppo al empezar la etapa). Solo se
    reanuda si los parámetros y la versión del ambiente son los mismos (huella).
    """

    def __init__(self, carpeta, huella):
        self.carpeta, self.huella = Path(carpeta), huella

    def guardar(self, model, n_ep):
        self.carpeta.mkdir(parents=True, exist_ok=True)
        tmp = self.carpeta / "modelo.tmp.zip"
        model.save(tmp)
        tmp.replace(self.carpeta / "modelo.zip")    # escritura atómica
        (self.carpeta / "estado.json").write_text(json.dumps(
            {"huella": self.huella, "pasos": int(model.num_timesteps), "episodios": n_ep}), encoding="utf-8")

    def cargar(self):
        try:
            est = json.loads((self.carpeta / "estado.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if est.get("huella") != self.huella or not (self.carpeta / "modelo.zip").exists():
            return None
        return est

    def borrar(self):
        for f in ("modelo.zip", "estado.json"):
            (self.carpeta / f).unlink(missing_ok=True)


class PilotoPPO:
    """Usa el modelo entrenado como piloto (acción determinista).

    Los modelos de la familia 0.3 (v3 y v4, 20 observaciones) corren con un adaptador:
    reciben las 20 primeras y los rayos otra vez divididos por el alcance. Los de la moto
    (26 observaciones) solo corren en el ambiente de la moto.
    """

    def __init__(self, ruta):
        self.model = PPO.load(ruta, device="cpu")
        self.n_obs = self.model.observation_space.shape[0]

    def __call__(self, obs, info):
        o = np.asarray(obs, dtype=np.float32)
        if self.n_obs == 20:
            r_max = o[22] * RAYO_REF
            o = o[:20].copy()
            o[6:13] *= RAYO_REF / r_max
        a, _ = self.model.predict(o, deterministic=True)
        return np.clip(a, -1, 1)


def entrenar(ambiente, p, demos_path, salida, grabador=None, evaluador=None, punto=None):
    n_envs = p["n_envs"]
    venv = SubprocVecEnv([crear_env(ambiente, p, i) for i in range(n_envs)])
    previo = punto.cargar() if punto else None
    if previo:
        # Se reanuda donde quedó (el computador se apagó a mitad del entrenamiento)
        model = PPO.load(punto.carpeta / "modelo.zip", env=venv, device="cpu")
        perdidas = []
        print(f"  Reanudando desde el paso {previo['pasos']:,} (punto de guardado)")
        mlflow.set_tag("reanudado_desde_paso", previo["pasos"])
    else:
        model = PPO(
            "MlpPolicy", venv, learning_rate=p["learning_rate"], n_steps=p["n_steps"],
            batch_size=p["batch_size"], gamma=p["gamma"], gae_lambda=0.95, ent_coef=p["ent_coef"],
            clip_range=0.2, policy_kwargs={"net_arch": dict(pi=p["capas"], vf=p["capas"]),
                                           "log_std_init": p["log_std_init"]},
            seed=p["semilla"], device="cpu", verbose=0,
        )
        if p.get("dagger_iter", 0) > 0:
            perdidas = dagger(model, ambiente, p, evaluador)
        else:
            perdidas = imitar(model, demos_path, p["bc_epocas"]) if p["bc_epocas"] > 0 else []
    salida = Path(salida)
    mejor = MejorModelo(punto.carpeta if punto else salida)
    if not previo:
        mejor.borrar()   # de una corrida anterior con otros parámetros
        if evaluador:    # el punto de partida (red recién imitada) también compite
            mejor.revisar(model, evaluador(model), 0)
    hechos = previo["pasos"] if previo else 0
    cb = Seguimiento(grabador, evaluador, p["eval_cada"], n_envs, punto, hechos,
                     previo["episodios"] if previo else 0, mejor if evaluador else None)
    model.learn(total_timesteps=max(p["pasos"] - hechos, 0), callback=cb, progress_bar=False,
                reset_num_timesteps=not previo)
    if evaluador:
        mejor.revisar(model, evaluador(model), model.num_timesteps)
    salida.mkdir(parents=True, exist_ok=True)
    if mejor.paso is not None:
        model = PPO.load(mejor.ruta, device="cpu")
        mlflow.log_metrics({f"mejor_{k}": v for k, v in mejor.metricas.items() if v is not None})
        mlflow.set_tag("mejor_paso", mejor.paso)
        print(f"  Mejor modelo: paso {mejor.paso:,} · {mejor.metricas}")
    model.save(salida / "modelo.zip")
    (salida / "info.json").write_text(json.dumps({
        "algoritmo": "PPO" + (" + DAgger" if p.get("dagger_iter", 0) > 0 else ""),
        "pasos": p["pasos"], "episodios": cb.n_ep,
        "imitacion_perdida_final": perdidas[-1] if perdidas else None,
        "mejor_paso": mejor.paso, "mejor_eval_rapida": mejor.metricas,
        "observacion": int(venv.observation_space.shape[0]),
        "reanudado_desde_paso": hechos or None,
    }, indent=2), encoding="utf-8")
    venv.close()
    if punto:
        punto.borrar()   # terminó: el punto de guardado ya no hace falta
        mejor.borrar()
    return model, cb.n_ep
