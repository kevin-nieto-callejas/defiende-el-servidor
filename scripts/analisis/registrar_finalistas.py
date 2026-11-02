"""Registra en MLflow los modelos elegidos y les pone el alias champion."""
import json
import warnings

warnings.filterwarnings("ignore")
import mlflow
from mlflow import MlflowClient

from rally import pipeline, seleccion
from rally.agentes import seguimiento

ELEGIDOS = (("ppo", "ppo-modelo-v5-s1", "finalistas/ppo-s1/modelo.zip"),
            ("qlearning", "qlearning-modelo-qlearning-v8-s1", "finalistas/qlearning-s1/q_table.npz"))

seguimiento.iniciar()
c = MlflowClient()
prueba = json.load(open("metrics/test-final.json"))["resultados"]
for tipo, nombre, pesos in ELEGIDOS:
    run_id = json.load(open(f"manifests/{nombre}.json"))["run_id"]
    with mlflow.start_run(run_id=run_id):
        version = pipeline._registrar_modelo(tipo, pesos, pipeline._ejemplo_obs())
        mlflow.set_tags({"decision": "aceptado", "level_id": "N3", "manifiesto": nombre})
        mlflow.log_metrics({f"test_final_{c_}_vueltas_pct": prueba[tipo][c_]["vueltas_pct"] for c_ in ("seco", "mojado")})
    modelo = seguimiento.MODELOS[tipo]
    c.set_registered_model_alias(modelo, "champion", version)
    print(modelo, "v" + str(version), "→ @champion", nombre)
