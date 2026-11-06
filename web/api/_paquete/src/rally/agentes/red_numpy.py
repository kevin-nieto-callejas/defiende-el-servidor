"""Red de PPO en numpy: la misma cuenta que hace PyTorch, sin PyTorch.

La API publicada en Vercel no puede cargar PyTorch: pesa más que el límite de una función.
`exportar` pasa la red de política de un modelo de Stable-Baselines3 a un .npz y comprueba,
antes de escribirlo, que numpy y PyTorch den las mismas acciones. `RedNumpy` es el piloto que
usa ese .npz. El .npz guarda el SHA-256 del modelo original, así la identidad del modelo
publicado sigue siendo la del manifiesto.

Solo se exporta lo que decide la acción en evaluación: extractor de la política y `action_net`.
El crítico y el `log_std` sirven para entrenar, no para manejar en modo determinista.
"""
import hashlib
from pathlib import Path

import numpy as np

ACTIVACIONES = {"Tanh": np.tanh, "ReLU": lambda x: np.maximum(x, 0.0)}
TOLERANCIA = 1e-5


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


class RedNumpy:
    """Política determinista: capas ocultas con activación y salida lineal, recortada a [low, high]."""

    def __init__(self, ruta):
        d = np.load(ruta, allow_pickle=False)
        self.n_capas = int(d["n_capas"])
        self.pesos = [(d[f"w{i}"], d[f"b{i}"]) for i in range(self.n_capas)]
        self.activacion = str(d["activacion"])
        self.f = ACTIVACIONES[self.activacion]
        self.n_obs = int(d["n_obs"])
        self.low, self.high = d["low"], d["high"]
        self.fuente_sha256 = str(d["fuente_sha256"])
        self.max_diferencia = float(d["max_diferencia"])

    def acciones(self, obs):
        """Lote de observaciones (n, n_obs) → acciones (n, n_acciones), en float32 como PyTorch."""
        x = np.asarray(obs, dtype=np.float32)
        for i, (w, b) in enumerate(self.pesos):
            x = x @ w.T + b
            if i < self.n_capas - 1:
                x = self.f(x)
        return np.clip(x, self.low, self.high)

    def __call__(self, obs):
        return self.acciones(np.asarray(obs, dtype=np.float32)[None, :])[0]


def _observaciones_de_prueba(n_obs, n_aleatorias, semilla):
    """Observaciones reales (vueltas del piloto maestro en seco y con lluvia) y aleatorias en [-1.5, 1.5]."""
    from rally import policies
    from rally.env import AutonomousRallyEnv
    from rally.historicos import adaptar

    reales = []
    for mu in (0.9, 0.5):
        env = AutonomousRallyEnv(mu=mu)
        obs, info = env.reset(seed=semilla)
        piloto = policies.crear("maestro", semilla)
        for _ in range(3000):
            reales.append(adaptar(obs, n_obs))
            obs, _, term, trunc, info = env.step(piloto(obs, info))
            if term or trunc:
                break
    rng = np.random.default_rng(semilla)
    aleatorias = rng.uniform(-1.5, 1.5, size=(n_aleatorias, n_obs)).astype(np.float32)
    return np.concatenate([np.asarray(reales, dtype=np.float32), aleatorias])


def exportar(ruta_zip, destino, n_aleatorias=5000, semilla=0, tolerancia=TOLERANCIA):
    """SB3 (.zip) → .npz. Falla si alguna acción difiere en más de `tolerancia`. Devuelve el resumen."""
    import torch.nn as nn
    from stable_baselines3 import PPO

    model = PPO.load(ruta_zip, device="cpu")
    pol = model.policy
    capas, activacion = [], None
    for m in pol.mlp_extractor.policy_net:
        if isinstance(m, nn.Linear):
            capas.append(m)
        else:
            activacion = type(m).__name__
    capas.append(pol.action_net)
    if activacion not in ACTIVACIONES:
        raise ValueError(f"activación {activacion} sin equivalente en numpy")
    if type(pol.features_extractor).__name__ != "FlattenExtractor":
        raise ValueError("solo se exportan políticas MLP con FlattenExtractor")

    n_obs = int(model.observation_space.shape[0])
    datos = {f"w{i}": c.weight.detach().cpu().numpy().astype(np.float32) for i, c in enumerate(capas)}
    datos |= {f"b{i}": c.bias.detach().cpu().numpy().astype(np.float32) for i, c in enumerate(capas)}
    datos |= {"n_capas": np.int64(len(capas)), "activacion": np.str_(activacion), "n_obs": np.int64(n_obs),
              "low": model.action_space.low.astype(np.float32), "high": model.action_space.high.astype(np.float32),
              "fuente_sha256": np.str_(sha256(ruta_zip))}

    obs = _observaciones_de_prueba(n_obs, n_aleatorias, semilla)
    esperadas, _ = model.predict(obs, deterministic=True)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + ".tmp.npz")
    np.savez(tmp, **datos, max_diferencia=np.float64(0.0))
    obtenidas = RedNumpy(tmp).acciones(obs)
    dif = float(np.max(np.abs(obtenidas - np.clip(esperadas, -1, 1))))
    tmp.unlink()
    if dif > tolerancia:
        raise ValueError(f"numpy y PyTorch no coinciden: diferencia {dif:.2e} > {tolerancia:.0e}")
    np.savez(destino, **datos, max_diferencia=np.float64(dif))
    return {"fuente_sha256": str(datos["fuente_sha256"]), "npz_sha256": sha256(destino), "n_obs": n_obs,
            "capas": [int(c.out_features) for c in capas], "activacion": activacion,
            "observaciones_probadas": int(len(obs)), "max_diferencia": dif}
