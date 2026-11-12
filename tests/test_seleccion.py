"""Selección con criterios fijados y rollback."""
import json

import pytest

from rally import seleccion


def _eval(seco, mojado, t=78.0):
    return {"resultados": {"ppo": {"seco": {"vueltas_pct": seco, "tiempo_mediano_s": t},
                                   "mojado": {"vueltas_pct": mojado, "tiempo_mediano_s": 95.0}}}}


def _gen(valores):
    return {"pruebas": {k: {"referencia": "seco"} for k in valores} | {"informativa": {}},
            "resultados": {"ppo": {k: {"vueltas_pct": v} for k, v in valores.items()} | {"informativa": {"vueltas_pct": 0}}}}


def test_candidato_bueno_pasa():
    v = seleccion.decidir("x", "ppo", _eval(100, 100), _gen({"a": 100, "b": 90}))
    assert v["aceptado"] and v["valores"]["extremos_pct"] == 95


def test_una_prueba_muy_mala_rechaza_aunque_el_promedio_pase():
    v = seleccion.decidir("x", "ppo", _eval(100, 100), _gen({"a": 100, "b": 100, "c": 100, "d": 100, "e": 40}))
    assert not v["aceptado"] and not v["criterios"]["peor_prueba"]


def test_tiempo_en_seco_tiene_tope():
    assert not seleccion.decidir("x", "ppo", _eval(100, 100, t=85.0), _gen({"a": 100}))["criterios"]["tiempo_seco"]


def test_no_puede_perder_frente_al_recomendado():
    actual = {"resultados": {"seco": {"vueltas_pct": 100}, "mojado": {"vueltas_pct": 100}}}
    v = seleccion.decidir("x", "ppo", _eval(100, 98.5 - 1), _gen({"a": 100}), actual)
    assert not v["criterios"]["no_pierde_mojado"]


def test_rollback_restaura_la_anterior_y_lo_deja_en_el_historial(tmp_path, monkeypatch):
    monkeypatch.setattr(seleccion, "RECOMENDADO", tmp_path / "r.json")
    monkeypatch.setattr(seleccion, "HISTORIAL", tmp_path / "h.json")
    seleccion.promover("v4", "gana")
    seleccion.promover("v5", "gana")
    seleccion.volver("incidente")
    assert json.loads((tmp_path / "r.json").read_text())["modelo"] == "v4"
    assert [h["modelo"] for h in json.loads((tmp_path / "h.json").read_text())] == ["v4", "v5", "v4"]


def test_promover_dos_veces_no_duplica_el_historial(tmp_path, monkeypatch):
    monkeypatch.setattr(seleccion, "RECOMENDADO", tmp_path / "r.json")
    monkeypatch.setattr(seleccion, "HISTORIAL", tmp_path / "h.json")
    seleccion.promover("v4", "gana")
    seleccion.promover("v5", "gana")
    seleccion.promover("v5", "pipeline repetido")
    assert len(json.loads((tmp_path / "h.json").read_text())) == 2


def test_candidato_de_otra_semilla_usa_sus_resultados(tmp_path, monkeypatch):
    (tmp_path / "metrics").mkdir()
    criterios = seleccion.CRITERIOS.resolve()
    monkeypatch.setattr(seleccion, "CRITERIOS", criterios)
    monkeypatch.chdir(tmp_path)
    fila = {"vueltas_pct": 100, "tiempo_mediano_s": 70.0}
    (tmp_path / "metrics/evaluacion.json").write_text(json.dumps(_eval(100, 100)))
    (tmp_path / "metrics/generalizacion.json").write_text(json.dumps(_gen({"a": 100})))
    (tmp_path / "metrics/semillas.json").write_text(json.dumps(
        {"ppo-s1": {"seco": fila, "mojado": {**fila, "vueltas_pct": 90}, "a": fila, "informativa": fila}}))
    v = seleccion.evaluar_candidato("x", "ppo", 1)
    assert v["valores"]["tiempo_seco_s"] == 70.0 and not v["criterios"]["mojado"]


def test_rollback_sin_anterior_falla(tmp_path, monkeypatch):
    monkeypatch.setattr(seleccion, "RECOMENDADO", tmp_path / "r.json")
    monkeypatch.setattr(seleccion, "HISTORIAL", tmp_path / "h.json")
    seleccion.promover("v4", "gana")
    with pytest.raises(ValueError):
        seleccion.volver("incidente")


def test_rechazo_queda_anotado_sin_tocar_historial_ni_rollback(tmp_path, monkeypatch):
    for nombre in ("RECOMENDADO", "HISTORIAL", "DECISIONES"):
        monkeypatch.setattr(seleccion, nombre, tmp_path / f"{nombre}.json")
    seleccion.promover("a", "inicial")
    seleccion.promover("b", "mejor")
    malo = seleccion.decidir("c", "ppo", _eval(100, 100), _gen({"a": 100, "b": 0})) | {"tipo": "ppo"}
    seleccion.anotar(malo)
    seleccion.anotar(malo)   # repetir la misma evaluación no duplica
    d = json.loads((tmp_path / "DECISIONES.json").read_text(encoding="utf-8"))
    assert len(d) == 1 and d[0]["candidato"] == "c" and d[0]["aceptado"] is False
    assert seleccion.volver("prueba")["modelo"] == "a"   # el rollback sigue usando solo promociones


def test_manifiestos_tienen_todos_los_campos_del_enunciado():
    from pathlib import Path
    pide = ("run_id level_id environment_version git_commit config_sha256 model_uri model_sha256 "
            "normalization_uri runtime_ref evaluation_suite_id seed parent_run_id").split()
    for ruta in Path("manifests").glob("*-*.json"):
        m = json.loads(ruta.read_text(encoding="utf-8"))
        assert set(pide) <= set(m), ruta
        assert m["normalization_uri"] and m["parent_run_nota"], ruta   # parent_run_id nulo, pero explicado
