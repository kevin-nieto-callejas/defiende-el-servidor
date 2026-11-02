"""Mide la tabla actual con 100 semillas en toda la suite, sin correr DVC."""
import json

from rally import semillas

if __name__ == "__main__":
    r = semillas.evaluar("qlearning", "models/qlearning/q_table.npz")
    json.dump(r, open("runs/logs/medir-q8.json", "w"), indent=1)
    for c, m in r.items():
        print(f"{c:26s} {m['vueltas_pct']:6.1f}% t={m['tiempo_mediano_s']} prog={m['progreso_pct']}", flush=True)
    print("MEDIDO")
