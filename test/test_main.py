# -*- coding: utf-8 -*-
"""
Pruebas unitarias para funciones lógicas de src/Modulo/main.py.

Cubre utilidades no interactivas:
- Hash y verificación de contraseñas (_hash_password, _verify_password)
- Carga y normalización de posts (_cargar_todos_los_posts)
- Recolección y orden de tags (_recolectar_tags_conteo)
- Obtención de posts y comentarios propios
- Resolución de nombre de autor por ID (nombre_autor)

Las pruebas usan un directorio temporal para no afectar data real.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Asegurar que los módulos del proyecto sean importables desde src/Modulo
MODULE_DIR = Path(__file__).resolve().parents[1] / "src" / "Modulo"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from src.Modulo import gestor_datos  # noqa: E402  (después de ajustar sys.path)


def _load_main_module() -> Any:
    """
    Carga src/Modulo/main.py dinámicamente y retorna el módulo.

    Se evita depender de que 'src' sea un paquete instalable.
    """
    module_path = MODULE_DIR / "main.py"
    spec = importlib.util.spec_from_file_location(
        "main_under_test",
        str(module_path),
    )
    assert spec and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


@pytest.fixture
def main_mod(tmp_path: Path) -> Any:
    """
    Devuelve el módulo main cargado y preparado para usar un data temporal.
    """
    mod = _load_main_module()

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    posts = str(data_dir / "posts.json")
    autores = str(data_dir / "autores.csv")

    setattr(mod, "POSTS_JSON", posts)
    setattr(mod, "AUTORES_CSV", autores)

    gestor_datos.inicializar_archivo(posts)
    gestor_datos.inicializar_archivo(autores)

    return mod


def test_hash_and_verify_password_basic(main_mod: Any) -> None:
    """
    _hash_password debe producir 'salt$hash' y _verify_password validar
    correcto/incorrecto.
    """
    pwd = "secreto123"
    stored = main_mod._hash_password(pwd)
    assert isinstance(stored, str)
    assert "$" in stored
    assert main_mod._verify_password(stored, pwd)
    assert not main_mod._verify_password(stored, "otra")


def test_verify_password_malformed_returns_false(main_mod: Any) -> None:
    """
    _verify_password debe retornar False si 'stored' no contiene separador.
    """
    assert not main_mod._verify_password("sin_separador", "pwd")


def _sample_posts_for_tags() -> List[Dict[str, Any]]:
    """
    Construye posts de ejemplo con tags variados para probar conteos.
    """
    return [
        {
            "id_post": "1",
            "id_autor": "10",
            "titulo": "Post A",
            "contenido": "Contenido A",
            "fecha_publicacion": "2025-01-01 00:00:00",
            "tags": ["python", "dev"],
            "comentarios": [],
        },
        {
            "id_post": "2",
            "id_autor": "11",
            "titulo": "Post B",
            "contenido": "Contenido B",
            "fecha_publicacion": "2025-01-02 00:00:00",
            "tags": ["python", "tutorial"],
            "comentarios": [],
        },
        {
            "id_post": "3",
            "id_autor": "10",
            "titulo": "Post C",
            "contenido": "Contenido C",
            "fecha_publicacion": "2025-01-03 00:00:00",
            "tags": ["Dev", "misc"],
            "comentarios": [],
        },
    ]


def test_cargar_todos_los_posts_normaliza_estructura(main_mod: Any) -> None:
    """
    _cargar_todos_los_posts debe asegurar 'tags' y 'comentarios' como listas.
    """
    posts = _sample_posts_for_tags()
    gestor_datos.guardar_datos(main_mod.POSTS_JSON, posts)

    loaded = main_mod._cargar_todos_los_posts()
    ESPERADOS = 3
    assert isinstance(loaded, list)
    assert len(loaded) == ESPERADOS
    for p in loaded:
        assert isinstance(p.get("tags"), list)
        assert isinstance(p.get("comentarios"), list)


def test_recolectar_tags_conteo_y_orden(main_mod: Any) -> None:
    """
    _recolectar_tags_conteo debe ordenar por frecuencia desc y luego alfabético.
    """
    posts = _sample_posts_for_tags()
    posts.append(
        {
            "id_post": "4",
            "id_autor": "12",
            "titulo": "Post D",
            "contenido": "Contenido D",
            "fecha_publicacion": "2025-01-04 00:00:00",
            "tags": ["misc", "python"],
            "comentarios": [],
        }
    )
    gestor_datos.guardar_datos(main_mod.POSTS_JSON, posts)

    tags_conteo = main_mod._recolectar_tags_conteo()
    mapa = {t: c for t, c in tags_conteo}
    PYTHON_COUNT = 3
    MISC_COUNT = 2
    assert mapa.get("python", 0) == PYTHON_COUNT
    assert mapa.get("misc", 0) == MISC_COUNT
    assert tags_conteo[0][0].lower() == "python"


def test_obtener_mis_posts_sin_sesion_devuelve_lista_vacia(
    main_mod: Any,
) -> None:
    """
    _obtener_mis_posts debe devolver [] si no hay sesión activa.
    """
    main_mod.Sesion.limpiar()
    assert main_mod._obtener_mis_posts() == []


def test_recolectar_mis_comentarios_y_mis_posts(main_mod: Any) -> None:
    """
    Con sesión, _recolectar_mis_comentarios filtra por id_autor y
    _obtener_mis_posts devuelve solo posts del autor en sesión.
    """
    posts = [
        {
            "id_post": "10",
            "id_autor": "99",
            "titulo": "Mi post",
            "contenido": "Contenido",
            "fecha_publicacion": "2025-01-01 00:00:00",
            "tags": ["x"],
            "comentarios": [
                {
                    "id_comentario": "100",
                    "autor": "Autor99",
                    "contenido": "Mi comentario",
                    "fecha": "2025-01-01 01:00:00",
                    "id_autor": "99",
                }
            ],
        },
        {
            "id_post": "11",
            "id_autor": "20",
            "titulo": "Otro post",
            "contenido": "Contenido2",
            "fecha_publicacion": "2025-01-02 00:00:00",
            "tags": ["y"],
            "comentarios": [
                {
                    "id_comentario": "101",
                    "autor": "Autor20",
                    "contenido": "Comentario ajeno",
                    "fecha": "2025-01-02 01:00:00",
                    "id_autor": "20",
                }
            ],
        },
    ]
    gestor_datos.guardar_datos(main_mod.POSTS_JSON, posts)

    main_mod.Sesion.establecer(
        {"id_autor": "99", "nombre_autor": "Test", "email": "t@test"}
    )
    try:
        mis_coms = main_mod._recolectar_mis_comentarios()
        assert isinstance(mis_coms, list)
        assert any(
            c["id_comentario"] == "100" and c["id_post"] == "10"
            for c in mis_coms
        )

        mis_posts = main_mod._obtener_mis_posts()
        assert isinstance(mis_posts, list)
        assert any(p["id_post"] == "10" for p in mis_posts)
        assert all(str(p["id_autor"]) == "99" for p in mis_posts)
    finally:
        main_mod.Sesion.limpiar()


def test_nombre_autor_con_indice(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    nombre_autor devuelve el nombre si existe, o 'Autor #<id>' si no existe.
    """
    mod = _load_main_module()

    def _fake_index():
        return {"5": {"id_autor": "5", "nombre_autor": "Alice", "email": "a@x"}}

    monkeypatch.setattr(mod, "cargar_autores_indexado", _fake_index)
    assert mod.nombre_autor("5") == "Alice"
    assert mod.nombre_autor("999") == "Autor #999"


# -------------------------
# PRUEBAS ADICIONALES (13)
# -------------------------

def test_tabla_tags_estructura_y_datos(main_mod: Any) -> None:
    posts = _sample_posts_for_tags()
    gestor_datos.guardar_datos(main_mod.POSTS_JSON, posts)
    tags_conteo = main_mod._recolectar_tags_conteo()
    tabla = main_mod._tabla_tags(tags_conteo)
    assert hasattr(tabla, "columns")
    assert tabla.row_count == len(tags_conteo)
    headers = [col.header for col in tabla.columns]
    assert headers == ["Tag", "Usos"]


def test_render_post_twitter_no_explode_con_y_sin_comentarios(
    main_mod: Any,
) -> None:
    post1 = {
        "id_post": "100",
        "id_autor": "50",
        "titulo": "Titulo X",
        "contenido": "Contenido X",
        "fecha_publicacion": "2025-01-01 10:00:00",
        "tags": ["x"],
        "comentarios": [],
    }
    post2 = {
        "id_post": "101",
        "id_autor": "51",
        "titulo": "Titulo Y",
        "contenido": "Contenido Y",
        "fecha_publicacion": "2025-01-02 11:00:00",
        "tags": ["y"],
        "comentarios": [
            {
                "id_comentario": "1",
                "autor": "A",
                "contenido": "Hola",
                "fecha": "2025-01-02 11:01:00",
                "id_autor": "51",
            }
        ],
    }
    with main_mod.console.capture() as cap:
        main_mod.render_post_twitter(post1)
        main_mod.render_post_twitter(post2)
    out = cap.get()
    assert isinstance(out, str)
    assert "Titulo X" in out or "Titulo Y" in out


def test_sesion_ciclo_activa_establecer_limpiar(main_mod: Any) -> None:
    main_mod.Sesion.limpiar()
    assert not main_mod.Sesion.activa()
    main_mod.Sesion.establecer(
        {"id_autor": "7", "nombre_autor": "Zoe", "email": "z@x"}
    )
    assert main_mod.Sesion.activa()
    assert main_mod.Sesion.id_autor == "7"
    main_mod.Sesion.limpiar()
    assert not main_mod.Sesion.activa()


def test_recolectar_tags_empates_orden_alfabetico(main_mod: Any) -> None:
    posts = [
        {
            "id_post": "1",
            "id_autor": "1",
            "titulo": "A",
            "contenido": "A",
            "fecha_publicacion": "2025-01-01 00:00:00",
            "tags": ["b", "a"],
            "comentarios": [],
        },
        {
            "id_post": "2",
            "id_autor": "1",
            "titulo": "B",
            "contenido": "B",
            "fecha_publicacion": "2025-01-02 00:00:00",
            "tags": ["a", "b"],
            "comentarios": [],
        },
    ]
    gestor_datos.guardar_datos(main_mod.POSTS_JSON, posts)
    tags = main_mod._recolectar_tags_conteo()
    assert tags[0][0] == "a"
    assert tags[1][0] == "b"


def test_mostrar_error_ok_y_advertencia_no_explotan(main_mod: Any) -> None:
    with main_mod.console.capture() as cap:
        main_mod.mostrar_error("err")
        main_mod.mostrar_ok("ok")
        main_mod.mostrar_advertencia("warn")
    out = cap.get()
    assert isinstance(out, str)
    assert len(out) > 0


def test_mostrar_tabla_y_detalle_posts_no_explode(main_mod: Any) -> None:
    posts = _sample_posts_for_tags()
    with main_mod.console.capture() as cap:
        main_mod._mostrar_tabla_y_detalle_posts(posts)
    out = cap.get()
    assert (
        "Publicaciones" in out or "Post A" in out or "Comentarios" in out
    )


def test_mostrar_tabla_y_detalle_mis_comentarios_no_explode(
    main_mod: Any,
) -> None:
    posts = [
        {
            "id_post": "55",
            "id_autor": "9",
            "titulo": "P",
            "contenido": "C",
            "fecha_publicacion": "2025-02-01 00:00:00",
            "tags": ["t"],
            "comentarios": [
                {
                    "id_comentario": "900",
                    "autor": "Yo",
                    "contenido": "Hola",
                    "fecha": "2025-02-01 01:00:00",
                    "id_autor": "88",
                }
            ],
        }
    ]
    gestor_datos.guardar_datos(main_mod.POSTS_JSON, posts)
    main_mod.Sesion.establecer(
        {"id_autor": "88", "nombre_autor": "Yo", "email": "yo@x"}
    )
    try:
        mis = main_mod._recolectar_mis_comentarios()
        with main_mod.console.capture() as cap:
            main_mod._mostrar_tabla_y_detalle_mis_comentarios(mis)
        out = cap.get()
        assert "Mis Comentarios" in out or "55" in out or "Hola" in out
    finally:
        main_mod.Sesion.limpiar()


def test_ensure_sistema_y_bienvenida_crea_y_idempotente(
    main_mod: Any,
) -> None:
    p1 = main_mod.ensure_sistema_y_bienvenida()
    assert isinstance(p1, dict)
    assert main_mod.BIENVENIDA_TAG in (p1.get("tags") or [])

    p2 = main_mod.ensure_sistema_y_bienvenida()
    assert p1.get("id_post") == p2.get("id_post")

    autor_sys = main_mod.modelo.buscar_autor_por_email(
        main_mod.AUTORES_CSV,
        main_mod.SISTEMA_EMAIL,
    )
    assert autor_sys is not None
    posts_tag = main_mod.modelo.buscar_posts_por_tag(
        main_mod.POSTS_JSON,
        main_mod.BIENVENIDA_TAG,
    )
    posts_tag_sys = [
        p for p in posts_tag if p.get("id_autor") == autor_sys["id_autor"]
    ]
    UNO = 1
    assert len(posts_tag_sys) == UNO
