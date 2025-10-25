# -*- coding: utf-8 -*-
"""
Módulo Principal - Interfaz de Usuario (UI) con Rich
Sistema de Blog Multi-Usuario (consola)

- CRUD de Autores (CSV)
- Posts (JSON): crear, listar por autor, buscar por tag, actualizar/eliminar propio
- Comentarios: agregar, listar, eliminar (opcionalmente validando autor del comentario)
- Sesión simulada por email

Este módulo orquesta la interacción de usuario y delega:
- Lógica de negocio en blog_multi_usuario (Modelo)
- Persistencia en gestor_datos (Controlador/I/O)
"""

from __future__ import (
    annotations,  # Permite posponer evaluación de anotaciones de tipos
)

# NUEVO: hashing de contraseñas (en memoria)
import hashlib  # Hashing (SHA-256) para proteger contraseñas
import os  # Manejo de rutas y sistema de archivos
import secrets  # Generación de valores aleatorios seguros (salts)
from typing import Any, Dict, List, Optional  # Tipos auxiliares para anotar firmas

import blog_multi_usuario as modelo  # Lógica de negocio (modelo del dominio)
import gestor_datos  # Persistencia (lectura/escritura CSV/JSON)

# --- Rich ---
from rich.console import Console, Group  # Consola y agrupador de componentes Rich
from rich.markup import escape  # Escapar contenido dinámico en markup
from rich.panel import Panel  # Paneles con bordes y títulos
from rich.prompt import Confirm, Prompt  # Prompts interactivos (texto y confirmación)
from rich.table import Table  # Tablas con estilos y columnas
from rich.text import Text  # Texto con estilos

console = Console()

# --- Constantes (evitar valores mágicos) ---
MIN_PASSWORD_LENGTH = 4
RESUMEN_COMENTARIO_MAX = 80


# --- Cancelación de formularios ---
Cancelado = Exception


def pedir(
    mensaje: str,
    *,
    password: bool = False,
    default: Optional[str] = None,
    to_lower: bool = False,
) -> str:
    """
    Solicita un valor al usuario (Prompt) con opción de cancelar.

    Si el usuario ingresa "0" se cancela la operación mediante la excepción Cancelado.
    Nunca retorna None; siempre entrega cadena (posiblemente vacía si hay default).

    Args:
        mensaje: Texto a mostrar en el prompt.
        password: Si True, oculta la entrada del usuario.
        default: Valor por defecto si el usuario solo presiona Enter.
        to_lower: Si True, retorna la cadena en minúsculas.

    Returns:
        str: Valor ingresado por el usuario (no None).

    Raises:
        Cancelado: Cuando el usuario ingresa "0".
    """
    etiqueta = (
        f"[magenta]{mensaje}[/magenta] [dim](0 para salir)[/dim]"
    )
    if default is None:
        raw = Prompt.ask(etiqueta, password=password)
    else:
        raw = Prompt.ask(
            etiqueta,
            password=password,
            default=str(default),
        )

    valor = "" if raw is None else str(raw)
    valor = valor.strip()

    if valor == "0":
        raise Cancelado()
    return valor.lower() if to_lower else valor


def mostrar_advertencia(mensaje: str) -> None:
    """
    Muestra un panel de advertencia estilizado.

    Args:
        mensaje: Texto de la advertencia a mostrar.

    Returns:
        None
    """
    console.print(
        Panel(
            f"[yellow]{mensaje}[/yellow]",
            border_style="yellow",
            title="[bold yellow]Aviso[/bold yellow]",
        )
    )


def pedir_obligatorio(
    mensaje: str,
    *,
    password: bool = False,
    default: Optional[str] = None,
    to_lower: bool = False,
) -> str:
    """
    Solicita un valor no vacío; reintenta si el usuario deja el campo vacío.

    Args:
        mensaje: Texto del prompt.
        password: Si True, oculta la entrada.
        default: Valor por defecto si el usuario solo presiona Enter.
        to_lower: Si True, retorna el valor en minúsculas.

    Returns:
        str: Cadena no vacía ingresada por el usuario.

    Raises:
        Cancelado: Cuando el usuario ingresa "0".
    """
    while True:
        valor = pedir(
            mensaje,
            password=password,
            default=default,
            to_lower=to_lower,
        )
        if valor != "":
            return valor
        mostrar_advertencia(
            "El campo no puede estar vacío. Inténtalo de nuevo."
        )


def _hash_password(pwd: str, salt: Optional[str] = None) -> str:
    """
    Genera un hash seguro (salt + SHA-256) para una contraseña.

    Formato devuelto: "<salt>$<hash_hex>".

    Args:
        pwd: Contraseña en texto plano.
        salt: Salt hexadecimal opcional; si no se provee, se genera.

    Returns:
        str: Cadena con el salt y el hash concatenados.
    """
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256()
    h.update((salt + pwd).encode("utf-8"))
    return f"{salt}${h.hexdigest()}"


def _verify_password(stored: str, pwd: str) -> bool:
    """
    Verifica una contraseña comparándola con un hash almacenado.

    Args:
        stored: Valor almacenado con formato "<salt>$<hash_hex>".
        pwd: Contraseña en texto plano a validar.

    Returns:
        bool: True si coincide; False en caso contrario.
    """
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return _hash_password(pwd, salt) == stored


def pedir_password_nuevo() -> str:
    """
    Solicita una nueva contraseña y su confirmación, validando reglas mínimas.

    Reglas: las contraseñas deben coincidir y tener longitud mínima definida.

    Returns:
        str: Contraseña válida ingresada por el usuario.

    Raises:
        modelo.ValidacionError: Si no coincide o no cumple la longitud mínima.
        Cancelado: Si el usuario cancela con "0".
    """
    pwd1 = pedir("Contraseña", password=True)
    pwd2 = pedir("Confirmar contraseña", password=True)
    if pwd1 != pwd2:
        raise modelo.ValidacionError("Las contraseñas no coinciden.")
    if len(pwd1) < MIN_PASSWORD_LENGTH:
        raise modelo.ValidacionError(
            f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
        )
    return pwd1


# --- Configuración de rutas ---
# Hacemos la ruta a 'data/' robusta, independiente del cwd
# (dos niveles arriba de este archivo)
BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
DIRECTORIO_DATOS = os.path.join(BASE_DIR, "data")
AUTORES_CSV = os.path.join(DIRECTORIO_DATOS, "autores.csv")
POSTS_JSON = os.path.join(DIRECTORIO_DATOS, "posts.json")


# --- Estado de sesión (simulado) ---
class Sesion:
    """
    Gestiona el estado de la sesión del usuario actual.

    Atributos de clase:
        id_autor (Optional[str]): ID del autor autenticado.
        nombre_autor (Optional[str]): Nombre visible del autor.
        email (Optional[str]): Correo electrónico del autor.
    """

    id_autor: Optional[str] = None
    nombre_autor: Optional[str] = None
    email: Optional[str] = None

    @classmethod
    def activa(cls) -> bool:
        """
        Indica si existe una sesión activa.

        Returns:
            bool: True si hay un autor en sesión; False en caso contrario.
        """
        return cls.id_autor is not None

    @classmethod
    def establecer(cls, autor: Dict[str, Any]) -> None:
        """
        Establece la sesión con los datos del autor autenticado.

        Args:
            autor: Diccionario con llaves 'id_autor', 'nombre_autor' y 'email'.

        Returns:
            None
        """
        cls.id_autor = autor.get("id_autor")
        cls.nombre_autor = autor.get("nombre_autor")
        cls.email = autor.get("email")

    @classmethod
    def limpiar(cls) -> None:
        """
        Limpia el estado de la sesión (cierra sesión).

        Returns:
            None
        """
        cls.id_autor = None
        cls.nombre_autor = None
        cls.email = None


# --- Helpers UI ---
def init_archivos() -> None:
    """
    Asegura que los archivos de datos existan e inicializa su contenido si faltan.

    Returns:
        None
    """
    gestor_datos.inicializar_archivo(AUTORES_CSV)
    gestor_datos.inicializar_archivo(POSTS_JSON)


def banner() -> None:
    """
    Muestra el banner principal de la aplicación.

    Returns:
        None
    """
    console.print(
        Panel.fit(
            "[bold cyan]Sistema de Blog Multi-usuario[/bold cyan]",
            border_style="bright_magenta",
        )
    )


def mostrar_error(mensaje: str) -> None:
    """
    Muestra un panel de error estilizado.

    Args:
        mensaje: Descripción del error.

    Returns:
        None
    """
    console.print(
        Panel(
            f"[bright_red]{mensaje}[/bright_red]",
            border_style="red",
            title="[bold red]Error[/bold red]",
        )
    )


def mostrar_ok(mensaje: str) -> None:
    """
    Muestra un panel de éxito/confirmación.

    Args:
        mensaje: Mensaje de confirmación.

    Returns:
        None
    """
    console.print(
        Panel(
            f"[bright_green]{mensaje}[/bright_green]",
            border_style="green",
            title="[bold green]Éxito[/bold green]",
        )
    )


def _avisar_requiere_sesion() -> None:
    """
    Muestra un aviso estándar indicando que la acción requiere sesión activa.

    Returns:
        None
    """
    console.print(
        Panel(
            "[yellow]Sin sesión activa: solo puedes visualizar y listar.[/yellow]\n"
            "[white]Para crear, editar o eliminar, inicia sesión o regístrate.[/white]",
            title="[bold cyan]Acción restringida[/bold cyan]",
            border_style="bright_cyan",
        )
    )


def input_email() -> str:
    """
    Solicita un email y lo retorna normalizado en minúsculas.

    Returns:
        str: Correo electrónico ingresado sin espacios y en minúsculas.
    """
    return Prompt.ask("[magenta]Email[/magenta]").strip().lower()


def cargar_autores_indexado() -> Dict[str, Dict[str, Any]]:
    """
    Carga todos los autores y retorna un índice por id_autor.

    Returns:
        Dict[str, Dict[str, Any]]: Mapa id_autor -> autor.
    """
    autores = modelo.leer_todos_los_autores(AUTORES_CSV)
    return {a["id_autor"]: a for a in autores}


def nombre_autor(id_autor: str) -> str:
    """
    Obtiene el nombre visible de un autor a partir de su ID.

    Args:
        id_autor: Identificador del autor.

    Returns:
        str: Nombre del autor o "Autor #<id>" si no se encuentra.
    """
    autores = cargar_autores_indexado()
    autor = autores.get(id_autor)
    return autor["nombre_autor"] if autor else f"Autor #{id_autor}"


def tabla_autores(autores: List[Dict[str, Any]]) -> Table:
    """
    Construye una tabla Rich con la lista de autores.

    Args:
        autores: Lista de diccionarios de autores.

    Returns:
        Table: Tabla formateada para impresión en consola.
    """
    tabla = Table(
        title="Autores",
        border_style="blue",
        show_header=True,
        header_style="bold magenta",
        expand=True,
    )
    tabla.add_column("ID", style="dim", width=6)
    tabla.add_column("Nombre")
    tabla.add_column("Email")

    autores_ordenados = sorted(autores, key=lambda a: int(a["id_autor"]))
    for a in autores_ordenados:
        tabla.add_row(a["id_autor"], a["nombre_autor"], a["email"])
    return tabla


def tabla_posts(posts: List[Dict[str, Any]], mostrar_autor: bool = True) -> Table:
    """
    Construye una tabla Rich con publicaciones.

    Args:
        posts: Lista de publicaciones.
        mostrar_autor: Si True, incluye la columna 'Autor'.

    Returns:
        Table: Tabla formateada con posts.
    """
    tabla = Table(
        title="Publicaciones",
        border_style="blue",
        show_header=True,
        header_style="bold magenta",
        expand=True,
    )
    tabla.add_column("ID", width=6, style="dim")
    if mostrar_autor:
        tabla.add_column("Autor", width=20)
    tabla.add_column("Título", width=32)
    tabla.add_column("Fecha", width=19)
    tabla.add_column("Tags", width=30)
    tabla.add_column("Comentarios", justify="right", width=12)

    for p in sorted(posts, key=lambda x: int(x["id_post"])):
        tags = ", ".join(p.get("tags") or [])
        n_com = len(p.get("comentarios") or [])
        fila = [p["id_post"]]
        if mostrar_autor:
            fila.append(nombre_autor(p["id_autor"]))
        fila.extend([p["titulo"], p["fecha_publicacion"], tags, str(n_com)])
        tabla.add_row(*fila)

    return tabla


def render_post_twitter(post: Dict[str, Any]) -> None:
    """
    Renderiza un post con formato tipo 'tweet' incluyendo sus comentarios.

    Args:
        post: Publicación a mostrar.

    Returns:
        None
    """
    autor = nombre_autor(post["id_autor"])
    titulo = post["titulo"]
    contenido = post["contenido"]
    fecha = post["fecha_publicacion"]
    tags = ", ".join(post.get("tags") or [])

    # Encabezado estilo Twitter (autor izq., título centrado, fecha derecha)
    header = Table.grid(expand=True)
    header.add_column(ratio=2)
    header.add_column(ratio=3, justify="center")
    header.add_column(ratio=2, justify="right")
    header.add_row(
        Text(f"@{autor}", style="bold cyan"),
        Text(titulo, style="bold white"),
        Text(fecha, style="dim"),
    )

    # Contenido principal
    cuerpo = Panel(
        Text(contenido, style="white"),
        border_style="cyan",
        padding=(1, 2),
    )

    # Comentarios
    comentarios_tbl = Table.grid(padding=(0, 1))
    comentarios_tbl.add_column(justify="left", ratio=1)
    comentarios = post.get("comentarios") or []
    if comentarios:
        for c in comentarios:
            cab = Text(
                f"{c['autor']} · {c['fecha']}",
                style="magenta",
            )
            comentarios_tbl.add_row(
                Panel(
                    Text(c["contenido"]),
                    title=cab,
                    border_style="magenta",
                )
            )
    else:
        comentarios_tbl.add_row(
            Text("Sé el primero en comentar...", style="dim")
        )

    post_panel = Panel.fit(
        Group(
            header,
            cuerpo,
            Panel(
                comentarios_tbl,
                title="Comentarios",
                border_style="blue",
            ),
        ),
        title=Text(f"#{post['id_post']}", style="bold blue"),
        border_style="blue",
        padding=(1, 1),
    )
    console.print(post_panel)
    if tags:
        console.print(Text(f"Tags: {tags}", style="yellow"))


def ver_post_con_interacciones(id_post: str) -> None:
    """
    Muestra un post en vista de detalle y ofrece publicar un comentario.

    Args:
        id_post: Identificador de la publicación a abrir.

    Returns:
        None
    """
    post = modelo.buscar_post_por_id(POSTS_JSON, id_post)
    if not post:
        mostrar_error("No existe un post con ese ID.")

        return
    console.print()
    render_post_twitter(post)
    console.print()
    if Confirm.ask("¿Quieres comentar ahora?", default=False):
        if Sesion.activa():
            autor_nombre = Sesion.nombre_autor or "Anónimo"
            contenido = Prompt.ask("Escribe tu comentario").strip()
            if contenido:
                try:
                    modelo.agregar_comentario_a_post(
                        POSTS_JSON,
                        post["id_post"],
                        autor_nombre,
                        contenido,
                        id_autor=Sesion.id_autor,
                    )
                    mostrar_ok("¡Comentario publicado!")
                except modelo.ErrorDeDominio as e:
                    mostrar_error(str(e))
        else:
            console.print("[yellow]Inicia sesión para comentar.[/yellow]")


def ver_post_ui() -> None:
    """
    Flujo UI para solicitar un ID y mostrar un post en detalle.

    Returns:
        None
    """
    console.print(Panel.fit("[bold cyan]Ver Publicación[/bold cyan]"))
    id_post = Prompt.ask("[magenta]ID del post[/magenta]").strip()
    if id_post == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")

        return
    ver_post_con_interacciones(id_post)


# --- Bienvenida del sistema ---
SISTEMA_EMAIL = "sistema@blog.local"
SISTEMA_NOMBRE = "Sistema"
BIENVENIDA_TAG = "bienvenida"
BIENVENIDA_TITULO = "Bienvenido a tu timeline"
BIENVENIDA_CONTENIDO = (
    "Este es tu espacio. Crea publicaciones, comenta y explora.\n"
    "Consejo: usa tags para organizar tus temas favoritos."
)


def ensure_sistema_y_bienvenida() -> Dict[str, Any]:
    """
    Asegura la existencia del autor 'Sistema' y su post de bienvenida.

    Returns:
        Dict[str, Any]: Publicación de bienvenida (creada o existente).
    """
    # Asegurar autor Sistema
    autor_sys = modelo.buscar_autor_por_email(AUTORES_CSV, SISTEMA_EMAIL)
    if not autor_sys:
        autor_sys = modelo.crear_autor(AUTORES_CSV, SISTEMA_NOMBRE, SISTEMA_EMAIL)
    # Asegurar post de bienvenida
    posts = modelo.buscar_posts_por_tag(POSTS_JSON, BIENVENIDA_TAG)
    posts = [p for p in posts if p.get("id_autor") == autor_sys["id_autor"]]
    if posts:
        return posts[0]
    return modelo.crear_post(
        POSTS_JSON,
        autor_sys["id_autor"],
        BIENVENIDA_TITULO,
        BIENVENIDA_CONTENIDO,
        [BIENVENIDA_TAG, "intro"],
        validar_autor_en=AUTORES_CSV,
    )


def mostrar_post_bienvenida_y_comentar() -> None:
    """
    Muestra el post de bienvenida y ofrece comentar si hay sesión activa.

    Returns:
        None
    """
    post = ensure_sistema_y_bienvenida()
    console.print()
    render_post_twitter(post)
    console.print()
    if Confirm.ask(
        "¿Quieres comentar en la bienvenida ahora?",
        default=False,
    ):
        if Sesion.activa():
            autor_nombre = Sesion.nombre_autor or "Anónimo"
            contenido = Prompt.ask("Escribe tu comentario").strip()
            if contenido:
                try:
                    modelo.agregar_comentario_a_post(
                        POSTS_JSON,
                        post["id_post"],
                        autor_nombre,
                        contenido,
                        id_autor=Sesion.id_autor,
                    )
                    mostrar_ok("¡Comentario publicado!")
                except modelo.ErrorDeDominio as e:
                    mostrar_error(str(e))
        else:
            console.print("[yellow]Inicia sesión para comentar.[/yellow]")



# --- Onboarding inicial (registro / login) ---
def onboarding_inicio() -> bool:
    """
    Muestra el onboarding inicial y gestiona login/registro.

    Returns:
        bool: True si se completó el inicio (login/registro) o ya había sesión;
              False si el usuario decide salir.
    """
    # Menú de bienvenida con diseño más colorido y opciones 1/2/0
    menu = Table.grid(expand=True)
    menu.add_column(ratio=1, justify="center")
    menu.add_row(Text("Bienvenido", style="bold bright_cyan"))
    opciones = Table.grid(padding=(0, 2))
    opciones.add_column(justify="right", style="bold yellow")
    opciones.add_column(justify="left")
    opciones.add_row("1", "Iniciar sesión")
    opciones.add_row("2", "Registrarse")
    opciones.add_row("0", "Salir")
    panel = Panel(
        opciones,
        title="[bold cyan]Inicio[/bold cyan]",
        border_style="bright_cyan",
    )
    console.print(panel)

    while not Sesion.activa():
        opcion = Prompt.ask(
            "[magenta]Opción[/magenta]",
            choices=["1", "2", "0"],
            show_choices=False,
            default="1",
        )
        if opcion == "1":
            if iniciar_sesion_ui():
                mostrar_post_bienvenida_y_comentar()
                return True
        elif opcion == "2":
            if registrar_ui():
                mostrar_post_bienvenida_y_comentar()
                return True
        elif opcion == "0":
            return False
    return True


def registrar_ui() -> bool:
    """
    Flujo de registro de autor con configuración de contraseña.

    Returns:
        bool: True si se registró e inició sesión; False si se canceló o falló.
    """
    console.print(
        Panel.fit(
            "[bold cyan]Registro de Autor[/bold cyan]",
            border_style="bright_blue",
        )
    )
    try:
        nombre = pedir_obligatorio("Nombre del autor")
        email = pedir_obligatorio("Email", to_lower=True)
        # Crear autor sin contraseña persistida inicialmente
        autor = modelo.crear_autor(AUTORES_CSV, nombre, email)
        # Solicitar y configurar contraseña antes de iniciar sesión
        while True:
            try:
                pwd = pedir_password_nuevo()
                pwd_hash = _hash_password(pwd)
                modelo.actualizar_autor(
                    AUTORES_CSV,
                    autor["id_autor"],
                    {"password_hash": pwd_hash},
                )
                mostrar_ok("Contraseña configurada.")
                # reflejar en memoria del flujo actual
                autor["password_hash"] = pwd_hash
                break
            except modelo.ValidacionError as e:
                mostrar_error(str(e))
                if not Confirm.ask(
                    "[magenta]¿Reintentar configurar la contraseña?"
                    "[/magenta]",
                    default=True,
                ):
                    console.print(
                        "[yellow]Registro completado sin contraseña. "
                        "Deberá crearla al iniciar sesión.[/yellow]"
                    )

                    return False
            except Cancelado:
                console.print(
                    "[yellow]Operación cancelada. Registro sin "
                    "contraseña.[/yellow]"
                )

                return False

        Sesion.establecer(autor)
        mostrar_ok(f"Cuenta creada. Bienvenido, {autor['nombre_autor']}.")

        return True
    except Cancelado:
        console.print("[yellow]Operación cancelada. Volviendo al menú.[/yellow]")

        return False
    except (modelo.EmailDuplicado, modelo.ValidacionError) as e:
        mostrar_error(str(e))

        return False


def crear_autor_ui() -> None:
    """
    Crea un autor desde la UI y permite configurar su contraseña.

    Returns:
        None
    """
    console.print(
        Panel.fit(
            "[bold cyan]Crear Autor[/bold cyan]",
            border_style="bright_blue",
        )
    )
    try:
        nombre = pedir_obligatorio("Nombre del autor")
        email = pedir_obligatorio("Email", to_lower=True)
        autor = modelo.crear_autor(AUTORES_CSV, nombre, email)
        # Solicitar contraseña para el autor creado
        try:
            pwd = pedir_password_nuevo()
            pwd_hash = _hash_password(pwd)
            modelo.actualizar_autor(
                AUTORES_CSV,
                autor["id_autor"],
                {"password_hash": pwd_hash},
            )
            mostrar_ok(
                "Autor creado con ID "
                f"[bold yellow]{autor['id_autor']}[/bold yellow] "
                "y contraseña configurada."
            )
        except Cancelado:
            console.print("[yellow]Autor creado sin contraseña.[/yellow]")
        except modelo.ValidacionError as e:
            mostrar_error(
                "Autor creado, pero la contraseña no se configuró: "
                f"{e}"
            )
    except Cancelado:
        console.print("[yellow]Operación cancelada.[/yellow]")
    except modelo.EmailDuplicado as e:
        mostrar_error(str(e))
    except modelo.ValidacionError as e:
        mostrar_error(str(e))



def ver_autores_ui() -> None:
    """
    Lista todos los autores en una tabla.

    Returns:
        None
    """
    console.print(
        Panel.fit(
            "[bold cyan]Lista de Autores[/bold cyan]",
            border_style="bright_blue",
        )
    )
    autores = modelo.leer_todos_los_autores(AUTORES_CSV)
    if not autores:
        console.print("[yellow]No hay autores registrados.[/yellow]")
    else:
        console.print(tabla_autores(autores))



def actualizar_autor_ui() -> None:
    """
    Actualiza los datos del autor en sesión (nombre y email).

    Returns:
        None

    Raises:
        Cancelado: Si el usuario cancela durante la edición.
    """
    console.print(
        Panel.fit(
            "[bold cyan]Actualizar Autor[/bold cyan]",
            border_style="bright_blue",
        )
    )
    # NUEVO: solo el autor en sesión puede editar su propio perfil
    if not Sesion.activa():
        _avisar_requiere_sesion()

        return
    try:
        id_autor = Sesion.id_autor  # usar siempre el autor en sesión
        autor_actual = modelo.buscar_autor_por_id(AUTORES_CSV, id_autor)
        if not autor_actual:
            mostrar_error("No se encontró el autor de la sesión.")

            return

        console.print("\nPresione Enter para no modificar un campo.")
        datos: Dict[str, Any] = {}
        nuevo_nombre = Prompt.ask(
            "[magenta]Nombre[/magenta]",
            default=autor_actual["nombre_autor"],
        ).strip()
        if nuevo_nombre == "0":
            raise Cancelado()
        if nuevo_nombre != autor_actual["nombre_autor"]:
            datos["nombre_autor"] = nuevo_nombre

        nuevo_email = Prompt.ask(
            "[magenta]Email[/magenta]",
            default=autor_actual["email"],
        ).strip()
        if nuevo_email == "0":
            raise Cancelado()
        if nuevo_email != autor_actual["email"]:
            datos["email"] = nuevo_email

        if not datos:
            console.print("[yellow]No se modificó ningún dato.[/yellow]")
        else:
            autor_act = modelo.actualizar_autor(
                AUTORES_CSV,
                id_autor,
                datos,
            )
            mostrar_ok(
                "Autor actualizado: "
                f"{autor_act['nombre_autor']} "
                f"<{autor_act['email']}>"
            )
    except Cancelado:
        console.print("[yellow]Operación cancelada.[/yellow]")
    except (
        modelo.AutorNoEncontrado,
        modelo.EmailDuplicado,
        modelo.ValidacionError,
    ) as e:
        mostrar_error(str(e))



def eliminar_autor_ui() -> None:
    """
    Elimina la cuenta del autor en sesión (y cierra sesión).

    Returns:
        None
    """
    console.print(
        Panel.fit(
            "[bold cyan]Eliminar Autor[/bold cyan]",
            border_style="bright_blue",
        )
    )
    # NUEVO: solo el autor en sesión puede eliminar su propia cuenta
    if not Sesion.activa():
        _avisar_requiere_sesion()

        return

    # Mostrar datos del autor a eliminar (el propio)
    autor_actual = modelo.buscar_autor_por_id(AUTORES_CSV, Sesion.id_autor)
    if not autor_actual:
        mostrar_error("No se encontró el autor de la sesión.")

        return

    console.print(
        Panel(
            "Eliminarás tu cuenta: "
            f"[bold]{autor_actual['nombre_autor']}[/bold] "
            f"<{autor_actual['email']}>",
            border_style="red",
        )
    )
    if not Confirm.ask(
        "[magenta]¿Seguro que desea eliminar su cuenta?[/magenta]",
        default=False,
    ):
        console.print("[yellow]Operación cancelada.[/yellow]")

        return

    ok = modelo.eliminar_autor(AUTORES_CSV, Sesion.id_autor)
    if ok:
        mostrar_ok("Cuenta eliminada. La sesión se cerrará.")
        Sesion.limpiar()
    else:
        mostrar_error("No se pudo eliminar la cuenta.")



# --- Menú: Autores (CRUD) ---
def menu_autores() -> None:
    """
    Menú CRUD de autores: crear, ver, actualizar y eliminar.

    Returns:
        None
    """
    while True:
        console.print(
            Panel(
                "[bold yellow]1[/bold yellow]. Crear autor\n"
                "[bold yellow]2[/bold yellow]. Ver autores\n"
                "[bold yellow]3[/bold yellow]. Actualizar autor\n"
                "[bold yellow]4[/bold yellow]. Eliminar autor\n"
                "[bold yellow]5[/bold yellow]. Volver",
                title="[bold cyan]Autores[/bold cyan]",
                border_style="bright_blue",
            )
        )
        opcion = Prompt.ask(
            "[magenta]Opción[/magenta]",
            choices=["1", "2", "3", "4", "5"],
            show_choices=False,
        )
        if opcion == "1":
            crear_autor_ui()
        elif opcion == "2":
            ver_autores_ui()
        elif opcion == "3":
            actualizar_autor_ui()
        elif opcion == "4":
            eliminar_autor_ui()
        elif opcion == "5":
            return


# --- Menú: Sesión (simplificado según estado) ---
def menu_sesion() -> None:
    """
    Menú de sesión: muestra estado, permite cerrar o iniciar sesión.

    Returns:
        None
    """
    if Sesion.activa():
        estado = (
            f"Conectado como [bold green]"
            f"{escape(Sesion.nombre_autor or '')}[/bold green] "
            f"<{escape(Sesion.email or '')}> (ID {escape(str(Sesion.id_autor or ''))})"
        )
        console.print(
            Panel(estado, title="[bold cyan]Sesión[/bold cyan]"
                  , border_style="bright_cyan")
        )
        if Confirm.ask("[magenta]¿Desea cerrar sesión ahora?[/magenta]", default=True):
            Sesion.limpiar()
            mostrar_ok("Sesión cerrada.")
        else:
            console.print("[cyan]Operación cancelada.[/cyan]")

        return
    else:
        console.print(
            Panel(
                "[yellow]No hay sesión activa.[/yellow]\nInicie sesión para continuar.",
                title="[bold cyan]Sesión[/bold cyan]",
                border_style="bright_cyan",
            )
        )
        iniciar_sesion_ui()
        return


def iniciar_sesion_ui() -> bool:  # noqa: PLR0911, PLR0915
    """
    Flujo de inicio de sesión con verificación de contraseña.

    Si el email no existe ofrece registrarse. Si no hay contraseña configurada
    la solicitará y la persistirá.

    Returns:
        bool: True si inicia sesión correctamente; False en caso contrario.
    """
    console.print(
        Panel.fit("[bold cyan]Iniciar Sesión[/bold cyan]", border_style="bright_cyan")
    )
    try:
        email = pedir_obligatorio("Email", to_lower=True)
        autor = modelo.buscar_autor_por_email(AUTORES_CSV, email)

        if autor:
            # Si no tiene password, forzar creación y persistir
            if not autor.get("password_hash"):
                console.print(
                    "[yellow]Este autor no tiene contraseña. "
                    "Debe crearla para continuar.[/yellow]"
                )
                try:
                    pwd_new = pedir_password_nuevo()
                    pwd_hash = _hash_password(pwd_new)
                    modelo.actualizar_autor(
                        AUTORES_CSV, autor["id_autor"], {"password_hash": pwd_hash}
                    )
                    autor["password_hash"] = pwd_hash  # asegurar disponible en memoria
                    mostrar_ok("Contraseña creada.")
                except (Cancelado, modelo.ValidacionError) as e:
                    if isinstance(e, modelo.ValidacionError):
                        mostrar_error(str(e))
                    console.print(
                        "[yellow]No se configuró contraseña. "
                        "Inicio cancelado.[/yellow]"
                    )

                    # Evitar un return adicional; delegar al manejador general
                    raise Cancelado()

            # Validar contraseña persistida
            intentos = 3
            while intentos > 0:
                pwd = pedir("Contraseña", password=True)
                if _verify_password(autor.get("password_hash", ""), pwd):
                    Sesion.establecer(autor)
                    mostrar_ok(f"Bienvenido, {autor['nombre_autor']}.")

                    return True
                else:
                    intentos -= 1
                    mostrar_error(
                        f"Contraseña incorrecta. Intentos restantes: {intentos}"
                    )
            console.print("[red]Demasiados intentos fallidos.[/red]")

            return False

        # Email no registrado: ofrecer registro (con contraseña)
        console.print("[yellow]Email no registrado.[/yellow]")
        if Confirm.ask(
            "[magenta]¿Desea crear una cuenta con este email?[/magenta]",
            default=True,
        ):
            nombre = pedir_obligatorio("Nombre del autor")
            try:
                pwd_new = pedir_password_nuevo()
                pwd_hash = _hash_password(pwd_new)
                autor = modelo.crear_autor(AUTORES_CSV, nombre, email)
                modelo.actualizar_autor(
                    AUTORES_CSV, autor["id_autor"], {"password_hash": pwd_hash}
                )
                autor["password_hash"] = pwd_hash
                Sesion.establecer(autor)
                mostrar_ok(f"Cuenta creada e iniciada: {nombre}.")

                return True
            except (modelo.EmailDuplicado, modelo.ValidacionError) as e:
                mostrar_error(str(e))

        return False
    except (Cancelado, modelo.ValidacionError) as e:
        if isinstance(e, Cancelado):
            console.print("[yellow]Operación cancelada. Volviendo al menú.[/yellow]")
        else:
            mostrar_error(str(e))

        return False


# --- Menús: Publicaciones ---
def menu_publicaciones() -> None:
    """
    Menú de publicaciones: crear, listar por autor, buscar por tag, editar y
    eliminar.

    Returns:
        None
    """
    while True:
        console.print(
            Panel(
                "[bold yellow]1[/bold yellow]. Crear post (requiere sesión)\n"
                "[bold yellow]2[/bold yellow]. Listar posts de un autor\n"
                "[bold yellow]3[/bold yellow]. Buscar posts por tag\n"
                "[bold yellow]4[/bold yellow]. Editar mi post "
                "(requiere sesión)\n"
                "[bold yellow]5[/bold yellow]. Eliminar mi post "
                "(requiere sesión)\n"
                "[bold yellow]6[/bold yellow]. Volver",
                title="[bold cyan]Publicaciones[/bold cyan]",
                border_style="bright_blue",
            )
        )
        opcion = Prompt.ask(
            "[magenta]Opción[/magenta]",
            choices=["1", "2", "3", "4", "5", "6"],
            show_choices=False,
        )
        if opcion == "1":
            crear_post_ui()
        elif opcion == "2":
            listar_posts_de_autor_ui()
        elif opcion == "3":
            buscar_post_por_tag_ui()
        elif opcion == "4":
            editar_post_ui()
        elif opcion == "5":
            eliminar_post_ui()
        elif opcion == "6":
            return


def crear_post_ui() -> None:
    """
    Crea una publicación asociada al autor en sesión.

    Returns:
        None
    """
    if not Sesion.activa():
        mostrar_error("Debe iniciar sesión para crear publicaciones.")

        return

    console.print(
        Panel.fit(
            "[bold cyan]Crear Publicación[/bold cyan]"
            , border_style="bright_blue")
    )
    try:
        titulo = pedir_obligatorio("Título")
        contenido = pedir_obligatorio("Contenido")
        tags = pedir("Tags (separados por comas)", default="")
        post = modelo.crear_post(
            POSTS_JSON,
            Sesion.id_autor,
            titulo,
            contenido,
            tags,
            validar_autor_en=AUTORES_CSV,
        )
        mostrar_ok(f"Post creado con ID [bold yellow]{post['id_post']}[/bold yellow].")
    except Cancelado:
        console.print("[yellow]Operación cancelada.[/yellow]")
    except (modelo.ValidacionError, modelo.AutorNoEncontrado) as e:
        mostrar_error(str(e))



def listar_posts_de_autor_ui() -> None:
    """
    Lista posts de un autor (sesión o seleccionado) con opción de abrir
    detalle.

    Returns:
        None
    """
    console.print(
        Panel.fit(
            "[bold cyan]Posts por Autor[/bold cyan]",
            border_style="bright_blue",
        )
    )
    if Confirm.ask(
        "[magenta]¿Usar autor en sesión?[/magenta]",
        default=Sesion.activa(),
    ):
        if not Sesion.activa():
            mostrar_error("No hay sesión activa.")

            return
        id_autor = Sesion.id_autor
    else:
        # Mostrar tabla de autores para guiar la selección
        autores = modelo.leer_todos_los_autores(AUTORES_CSV)
        if not autores:
            console.print("[yellow]No hay autores registrados.[/yellow]")

            return
        console.print(tabla_autores(autores))
        ids_validos = {a["id_autor"] for a in autores}
        id_autor = Prompt.ask("[magenta]ID del autor[/magenta]").strip()
        if id_autor not in ids_validos:
            mostrar_error("El ID de autor no es válido.")

            return

    posts = modelo.listar_posts_por_autor(POSTS_JSON, id_autor)
    if not posts:
        console.print("[yellow]Este autor no tiene publicaciones.[/yellow]")

        return
    console.print(tabla_posts(posts, mostrar_autor=False))
    # Abrir en vista detalle
    if Confirm.ask("[magenta]¿Abrir un post en vista detalle?[/magenta]", default=True):
        ids_validos = {p["id_post"] for p in posts}
        id_sel = Prompt.ask("[magenta]ID del post a abrir[/magenta]").strip()
        if id_sel not in ids_validos:
            mostrar_error("El ID no pertenece a la lista mostrada.")

            return
        ver_post_con_interacciones(id_sel)



def buscar_post_por_tag_ui() -> None:
    """
    Busca publicaciones por tag, mostrando primero los tags disponibles.

    Returns:
        None
    """
    console.print(
        Panel.fit(
            "[bold cyan]Buscar Posts por Tag[/bold cyan]\n",
            border_style="bright_blue",
        )
    )
    # Mostrar primero los tags disponibles con su conteo
    tags_conteo = _recolectar_tags_conteo()
    if not tags_conteo:
        console.print("[yellow]Aún no hay tags usados en las publicaciones.[/yellow]")

        return
    console.print(_tabla_tags(tags_conteo))

    while True:
        tag = Prompt.ask("[magenta]Tag a buscar[/magenta]").strip()
        if tag == "0":
            console.print("[yellow]Operación cancelada.[/yellow]")

            return
        if not tag:
            mostrar_advertencia("El tag no puede estar vacío. Inténtalo de nuevo.")
            continue
        break
    try:
        posts = modelo.buscar_posts_por_tag(POSTS_JSON, tag)
        if not posts:
            console.print(
                "[yellow]No se encontraron publicaciones con ese tag."
                "[/yellow]"
            )

            return
        console.print(tabla_posts(posts, mostrar_autor=True))
        if Confirm.ask(
            "[magenta]¿Abrir un post en vista detalle?[/magenta]",
            default=True,
        ):
            ids_validos = {p["id_post"] for p in posts}
            id_sel = Prompt.ask(
                "[magenta]ID del post a abrir[/magenta]"
            ).strip()
            if id_sel not in ids_validos:
                mostrar_error(
                    "El ID no pertenece a la lista mostrada."
                )
                return
            ver_post_con_interacciones(id_sel)
    except modelo.ValidacionError as e:
        mostrar_error(str(e))


def _obtener_mis_posts() -> List[Dict[str, Any]]:
    """
    Obtiene todas las publicaciones del autor en sesión.

    Returns:
        List[Dict[str, Any]]: Lista de posts propios (o vacía si no hay sesión).
    """
    if not Sesion.activa():
        return []
    return modelo.listar_posts_por_autor(POSTS_JSON, Sesion.id_autor)


def _mostrar_tabla_y_detalle_posts(posts: List[Dict[str, Any]]) -> None:
    """
    Muestra una tabla de posts y a continuación su vista detalle.

    Args:
        posts: Publicaciones a listar y detallar.

    Returns:
        None
    """
    if not posts:
        console.print("[yellow]No tienes publicaciones.[/yellow]")
        return
    console.print(tabla_posts(posts, mostrar_autor=False))
    console.print()  # separación
    for p in posts:
        render_post_twitter(p)
        console.print()  # separación entre posts


def _cargar_todos_los_posts() -> List[Dict[str, Any]]:
    """
    Carga sin validación estricta el JSON de posts desde disco.

    Returns:
        List[Dict[str, Any]]: Lista de publicaciones (normaliza campos mínimos).
    """
    try:
        datos = gestor_datos.cargar_datos(POSTS_JSON) or []
        # Normalizar estructuras esperadas
        for p in datos:
            p.setdefault("comentarios", [])
            p.setdefault("tags", [])
        return datos
    except Exception:
        return []


# NUEVO: recolectar tags usados con conteo y tabla para mostrarlos
def _recolectar_tags_conteo():
    """
    Recolecta todos los tags usados en publicaciones y su conteo.

    Returns:
        List[Tuple[str, int]]: Lista de pares (tag, conteo) ordenada por uso desc.
    """
    posts = _cargar_todos_los_posts()
    contador: Dict[str, int] = {}
    for p in posts:
        for t in p.get("tags") or []:
            t_norm = str(t).strip()
            if t_norm:
                contador[t_norm] = contador.get(t_norm, 0) + 1
    # Orden: más usados primero, luego alfabético
    return sorted(contador.items(), key=lambda kv: (-kv[1], kv[0].lower()))


def _tabla_tags(tags_conteo) -> Table:
    """
    Construye la tabla de tags con su número de usos.

    Args:
        tags_conteo: Secuencia de pares (tag, conteo).

    Returns:
        Table: Tabla formateada para impresión.
    """
    tabla = Table(
        title="Tags disponibles",
        border_style="blue",
        show_header=True,
        header_style="bold magenta",
        expand=True,
    )
    tabla.add_column("Tag", width=28)
    tabla.add_column("Usos", justify="right", width=6)
    for tag, cnt in tags_conteo:
        tabla.add_row(str(tag), str(cnt))
    return tabla


def _recolectar_mis_comentarios() -> List[Dict[str, Any]]:
    """
    Devuelve los comentarios realizados por el autor en sesión.

    Returns:
        List[Dict[str, Any]]: Cada item contiene
        id_comentario, id_post, fecha, autor y contenido.
    """
    if not Sesion.activa():
        return []
    posts = _cargar_todos_los_posts()
    mis: List[Dict[str, Any]] = []
    for p in posts:
        for c in p.get("comentarios") or []:
            if str(c.get("id_autor") or "") == str(Sesion.id_autor):
                mis.append({
                    "id_comentario": str(c.get("id_comentario")),
                    "id_post": str(p.get("id_post")),
                    "fecha": str(c.get("fecha", "")),
                    "autor": str(c.get("autor", "")),
                    "contenido": str(c.get("contenido", "")),
                })
    return mis


def _tabla_mis_comentarios(mis: List[Dict[str, Any]]) -> Table:
    """
    Construye una tabla con los comentarios del autor en sesión.

    Args:
        mis: Lista de comentarios propios.

    Returns:
        Table: Tabla formateada con comentarios.
    """
    tabla = Table(
        title="Mis Comentarios",
        border_style="blue",
        show_header=True,
        header_style="bold magenta",
        expand=True,
    )
    tabla.add_column("ID Comentario", width=14, style="dim")
    tabla.add_column("ID Post", width=8)
    tabla.add_column("Fecha", width=19)
    tabla.add_column("Contenido", overflow="fold")
    for c in mis:
        contenido = c["contenido"]
        if len(contenido) <= RESUMEN_COMENTARIO_MAX:
            contenido_corto = contenido
        else:
            # Reservar 3 caracteres para '...'
            contenido_corto = contenido[: RESUMEN_COMENTARIO_MAX - 3] + "..."
        tabla.add_row(
            c["id_comentario"],
            c["id_post"],
            c["fecha"],
            contenido_corto,
        )
    return tabla


def _mostrar_tabla_y_detalle_mis_comentarios(mis: List[Dict[str, Any]]) -> None:
    """
    Muestra tabla de mis comentarios y luego la vista detalle de los posts.

    Args:
        mis: Lista de comentarios propios.

    Returns:
        None
    """
    if not mis:
        console.print("[yellow]No has realizado comentarios.[/yellow]")
        return
    console.print(_tabla_mis_comentarios(mis))
    console.print()
    # Mostrar detalle de los posts donde están mis comentarios (sin repetir)
    posts_unicos = []
    vistos = set()
    for c in mis:
        if c["id_post"] not in vistos:
            vistos.add(c["id_post"])
            posts_unicos.append(c["id_post"])
    for id_post in posts_unicos:
        post = modelo.buscar_post_por_id(POSTS_JSON, id_post)
        if post:
            render_post_twitter(post)
            console.print()


def editar_post_ui() -> None:  # noqa: PLR0911, PLR0912, PLR0915
    """
    Edita una publicación del autor en sesión, guiando con tabla y detalle.

    Returns:
        None
    """
    if not Sesion.activa():
        mostrar_error("Debe iniciar sesión para editar sus publicaciones.")
        return

    console.print(
        Panel.fit(
            "[bold cyan]Editar Publicación[/bold cyan]", border_style="bright_blue"
        )
    )

    # 1) Mostrar primero mis posts (tabla + detalle)
    mis_posts = _obtener_mis_posts()
    if not mis_posts:
        console.print("[yellow]No tienes publicaciones para editar.[/yellow]")
        return
    _mostrar_tabla_y_detalle_posts(mis_posts)

    # 2) Pedir ID del post a editar (validando que sea mío)
    ids_validos = {p["id_post"] for p in mis_posts}
    id_post = Prompt.ask("[magenta]ID del post a editar[/magenta]").strip()
    if id_post == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        return
    if id_post not in ids_validos:
        mostrar_error("El ID indicado no pertenece a tus publicaciones.")
        return

    post = modelo.buscar_post_por_id(POSTS_JSON, id_post)
    if not post:
        mostrar_error("No existe un post con ese ID.")
        return

    # 3) Solicitar cambios
    console.print("\nPresione Enter para no modificar un campo.")
    nuevos: Dict[str, Any] = {}
    nuevo_titulo = Prompt.ask(
        "[magenta]Título[/magenta]", default=post["titulo"]
    ).strip()
    if nuevo_titulo == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        return
    if nuevo_titulo != post["titulo"]:
        nuevos["titulo"] = nuevo_titulo

    nuevo_contenido = Prompt.ask(
        "[magenta]Contenido[/magenta]", default=post["contenido"]
    ).strip()
    if nuevo_contenido == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        return
    if nuevo_contenido != post["contenido"]:
        nuevos["contenido"] = nuevo_contenido

    actuales = ", ".join(post.get("tags") or [])
    nuevos_tags = Prompt.ask("[magenta]Tags (coma)[/magenta]", default=actuales).strip()
    if nuevos_tags == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        return
    if nuevos_tags != actuales:
        nuevos["tags"] = nuevos_tags

    if not nuevos:
        console.print("[yellow]No se modificó ningún campo.[/yellow]")
        return

    # 4) Confirmar y aplicar
    if not Confirm.ask(
        "[magenta]¿Confirmar actualización del post?[/magenta]", default=True
    ):
        console.print("[yellow]Operación cancelada.[/yellow]")
        return

    try:
        post_act = modelo.actualizar_post(POSTS_JSON, id_post, Sesion.id_autor, nuevos)
        mostrar_ok(f"Post actualizado: {post_act['titulo']}")
        # 5) Mostrar resultado: tabla actualizada + vista detalle del post
        mis_posts = _obtener_mis_posts()
        _mostrar_tabla_y_detalle_posts(mis_posts)
        ver_post_con_interacciones(id_post)
    except (
        modelo.PostNoEncontrado,
        modelo.AccesoNoAutorizado,
        modelo.ValidacionError,
    ) as e:
        mostrar_error(str(e))


def eliminar_post_ui() -> None:
    """
    Elimina una publicación del autor en sesión, tras confirmación.

    Returns:
        None
    """
    if not Sesion.activa():
        mostrar_error("Debe iniciar sesión para eliminar sus publicaciones.")
        return

    console.print(
        Panel.fit(
            "[bold cyan]Eliminar Publicación[/bold cyan]\n", border_style="bright_blue"
        )
    )

    # 1) Mostrar primero mis posts (tabla + detalle)
    mis_posts = _obtener_mis_posts()
    if not mis_posts:
        console.print("[yellow]No tienes publicaciones para eliminar.[/yellow]")
        return
    _mostrar_tabla_y_detalle_posts(mis_posts)

    # 2) Pedir ID del post a eliminar (validando que sea mío)
    ids_validos = {p["id_post"] for p in mis_posts}
    id_post = Prompt.ask("[magenta]ID del post a eliminar[/magenta]").strip()
    if id_post == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")

        return
    if id_post not in ids_validos:
        mostrar_error("El ID indicado no pertenece a tus publicaciones.")

        return

    # 3) Confirmar y aplicar
    if not Confirm.ask(
        "[magenta]¿Seguro que desea eliminar este post?[/magenta]", default=False
    ):
        console.print("[yellow]Operación cancelada.[/yellow]")
        return

    try:
        ok = modelo.eliminar_post(POSTS_JSON, id_post, Sesion.id_autor)
        if ok:
            mostrar_ok("Publicación eliminada.")
        else:
            mostrar_error("No existe un post con ese ID.")
        # 4) Mostrar resultado: tabla actualizada + detalle de los restantes
        mis_posts = _obtener_mis_posts()
        if mis_posts:
            _mostrar_tabla_y_detalle_posts(mis_posts)
        else:
            console.print("[yellow]Ya no tienes publicaciones.[/yellow]")
    except modelo.AccesoNoAutorizado as e:
        mostrar_error(str(e))


def eliminar_comentario_ui() -> None:  # noqa: PLR0912
    """
    Elimina un comentario propio, mostrando primero tabla y detalle para guiar.

    Returns:
        None
    """
    console.print(
        Panel.fit(
            "[bold cyan]Eliminar Comentario[/bold cyan]",
            border_style="bright_magenta",
        )
    )

    # Requiere sesión para filtrar “mis comentarios”
    if not Sesion.activa():
        mostrar_error("Debe iniciar sesión para eliminar sus comentarios.")
        return

    # 1) Mostrar primero mis comentarios (tabla + detalle de sus posts)
    mis_coms = _recolectar_mis_comentarios()
    if not mis_coms:
        console.print("[yellow]No has realizado comentarios para eliminar.[/yellow]")
        return
    _mostrar_tabla_y_detalle_mis_comentarios(mis_coms)

    # Índice por id_comentario -> lista de id_post (por si hubiera colisiones)
    idx: Dict[str, List[str]] = {}
    for c in mis_coms:
        idx.setdefault(c["id_comentario"], []).append(c["id_post"])

    # 2) Pedir ID del comentario (y post si es necesario)
    id_com = Prompt.ask("[magenta]ID del comentario a eliminar[/magenta]").strip()
    if id_com == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        return
    if id_com not in idx:
        mostrar_error("El ID de comentario no pertenece a tus comentarios.")
        return

    posts_posibles = idx[id_com]
    id_post = posts_posibles[0]
    if len(posts_posibles) > 1:
        # Desambiguar si ese id_comentario aparece más de una vez (raro, pero seguro)
        id_post = Prompt.ask(
            "[magenta]ID del post que contiene el comentario[/magenta]"
        ).strip()
        if id_post not in posts_posibles:
            mostrar_error("La combinación de IDs no es válida.")
            return

    # 3) Confirmar y aplicar
    if not Confirm.ask(
        "[magenta]¿Seguro que desea eliminar este comentario?[/magenta]",
        default=False,
    ):
        console.print("[yellow]Operación cancelada.[/yellow]")
        return

    try:
        ok = modelo.eliminar_comentario_de_post(
            POSTS_JSON, id_post, id_com, id_autor_en_sesion=Sesion.id_autor
        )
        if ok:
            mostrar_ok("Comentario eliminado.")
        else:
            mostrar_error("No se encontró el comentario.")
        # 4) Mostrar resultado: tabla actualizada + detalle de posts con mis comentarios
        mis_coms = _recolectar_mis_comentarios()
        if mis_coms:
            _mostrar_tabla_y_detalle_mis_comentarios(mis_coms)
        else:
            console.print("[yellow]Ya no tienes comentarios propios.[/yellow]")
    except (modelo.PostNoEncontrado, modelo.AccesoNoAutorizado) as e:
        mostrar_error(str(e))


# --- Menú y UIs: Comentarios ---
def agregar_comentario_ui() -> None:
    """
    Agrega un comentario a un post, mostrando el detalle antes de confirmar.

    Returns:
        None
    """
    if not Sesion.activa():
        mostrar_error("Debe iniciar sesión para comentar.")
        return

    console.print(
        Panel.fit(
            "[bold cyan]Agregar Comentario[/bold cyan]",
            border_style="bright_magenta",
        )
    )
    id_post = Prompt.ask("[magenta]ID del post a comentar[/magenta]").strip()
    if id_post == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        return

    post = modelo.buscar_post_por_id(POSTS_JSON, id_post)
    if not post:
        mostrar_error("No existe un post con ese ID.")
        return

    # Mostrar primero la vista detalle del post a comentar
    render_post_twitter(post)
    console.print()
    contenido = pedir_obligatorio("Contenido del comentario")
    if not Confirm.ask("[magenta]¿Publicar este comentario?[/magenta]", default=True):
        console.print("[yellow]Operación cancelada.[/yellow]")
        return

    try:
        modelo.agregar_comentario_a_post(
            POSTS_JSON,
            id_post,
            Sesion.nombre_autor or "Anónimo",
            contenido,
            id_autor=Sesion.id_autor,
        )
        mostrar_ok("¡Comentario publicado!")
        # Mostrar el post actualizado en vista detalle
        post_act = modelo.buscar_post_por_id(POSTS_JSON, id_post)
        if post_act:
            console.print()
            render_post_twitter(post_act)
    except modelo.ErrorDeDominio as e:
        mostrar_error(str(e))


def editar_comentario_ui() -> None:  # noqa: PLR0911, PLR0912, PLR0915
    """
    Edita un comentario propio, guiando con tabla y detalle y confirmación
    final.

    Returns:
        None
    """
    if not Sesion.activa():
        mostrar_error("Debe iniciar sesión para editar sus comentarios.")
        return

    console.print(
        Panel.fit(
            "[bold cyan]Editar Comentario[/bold cyan]",
            border_style="bright_magenta",
        )
    )

    # 1) Mostrar primero mis comentarios (tabla + detalle de sus posts)
    mis_coms = _recolectar_mis_comentarios()
    if not mis_coms:
        console.print("[yellow]No has realizado comentarios para editar.[/yellow]")
        return
    _mostrar_tabla_y_detalle_mis_comentarios(mis_coms)

    # Índice por id_comentario -> lista de id_post (por si hubiera colisiones)
    idx: Dict[str, List[str]] = {}
    for c in mis_coms:
        idx.setdefault(c["id_comentario"], []).append(c["id_post"])

    # 2) Pedir ID del comentario (y post si es necesario)
    id_com = Prompt.ask("[magenta]ID del comentario a editar[/magenta]").strip()
    if id_com == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        return
    if id_com not in idx:
        mostrar_error("El ID de comentario no pertenece a tus comentarios.")
        return

    posts_posibles = idx[id_com]
    id_post = posts_posibles[0]
    if len(posts_posibles) > 1:
        id_post = Prompt.ask(
            "[magenta]ID del post que contiene el comentario[/magenta]"
        ).strip()
        if id_post not in posts_posibles:
            mostrar_error("La combinación de IDs no es válida.")
            return

    # Obtener el contenido actual para usarlo como default
    post = modelo.buscar_post_por_id(POSTS_JSON, id_post)
    if not post:
        mostrar_error("No existe un post con ese ID.")
        return
    comentario_actual = None
    for c in post.get("comentarios") or []:
        if (
            str(c.get("id_comentario")) == id_com
            and str(c.get("id_autor")) == str(Sesion.id_autor)
        ):
            comentario_actual = c
            break
    if not comentario_actual:
        mostrar_error("No se encontró el comentario a editar en ese post.")
        return

    nuevo_contenido = pedir_obligatorio(
        "Nuevo contenido",
        default=str(comentario_actual.get("contenido", "")),
    )
    if not Confirm.ask(
        "[magenta]¿Confirmar actualización del comentario?[/magenta]",
        default=True,
    ):
        console.print("[yellow]Operación cancelada.[/yellow]")
        return

    try:
        # Se asume que el modelo expone esta operación. Si no existe, mostrar aviso.
        if hasattr(modelo, "actualizar_comentario_de_post"):
            modelo.actualizar_comentario_de_post(
                POSTS_JSON,
                id_post,
                id_com,
                {"contenido": nuevo_contenido},
                id_autor_en_sesion=Sesion.id_autor,
            )
            mostrar_ok("Comentario actualizado.")
        else:
            mostrar_error(
                "La edición de comentarios no está disponible en el "
                "modelo (falta 'actualizar_comentario_de_post')."
            )
            return

        # 4) Mostrar resultado: tabla actualizada +
        # detalle de los posts donde tengo comentarios
        mis_coms = _recolectar_mis_comentarios()
        if mis_coms:
            _mostrar_tabla_y_detalle_mis_comentarios(mis_coms)
        else:
            console.print("[yellow]Ya no tienes comentarios propios.[/yellow]")
        # También mostrar el post afectado
        post_act = modelo.buscar_post_por_id(POSTS_JSON, id_post)
        if post_act:
            console.print()
            render_post_twitter(post_act)
    except (
        modelo.PostNoEncontrado,
        modelo.AccesoNoAutorizado,
        modelo.ValidacionError,
    ) as e:
        mostrar_error(str(e))


def menu_comentarios() -> None:
    """
    Menú de comentarios: agregar, editar y eliminar.

    Returns:
        None
    """
    while True:
        console.print(
            Panel(
                "[bold yellow]1.[/bold yellow]Agregar comentario\n"
                "[bold yellow]2.[/bold yellow] Editar mi comentario\n"
                "[bold yellow]3.[/bold yellow] Eliminar mi comentario\n"
                "[bold yellow]4.[/bold yellow] Volver",
                title="[bold cyan]Comentarios[/bold cyan]",
                border_style="bright_blue",
            )
        )
        opcion = Prompt.ask(
            "[magenta]Opción[/magenta]",
            choices=["1", "2", "3", "4"],
            show_choices=False,
        )
        if opcion == "1":
            agregar_comentario_ui()
        elif opcion == "2":
            editar_comentario_ui()
        elif opcion == "3":
            eliminar_comentario_ui()
        elif opcion == "4":
            return


# --- Menú principal ---
def mostrar_menu_principal() -> None:
    """
    Muestra el menú principal y el estado de sesión como subtítulo.

    Returns:
        None
    """
    sesion_txt = (
        Text.assemble(
            Text("Conectado: ", style="bright_green"),
            Text(
                f"{Sesion.nombre_autor} <{Sesion.email}>",
                style="green",
            ),
        )
        if Sesion.activa()
        else Text("Sin sesión", style="bright_yellow")
    )
    console.print(
        Panel(
            "[bold cyan]Bienvenido a Nuestro Blog Multi-usuario[/bold cyan]\n"
            "[bold cyan]1)[/bold cyan] [bold yellow]Publicaciones (POSTS)"
            "[/bold yellow]\n"
            "[bold cyan]2)[/bold cyan] [bold yellow]Comentarios[/bold yellow]\n"
            "[bold cyan]3)[/bold cyan] [bold yellow]Autores[/bold yellow]\n"
            "[bold cyan]4)[/bold cyan] [bold yellow]Sesión[/bold yellow]",
            title="[bold cyan]MENÚ PRINCIPAL[/bold cyan]",
            border_style="bright_cyan",
            subtitle=sesion_txt,
            subtitle_align="right",
        )
    )
    console.print("[bold red]5. Salir[/bold red]")


def main() -> None:
    """
    Punto de entrada de la aplicación.

    Inicializa archivos, muestra bienvenida y gestiona el bucle principal del
    menú.

    Returns:
        None
    """
    init_archivos()
    # Asegurar bienvenida del sistema
    ensure_sistema_y_bienvenida()
    banner()
    # Salida solicitada: etiqueta y rutas en verde
    console.print(
        (
            "Archivos de Datos: "
            f"[green]{os.path.join('data','autores.csv')}[/green], "
            f"[green]{os.path.join('data','posts.json')}[/green]"
        )
    )

    # Onboarding: inicio de sesión por defecto primero
    if not onboarding_inicio():
        console.print("\n[bold magenta]¡Hasta luego![/bold magenta]")
        return

    while True:
        mostrar_menu_principal()
        opcion = Prompt.ask(
            "[magenta]Opción[/magenta]",
            choices=["1", "2", "3", "4", "5"],
            show_choices=False,
        )
        if opcion == "1":
            menu_publicaciones()
        elif opcion == "2":
            menu_comentarios()
        elif opcion == "3":
            menu_autores()
        elif opcion == "4":
            menu_sesion()
        elif opcion == "5":
            console.print("\n[bold magenta]¡Hasta luego![/bold magenta]")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print(
            "\n\n[bold red]Programa interrumpido por el usuario. "
            "Adiós.[/bold red]"
        )
