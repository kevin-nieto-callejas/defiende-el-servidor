# Scripts

Herramientas usadas durante la corrida final. Quedan como registro y para repetir las mediciones. Corren desde la
raíz del repositorio. Lo normal del proyecto se hace con los comandos `rally` y `dvc`; ver la
[guía](../docs/guias/empezar.md).

## analisis/

| Script | Para qué sirve |
|---|---|
| `malla.py` | Mide un piloto en las 35 combinaciones de deslizadores: `python scripts/analisis/malla.py ppo` |
| `maestros.py` | Prueba al piloto maestro con control de tracción. `policies.py` lo cita con su ruta anterior, `runs/` |
| `validar_historicos.py` | Comprueba que cada modelo viejo reproduzca sus resultados con adaptador |
| `medir_ppo_s0.py`, `medir_q8.py` | Miden la semilla 0 con la suite común |
| `unir_semillas.py` | Une resultados y calcula media y desviación |
| `registrar_finalistas.py` | Registra los modelos elegidos en MLflow |
| `ordenar_mlflow.py`, `ordenar_apagon.py` | Cierran runs interrumpidos y agregan hipótesis |

## operacion/

| Script | Para qué sirve |
|---|---|
| `cola.sh` | Cola de entrenamientos que sigue donde iba si se corta |
| `vigilante.sh` | Relanza servicios caídos y anota errores |
| `final.sh`, `semillas-q.sh`, `testfinal.sh` | Pasos finales de la corrida del 1 de noviembre |

Los scripts de `operacion/` esperan estar en `runs/` y usar `$HOME/code/defiende-el-servidor`: cópialos ahí y
ajusta la ruta antes de usarlos. Algunos pasos ya terminaron y `testfinal.sh` no debe repetirse.
