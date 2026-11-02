"""Mide PPO semilla 0 (v5) con la misma suite que las semillas 1 y 2, para compararlas sin sesgo."""
import json

from rally import semillas

if __name__ == "__main__":
    r = semillas.evaluar("ppo", "models/ppo/modelo.zip")
    json.dump(r, open("runs/logs/medir-ppo-s0.json", "w"), indent=1)
    cal = [c for c in r if c not in ("seco", "mojado")]
    print("seco", r["seco"]["vueltas_pct"], "lluvia", r["mojado"]["vueltas_pct"],
          "extremos", round(sum(r[c]["vueltas_pct"] for c in cal) / len(cal), 1), flush=True)
