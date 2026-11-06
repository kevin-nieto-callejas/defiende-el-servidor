"""Las cinco transiciones de ejemplo de docs/ambiente-v0.1.md (circuito Mónaco).

Cada una trae el estado inicial, la acción y el resultado documentado en la
ficha. T1 se puede verificar a mano; las demás quedan como prueba de regresión:
si alguien cambia la física o la recompensa, `rally transiciones` y las pruebas
lo detectan.
"""

import math

from rally import track


def _en_pista(s, d=0.0, dpsi_deg=0.0):
    """Estado sobre la pista a la distancia s, desplazado d (m) a la izquierda."""
    x, y = track.point_at(s)
    h = track.heading_at(s)
    return dict(x=x - d * math.sin(h), y=y + d * math.cos(h), psi=h + math.radians(dpsi_deg))


def _inicio_curva(nombre):
    return float(next(s for s, n in zip(track.SS, track.NAMES) if n == nombre))


S_CP1 = track.GATES[0][0]
S_FAIRMONT = _inicio_curva("Fairmont")
N_PUERTAS = len(track.GATES)

TRANSICIONES = [
    {
        "id": "T1",
        "nombre": "Arranque en la línea de salida",
        "estado": _en_pista(0.0),
        "accion": (1.0, 0.0),
        "esperado": dict(recompensa=-0.096, next_cp=1, fin=None),
    },
    {
        "id": "T2",
        "nombre": "Cruce del CP1 (Beau Rivage)",
        "estado": {**_en_pista(S_CP1 - 1.0), "v": 20.0, "t": 14.0, "prev_action": (0.3, 0.0),
                   "s_cum": S_CP1 - 1.0},
        "accion": (0.3, 0.0),
        "esperado": dict(recompensa=10.150, next_cp=2, fin=None),
    },
    {
        "id": "T3",
        "nombre": "Horquilla de Fairmont demasiado rápido",
        "estado": {**_en_pista(S_FAIRMONT), "v": 15.0, "next_cp": 3, "t": 40.0,
                   "s_cum": S_FAIRMONT},
        "accion": (0.0, -1.0),
        "esperado": dict(recompensa=-0.101, next_cp=3, fin=None),
    },
    {
        "id": "T4",
        "nombre": "Choque contra el muro (zona de escape agotada)",
        "estado": {**_en_pista(100.0, d=4.5, dpsi_deg=25.0), "v": 12.0, "t": 6.0,
                   "prev_action": (0.5, 0.0), "s_cum": 100.0},
        "accion": (0.5, 0.0),
        "esperado": dict(recompensa=-51.05, next_cp=1, fin="choque"),
    },
    {
        "id": "T5",
        "nombre": "Cierre de vuelta en la meta",
        "estado": {**_en_pista(track.LAP - 1.0), "v": 16.0, "next_cp": N_PUERTAS, "t": 77.0,
                   "prev_action": (0.8, 0.0), "s_cum": track.LAP - 1.0},
        "accion": (1.0, 0.0),
        "esperado": dict(recompensa=50.04, next_cp=N_PUERTAS + 1, fin="exito"),
    },
]


def ejecutar(env, tr):
    """Corre una transición y devuelve (obs_inicial, recompensa, info)."""
    obs, _ = env.reset(options={"state": tr["estado"]})
    _, r, _, _, info = env.step(tr["accion"])
    return obs, r, info
