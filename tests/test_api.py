"""Contrato de la API que usa la web: identidad del modelo, errores y evaluación por caso."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from rally import historicos  # noqa: E402
from rally.api import app  # noqa: E402
from rally.historicos import adaptar  # noqa: E402
from rally.env import AutonomousRallyEnv  # noqa: E402

cliente = TestClient(app)
disponibles = pytest.mark.skipif(not historicos.SALIDA.joinpath("catalogo.json").exists(), reason="sin manifiestos")


def test_salud_dice_que_version_se_sirve():
    r = cliente.get("/api/salud").json()
    assert r["estado"] == "ok" and r["ambiente"].startswith("0.4") and "commit" in r


def test_episodio_de_referencia_se_identifica_como_referencia():
    r = cliente.get("/api/episodio", params={"piloto": "maestro"}).json()
    assert r["modo"] == "referencia" and r["resultado"] == "exito" and r["modelo"] == "maestro"


def test_modelo_inexistente_es_error_y_no_un_episodio():
    assert cliente.get("/api/episodio", params={"piloto": "no-existe"}).status_code == 404
    assert cliente.post("/api/evaluar", json={"modelo": "no-existe"}).status_code == 404


def test_evaluacion_limita_el_presupuesto():
    assert cliente.post("/api/evaluar", json={"modelo": "maestro", "episodios": 500}).status_code == 422


def test_evaluacion_entrega_resultados_por_caso():
    r = cliente.post("/api/evaluar", json={"modelo": "maestro", "episodios": 2, "mu": 0.5}).json()
    assert [c["semilla"] for c in r["casos"]] == [0, 1]
    assert r["fallos_por_causa"] == {"exito": 2} and r["vueltas_pct"] == 100.0


def test_ruta_del_manifiesto_no_sale_de_la_carpeta():
    with pytest.raises(KeyError):
        historicos.manifiesto("../params")


def test_adaptador_entrega_rayos_de_la_familia_vieja():
    obs = AutonomousRallyEnv(r_max=20.0).reset(seed=0)[0]
    assert adaptar(obs, 24) is not None and adaptar(obs, 16).shape == (16,)
    assert adaptar(obs, 20)[6] == pytest.approx(obs[6] * 2)


@disponibles
def test_catalogo_marca_las_tablas_antiguas_como_evidencia():
    filas = {f["nombre"]: f for f in cliente.get("/api/modelos").json()["modelos"]}
    assert filas["qlearning-modelo-v1"]["ejecutable"] is False
    assert filas["ppo-modelo-v1"]["ejecutable"] is True
    assert len(filas["ppo-modelo-v4"]["model_sha256"]) == 64


def test_tabla_antigua_es_conflicto_y_no_un_fallo_del_servidor():
    """Las tablas anteriores a la v6 se muestran como evidencia: la API lo dice con 409."""
    assert cliente.get("/api/episodio", params={"piloto": "qlearning-modelo-v1"}).status_code == 409


def test_pista_por_defecto_es_monaco_y_ofrece_las_no_reservadas():
    r = cliente.get("/api/pista").json()
    assert r["pista"] == "monaco" and r["titulo"] == "Mónaco"
    assert [p["nombre"] for p in r["pistas"]] == ["monaco", "bosque", "puerto"]


def test_se_puede_pedir_otra_pista():
    a, b = cliente.get("/api/pista").json(), cliente.get("/api/pista", params={"pista": "bosque"}).json()
    assert b["pista"] == "bosque" and b["largo"] != a["largo"] and b["centro"] != a["centro"]


def test_episodio_y_evaluacion_corren_en_la_pista_pedida():
    ep = cliente.get("/api/episodio", params={"piloto": "maestro", "pista": "puerto"}).json()
    assert ep["pista"] == "puerto" and ep["params"]["pista"] == "puerto" and ep["resultado"] == "exito"
    ev = cliente.post("/api/evaluar", json={"modelo": "maestro", "episodios": 1, "pista": "bosque"}).json()
    assert ev["params"]["pista"] == "bosque" and ev["vueltas_pct"] == 100.0


def test_pista_reservada_y_desconocida_son_error():
    for ruta in ("/api/pista", "/api/episodio"):
        assert cliente.get(ruta, params={"piloto": "maestro", "pista": "sierra"}).status_code == 403
        assert cliente.get(ruta, params={"piloto": "maestro", "pista": "spa"}).status_code == 404
    assert cliente.post("/api/evaluar", json={"modelo": "maestro", "pista": "sierra"}).status_code == 403
