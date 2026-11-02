"""Une la semilla 0 de cada agente a sus resultados y calcula media y desviación por condición."""
import json
from pathlib import Path

from rally.semillas import resumen

GRUPOS = {"ppo": ("metrics/semillas.json", "runs/logs/medir-ppo-s0.json"),
          "qlearning": ("metrics/semillas-qlearning.json", "runs/logs/medir-q8.json")}

salida = {}
for tipo, (ruta, cero) in GRUPOS.items():
    r = json.loads(Path(ruta).read_text(encoding="utf-8"))
    r[f"{tipo}-s0"] = json.loads(Path(cero).read_text(encoding="utf-8"))
    r = dict(sorted(r.items()))
    Path(ruta).write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    salida.update(resumen(r))
    print(tipo)
    for k, v in r.items():
        cal = [c for c in v if c not in ("seco", "mojado")]
        print(f"  {k}: seco {v['seco']['vueltas_pct']} {v['seco']['tiempo_mediano_s']} s · lluvia {v['mojado']['vueltas_pct']} "
              f"{v['mojado']['tiempo_mediano_s']} s · extremos {sum(v[c]['vueltas_pct'] for c in cal) / len(cal):.1f} · "
              f"peores {sorted((v[c]['vueltas_pct'], c) for c in cal)[:3]}")
    m = salida[tipo]
    print(f"  media seco {m['seco']['media_pct']} ± {m['seco']['desviacion_pct']} · lluvia {m['mojado']['media_pct']} ± {m['mojado']['desviacion_pct']}")
Path("metrics/semillas-resumen.json").write_text(json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")
