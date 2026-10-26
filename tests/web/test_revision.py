"""Revisión de código: concurrencia real, corridas inmutables, búsqueda, esquema, detalles."""

from __future__ import annotations

import socket
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core.config import settings
from app.db.modelos import Finca, Paradero, Persona, TipoBus, Usuario
from tests.web.conftest import CLAVE, Api

RAIZ = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------ 1. concurrencia REAL (uvicorn + httpx)
@pytest.fixture
def servidor(tmp_path):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
    s.close()
    app = create_app(db_url=f"sqlite:///{(tmp_path / 'c.db').as_posix()}", logs_dir=tmp_path / "logs",
                     frontend_dist=tmp_path / "no")
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning"))
    hilo = threading.Thread(target=srv.run, daemon=True)
    hilo.start()
    while not srv.started:
        time.sleep(0.05)
    yield SimpleNamespace(app=app, url=f"http://127.0.0.1:{puerto}", api=Api(app, tmp_path))
    srv.should_exit = True
    hilo.join(15)


def test_peticiones_simultaneas_no_dan_database_is_locked(servidor):
    api, n = servidor.api, 8
    api.crear_usuario("ana", "admin")
    with api.db() as db:
        f = [Finca(nombre=f"F{i}", lat=4.80 + i * 0.001, lon=-74.24) for i in range(n)]
        p = [Paradero(nombre=f"P{i}", lat=4.81 + i * 0.001, lon=-74.25) for i in range(n)]
        db.add_all([*f, *p, TipoBus(tipo="BUS", capacidad=40, costo=100)])
        db.flush()
        db.add_all([Persona(identificacion=str(i), nombre="x", finca_id=f[i].id, paradero_id=p[i].id)
                    for i in range(n)])
        db.commit()
        fincas = [x.id for x in f]
    estados, barrera = [], threading.Barrier(n)

    def trabajo(i):
        c = httpx.Client(base_url=servidor.url, headers={"Origin": servidor.url}, timeout=120)
        assert c.post("/api/auth/login", json={"usuario": "ana", "clave": CLAVE}).status_code == 200
        barrera.wait()
        for k in range(5):
            estados.append(c.patch(f"/api/fincas/{fincas[i]}", json={"nombre": f"F{i}-{k}"}).status_code)
        for _ in range(3):
            estados.append(c.get("/api/fincas").status_code)
        estados.append(c.post("/api/simulador/ejecutar").status_code)
        estados.append(c.post("/api/fincas", json={"nombre": f"N{i}", "lat": 1, "lon": 1}).status_code)

    hilos = [threading.Thread(target=trabajo, args=(i,)) for i in range(n)]
    [h.start() for h in hilos]
    [h.join(180) for h in hilos]
    assert len(estados) == n * 10
    assert sorted(set(estados)) == [200, 201], [e for e in estados if e >= 500]
    assert "database is locked" not in api.log()


# ------------------------------------------------------------ datos fabricados
def _datos(admin, finca="F", personas=(("a", 0.0), ("b", 0.0), ("c", 0.0)), capacidad=40, costo=100):
    """Una finca y un paradero por grupo de personas; ``dlat`` desplaza el paradero (0.09 ≈ 10 km)."""
    f = admin.post("/api/fincas", json={"nombre": finca, "lat": 4.80, "lon": -74.24}).json()["id"]
    admin.post("/api/tipos-bus", json={"tipo": "BUS", "capacidad": capacidad, "costo": costo})
    paraderos = {}
    for ident, dlat in personas:
        if dlat not in paraderos:
            paraderos[dlat] = admin.post("/api/paraderos", json={"nombre": f"P{dlat}", "lat": 4.80 + dlat,
                                                                 "lon": -74.24}).json()["id"]
        admin.post("/api/personas", json={"identificacion": ident, "nombre": ident, "finca_id": f,
                                          "paradero_id": paraderos[dlat]})
    return f, paraderos


# ------------------------------------------------------------ 3. corridas inmutables
def test_corrida_es_un_snapshot_inmutable(admin):
    f, par = _datos(admin, personas=(("a", 0.01), ("b", 0.01), ("c", 0.02)))
    c = admin.post("/api/simulador/ejecutar").json()
    assert c["rutas"][0]["finca_nombre"] == "F"
    assert all({"id", "nombre", "lat", "lon"} <= set(p) for r in c["rutas"] for p in r["paraderos"])
    admin.patch(f"/api/paraderos/{par[0.01]}", json={"nombre": "Renombrado", "lat": 5.5})
    personas = admin.get("/api/personas", params={"q": "c"}).json()["items"]
    admin.delete(f"/api/personas/{personas[0]['id']}")
    assert admin.delete(f"/api/paraderos/{par[0.02]}").status_code == 204
    admin.patch(f"/api/fincas/{f}", json={"nombre": "Otra finca"})
    assert admin.get(f"/api/corridas/{c['id']}").json() == c


def test_corrida_con_formato_viejo_se_lee_de_la_tabla_viva(api, admin):
    from app.db.modelos import Corrida, CorridaRuta

    f, par = _datos(admin)
    with api.db() as db:
        uid = db.query(Usuario).first().id
        db.add(Corrida(usuario_id=uid, parametros={}, resumen={}, rutas=[CorridaRuta(
            ruta_simulada=1, finca_id=f, paraderos=[par[0.0]], personas=3, km=1.0, minutos_max=2.0,
            tipo_bus="BUS", capacidad=40, buses=1, costo_total=100)]))
        db.commit()
    r = admin.get("/api/corridas/1").json()["rutas"][0]
    assert r["paraderos"] == [{"id": par[0.0], "nombre": "P0.0", "lat": 4.8, "lon": -74.24}]
    assert r["finca_nombre"] == "F"


# ------------------------------------------------------------ 4. comparación y advertencias
FIJAS = (("Comparación orientativa: la red actual se calcula como la suma de las tarifas REGULAR suponiendo un "
          "bus por fila de tarifa; no está confirmado con el proveedor."),
         "Distancias en línea recta (haversine); el recorrido real por carretera es mayor.")


def _parametros(api, **kv):
    from app.db.modelos import Parametro

    with api.db() as db:
        for k, v in kv.items():
            db.merge(Parametro(clave=k, valor=str(v)))
        db.commit()


def test_diferencia_pct_y_advertencias_fijas(api, admin):
    _datos(admin)
    r = admin.post("/api/simulador/ejecutar").json()["resumen"]
    assert r["costo_red_actual"] is None and r["diferencia_pct"] is None  # sin red actual
    assert list(FIJAS) == r["advertencias"][:2]
    _parametros(api, costo_red_actual=200)
    r = admin.post("/api/simulador/ejecutar").json()["resumen"]
    assert (r["costo_total"], r["costo_red_actual"], r["diferencia_pct"]) == (100, 200, -50.0)


def test_diferencia_pct_nula_sin_rutas(api, admin):
    _datos(admin, personas=(("a", 1.0),))  # a ~111 km: sin servicio
    _parametros(api, costo_red_actual=200)
    r = admin.post("/api/simulador/ejecutar").json()["resumen"]
    assert r["rutas"] == 0 and r["costo_red_actual"] == 200 and r["diferencia_pct"] is None


@pytest.mark.parametrize("que", ["persona", "finca", "bus", "paradero"])
def test_diferencia_pct_nula_con_inactivos(api, admin, que):
    _datos(admin, personas=(("a", 0.0), ("b", 0.0), ("c", 0.01)))
    admin.post("/api/tipos-bus", json={"tipo": "OTRO", "capacidad": 10, "costo": 999})
    _parametros(api, costo_red_actual=1000)
    if que == "persona":
        admin.patch(f"/api/personas/{admin.get('/api/personas').json()['items'][0]['id']}", json={"activo": False})
    elif que == "finca":
        f2 = admin.post("/api/fincas", json={"nombre": "G", "lat": 4.9, "lon": -74.2}).json()["id"]
        admin.patch(f"/api/fincas/{f2}", json={"activo": False})
    elif que == "bus":
        admin.patch(f"/api/tipos-bus/{admin.get('/api/tipos-bus').json()['items'][1]['id']}", json={"activo": False})
    else:
        p2 = admin.post("/api/paraderos", json={"nombre": "Z", "lat": 4.9, "lon": -74.2}).json()["id"]
        admin.patch(f"/api/paraderos/{p2}", json={"activo": False})
    r = admin.post("/api/simulador/ejecutar").json()["resumen"]
    assert r["diferencia_pct"] is None and r["costo_red_actual"] == 1000
    assert any("inactivos" in a for a in r["advertencias"])


def test_advertencias_del_maestro_y_duplicados(api, admin):
    _datos(admin)
    _parametros(api, maestro_personas_total=1160, maestro_personas_simuladas=415, duplicados_filas=58,
                duplicados_paraderos_distintos=18, regla_duplicados="ultima")
    a = admin.post("/api/simulador/ejecutar").json()["resumen"]["advertencias"]
    assert "Solo 415 de 1160 personas del maestro cruzan con el catálogo de rutas (35,8 %); " \
           "las demás no se simularon." in a
    assert "18 personas tienen identificación repetida con paraderos distintos; se usó la regla ultima." in a


# ------------------------------------------------------------ simulación: parámetros y activos
def test_simulacion_respeta_parametros_discriminante(admin):
    _datos(admin, personas=(("a", 0.09), ("b", 0.09)))  # paradero a ~10 km de la finca
    base = admin.post("/api/simulador/ejecutar").json()
    assert (base["resumen"]["personas"], base["resumen"]["personas_sin_servicio"]) == (2, 0)
    # 10 km/h * 30 min = 5 km: el paradero queda fuera de alcance
    c = admin.post("/api/simulador/ejecutar", json={"velocidad_kmh": 10, "tiempo_max_min": 30}).json()
    assert c["parametros"] == {"velocidad_kmh": 10, "tiempo_max_min": 30}
    assert (c["resumen"]["personas"], c["resumen"]["personas_sin_servicio"], c["resumen"]["rutas"]) == (0, 2, 0)


def test_simulacion_ignora_inactivos(admin):
    f, _ = _datos(admin, personas=(("a", 0.0), ("b", 0.0), ("c", 0.01)))
    personas = {p["identificacion"]: p["id"] for p in admin.get("/api/personas").json()["items"]}
    assert admin.post("/api/simulador/ejecutar").json()["resumen"]["personas"] == 3
    admin.patch(f"/api/personas/{personas['c']}", json={"activo": False})  # persona inactiva
    assert admin.post("/api/simulador/ejecutar").json()["resumen"]["personas"] == 2
    admin.patch(f"/api/fincas/{f}", json={"activo": False})  # finca inactiva: nadie que simular
    r = admin.post("/api/simulador/ejecutar")
    assert r.status_code == 422 and "finca" in r.json()["error"]["mensaje"]


def test_simulacion_ignora_bus_inactivo(admin):
    _datos(admin, costo=100)
    caro = admin.post("/api/tipos-bus", json={"tipo": "CARO", "capacidad": 40, "costo": 500}).json()["id"]
    barato = admin.get("/api/tipos-bus").json()["items"][0]["id"]
    assert admin.post("/api/simulador/ejecutar").json()["resumen"]["costo_total"] == 100
    admin.patch(f"/api/tipos-bus/{barato}", json={"activo": False})
    assert admin.post("/api/simulador/ejecutar").json()["resumen"]["costo_total"] == 500
    admin.patch(f"/api/tipos-bus/{caro}", json={"activo": False})
    r = admin.post("/api/simulador/ejecutar")
    assert r.status_code == 422 and "tipos de bus" in r.json()["error"]["mensaje"]


# ------------------------------------------------------------ 5. búsqueda sin tildes ni mayúsculas
@pytest.mark.parametrize("q", ["peñalisa", "PEÑALISA", "penalisa", "PENALISA", "Peñ"])
def test_busqueda_insensible_a_mayusculas_y_tildes(admin, q):
    admin.post("/api/fincas", json={"nombre": "Peñalisa", "lat": 1, "lon": 1})
    admin.post("/api/fincas", json={"nombre": "Otra", "lat": 1, "lon": 1})
    assert [x["nombre"] for x in admin.get("/api/fincas", params={"q": q}).json()["items"]] == ["Peñalisa"]


@pytest.mark.parametrize("q", ["árbol", "ARBOL", "arbol", "ÁRB"])
def test_busqueda_arbol(admin, q):
    admin.post("/api/fincas", json={"nombre": "El Árbol", "lat": 1, "lon": 1})
    assert admin.get("/api/fincas", params={"q": q}).json()["total"] == 1


def test_busqueda_trata_comodines_como_texto(admin):
    admin.post("/api/fincas", json={"nombre": "Alta", "lat": 1, "lon": 1})
    assert admin.get("/api/fincas", params={"q": "%"}).json()["total"] == 0


# ------------------------------------------------------------ 6. eventos: hasta inclusivo al segundo
def test_hasta_con_timestamp_mostrado_incluye_el_evento(admin):
    admin.post("/api/fincas", json={"nombre": "F", "lat": 1, "lon": 1})
    ev = admin.get("/api/eventos", params={"accion": "crear"}).json()["items"][0]
    assert ev["fecha"].endswith("Z") and "." not in ev["fecha"]
    for hasta in (ev["fecha"], ev["fecha"][:-1], ev["fecha"][:-1] + "+00:00"):
        assert admin.get("/api/eventos", params={"hasta": hasta, "accion": "crear"}).json()["total"] == 1, hasta
    assert admin.get("/api/eventos", params={"desde": ev["fecha"], "accion": "crear"}).json()["total"] >= 0


# ------------------------------------------------------------ 7. cambiar la propia clave
def test_cambiar_la_propia_clave_conserva_la_sesion_actual(api, admin):
    otra = api.cliente("ana")  # segunda sesión del mismo usuario
    uid = admin.get("/api/auth/yo").json()["id"]
    assert admin.patch(f"/api/usuarios/{uid}", json={"clave": "clave-nueva-muy-larga-7"}).status_code == 200
    assert admin.get("/api/auth/yo").status_code == 200  # la actual sigue
    assert otra.get("/api/auth/yo").status_code == 401  # las demás se revocan
    assert api.cliente("ana", "clave-nueva-muy-larga-7").get("/api/auth/yo").status_code == 200


# ------------------------------------------------------------ 8. base de una versión anterior
def test_arranque_falla_con_mensaje_claro_si_falta_una_columna(tmp_path):
    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, usuario VARCHAR(60))")
    con.commit()
    con.close()
    app = create_app(db_url=f"sqlite:///{ruta.as_posix()}", logs_dir=tmp_path / "l", hosts=["testserver"])
    with pytest.raises(RuntimeError, match=r"usuarios\.clave_hash"), TestClient(app):
        pass


def test_arranque_falla_con_columna_obsoleta_obligatoria(tmp_path):
    ruta = tmp_path / "vieja2.db"
    app = create_app(db_url=f"sqlite:///{ruta.as_posix()}", logs_dir=tmp_path / "l", hosts=["testserver"])
    with TestClient(app):
        pass
    con = sqlite3.connect(ruta)
    con.execute("ALTER TABLE usuarios ADD COLUMN intentos_fallidos INTEGER NOT NULL DEFAULT 0")
    con.commit()
    con.close()
    with TestClient(app):  # con valor por defecto no estorba
        pass
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA foreign_keys=OFF")
    con.executescript("""DROP TABLE usuarios; CREATE TABLE usuarios (id INTEGER PRIMARY KEY, usuario VARCHAR(60),
        nombre VARCHAR(200), clave_hash VARCHAR(300), rol VARCHAR(10), activo BOOLEAN, creado DATETIME,
        intentos_fallidos INTEGER NOT NULL);""")
    con.close()
    with pytest.raises(RuntimeError, match="intentos_fallidos"), TestClient(app):
        pass


def test_salud_devuelve_503_si_la_base_no_responde(api, anon):
    con = sqlite3.connect(api.tmp / "test.db")
    con.execute("PRAGMA foreign_keys=OFF")
    con.executescript("DROP TABLE usuarios")
    con.close()
    r = anon.get("/api/salud")
    assert r.status_code == 503 and r.json()["base_datos"] == "error" and r.json()["estado"] != "ok"


def test_usuarios_sin_columnas_muertas():
    assert not hasattr(Usuario, "intentos_fallidos") and not hasattr(Usuario, "bloqueado_hasta")


# ------------------------------------------------------------ 9. detalles
def test_json_malformado_usa_campo_body(admin):
    r = admin.post("/api/fincas", content=b"{no es json", headers={"Content-Type": "application/json"})
    e = r.json()["error"]
    assert r.status_code == 422 and e["codigo"] == "VALIDACION"
    assert [d["campo"] for d in e["detalle"]] == ["body"]


def test_host_no_permitido_lleva_request_id(anon):
    r = anon.get("/api/salud", headers={"Host": "evil.example"})
    assert r.status_code == 400 and len(r.headers["X-Request-ID"]) >= 8
    assert r.json()["error"]["request_id"] == r.headers["X-Request-ID"]


def test_crear_admin_rechaza_nombre_en_blanco(tmp_path):
    env = {**__import__("os").environ, "TRANSPORTE_DB_URL": f"sqlite:///{(tmp_path / 'ca.db').as_posix()}"}
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "crear_admin.py"), "bob", "--nombre", "   ",
                        "--clave-stdin"], input="clave-de-prueba-123\n", capture_output=True, text=True, env=env,
                       cwd=RAIZ, check=False)
    assert r.returncode == 2 and "nombre" in r.stderr.lower()
    assert not (tmp_path / "ca.db").exists()


def test_paraderos_duplicados_con_coordenadas_redondeadas(admin):
    assert admin.post("/api/paraderos", json={"nombre": "P", "lat": 4.7, "lon": -74.3}).status_code == 201
    assert admin.post("/api/paraderos", json={"nombre": "P", "lat": 4.70000001, "lon": -74.3}).status_code == 409
    otro = admin.post("/api/paraderos", json={"nombre": "P", "lat": 4.8, "lon": -74.3}).json()["id"]
    assert admin.patch(f"/api/paraderos/{otro}", json={"lat": 4.700000004}).status_code == 409


def test_cod_nivel2_unico_pero_varios_nulos(admin):
    cuerpo = {"lat": 1, "lon": 1, "cod_nivel2": 86}
    assert admin.post("/api/fincas", json={**cuerpo, "nombre": "A"}).status_code == 201
    assert admin.post("/api/fincas", json={**cuerpo, "nombre": "B"}).status_code == 409
    assert admin.post("/api/fincas", json={"nombre": "C", "lat": 1, "lon": 1}).status_code == 201
    assert admin.post("/api/fincas", json={"nombre": "D", "lat": 1, "lon": 1}).status_code == 201


# ------------------------------------------------------------ mejoras: config y sin efectos al importar
def test_parametros_en_config():
    assert (settings.milp_tiempo_limite_s, settings.milp_semillas, settings.milp_vecinos) == (60, 200, 6)
    assert settings.regla_duplicados == "ultima" and settings.puerto == 8000
    assert settings.por_pagina_defecto == 50 and settings.por_pagina_max == 200
    assert settings.kml_file.name == "fincas_sunshine.kml"


def test_importar_el_modulo_no_crea_carpetas(tmp_path):
    env = {**__import__("os").environ, "TRANSPORTE_DB_URL": f"sqlite:///{(tmp_path / 'sub' / 'x.db').as_posix()}",
           "TRANSPORTE_LOGS_DIR": str(tmp_path / "logs")}
    r = subprocess.run([sys.executable, "-c", "import app.api.main"], capture_output=True, text=True, env=env,
                       cwd=RAIZ, check=False)
    assert r.returncode == 0, r.stderr
    assert not (tmp_path / "sub").exists() and not (tmp_path / "logs").exists()


def test_sin_servicio_trae_snapshot_y_fallback_a_la_tabla_viva(api, admin):
    from app.db.modelos import Corrida, CorridaSinServicio

    f, par = _datos(admin, personas=(("a", 0.0), ("b", 1.0)))  # b queda a ~111 km: sin servicio
    c = admin.post("/api/simulador/ejecutar").json()
    s = c["sin_servicio"][0]
    assert s["paradero_nombre"] == "P1.0" and (s["lat"], s["lon"]) == (5.8, -74.24) and s["finca_nombre"] == "F"
    admin.patch(f"/api/paraderos/{par[1.0]}", json={"nombre": "Otro", "lat": 6.0})
    admin.patch(f"/api/fincas/{f}", json={"nombre": "G"})
    assert admin.get(f"/api/corridas/{c['id']}").json()["sin_servicio"] == c["sin_servicio"]
    with api.db() as db:  # formato viejo: sin snapshot -> tabla viva
        uid = db.query(Usuario).first().id
        db.add(Corrida(usuario_id=uid, parametros={}, resumen={}, sin_servicio=[
            CorridaSinServicio(finca_id=f, paradero_id=par[1.0], personas=1),
            CorridaSinServicio(finca_id=999, paradero_id=998, personas=1)]))
        db.commit()
    viejo = admin.get("/api/corridas/2").json()["sin_servicio"]
    assert (viejo[0]["paradero_nombre"], viejo[0]["lat"], viejo[0]["finca_nombre"]) == ("Otro", 6.0, "G")
    assert (viejo[1]["paradero_nombre"], viejo[1]["lat"], viejo[1]["finca_nombre"]) == (None, None, None)
