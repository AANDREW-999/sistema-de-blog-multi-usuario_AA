# -*- coding: utf-8 -*-
"""
Módulo de Lógica de Negocio (Modelo) — Sistema de Blog Multi-usuario.
"""
from __future__ import annotations  # Anotaciones diferidas para tipos

import re  # Expresiones regulares para validar emails
from datetime import datetime  # Fechas y horas para marcas de tiempo
from typing import Any, Dict, List, Optional, Sequence  # Tipado para ayudas y claridad

import gestor_datos  # Persistencia (CSV/JSON) desacoplada del modelo

# =========================
# Excepciones de dominio
# =========================

ErrorDeDominio = Exception
ValidacionError = ErrorDeDominio
EmailDuplicado = ErrorDeDominio
AutorNoEncontrado = ErrorDeDominio
PostNoEncontrado = ErrorDeDominio
AccesoNoAutorizado = ErrorDeDominio


# =========================
# Helpers y validaciones
# =========================

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _ahora_str() -> str:
    """Obtiene la fecha y hora actual formateada.

    Returns:
        str: Marca de tiempo en formato 'YYYY-MM-DD HH:MM:SS'.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _es_str_no_vacio(valor: Any) -> bool:
    """Indica si el valor es una cadena no vacía tras strip().

    Args:
        valor: Valor a evaluar.

    Returns:
        bool: True si es str y no está vacío; False en caso contrario.
    """
    return isinstance(valor, str) and valor.strip() != ""


def _validar_email(email: str) -> None:
    """Valida el formato del email.

    Args:
        email: Correo a validar.

    Raises:
        ValidacionError: Si el email está vacío o no cumple el formato.
    """
    if not _es_str_no_vacio(email) or not _EMAIL_RE.match(email):
        raise ValidacionError("El email no tiene un formato válido.")


def _normalizar_tags(tags: Sequence[str]) -> List[str]:
    """Normaliza y deduplica tags preservando el orden.

    Convierte a minúsculas, aplica strip() y elimina duplicados.

    Args:
        tags: Secuencia de cadenas (tags).

    Returns:
        List[str]: Lista de tags normalizados sin duplicados.

    Raises:
        ValidacionError: Si algún elemento no es cadena.
    """
    vistos = set()
    normalizados: List[str] = []
    for t in tags:
        if not isinstance(t, str):
            raise ValidacionError("Todos los tags deben ser cadenas de texto.")
        tt = t.strip().lower()
        if tt and tt not in vistos:
            vistos.add(tt)
            normalizados.append(tt)
    return normalizados


def _parsear_tags(tags: Any) -> List[str]:
    """Convierte la entrada de tags a una lista normalizada.

    Admite lista/tupla de strings o una cadena separada por comas.

    Args:
        tags: Lista/tupla de strings, cadena separada por comas o None.

    Returns:
        List[str]: Lista de tags normalizados.

    Raises:
        ValidacionError: Si el formato no es soportado.
    """
    if tags is None:
        return []
    if isinstance(tags, (list, tuple)):
        return _normalizar_tags(list(tags))
    if isinstance(tags, str):
        separados = [p.strip() for p in tags.split(",")]
        return _normalizar_tags(separados)
    raise ValidacionError("Formato de 'tags' no soportado. Use lista o cadena separada "
                          "por comas.")


def _generar_id(items: List[Dict[str, Any]], clave_id: str) -> int:
    """Genera un ID entero autoincremental.

    Busca el máximo valor de 'clave_id' y retorna el siguiente.

    Args:
        items: Lista de diccionarios fuente.
        clave_id: Nombre de la clave que contiene el ID.

    Returns:
        int: ID siguiente (1 si la lista está vacía o inválida).
    """
    if not items:
        return 1
    try:
        max_id = max(int(it.get(clave_id, 0)) for it in items)
    except ValueError:
        max_id = 0
    return max_id + 1


def _generar_id_comentario(post: Dict[str, Any]) -> int:
    """Genera un ID autoincremental para comentarios de un post.

    Args:
        post: Diccionario del post (con su lista 'comentarios').

    Returns:
        int: Siguiente ID de comentario.
    """
    comentarios = post.get("comentarios") or []
    if not comentarios:
        return 1
    try:
        max_id = max(int(c.get("id_comentario", 0)) for c in comentarios)
    except ValueError:
        max_id = 0
    return max_id + 1

def crear_autor(autores_filepath: str, nombre_autor: str, email: str, password_hash: str
= "") -> Dict[str, Any]:
    """Crea un nuevo autor.

    Valida el email y su unicidad, y persiste el registro en CSV.

    Args:
        autores_filepath: Ruta al CSV de autores.
        nombre_autor: Nombre a mostrar del autor.
        email: Correo electrónico único.
        password_hash: Hash de la contraseña del autor (opcional).

    Returns:
        Dict[str, Any]: Autor creado.

    Raises:
        ValidacionError: Si faltan datos o el formato es inválido.
        EmailDuplicado: Si el email ya existe.
    """
    if not _es_str_no_vacio(nombre_autor):
        raise ValidacionError("El nombre del autor es obligatorio.")
    _validar_email(email)

    autores = gestor_datos.cargar_datos(autores_filepath)

    if any(a.get("email", "").strip().lower() == email.strip().lower()
           for a in autores):
        raise EmailDuplicado(f"El email '{email}' ya se encuentra registrado.")

    nuevo_id = _generar_id(autores, "id_autor")
    autor = {
        "id_autor": str(nuevo_id),
        "nombre_autor": nombre_autor.strip(),
        "email": email.strip().lower(),
        "password_hash": str(password_hash or "").strip(),
    }
    autores.append(autor)
    gestor_datos.guardar_datos(autores_filepath, autores)
    return autor


def leer_todos_los_autores(autores_filepath: str) -> \
        (List)[Dict[str, Any]]:
    """Obtiene la lista completa de autores.

    Args:
        autores_filepath: Ruta al CSV de autores.

    Returns:
        List[Dict[str, Any]]: Lista de autores.
    """
    return gestor_datos.cargar_datos(autores_filepath)


def buscar_autor_por_id(autores_filepath: str, id_autor: str | int) \
        -> Optional[Dict[str, Any]]:
    """Busca un autor por su ID.

    Args:
        autores_filepath: Ruta al CSV de autores.
        id_autor: ID del autor.

    Returns:
        Optional[Dict[str, Any]]: Autor encontrado o None.
    """
    autores = gestor_datos.cargar_datos(autores_filepath)
    id_str = str(id_autor)
    for a in autores:
        if a.get("id_autor") == id_str:
            return a
    return None


def buscar_autor_por_email(autores_filepath: str, email: str) \
        -> Optional[Dict[str, Any]]:
    """Busca un autor por email (insensible a mayúsculas).

    Args:
        autores_filepath: Ruta al CSV de autores.
        email: Correo a buscar.

    Returns:
        Optional[Dict[str, Any]]: Autor encontrado o None.

    Raises:
        ValidacionError: Si el email no es válido.
    """
    _validar_email(email)
    autores = gestor_datos.cargar_datos(autores_filepath)
    email_l = email.strip().lower()
    for a in autores:
        if a.get("email", "").strip().lower() == email_l:
            return a
    return None


def actualizar_autor(
    autores_filepath: str,
    id_autor: str | int,
    datos_nuevos: Dict[str, Any],
) -> Dict[str, Any]:
    """Actualiza campos de un autor.

    Reglas:
    - Si se cambia el email, validar formato y unicidad.
    - Convierte todos los valores a str para consistencia.

    Args:
        autores_filepath: Ruta al CSV de autores.
        id_autor: ID del autor a actualizar.
        datos_nuevos: Campos a modificar (nombre_autor, email, password_hash).

    Returns:
        Dict[str, Any]: Autor actualizado.

    Raises:
        AutorNoEncontrado: Si el autor no existe.
        EmailDuplicado: Si el nuevo email ya está en uso.
        ValidacionError: Si algún campo es inválido.
    """
    autores = gestor_datos.cargar_datos(autores_filepath)
    id_str = str(id_autor)

    idx = -1
    for i, a in enumerate(autores):
        if a.get("id_autor") == id_str:
            idx = i
            break
    if idx == -1:
        raise AutorNoEncontrado(f"No existe autor con id_autor='{id_str}'.")

    autor = dict(autores[idx])  # copia

    if "nombre_autor" in datos_nuevos:
        if not _es_str_no_vacio(datos_nuevos["nombre_autor"]):
            raise ValidacionError("El nombre del autor no puede estar vacío.")
        autor["nombre_autor"] = str(datos_nuevos["nombre_autor"]).strip()

    if "email" in datos_nuevos:
        nuevo_email = str(datos_nuevos["email"]).strip().lower()
        _validar_email(nuevo_email)
        # verificar unicidad
        for a in autores:
            if (a.get("id_autor") != id_str and a.get("email", "").strip().lower()
                    == nuevo_email):
                raise EmailDuplicado(f"El email '{nuevo_email}"
                                     f"' ya está en uso por otro autor.")
        autor["email"] = nuevo_email

    if "password_hash" in datos_nuevos:
        autor["password_hash"] = str(datos_nuevos["password_hash"] or "").strip()

    autores[idx] = autor
    gestor_datos.guardar_datos(autores_filepath, autores)
    return autor


def eliminar_autor(autores_filepath: str, id_autor: str | int) -> bool:
    """Elimina un autor por su ID.

    Args:
        autores_filepath: Ruta al CSV de autores.
        id_autor: ID del autor a eliminar.

    Returns:
        bool: True si se eliminó; False si no existía.
    """
    autores = gestor_datos.cargar_datos(autores_filepath)
    id_str = str(id_autor)
    original = len(autores)
    autores = [a for a in autores if a.get("id_autor") != id_str]
    if len(autores) < original:
        gestor_datos.guardar_datos(autores_filepath, autores)
        return True
    return False


def crear_post(
        posts_filepath: str,
        id_autor_en_sesion: str | int,
        titulo: str,
        contenido: str,
        tags: Any,
        **opciones,
) -> Dict[str, Any]:
    """Crea una nueva publicación asociada al autor en sesión.

    Args:
        posts_filepath: Ruta al JSON de publicaciones.
        id_autor_en_sesion: ID del autor autenticado.
        titulo: Título del post.
        contenido: Contenido del post.
        tags: Lista/tupla de strings o cadena separada por comas.
        **opciones: Opciones adicionales:
            - validar_autor_en (str):
            Ruta al CSV de autores para validar existencia del autor.
            - fecha_publicacion (str): Fecha personalizada 'YYYY-MM-DD HH:MM:SS'.

    Returns:
        Dict[str, Any]: Post creado.

    Raises:
        AutorNoEncontrado: Si el autor no existe al validar.
        ValidacionError: Si los datos son inválidos.
    """
    # Extraer opciones
    validar_autor_en = opciones.get('validar_autor_en')
    fecha_publicacion = opciones.get('fecha_publicacion')

    if not _es_str_no_vacio(titulo):
        raise ValidacionError("El título es obligatorio.")
    if not _es_str_no_vacio(contenido):
        raise ValidacionError("El contenido es obligatorio.")

    id_autor_str = str(id_autor_en_sesion)

    if validar_autor_en:
        autor = buscar_autor_por_id(validar_autor_en, id_autor_str)
        if not autor:
            raise AutorNoEncontrado(f"No existe autor con id_autor='{id_autor_str}'.")

    posts = gestor_datos.cargar_datos(posts_filepath)
    nuevo_id = _generar_id(posts, "id_post")

    post = {
        "id_post": str(nuevo_id),
        "id_autor": id_autor_str,
        "titulo": titulo.strip(),
        "contenido": contenido.strip(),
        "fecha_publicacion": fecha_publicacion.strip() if _es_str_no_vacio
        (fecha_publicacion or "") else _ahora_str(),
        "tags": _parsear_tags(tags),
        "comentarios": [],
    }
    posts.append(post)
    gestor_datos.guardar_datos(posts_filepath, posts)
    return post


def leer_todos_los_posts(posts_filepath: str) -> List[Dict[str, Any]]:
    """Obtiene la lista completa de publicaciones.

    Args:
        posts_filepath: Ruta al JSON de publicaciones.

    Returns:
        List[Dict[str, Any]]: Lista de posts.
    """
    return gestor_datos.cargar_datos(posts_filepath)


def listar_posts_por_autor(posts_filepath: str, id_autor: str | int) \
        -> List[Dict[str, Any]]:
    """Lista todas las publicaciones de un autor específico.

    Args:
        posts_filepath: Ruta al JSON de publicaciones.
        id_autor: ID del autor.

    Returns:
        List[Dict[str, Any]]: Publicaciones del autor.
    """
    id_str = str(id_autor)
    posts = gestor_datos.cargar_datos(posts_filepath)
    return [p for p in posts if p.get("id_autor") == id_str]


def buscar_posts_por_tag(posts_filepath: str, tag: str) -> List[Dict[str, Any]]:
    """Busca publicaciones que contengan el tag indicado.

    La comparación es insensible a mayúsculas/minúsculas.

    Args:
        posts_filepath: Ruta al JSON de publicaciones.
        tag: Tag a buscar.

    Returns:
        List[Dict[str, Any]]: Publicaciones que contienen el tag.

    Raises:
        ValidacionError: Si el tag está vacío.
    """
    if not _es_str_no_vacio(tag):
        raise ValidacionError("El tag de búsqueda no puede estar vacío.")
    t = tag.strip().lower()
    posts = gestor_datos.cargar_datos(posts_filepath)
    return [p for p in posts if t in [tt.lower() for tt in (p.get("tags") or [])]]


def buscar_post_por_id(posts_filepath: str, id_post: str | int) \
        -> Optional[Dict[str, Any]]:
    """Obtiene un post por su ID.

    Args:
        posts_filepath: Ruta al JSON de publicaciones.
        id_post: ID del post.

    Returns:
        Optional[Dict[str, Any]]: Post encontrado o None.
    """
    posts = gestor_datos.cargar_datos(posts_filepath)
    id_str = str(id_post)
    for p in posts:
        if p.get("id_post") == id_str:
            return p
    return None


def actualizar_post(
    posts_filepath: str,
    id_post: str | int,
    id_autor_en_sesion: str | int,
    datos_nuevos: Dict[str, Any],
) -> Dict[str, Any]:
    """Actualiza un post (solo su dueño).

    Campos permitidos: 'titulo', 'contenido', 'tags'.

    Args:
        posts_filepath: Ruta al JSON de publicaciones.
        id_post: ID del post a actualizar.
        id_autor_en_sesion: ID del autor autenticado.
        datos_nuevos: Campos a modificar.

    Returns:
        Dict[str, Any]: Post actualizado.

    Raises:
        PostNoEncontrado: Si el post no existe.
        AccesoNoAutorizado: Si el post no pertenece al autor.
        ValidacionError: Si algún campo es inválido.
    """
    posts = gestor_datos.cargar_datos(posts_filepath)
    id_post_str = str(id_post)
    id_autor_sesion_str = str(id_autor_en_sesion)

    idx = -1
    for i, p in enumerate(posts):
        if p.get("id_post") == id_post_str:
            idx = i
            break
    if idx == -1:
        raise PostNoEncontrado(f"No existe post con id_post='{id_post_str}'.")

    post = dict(posts[idx])  # copia
    if post.get("id_autor") != id_autor_sesion_str:
        raise AccesoNoAutorizado("No puedes modificar publicaciones de otros autores.")

    if "titulo" in datos_nuevos:
        if not _es_str_no_vacio(datos_nuevos["titulo"]):
            raise ValidacionError("El título no puede estar vacío.")
        post["titulo"] = str(datos_nuevos["titulo"]).strip()

    if "contenido" in datos_nuevos:
        if not _es_str_no_vacio(datos_nuevos["contenido"]):
            raise ValidacionError("El contenido no puede estar vacío.")
        post["contenido"] = str(datos_nuevos["contenido"]).strip()

    if "tags" in datos_nuevos:
        post["tags"] = _parsear_tags(datos_nuevos["tags"])

    posts[idx] = post
    gestor_datos.guardar_datos(posts_filepath, posts)
    return post


def eliminar_post(
    posts_filepath: str,
    id_post: str | int,
    id_autor_en_sesion: str | int,
) -> bool:
    """Elimina un post si pertenece al autor en sesión.

    Args:
        posts_filepath: Ruta al JSON de publicaciones.
        id_post: ID del post a eliminar.
        id_autor_en_sesion: ID del autor autenticado.

    Returns:
        bool: True si se eliminó; False si no existía.

    Raises:
        AccesoNoAutorizado: Si el post no pertenece al autor.
    """
    posts = gestor_datos.cargar_datos(posts_filepath)
    id_post_str = str(id_post)
    id_autor_sesion_str = str(id_autor_en_sesion)

    post = None
    for p in posts:
        if p.get("id_post") == id_post_str:
            post = p
            break

    if post is None:
        return False

    if post.get("id_autor") != id_autor_sesion_str:
        raise AccesoNoAutorizado("No puedes eliminar publicaciones de otros autores.")

    posts = [p for p in posts if p.get("id_post") != id_post_str]
    gestor_datos.guardar_datos(posts_filepath, posts)
    return True


# =========================
# Comentarios (reto)
# =========================

def agregar_comentario_a_post(
    posts_filepath: str,
    id_post: str | int,
    autor: str,
    contenido: str,
    *,
    id_autor: Optional[str | int] = None,
) -> Dict[str, Any]:
    """Agrega un comentario a un post.

    Args:
        posts_filepath: Ruta al JSON de posts.
        id_post: ID del post a comentar.
        autor: Nombre a mostrar del comentarista.
        contenido: Texto del comentario.
        id_autor: ID del autor registrado (opcional).

    Returns:
        Dict[str, Any]: Comentario creado.

    Raises:
        PostNoEncontrado: Si el post no existe.
        ValidacionError: Si 'autor' o 'contenido' están vacíos.
    """
    if not _es_str_no_vacio(autor):
        raise ValidacionError("El autor del comentario es obligatorio.")
    if not _es_str_no_vacio(contenido):
        raise ValidacionError("El contenido del comentario es obligatorio.")

    posts = gestor_datos.cargar_datos(posts_filepath)
    id_post_str = str(id_post)

    idx = -1
    for i, p in enumerate(posts):
        if p.get("id_post") == id_post_str:
            idx = i
            break
    if idx == -1:
        raise PostNoEncontrado(f"No existe post con id_post='{id_post_str}'.")

    post = dict(posts[idx])  # copia
    comentarios: List[Dict[str, Any]] = list(post.get("comentarios") or [])
    nuevo_id = _generar_id_comentario(post)
    comentario = {
        "id_comentario": str(nuevo_id),
        "autor": autor.strip(),
        "contenido": contenido.strip(),
        "fecha": _ahora_str(),
        "id_autor": str(id_autor) if id_autor is not None else "",
    }
    comentarios.append(comentario)
    post["comentarios"] = comentarios

    posts[idx] = post
    gestor_datos.guardar_datos(posts_filepath, posts)
    return comentario


def listar_comentarios_de_post(posts_filepath: str, id_post: str | int) \
        -> List[Dict[str, Any]]:
    """Lista todos los comentarios de un post.

    Args:
        posts_filepath: Ruta al JSON de publicaciones.
        id_post: ID del post.

    Returns:
        List[Dict[str, Any]]: Comentarios del post.

    Raises:
        PostNoEncontrado: Si el post no existe.
    """
    post = buscar_post_por_id(posts_filepath, id_post)
    if not post:
        raise PostNoEncontrado(f"No existe post con id_post='{id_post}'.")
    return list(post.get("comentarios") or [])


def eliminar_comentario_de_post(
    posts_filepath: str,
    id_post: str | int,
    id_comentario: str | int,
    *,
    id_autor_en_sesion: Optional[str | int] = None,
) -> bool:
    """Elimina un comentario por su ID dentro de un post.

    Reglas de autorización:
    - Si el comentario tiene 'id_autor' y se proporciona 'id_autor_en_sesion',
      solo se permite eliminar si coinciden.

    Args:
        posts_filepath: Ruta al JSON de publicaciones.
        id_post: ID del post.
        id_comentario: ID del comentario a eliminar.
        id_autor_en_sesion: ID del autor autenticado (opcional).

    Returns:
        bool: True si se eliminó; False si no existía.

    Raises:
        PostNoEncontrado: Si el post no existe.
        AccesoNoAutorizado: Si no es dueño del comentario.
    """
    posts = gestor_datos.cargar_datos(posts_filepath)
    id_post_str = str(id_post)
    id_com_str = str(id_comentario)

    pidx = -1
    for i, p in enumerate(posts):
        if p.get("id_post") == id_post_str:
            pidx = i
            break
    if pidx == -1:
        raise PostNoEncontrado(f"No existe post con id_post='{id_post_str}'.")

    post = dict(posts[pidx])
    comentarios: List[Dict[str, Any]] = list(post.get("comentarios") or [])

    c_encontrado = None
    for c in comentarios:
        if c.get("id_comentario") == id_com_str:
            c_encontrado = c
            break

    if c_encontrado is None:
        return False

    if c_encontrado.get("id_autor") and id_autor_en_sesion is not None:
        if str(c_encontrado.get("id_autor")) != str(id_autor_en_sesion):
            raise AccesoNoAutorizado("No puedes eliminar comentarios de otros autores.")

    comentarios = [c for c in comentarios if c.get("id_comentario") != id_com_str]
    post["comentarios"] = comentarios
    posts[pidx] = post
    gestor_datos.guardar_datos(posts_filepath, posts)
    return True


def actualizar_comentario_de_post(
    posts_filepath: str,
    id_post: str | int,
    id_comentario: str | int,
    datos_nuevos: Dict[str, Any],
    *,
    id_autor_en_sesion: Optional[str | int] = None,
) -> Dict[str, Any]:
    """Actualiza campos permitidos de un comentario.

    Campo permitido: 'contenido'.

    Args:
        posts_filepath: Ruta al JSON de publicaciones.
        id_post: ID del post.
        id_comentario: ID del comentario a actualizar.
        datos_nuevos: Campos a modificar.
        id_autor_en_sesion: ID del autor autenticado (opcional).

    Returns:
        Dict[str, Any]: Comentario actualizado.

    Raises:
        PostNoEncontrado: Si el post no existe.
        ValidacionError: Si 'contenido' es inválido.
        AccesoNoAutorizado: Si no es dueño del comentario.
    """
    posts = gestor_datos.cargar_datos(posts_filepath)
    id_post_str = str(id_post)
    id_com_str = str(id_comentario)

    pidx = -1
    for i, p in enumerate(posts):
        if p.get("id_post") == id_post_str:
            pidx = i
            break
    if pidx == -1:
        raise PostNoEncontrado(f"No existe post con id_post='{id_post_str}'.")

    post = dict(posts[pidx])
    comentarios: List[Dict[str, Any]] = list(post.get("comentarios") or [])

    cidx = -1
    for i, c in enumerate(comentarios):
        if c.get("id_comentario") == id_com_str:
            cidx = i
            break
    if cidx == -1:
        raise ValidacionError("No se encontró el comentario indicado.")

    comentario = dict(comentarios[cidx])

    # Autorización (si ambas partes están presentes)
    if comentario.get("id_autor") and id_autor_en_sesion is not None:
        if str(comentario.get("id_autor")) != str(id_autor_en_sesion):
            raise AccesoNoAutorizado("No puedes editar comentarios de otros autores.")

    # Validar y aplicar cambios permitidos
    if "contenido" in datos_nuevos:
        nuevo_contenido = str(datos_nuevos["contenido"]) if (datos_nuevos["contenido"]
                                                             is not None) else ""
        if not _es_str_no_vacio(nuevo_contenido):
            raise ValidacionError("El contenido del comentario no puede estar vacío.")
        comentario["contenido"] = nuevo_contenido.strip()

    # Persistir
    comentarios[cidx] = comentario
    post["comentarios"] = comentarios
    posts[pidx] = post
    gestor_datos.guardar_datos(posts_filepath, posts)
    return comentario



__all__ = [
    # Excepciones
    "ErrorDeDominio",
    "ValidacionError",
    "EmailDuplicado",
    "AutorNoEncontrado",
    "PostNoEncontrado",
    "AccesoNoAutorizado",
    # Autores
    "crear_autor",
    "leer_todos_los_autores",
    "buscar_autor_por_id",
    "buscar_autor_por_email",
    "actualizar_autor",
    "eliminar_autor",
    # Posts
    "crear_post",
    "leer_todos_los_posts",
    "listar_posts_por_autor",
    "buscar_posts_por_tag",
    "buscar_post_por_id",
    "actualizar_post",
    "eliminar_post",
    # Comentarios
    "agregar_comentario_a_post",
    "listar_comentarios_de_post",
    "eliminar_comentario_de_post",
    "actualizar_comentario_de_post",
]
