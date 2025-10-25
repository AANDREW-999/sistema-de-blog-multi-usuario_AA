# -*- coding: utf-8 -*-
"""
Pruebas unitarias para src/Modulo/blog_multi_usuario.py.

Cubre casos de éxito y casos borde para:
- CRUD de Autores
- Creación/Listado/Búsqueda/Actualización/Eliminación de Posts
- Comentarios: añadir, listar, actualizar, eliminar con reglas de autorización

Las pruebas usan un directorio temporal (pytest tmp_path) para no tocar data/ real.
Cumple PEP 8 y valida con ruff.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

# Asegurar que los módulos del proyecto (en src/Modulo) sean importables
MODULE_DIR = Path(__file__).resolve().parents[1] / "src" / "Modulo"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from src.Modulo import gestor_datos  # noqa: E402


def _load_model_module() -> Any:
    """
    Carga dinámicamente src/Modulo/blog_multi_usuario.py y devuelve el módulo.

    Esto evita requerir instalación del paquete para las pruebas.
    """
    module_path = MODULE_DIR / "blog_multi_usuario.py"
    spec = importlib.util.spec_from_file_location(
        "blog_multi_usuario_under_test",
        str(module_path),
    )
    assert spec and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


@pytest.fixture
def modelo(tmp_path: Path) -> Any:
    """
    Devuelve el módulo del modelo listo para trabajar con archivos temporales.
    """
    m = _load_model_module()

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    autores_csv = str(data_dir / "autores.csv")
    posts_json = str(data_dir / "posts.json")

    # Inicializar archivos
    gestor_datos.inicializar_archivo(autores_csv)
    gestor_datos.inicializar_archivo(posts_json)

    # Exponer rutas en el módulo (para comodidad en tests)
    m._AUTORES = autores_csv  # type: ignore[attr-defined]
    m._POSTS = posts_json  # type: ignore[attr-defined]

    return m


# -------------------
# Autores (CSV)
# -------------------

def test_crear_autor_y_buscar_por_email_y_id(modelo: Any) -> None:
    """
    Crear autor debe persistir y permitir buscar por email (case-insensitive) e ID.
    """
    a1 = modelo.crear_autor(modelo._AUTORES, "Alice", "alice@example.com")  # type: ignore[attr-defined]
    assert a1["id_autor"].isdigit()
    assert a1["nombre_autor"] == "Alice"
    assert a1["email"] == "alice@example.com"

    # Buscar por email (insensible a mayúsculas)
    a1b = modelo.buscar_autor_por_email(  # type: ignore[attr-defined]
        modelo._AUTORES,
        "ALICE@EXAMPLE.COM",
    )
    assert a1b and a1b["id_autor"] == a1["id_autor"]

    # Buscar por ID
    a1c = modelo.buscar_autor_por_id(modelo._AUTORES, a1["id_autor"])  # type: ignore[attr-defined]
    assert a1c and a1c["email"] == "alice@example.com"

    # No permite duplicar email
    with pytest.raises(modelo.EmailDuplicado):
        modelo.crear_autor(modelo._AUTORES, "Alice 2", "alice@example.com")  # type: ignore[attr-defined]

    # Email inválido
    with pytest.raises(modelo.ValidacionError):
        modelo.crear_autor(modelo._AUTORES, "Bob", "correo-malo")  # type: ignore[attr-defined]


def test_actualizar_autor_nombre_y_email_y_unicidad(modelo: Any) -> None:
    """
    Actualizar autor debe validar nombre no vacío y unicidad de email.
    """
    a1 = modelo.crear_autor(modelo._AUTORES, "Alice", "alice@example.com")  # type: ignore[attr-defined]
    modelo.crear_autor(modelo._AUTORES, "Bob", "bob@example.com")  # type: ignore[attr-defined]

    # No puede cambiar a un email ya en uso
    with pytest.raises(modelo.EmailDuplicado):
        modelo.actualizar_autor(  # type: ignore[attr-defined]
            modelo._AUTORES,
            a1["id_autor"],
            {"email": "bob@example.com"},
        )

    # Nombre no puede ser vacío
    with pytest.raises(modelo.ValidacionError):
        modelo.actualizar_autor(  # type: ignore[attr-defined]
            modelo._AUTORES,
            a1["id_autor"],
            {"nombre_autor": "  "},
        )

    # Cambio válido de nombre y email
    act = modelo.actualizar_autor(
        modelo._AUTORES,  # type: ignore[attr-defined]
        a1["id_autor"],
        {"nombre_autor": "Alicia", "email": "alicia@ex.com"},
    )
    assert act["nombre_autor"] == "Alicia"
    assert act["email"] == "alicia@ex.com"

    # Autor inexistente
    with pytest.raises(modelo.AutorNoEncontrado):
        modelo.actualizar_autor(  # type: ignore[attr-defined]
            modelo._AUTORES,
            "99999",
            {"nombre_autor": "X"},
        )


def test_eliminar_autor(modelo: Any) -> None:
    """
    Eliminar autor debe devolver True la primera vez y False si ya no existe.
    """
    a1 = modelo.crear_autor(modelo._AUTORES, "Alice", "alice@example.com")  # type: ignore[attr-defined]
    ok_primero = modelo.eliminar_autor(modelo._AUTORES, a1["id_autor"])  # type: ignore[attr-defined]
    assert ok_primero is True

    ok_segundo = modelo.eliminar_autor(modelo._AUTORES, a1["id_autor"])  # type: ignore[attr-defined]
    assert ok_segundo is False


# -------------------
# Posts (JSON)
# -------------------

def test_crear_post_validaciones_y_tags(modelo: Any) -> None:
    """
    crear_post debe validar título y contenido, y normalizar tags.
    """
    autor = modelo.crear_autor(modelo._AUTORES, "Alice", "alice@example.com")  # type: ignore[attr-defined]
    # Tags desde string con duplicados y espacios
    post = modelo.crear_post(
        modelo._POSTS,  # type: ignore[attr-defined]
        autor["id_autor"],
        "Mi Post",
        "Contenido",
        "Python, Desarrollo , python",
        validar_autor_en=modelo._AUTORES,  # type: ignore[attr-defined]
    )
    assert post["id_post"].isdigit()
    assert post["tags"] == ["python", "desarrollo"]

    # Tags con formato inválido (no lista ni string)
    with pytest.raises(modelo.ValidacionError):
        modelo.crear_post(modelo._POSTS, autor["id_autor"], "T", "C", 123)  # type: ignore[arg-type, attr-defined]

    # Título/Contenido requeridos
    with pytest.raises(modelo.ValidacionError):
        modelo.crear_post(modelo._POSTS, autor["id_autor"], "  ", "C", [])  # type: ignore[attr-defined]
    with pytest.raises(modelo.ValidacionError):
        modelo.crear_post(modelo._POSTS, autor["id_autor"], "T", " ", [])  # type: ignore[attr-defined]

    # Validación de autor inexistente
    with pytest.raises(modelo.AutorNoEncontrado):
        modelo.crear_post(
            modelo._POSTS,  # type: ignore[attr-defined]
            "999",
            "T",
            "C",
            [],
            validar_autor_en=modelo._AUTORES,  # type: ignore[attr-defined]
        )


def test_listar_y_buscar_posts(modelo: Any) -> None:
    """
    Debe listar por autor y buscar por tag de forma case-insensitive.
    """
    a1 = modelo.crear_autor(  # type: ignore[attr-defined]
        modelo._AUTORES,
        "Alice",
        "alice@example.com",
    )
    a2 = modelo.crear_autor(  # type: ignore[attr-defined]
        modelo._AUTORES,
        "Bob",
        "bob@example.com",
    )

    modelo.crear_post(  # type: ignore[attr-defined]
        modelo._POSTS,
        a1["id_autor"],
        "P1",
        "C",
        ["python", "dev"],
    )
    modelo.crear_post(  # type: ignore[attr-defined]
        modelo._POSTS,
        a1["id_autor"],
        "P2",
        "C",
        ["tutorial"],
    )
    modelo.crear_post(  # type: ignore[attr-defined]
        modelo._POSTS,
        a2["id_autor"],
        "P3",
        "C",
        ["Python"],
    )

    posts_a1 = modelo.listar_posts_por_autor(  # type: ignore[attr-defined]
        modelo._POSTS,
        a1["id_autor"],
    )
    ESPERADOS_A1 = 2
    assert len(posts_a1) == ESPERADOS_A1

    # Búsqueda por tag insensible a mayúsculas
    encontrados = modelo.buscar_posts_por_tag(  # type: ignore[attr-defined]
        modelo._POSTS,
        "PYTHON",
    )
    assert {p["titulo"] for p in encontrados} == {"P1", "P3"}

    # Tag vacío no permitido
    with pytest.raises(modelo.ValidacionError):
        modelo.buscar_posts_por_tag(modelo._POSTS, "  ")  # type: ignore[attr-defined]


def test_actualizar_post_autorizacion_y_validacion(modelo: Any) -> None:
    """
    Solo el dueño puede actualizar; título y contenido no pueden quedar vacíos.
    """
    a1 = modelo.crear_autor(modelo._AUTORES, "Alice", "alice@example.com")  # type: ignore[attr-defined]
    a2 = modelo.crear_autor(modelo._AUTORES, "Bob", "bob@example.com")  # type: ignore[attr-defined]

    p = modelo.crear_post(modelo._POSTS, a1["id_autor"], "T1", "C1", ["x"])  # type: ignore[attr-defined]

    # No dueño
    with pytest.raises(modelo.AccesoNoAutorizado):
        modelo.actualizar_post(  # type: ignore[attr-defined]
            modelo._POSTS,
            p["id_post"],
            a2["id_autor"],
            {"titulo": "Otro"},
        )

    # Post inexistente
    with pytest.raises(modelo.PostNoEncontrado):
        modelo.actualizar_post(  # type: ignore[attr-defined]
            modelo._POSTS,
            "999",
            a1["id_autor"],
            {"titulo": "X"},
        )

    # Título/Contenido no pueden ser vacíos
    with pytest.raises(modelo.ValidacionError):
        modelo.actualizar_post(  # type: ignore[attr-defined]
            modelo._POSTS,
            p["id_post"],
            a1["id_autor"],
            {"titulo": "  "},
        )
    with pytest.raises(modelo.ValidacionError):
        modelo.actualizar_post(  # type: ignore[attr-defined]
            modelo._POSTS,
            p["id_post"],
            a1["id_autor"],
            {"contenido": ""},
        )

    # Actualización válida (incluye tags como string)
    act = modelo.actualizar_post(
        modelo._POSTS,  # type: ignore[attr-defined]
        p["id_post"],
        a1["id_autor"],
        {"titulo": "Nuevo", "contenido": "NC", "tags": "a, b, a"},
    )
    assert act["titulo"] == "Nuevo"
    assert act["contenido"] == "NC"
    assert act["tags"] == ["a", "b"]


def test_eliminar_post_autorizacion(modelo: Any) -> None:
    """
    Solo el dueño puede eliminar; si el post no existe, retorna False.
    """
    a1 = modelo.crear_autor(modelo._AUTORES, "Alice", "alice@example.com")  # type: ignore[attr-defined]
    a2 = modelo.crear_autor(modelo._AUTORES, "Bob", "bob@example.com")  # type: ignore[attr-defined]

    p = modelo.crear_post(modelo._POSTS, a1["id_autor"], "T1", "C1", [])  # type: ignore[attr-defined]

    with pytest.raises(modelo.AccesoNoAutorizado):
        modelo.eliminar_post(modelo._POSTS, p["id_post"], a2["id_autor"])  # type: ignore[attr-defined]

    ok = modelo.eliminar_post(modelo._POSTS, p["id_post"], a1["id_autor"])  # type: ignore[attr-defined]
    assert ok is True

    # Ya fue eliminado
    ok2 = modelo.eliminar_post(modelo._POSTS, p["id_post"], a1["id_autor"])  # type: ignore[attr-defined]
    assert ok2 is False


# -------------------
# Comentarios
# -------------------

def test_agregar_listar_y_eliminar_comentario_con_autorizacion(modelo: Any) -> None:
    """
    Agregar comentario, listar y eliminar respetando la autorización del dueño.
    """
    a1 = modelo.crear_autor(modelo._AUTORES, "Alice", "alice@example.com")  # type: ignore[attr-defined]
    p = modelo.crear_post(modelo._POSTS, a1["id_autor"], "T1", "C1", [])  # type: ignore[attr-defined]

    # Comentario con id_autor=99
    c = modelo.agregar_comentario_a_post(
        modelo._POSTS,  # type: ignore[attr-defined]
        p["id_post"],
        "Comenter",
        "Hola!",
        id_autor="99",
    )
    assert c["id_comentario"] == "1"

    comentarios = modelo.listar_comentarios_de_post(modelo._POSTS, p["id_post"])  # type: ignore[attr-defined]
    assert len(comentarios) == 1

    # Intento de eliminar con otro autor -> no autorizado
    with pytest.raises(modelo.AccesoNoAutorizado):
        modelo.eliminar_comentario_de_post(  # type: ignore[attr-defined]
            modelo._POSTS,
            p["id_post"],
            c["id_comentario"],
            id_autor_en_sesion="100",
        )

    # Eliminación autorizada
    ok = modelo.eliminar_comentario_de_post(  # type: ignore[attr-defined]
        modelo._POSTS,
        p["id_post"],
        c["id_comentario"],
        id_autor_en_sesion="99",
    )
    assert ok is True

    # Comentario inexistente
    ok2 = modelo.eliminar_comentario_de_post(modelo._POSTS, p["id_post"], "999")  # type: ignore[attr-defined]
    assert ok2 is False


def test_actualizar_comentario_validaciones_y_autorizacion(modelo: Any) -> None:
    """
    Actualizar comentario requiere pertenencia (si hay id_autor) y contenido no vacío.
    """
    a1 = modelo.crear_autor(modelo._AUTORES, "Alice", "alice@example.com")  # type: ignore[attr-defined]
    p = modelo.crear_post(modelo._POSTS, a1["id_autor"], "T1", "C1", [])  # type: ignore[attr-defined]
    c = modelo.agregar_comentario_a_post(
        modelo._POSTS,  # type: ignore[attr-defined]
        p["id_post"],
        "Alice",
        "Hola!",
        id_autor=a1["id_autor"],
    )

    # Otro autor no puede editar
    with pytest.raises(modelo.AccesoNoAutorizado):
        modelo.actualizar_comentario_de_post(  # type: ignore[attr-defined]
            modelo._POSTS,
            p["id_post"],
            c["id_comentario"],
            {"contenido": "X"},
            id_autor_en_sesion="999",
        )

    # Contenido vacío no permitido
    with pytest.raises(modelo.ValidacionError):
        modelo.actualizar_comentario_de_post(  # type: ignore[attr-defined]
            modelo._POSTS,
            p["id_post"],
            c["id_comentario"],
            {"contenido": "   "},
            id_autor_en_sesion=a1["id_autor"],
        )

    # Actualización válida
    c2 = modelo.actualizar_comentario_de_post(  # type: ignore[attr-defined]
        modelo._POSTS,
        p["id_post"],
        c["id_comentario"],
        {"contenido": "Editado"},
        id_autor_en_sesion=a1["id_autor"],
    )
    assert c2["contenido"] == "Editado"
