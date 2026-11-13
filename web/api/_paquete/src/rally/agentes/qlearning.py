"""Agente Q-learning con tabla (el primer agente del tablero).

Q(s, a) <- Q(s, a) + α · [r + γ · max_a' Q(s', a') − Q(s, a)]

Usa las acciones discretas y el estado discretizado de `discreto.py`. Aprender
solo con ε-greedy desde cero casi nunca llega a la meta en un circuito de 1 km
(v1–v3: 0 % de vueltas), así que se entrena en dos fases:

1. Imitación con DAgger: la tabla maneja y un piloto maestro dice qué acción
   habría elegido en cada estado visitado (se cuentan sus votos por estado).
2. Q-learning: la tabla Q arranca con esos votos (la acción del maestro vale
   `q_inicial`) y se corrige con la ecuación de Bellman practicando con seco y
   lluvia. Así Q-learning arregla los lugares donde la imitación choca.

En las dos fases se evalúa cada cierto tiempo y se guarda la mejor tabla. El
avance queda en runs/qlearning-punto: si el computador se apaga, el próximo
`dvc repro` sigue donde quedó.
"""

import hashlib
import json
from pathlib import Path

import mlflow
import numpy as np

from rally import track, vehiculos
from rally.agentes.discreto import ACCIONES, N_ESTADOS, NEUTRA, a_mando, discreta, estado
from rally.policies import PurePursuit, PurePursuitMoto

# Semillas de entrenamiento lejos de las de evaluación (0-99) y del dataset (500+)
SEMILLA_BASE = 100_000
SEMILLA_EVAL = 10_000   # evaluación rápida (las mismas que usa PPO)


class AgenteQ:
    def __init__(self, alpha=0.1, gamma=0.99, seed=0):
        self.q = np.zeros((N_ESTADOS, len(ACCIONES)), dtype=np.float32)
        self.visitas = np.zeros(N_ESTADOS, dtype=np.int64)
        self.alpha, self.gamma = alpha, gamma
        self.rng = np.random.default_rng(seed)

    def mejor(self, s):
        # Empate con la acción neutra (estado sin experiencia, o las demás ya salieron
        # negativas): gana la neutra, no la primera de la tabla (frenar y girar a fondo)
        fila = self.q[s]
        return NEUTRA if fila[NEUTRA] == fila.max() else int(np.argmax(fila))

    def elegir(self, s, epsilon=0.0):
        if self.rng.random() < epsilon:
            return int(self.rng.integers(len(ACCIONES)))
        return self.mejor(s)

    def aprender(self, s, a, r, s2, terminal):
        objetivo = r if terminal else r + self.gamma * self.q[s2].max()
        self.q[s, a] += self.alpha * (objetivo - self.q[s, a])
        self.visitas[s] += 1

    # Como piloto para el visor y la evaluación: sin explorar y determinista
    def __call__(self, obs, info):
        return a_mando(ACCIONES[self.mejor(estado(obs))], obs)

    def guardar(self, ruta):
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(ruta, q=self.q, visitas=self.visitas,
                            alpha=self.alpha, gamma=self.gamma)

    @classmethod
    def cargar(cls, ruta):
        datos = np.load(ruta)
        ag = cls(float(datos["alpha"]), float(datos["gamma"]))
        ag.q, ag.visitas = datos["q"], datos["visitas"]
        return ag


class PuntoQ:
    """Guarda el entrenamiento a medias. Solo se reanuda si params y ambiente son los mismos."""

    def __init__(self, carpeta, huella):
        self.ruta, self.huella = Path(carpeta) / "punto.npz", huella

    def guardar(self, estado_json, **tablas):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.ruta.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, huella=self.huella, estado=json.dumps(estado_json), **tablas)
        tmp.replace(self.ruta)    # escritura atómica

    def cargar(self):
        try:
            d = np.load(self.ruta)
            if str(d["huella"]) != self.huella:
                return None
            return {**{k: d[k] for k in d.files}, "estado": json.loads(str(d["estado"]))}
        except (OSError, ValueError, KeyError):
            return None

    def borrar(self):
        self.ruta.unlink(missing_ok=True)


def maestro(p):
    """Pure pursuit que mira la señal de lluvia. Con lluvia va a 16 m/s en las rectas:
    así la frenada para la curva cabe en los 50 m que la tabla alcanza a ver.
    Para la moto (`vehiculo: moto` en sus parámetros) es el pure pursuit que pide inclinación."""
    clase = PurePursuitMoto if p.get("vehiculo") == "moto" else PurePursuit
    seco = clase(p["maestro_mu_seco"], traccion=p["maestro_traccion_seco"])
    lluvia = clase(p["maestro_mu_lluvia"], v_recta=p["maestro_v_recta_lluvia"],
                   traccion=p["maestro_traccion_lluvia"])
    return lambda obs, info: (lluvia if obs[19] > 0.5 else seco)(obs, info)


def puntaje(m):
    """Orden de las evaluaciones rápidas: vueltas, luego avance, luego tiempo."""
    tiempo = (m.get("seco_tiempo_s") or 999) + (m.get("mojado_tiempo_s") or 999)
    return [m["seco_vueltas_pct"] + m["mojado_vueltas_pct"] + m["robusto_vueltas_pct"],
            m["seco_progreso_pct"] + m["mojado_progreso_pct"], -tiempo]


def evaluar(politica, env, n=10, mu_seco=0.9, mu_mojado=0.5):
    """Evaluación rápida en seco, mojado y extremos de los deslizadores."""
    res, cfg = {}, env.unwrapped.cfg
    base = cfg.track_width, cfg.a_max
    robusto = []
    for nombre, mu, ancho, a_max in (("seco", mu_seco, *base), ("mojado", mu_mojado, *base),
                                     ("r1", 0.4, *base), ("r2", 0.75, *base), ("r3", mu_seco, 6.0, base[1]),
                                     ("r4", mu_mojado, 6.0, base[1]), ("r5", mu_seco, 12.0, base[1]),
                                     ("r6", mu_mojado, 12.0, base[1]), ("r7", mu_mojado, base[0], 6.0),
                                     ("r8", mu_seco, base[0], 2.0)):
        cfg.mu, cfg.track_width, cfg.a_max = mu, ancho, a_max
        veces = n if nombre in ("seco", "mojado") else max(n // 3, 1)
        ok, prog, tiempos = 0, 0.0, []
        for k in range(veces):
            obs, info = env.reset(seed=SEMILLA_EVAL + k)
            done = False
            while not done:
                obs, _, term, trunc, info = env.step(a_mando(ACCIONES[politica(obs)], obs))
                done = term or trunc
            ok += info["outcome"] == "exito"
            prog += info["s_best"] / track.largo(info)
            if info["outcome"] == "exito":
                tiempos.append(info["t"])
        if nombre in ("seco", "mojado"):
            res[f"{nombre}_vueltas_pct"] = 100 * ok / veces
            res[f"{nombre}_progreso_pct"] = 100 * prog / veces
            res[f"{nombre}_tiempo_s"] = round(float(np.mean(tiempos)), 2) if tiempos else None
        else:
            robusto.append(100 * ok / veces)
    cfg.track_width, cfg.a_max = base
    res["robusto_vueltas_pct"] = round(float(np.mean(robusto)), 1)
    return res


def entrenar(env_fn, params, grabador=None, al_terminar_episodio=None, carpeta_punto="runs/qlearning-punto"):
    """Entrena en dos fases (DAgger y Q-learning). Devuelve el agente y la lista de resúmenes."""
    from rally.agentes.ppo import DominioAleatorio, RuidoSensores

    p = params
    version = vehiculos.version(p.get("vehiculo", "carro"))
    huella = hashlib.sha1(json.dumps([p, version, N_ESTADOS], sort_keys=True).encode()).hexdigest()[:16]
    punto = PuntoQ(carpeta_punto, huella)
    previo = punto.cargar()
    ag = AgenteQ(p["alpha"], p["gamma"], p["semilla"])
    cuentas = np.zeros((N_ESTADOS, len(ACCIONES)), dtype=np.float32)
    mejores_cuentas, tabla_mejor = cuentas.copy(), None
    # Avance: iteraciones de DAgger y episodios de Q-learning hechos, y lo mejor visto
    st = {"it": 0, "k": 0, "pasos": 0, "episodios": 0, "mejor": None, "metricas": None, "paso_mejor": 0}
    if previo:
        st = previo["estado"]
        cuentas, mejores_cuentas = previo["cuentas"], previo["mejores_cuentas"]
        ag.q, ag.visitas = previo["q"], previo["visitas"]
        tabla_mejor = previo["tabla_mejor"] if st["k"] > 0 else None   # la fase 2 la crea al empezar
        print(f"  Reanudando: DAgger {st['it']}/{p['dagger_iter']} · Q-learning {st['k']}/{p['episodios']}")
        mlflow.set_tag("reanudado", f"dagger {st['it']}, q {st['k']}")

    def guardar_punto():
        punto.guardar(st, cuentas=cuentas, mejores_cuentas=mejores_cuentas, q=ag.q, visitas=ag.visitas,
                      tabla_mejor=tabla_mejor if tabla_mejor is not None else np.zeros(1))

    # Otra semilla al reanudar: no se repiten los mismos episodios
    env = DominioAleatorio(env_fn(), p)
    if p.get("ruido_sensores"):
        env = RuidoSensores(env, p["ruido_sensores"])
    env.reset(seed=SEMILLA_BASE + p["semilla"] * 10_000 + st["episodios"])
    env_eval = env_fn()
    profe = maestro(p)
    rng = np.random.default_rng(p["semilla"] + st["episodios"])
    historia = []

    def imitada(s):
        fila = cuentas[s]
        return NEUTRA if not fila.any() else int(np.argmax(fila))

    def episodio(elegir, fase, valor, etiquetar=False, aprender=False):
        obs, info = env.reset()
        s, done, total = estado(obs), False, 0.0
        while not done:
            if etiquetar:
                cuentas[s, discreta(profe(obs, info))] += 1
            a = elegir(s, obs, info)
            mando = a_mando(ACCIONES[a], obs)
            obs, r, term, trunc, info = env.step(mando)
            s2 = estado(obs)
            if aprender:
                ag.aprender(s, a, r, s2, term)
            else:
                ag.visitas[s] += 1
            if grabador is not None:
                grabador.paso(obs, info, mando, r)
            s, total, done = s2, total + r, term or trunc
            st["pasos"] += 1
        st["episodios"] += 1
        res = {"episodio": st["episodios"], "recompensa": total, "resultado": info["outcome"], "tiempo": info["t"],
               "progreso": info["s_best"], "epsilon": valor, "pasos": st["pasos"], "fase": fase}
        if grabador is not None:
            grabador.fin(info, st["pasos"], {"epsilon": valor})
        historia.append(res)
        if al_terminar_episodio:
            al_terminar_episodio(res, ag)

    def revisar(politica, paso, prefijo):
        """Evalúa y dice si es lo mejor visto hasta ahora."""
        m = evaluar(politica, env_eval)
        mlflow.log_metrics({f"{prefijo}_{k}": v for k, v in m.items() if v is not None}, step=paso)
        print(f"  {prefijo} {paso}: seco {m['seco_vueltas_pct']:.0f}% · mojado {m['mojado_vueltas_pct']:.0f}%", flush=True)
        if st["mejor"] is not None and puntaje(m) <= st["mejor"]:
            return False
        st["mejor"], st["metricas"], st["paso_mejor"] = puntaje(m), m, paso
        return True

    # ---- Fase 1: imitación con DAgger
    while st["it"] < p["dagger_iter"]:
        it = st["it"]
        beta = 1.0 if it == 0 else max(0.0, 0.6 - 0.06 * (it - 1))   # probabilidad de que maneje el maestro
        for _ in range(p["dagger_episodios"]):
            episodio(lambda s, obs, info: discreta(profe(obs, info)) if rng.random() < beta else imitada(s),
                     "dagger", beta, etiquetar=True)
        st["it"] += 1
        if revisar(lambda o: imitada(estado(o)), st["it"], "dagger"):
            mejores_cuentas = cuentas.copy()
        guardar_punto()

    # ---- Fase 2: Q-learning desde la mejor imitación
    if tabla_mejor is None:
        total = mejores_cuentas.sum(1, keepdims=True)
        ag.q = np.where(total > 0, p["q_inicial"] * mejores_cuentas / np.maximum(total, 1), 0).astype(np.float32)
        tabla_mejor = ag.q.copy()
        st["paso_mejor"] = 0
    while st["k"] < p["episodios"]:
        k = st["k"]
        frac = k / max(p["episodios"] - 1, 1)
        eps = p["epsilon_inicial"] + (p["epsilon_final"] - p["epsilon_inicial"]) * frac
        episodio(lambda s, obs, info: ag.elegir(s, eps), "qlearning", eps, aprender=True)
        st["k"] += 1
        if st["k"] % p["eval_cada"] == 0:
            if revisar(lambda o: ag.mejor(estado(o)), st["k"], "q"):
                tabla_mejor = ag.q.copy()
            guardar_punto()
    ag.q = tabla_mejor
    mlflow.log_metrics({f"mejor_{k}": v for k, v in st["metricas"].items() if v is not None})
    mlflow.set_tag("mejor_episodio_qlearning", st["paso_mejor"])
    print(f"  Mejor tabla: episodio de Q-learning {st['paso_mejor']} · {st['metricas']}")
    punto.borrar()   # terminó: el punto de guardado ya no hace falta
    return ag, historia
