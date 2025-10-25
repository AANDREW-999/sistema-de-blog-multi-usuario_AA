"""Pruebas unitarias del módulo `gestor_datos`.

Cubre operaciones sobre CSV y JSON: inicialización, carga, guardado y
utilidades auxiliares, incluyendo casos de éxito y casos borde.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import src.Modulo.gestor_datos as gd

# -----------------------------
# Utilidades internas
# -----------------------------

def test_es_csv_y_es_json() -> None:
    """Reconoce extensiones .csv y .json correctamente."""
    assert gd._es_csv("/tmp/autores.csv") is True  # noqa: SLF001
    assert gd._es_csv("/tmp/posts.json") is False  # noqa: SLF001

    assert gd._es_json("/tmp/posts.json") is True  # noqa: SLF001
    assert gd._es_json("/tmp/autores.csv") is False  # noqa: SLF001


def test_campos_csv_para_autores_y_fallback(tmp_path: Path) -> None:
    """Devuelve cabeceras esperadas para autores y usa fallback en otros casos."""
    autores = gd._campos_csv_para(str(tmp_path / "autores.csv"))  # noqa: SLF001
    assert autores == gd.CAMPOS_AUTORES

    otros = gd._campos_csv_para(str(tmp_path / "otra_tabla.csv"))  # noqa: SLF001
    assert otros == gd.CAMPOS_AUTORES


def test_asegurar_directorio_crea_parent(tmp_path: Path) -> None:
    """Crea el directorio padre si no existe."""
    destino = tmp_path / "nested" / "archivo.csv"
    assert not destino.parent.exists()
    gd._asegurar_directorio(str(destino))  # noqa: SLF001
    assert destino.parent.exists()


def test_escritura_atomica_reemplaza_contenido(tmp_path: Path) -> None:
    """Escritura atómica reemplaza el contenido final del archivo."""
    archivo = tmp_path / "data.json"
    # Primera escritura
    gd._escritura_atomica(str(archivo), "[1]", modo_binario=False)  # noqa: SLF001
    assert json.loads(archivo.read_text(encoding="utf-8")) == [1]

    # Reemplazo
    gd._escritura_atomica(str(archivo), "[1, 2, 3]", modo_binario=False)  # noqa: SLF001
    assert json.loads(archivo.read_text(encoding="utf-8")) == [1, 2, 3]


# -----------------------------
# Inicialización
# -----------------------------

def test_inicializar_archivo_csv_crea_cabecera(tmp_path: Path) -> None:
    """Crea un CSV con las cabeceras de autores si no existe."""
    ruta = tmp_path / "autores.csv"
    gd.inicializar_archivo(str(ruta))
    assert ruta.exists()

    with ruta.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == gd.CAMPOS_AUTORES
        # No hay filas
        assert list(reader) == []

    # Segunda llamada no debe fallar ni reescribir
    gd.inicializar_archivo(str(ruta))
    with ruta.open("r", encoding="utf-8") as fh:
        contenido = fh.read()
    assert all(h in contenido for h in gd.CAMPOS_AUTORES)


def test_inicializar_archivo_json_crea_lista_vacia(tmp_path: Path) -> None:
    """Crea un JSON vacío (lista) si no existe."""
    ruta = tmp_path / "posts.json"
    gd.inicializar_archivo(str(ruta))
    assert ruta.exists()
    assert json.loads(ruta.read_text(encoding="utf-8")) == []


# -----------------------------
# Carga de datos
# -----------------------------

def test_cargar_datos_csv_vacio(tmp_path: Path) -> None:
    """Al cargar CSV recién inicializado, retorna lista vacía."""
    ruta = tmp_path / "autores.csv"
    gd.inicializar_archivo(str(ruta))
    datos = gd.cargar_datos(str(ruta))
    assert datos == []


def test_cargar_datos_json_invalido_retorna_lista_vacia(tmp_path: Path) -> None:
    """Si el JSON es inválido o no es una lista, retorna []."""
    ruta = tmp_path / "posts.json"
    # Escribimos JSON inválido
    ruta.write_text("{ no-json }", encoding="utf-8")
    datos = gd.cargar_datos(str(ruta))
    assert datos == []

    # Escribimos un objeto en lugar de lista
    ruta.write_text(json.dumps({"a": 1}), encoding="utf-8")
    datos = gd.cargar_datos(str(ruta))
    assert datos == []


# -----------------------------
# Guardado de datos
# -----------------------------

def test_guardar_y_cargar_csv_redondea_campos_y_convierte_a_str(tmp_path: Path) -> None:
    """Guarda solo cabeceras esperadas y convierte valores a str.

    También convierte None a cadena vacía en CSV.
    """
    ruta = tmp_path / "autores.csv"
    # Guardamos con una clave extra que no está en CAMPOS_AUTORES
    filas = [
        {
            "id_autor": 1,
            "nombre_autor": " Alice ",
            "email": "alice@example.com",
            "password_hash": None,
            "extra": "ignorar",
        }
    ]
    gd.guardar_datos(str(ruta), filas)

    # Cargar desde CSV debe tener solo las cabeceras conocidas, como str
    datos = gd.cargar_datos(str(ruta))
    assert datos == [
        {
            "id_autor": "1",
            "nombre_autor": "Alice",
            "email": "alice@example.com",
            "password_hash": "",
        }
    ]


def test_guardar_y_cargar_json(tmp_path: Path) -> None:
    """Guarda y carga una lista JSON preservando el contenido."""
    ruta = tmp_path / "posts.json"
    entrada = [
        {"id_post": 1, "titulo": "Hola"},
        {"id_post": 2, "titulo": "Mundo"},
    ]
    gd.guardar_datos(str(ruta), entrada)
    salida = gd.cargar_datos(str(ruta))
    assert salida == entrada


def test_guardar_y_cargar_en_formato_no_soportado_no_falla(tmp_path: Path) -> None:
    """Extensiones no soportadas no lanzan excepción

    y retornan lista vacía al cargar.
    """
    ruta = tmp_path / "datos.txt"
    # Guardar no debe fallar
    gd.guardar_datos(str(ruta), [{"a": 1}])
    # Cargar retorna []
    assert gd.cargar_datos(str(ruta)) == []
