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

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import gestor_datos
import blog_multi_usuario as modelo

# --- Rich ---
from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

console = Console()

# --- Cancelación de formularios ---
class Cancelado(Exception):
    pass

def pedir(mensaje: str, *, password: bool = False, default: Optional[str] = None, to_lower: bool = False) -> str:
    """
    Envuelve Prompt.ask y permite cancelar con '0'.
    """
    etiqueta = f"{mensaje} [dim](0 para salir)[/dim]"
    valor = Prompt.ask(etiqueta, password=password, default=default).strip()
    if valor == "0":
        raise Cancelado()
    return valor.lower() if to_lower else valor

# --- Configuración de rutas ---
# Hacemos la ruta a 'data/' robusta, independiente del cwd
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DIRECTORIO_DATOS = os.path.join(BASE_DIR, "data")
AUTORES_CSV = os.path.join(DIRECTORIO_DATOS, "autores.csv")
POSTS_JSON = os.path.join(DIRECTORIO_DATOS, "posts.json")


# --- Estado de sesión (simulado) ---
class Sesion:
    id_autor: Optional[str] = None
    nombre_autor: Optional[str] = None
    email: Optional[str] = None

    @classmethod
    def activa(cls) -> bool:
        return cls.id_autor is not None

    @classmethod
    def establecer(cls, autor: Dict[str, Any]) -> None:
        cls.id_autor = autor.get("id_autor")
        cls.nombre_autor = autor.get("nombre_autor")
        cls.email = autor.get("email")

    @classmethod
    def limpiar(cls) -> None:
        cls.id_autor = None
        cls.nombre_autor = None
        cls.email = None


# --- Helpers UI ---
def init_archivos() -> None:
    gestor_datos.inicializar_archivo(AUTORES_CSV)
    gestor_datos.inicializar_archivo(POSTS_JSON)


def banner() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]Sistema de Blog Multi-usuario[/bold cyan]",
            border_style="bright_magenta",
        )
    )


def pausar():
    console.input("[bold blue]Dale Enter para continuar...[/bold blue]")


def mostrar_error(mensaje: str) -> None:
    console.print(Panel(f"[bright_red]{mensaje}[/bright_red]", border_style="red", title="[bold red]Error[/bold red]"))


def mostrar_ok(mensaje: str) -> None:
    console.print(Panel(f"[bright_green]{mensaje}[/bright_green]", border_style="green", title="[bold green]Éxito[/bold green]"))


def input_email() -> str:
    return Prompt.ask("Email").strip().lower()


def cargar_autores_indexado() -> Dict[str, Dict[str, Any]]:
    autores = modelo.leer_todos_los_autores(AUTORES_CSV)
    return {a["id_autor"]: a for a in autores}


def nombre_autor(id_autor: str) -> str:
    autores = cargar_autores_indexado()
    autor = autores.get(id_autor)
    return autor["nombre_autor"] if autor else f"Autor #{id_autor}"


def tabla_autores(autores: List[Dict[str, Any]]) -> Table:
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


# --- Vista tipo "Twitter" ---
def render_post_twitter(post: Dict[str, Any]) -> None:
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
            cab = Text(f"{c['autor']} · {c['fecha']}", style="magenta")
            comentarios_tbl.add_row(Panel(Text(c["contenido"]), title=cab, border_style="magenta"))
    else:
        comentarios_tbl.add_row(Text("Sé el primero en comentar...", style="dim"))

    post_panel = Panel.fit(
        Group(header, cuerpo, Panel(comentarios_tbl, title="Comentarios", border_style="blue")),
        title=Text(f"#{post['id_post']}", style="bold blue"),
        border_style="blue",
        padding=(1, 1),
    )
    console.print(post_panel)
    if tags:
        console.print(Text(f"Tags: {tags}", style="dim"))

# --- NUEVO: Vista detalle con interacción (misma interfaz que bienvenida) ---
def ver_post_con_interacciones(id_post: str) -> None:
    post = modelo.buscar_post_por_id(POSTS_JSON, id_post)
    if not post:
        mostrar_error("No existe un post con ese ID.")
        pausar()
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
                        POSTS_JSON, post["id_post"], autor_nombre, contenido, id_autor=Sesion.id_autor
                    )
                    mostrar_ok("¡Comentario publicado!")
                except modelo.ErrorDeDominio as e:
                    mostrar_error(str(e))
        else:
            console.print("[yellow]Inicia sesión para comentar.[/yellow]")
    pausar()


def ver_post_ui() -> None:
    console.print(Panel.fit("[bold cyan]Ver Publicación[/bold cyan]\n[dim]Use 0 para salir.[/dim]"))
    id_post = Prompt.ask("ID del post").strip()
    if id_post == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        pausar()
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
    # Asegurar autor Sistema
    autor_sys = modelo.buscar_autor_por_email(AUTORES_CSV, SISTEMA_EMAIL)
    if not autor_sys:
        # Contraseña irrelevante para el sistema (modelo no maneja contraseñas)
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
    post = ensure_sistema_y_bienvenida()
    console.print()
    render_post_twitter(post)
    console.print()
    if Confirm.ask("¿Quieres comentar en la bienvenida ahora?", default=False):
        if Sesion.activa():
            autor_nombre = Sesion.nombre_autor or "Anónimo"
            contenido = Prompt.ask("Escribe tu comentario").strip()
            if contenido:
                try:
                    modelo.agregar_comentario_a_post(
                        POSTS_JSON, post["id_post"], autor_nombre, contenido, id_autor=Sesion.id_autor
                    )
                    mostrar_ok("¡Comentario publicado!")
                except modelo.ErrorDeDominio as e:
                    mostrar_error(str(e))
        else:
            console.print("[yellow]Inicia sesión para comentar.[/yellow]")
    pausar()

# --- Onboarding inicial (registro / login) ---
def onboarding_inicio() -> bool:
    # Menú de bienvenida con diseño más colorido y opciones 1/2/0
    menu = Table.grid(expand=True)
    menu.add_column(ratio=1, justify="center")
    menu.add_row(Text("Bienvenido", style="bold bright_cyan"))
    opciones = Table.grid(padding=(0, 2))
    opciones.add_column(justify="right", style="bold yellow")
    opciones.add_column(justify="left")
    opciones.add_row("1", "Registrarse")
    opciones.add_row("2", "Iniciar sesión")
    opciones.add_row("0", "Salir")
    panel = Panel(opciones, title="[bold cyan]Inicio[/bold cyan]", border_style="bright_cyan")
    console.print(panel)

    while not Sesion.activa():
        opcion = Prompt.ask("Elige una opción", choices=["1", "2", "0"], show_choices=False, default="1")
        if opcion == "1":
            if registrar_ui():
                mostrar_post_bienvenida_y_comentar()
                return True
        elif opcion == "2":
            if iniciar_sesion_ui():
                mostrar_post_bienvenida_y_comentar()
                return True
        elif opcion == "0":
            return False
    return True

def registrar_ui() -> bool:
    console.print(Panel.fit("[bold cyan]Registro de Autor[/bold cyan]\n[dim]Use 0 en cualquier campo para salir.[/dim]", border_style="bright_blue"))
    try:
        nombre = pedir("Nombre del autor")
        email = pedir("Email", to_lower=True)
        # El modelo no maneja contraseñas; registro por email único
        autor = modelo.crear_autor(AUTORES_CSV, nombre, email)
        Sesion.establecer(autor)
        mostrar_ok(f"Cuenta creada. Bienvenido, {autor['nombre_autor']}.")
        pausar()
        return True
    except Cancelado:
        console.print("[yellow]Operación cancelada. Volviendo al menú.[/yellow]")
        pausar()
        return False
    except (modelo.EmailDuplicado, modelo.ValidacionError) as e:
        mostrar_error(str(e))
        pausar()
        return False


# --- Menú: Autores ---
def menu_autores():
    while True:
        console.print(
            Panel(
                "[bold yellow]1[/bold yellow]. Crear autor\n"
                "[bold yellow]2[/bold yellow]. Ver autores\n"
                "[bold yellow]3[/bold yellow]. Actualizar autor\n"
                "[bold yellow]4[/bold yellow]. Eliminar autor\n"
                "[bold yellow]5[/bold yellow]. Volver",
                title="[bold cyan]Autores[/bold cyan]",
                border_style="bright_green",
            )
        )
        opcion = Prompt.ask("Opción", choices=["1", "2", "3", "4", "5"], show_choices=False)

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


def crear_autor_ui():
    console.print(Panel.fit("[bold cyan]Crear Autor[/bold cyan]\n[dim]Use 0 en cualquier campo para salir.[/dim]", border_style="bright_blue"))
    try:
        nombre = pedir("Nombre del autor")
        email = pedir("Email", to_lower=True)
        autor = modelo.crear_autor(AUTORES_CSV, nombre, email)
        mostrar_ok(f"Autor creado con ID [bold yellow]{autor['id_autor']}[/bold yellow].")
    except Cancelado:
        console.print("[yellow]Operación cancelada.[/yellow]")
    except modelo.EmailDuplicado as e:
        mostrar_error(str(e))
    except modelo.ValidacionError as e:
        mostrar_error(str(e))
    pausar()


def ver_autores_ui():
    console.print(Panel.fit("[bold cyan]Lista de Autores[/bold cyan]", border_style="bright_blue"))
    autores = modelo.leer_todos_los_autores(AUTORES_CSV)
    if not autores:
        console.print("[yellow]No hay autores registrados.[/yellow]")
    else:
        console.print(tabla_autores(autores))
    pausar()


def actualizar_autor_ui():
    console.print(Panel.fit("[bold cyan]Actualizar Autor[/bold cyan]\n[dim]Use 0 en cualquier campo para salir.[/dim]", border_style="bright_blue"))
    try:
        id_autor = pedir("ID del autor a actualizar")
        autor_actual = modelo.buscar_autor_por_id(AUTORES_CSV, id_autor)
        if not autor_actual:
            mostrar_error("No se encontró el autor.")
            pausar()
            return

        console.print("\nPresione Enter para no modificar un campo.")
        datos: Dict[str, Any] = {}
        nuevo_nombre = Prompt.ask("Nombre", default=autor_actual["nombre_autor"]).strip()
        if nuevo_nombre == "0":
            raise Cancelado()
        if nuevo_nombre != autor_actual["nombre_autor"]:
            datos["nombre_autor"] = nuevo_nombre

        nuevo_email = Prompt.ask("Email", default=autor_actual["email"]).strip()
        if nuevo_email == "0":
            raise Cancelado()
        if nuevo_email != autor_actual["email"]:
            datos["email"] = nuevo_email

        if not datos:
            console.print("[yellow]No se modificó ningún dato.[/yellow]")
        else:
            autor_act = modelo.actualizar_autor(AUTORES_CSV, id_autor, datos)
            mostrar_ok(f"Autor actualizado: {autor_act['nombre_autor']} <{autor_act['email']}>")
    except Cancelado:
        console.print("[yellow]Operación cancelada.[/yellow]")
    except (modelo.AutorNoEncontrado, modelo.EmailDuplicado, modelo.ValidacionError) as e:
        mostrar_error(str(e))
    pausar()


def eliminar_autor_ui():
    console.print(Panel.fit("[bold cyan]Eliminar Autor[/bold cyan]\n[dim]Use 0 para salir.[/dim]", border_style="bright_blue"))
    id_autor = Prompt.ask("ID del autor a eliminar").strip()
    if id_autor == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        pausar()
        return
    if not Confirm.ask("¿Seguro que desea eliminar al autor?", default=False):
        console.print("[yellow]Operación cancelada.[/yellow]")
        pausar()
        return
    ok = modelo.eliminar_autor(AUTORES_CSV, id_autor)
    if ok:
        mostrar_ok("Autor eliminado.")
    else:
        mostrar_error("No se encontró el autor.")
    pausar()


# --- Menú: Sesión (simplificado según estado) ---
def menu_sesion():
    if Sesion.activa():
        estado = f"Conectado como [bold green]{Sesion.nombre_autor}[/bold green] <{Sesion.email}> (ID {Sesion.id_autor})"
        console.print(Panel(estado, title="[bold cyan]Sesión[/bold cyan]", border_style="bright_cyan"))
        if Confirm.ask("¿Desea cerrar sesión ahora?", default=True):
            Sesion.limpiar()
            mostrar_ok("Sesión cerrada.")
        else:
            console.print("[cyan]Operación cancelada.[/cyan]")
        pausar()
        return
    else:
        console.print(Panel("[yellow]No hay sesión activa.[/yellow]\nInicie sesión para continuar.", title="[bold cyan]Sesión[/bold cyan]", border_style="bright_cyan"))
        iniciar_sesion_ui()
        return

def iniciar_sesion_ui() -> bool:
    console.print(Panel.fit("[bold cyan]Iniciar Sesión[/bold cyan]\n[dim]Use 0 en cualquier campo para salir.[/dim]", border_style="bright_cyan"))
    try:
        email = pedir("Email", to_lower=True)
        # Autenticación simple por email (sin contraseña)
        autor = modelo.buscar_autor_por_email(AUTORES_CSV, email)
        if autor:
            Sesion.establecer(autor)
            mostrar_ok(f"Bienvenido, {autor['nombre_autor']}.")
            pausar()
            return True

        console.print("[yellow]Email no registrado.[/yellow]")
        if Confirm.ask("¿Desea crear una cuenta con este email?", default=True):
            nombre = pedir("Nombre del autor")
            try:
                autor = modelo.crear_autor(AUTORES_CSV, nombre, email)
                Sesion.establecer(autor)
                mostrar_ok(f"Cuenta creada e iniciada: {nombre}.")
                pausar()
                return True
            except (modelo.EmailDuplicado, modelo.ValidacionError) as e:
                mostrar_error(str(e))
        pausar()
        return False
    except Cancelado:
        console.print("[yellow]Operación cancelada. Volviendo al menú.[/yellow]")
        pausar()
        return False
    except modelo.ValidacionError as e:
        mostrar_error(str(e))
        pausar()
        return False

# --- Menús: Publicaciones ---
def menu_publicaciones():
    while True:
        console.print(
            Panel(
                "[bold yellow]1[/bold yellow]. Crear post (requiere sesión)\n"
                "[bold yellow]2[/bold yellow]. Listar posts de un autor\n"
                "[bold yellow]3[/bold yellow]. Buscar posts por tag\n"
                "[bold yellow]4[/bold yellow]. Editar mi post (requiere sesión)\n"
                "[bold yellow]5[/bold yellow]. Eliminar mi post (requiere sesión)\n"
                "[bold yellow]6[/bold yellow]. Volver",
                title="[bold cyan]Publicaciones[/bold cyan]",
                border_style="bright_blue",
            )
        )
        opcion = Prompt.ask("Opción", choices=["1", "2", "3", "4", "5", "6"], show_choices=False)
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


def crear_post_ui():
    if not Sesion.activa():
        mostrar_error("Debe iniciar sesión para crear publicaciones.")
        pausar()
        return

    console.print(Panel.fit("[bold cyan]Crear Publicación[/bold cyan]\n[dim]Use 0 en cualquier campo para salir.[/dim]", border_style="bright_blue"))
    try:
        titulo = pedir("Título")
        contenido = pedir("Contenido")
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
    pausar()

def listar_posts_de_autor_ui():
    console.print(Panel.fit("[bold cyan]Posts por Autor[/bold cyan]", border_style="bright_blue"))
    if Confirm.ask("¿Usar autor en sesión?", default=Sesion.activa()):
        if not Sesion.activa():
            mostrar_error("No hay sesión activa.")
            pausar()
            return
        id_autor = Sesion.id_autor
    else:
        id_autor = Prompt.ask("ID del autor").strip()

    posts = modelo.listar_posts_por_autor(POSTS_JSON, id_autor)
    if not posts:
        console.print("[yellow]Este autor no tiene publicaciones.[/yellow]")
        pausar()
        return
    console.print(tabla_posts(posts, mostrar_autor=False))
    # NUEVO: abrir en vista detalle (misma interfaz que bienvenida)
    if Confirm.ask("¿Abrir un post en vista detalle?", default=True):
        ids_validos = {p["id_post"] for p in posts}
        id_sel = Prompt.ask("ID del post a abrir").strip()
        if id_sel not in ids_validos:
            mostrar_error("El ID no pertenece a la lista mostrada.")
            pausar()
            return
        ver_post_con_interacciones(id_sel)
    else:
        pausar()


def buscar_post_por_tag_ui():
    console.print(Panel.fit("[bold cyan]Buscar Posts por Tag[/bold cyan]\n[dim]Use 0 para salir.[/dim]", border_style="bright_blue"))
    tag = Prompt.ask("Tag a buscar").strip()
    if tag == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        pausar()
        return
    try:
        posts = modelo.buscar_posts_por_tag(POSTS_JSON, tag)
        if not posts:
            console.print("[yellow]No se encontraron publicaciones con ese tag.[/yellow]")
            pausar()
            return
        console.print(tabla_posts(posts, mostrar_autor=True))
        # NUEVO: abrir en vista detalle (misma interfaz que bienvenida)
        if Confirm.ask("¿Abrir un post en vista detalle?", default=True):
            ids_validos = {p["id_post"] for p in posts}
            id_sel = Prompt.ask("ID del post a abrir").strip()
            if id_sel not in ids_validos:
                mostrar_error("El ID no pertenece a la lista mostrada.")
                pausar()
                return
            ver_post_con_interacciones(id_sel)
        else:
            pausar()
    except modelo.ValidacionError as e:
        mostrar_error(str(e))
        pausar()


def editar_post_ui():
    if not Sesion.activa():
        mostrar_error("Debe iniciar sesión para editar sus publicaciones.")
        pausar()
        return

    console.print(Panel.fit("[bold cyan]Editar Publicación[/bold cyan]\n[dim]Use 0 en cualquier campo para salir.[/dim]", border_style="bright_blue"))
    id_post = Prompt.ask("ID del post a editar").strip()
    if id_post == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        pausar()
        return
    post = modelo.buscar_post_por_id(POSTS_JSON, id_post)
    if not post:
        mostrar_error("No existe un post con ese ID.")
        pausar()
        return

    if post["id_autor"] != str(Sesion.id_autor):
        mostrar_error("No puede editar un post que no es suyo.")
        pausar()
        return

    console.print("\nPresione Enter para no modificar un campo.")
    nuevos: Dict[str, Any] = {}
    nuevo_titulo = Prompt.ask("Título", default=post["titulo"]).strip()
    if nuevo_titulo == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        pausar()
        return
    if nuevo_titulo != post["titulo"]:
        nuevos["titulo"] = nuevo_titulo
    nuevo_contenido = Prompt.ask("Contenido", default=post["contenido"]).strip()
    if nuevo_contenido == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        pausar()
        return
    if nuevo_contenido != post["contenido"]:
        nuevos["contenido"] = nuevo_contenido
    nuevos_tags = Prompt.ask("Tags (coma)", default=", ".join(post.get("tags") or [])).strip()
    if nuevos_tags == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        pausar()
        return
    if nuevos_tags != ", ".join(post.get("tags") or []):
        nuevos["tags"] = nuevos_tags

    if not nuevos:
        console.print("[yellow]No se modificó ningún campo.[/yellow]")
        pausar()
        return

    try:
        post_act = modelo.actualizar_post(POSTS_JSON, id_post, Sesion.id_autor, nuevos)
        mostrar_ok(f"Post actualizado: {post_act['titulo']}")
    except (modelo.PostNoEncontrado, modelo.AccesoNoAutorizado, modelo.ValidacionError) as e:
        mostrar_error(str(e))
    pausar()


def eliminar_post_ui():
    if not Sesion.activa():
        mostrar_error("Debe iniciar sesión para eliminar sus publicaciones.")
        pausar()
        return

    console.print(Panel.fit("[bold cyan]Eliminar Publicación[/bold cyan]\n[dim]Use 0 para salir.[/dim]", border_style="bright_blue"))
    id_post = Prompt.ask("ID del post a eliminar").strip()
    if id_post == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        pausar()
        return
    if not Confirm.ask("¿Seguro que desea eliminar este post?", default=False):
        console.print("[yellow]Operación cancelada.[/yellow]")
        pausar()
        return

    try:
        ok = modelo.eliminar_post(POSTS_JSON, id_post, Sesion.id_autor)
        if ok:
            mostrar_ok("Publicación eliminada.")
        else:
            mostrar_error("No existe un post con ese ID.")
    except modelo.AccesoNoAutorizado as e:
        mostrar_error(str(e))
    pausar()


# --- Menús: Comentarios (reto) ---
def menu_comentarios():
    while True:
        console.print(
            Panel(
                "[bold yellow]1[/bold yellow]. Agregar comentario a un post\n"
                "[bold yellow]2[/bold yellow]. Listar comentarios de un post\n"
                "[bold yellow]3[/bold yellow]. Eliminar comentario de un post\n"
                "[bold yellow]4[/bold yellow]. Volver",
                title="[bold cyan]Comentarios[/bold cyan]",
                border_style="bright_magenta",
            )
        )
        opcion = Prompt.ask("Opción", choices=["1", "2", "3", "4"], show_choices=False)
        if opcion == "1":
            agregar_comentario_ui()
        elif opcion == "2":
            listar_comentarios_ui()
        elif opcion == "3":
            eliminar_comentario_ui()
        elif opcion == "4":
            return


def agregar_comentario_ui():
    console.print(Panel.fit("[bold cyan]Agregar Comentario[/bold cyan]\n[dim]Use 0 en cualquier campo para salir.[/dim]", border_style="bright_magenta"))
    try:
        id_post = pedir("ID del post")
        if Sesion.activa():
            autor_nombre = pedir("Nombre para mostrar", default=Sesion.nombre_autor)
            id_autor = Sesion.id_autor
        else:
            autor_nombre = pedir("Nombre para mostrar")
            id_autor = None
        contenido = pedir("Contenido del comentario")
        comentario = modelo.agregar_comentario_a_post(
            POSTS_JSON, id_post, autor_nombre, contenido, id_autor=id_autor
        )
        mostrar_ok(f"Comentario agregado con ID {comentario['id_comentario']}.")
    except Cancelado:
        console.print("[yellow]Operación cancelada.[/yellow]")
    except (modelo.PostNoEncontrado, modelo.ValidacionError) as e:
        mostrar_error(str(e))
    pausar()

def listar_comentarios_ui():
    console.print(Panel.fit("[bold cyan]Listar Comentarios[/bold cyan]\n[dim]Use 0 para salir.[/dim]", border_style="bright_magenta"))
    id_post = Prompt.ask("ID del post").strip()
    if id_post == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        pausar()
        return
    try:
        comentarios = modelo.listar_comentarios_de_post(POSTS_JSON, id_post)
        if not comentarios:
            console.print("[yellow]Este post no tiene comentarios.[/yellow]")
        else:
            tabla = Table(title=f"Comentarios del Post #{id_post}", border_style="blue", header_style="bold magenta")
            tabla.add_column("ID", style="dim", width=6)
            tabla.add_column("Autor", width=20)
            tabla.add_column("Fecha", width=19)
            tabla.add_column("Contenido", width=60)
            for c in comentarios:
                tabla.add_row(c["id_comentario"], c["autor"], c["fecha"], c["contenido"])
            console.print(tabla)
    except modelo.PostNoEncontrado as e:
        mostrar_error(str(e))
    pausar()


def eliminar_comentario_ui():
    console.print(Panel.fit("[bold cyan]Eliminar Comentario[/bold cyan]\n[dim]Use 0 para salir.[/dim]", border_style="bright_magenta"))
    id_post = Prompt.ask("ID del post").strip()
    if id_post == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        pausar()
        return
    id_com = Prompt.ask("ID del comentario").strip()
    if id_com == "0":
        console.print("[yellow]Operación cancelada.[/yellow]")
        pausar()
        return
    try:
        ok = modelo.eliminar_comentario_de_post(
            POSTS_JSON, id_post, id_com, id_autor_en_sesion=Sesion.id_autor
        )
        if ok:
            mostrar_ok("Comentario eliminado.")
        else:
            mostrar_error("No se encontró el comentario.")
    except (modelo.PostNoEncontrado, modelo.AccesoNoAutorizado) as e:
        mostrar_error(str(e))
    pausar()


# --- Menú principal ---
def mostrar_menu_principal():
    sesion_txt = (
        Text.assemble(Text("Conectado: ", style="bright_green"), Text(f"{Sesion.nombre_autor} <{Sesion.email}>", style="green"))
        if Sesion.activa()
        else Text("Sin sesión", style="bright_yellow")
    )
    console.print(
        Panel(
            Text.assemble(
                "Seleccione una opción\n",
                "- ", Text("Autores", style="bold yellow"), " (CRUD)\n",
                "- ", Text("Publicaciones", style="bold yellow"), " (crear/listar/buscar/editar/eliminar)\n",
                "- ", Text("Comentarios", style="bold yellow"), " (reto)\n",
                "- ", Text("Sesión", style="bold yellow"), " (login)\n\n",
                "Estado: ", sesion_txt,
            ),
            title="[bold cyan]MENÚ PRINCIPAL — Blog Multi-usuario[/bold cyan]",
            border_style="bright_cyan",
        )
    )
    console.print(
        "[bold yellow]1[/bold yellow]. Autores   "
        "[bold yellow]2[/bold yellow]. Publicaciones   "
        "[bold yellow]3[/bold yellow]. Comentarios   "
        "[bold yellow]4[/bold yellow]. Sesión   "
        "[bold red]5[/bold red]. Salir"
    )

def main():
    init_archivos()
    # Asegurar bienvenida del sistema
    ensure_sistema_y_bienvenida()
    banner()
    console.print(f"Archivos de datos: [green]{AUTORES_CSV}[/green], [green]{POSTS_JSON}[/green]\n")

    # Onboarding: registro/login antes del menú
    if not onboarding_inicio():
        console.print("\n[bold magenta]¡Hasta luego![/bold magenta]")
        return

    while True:
        mostrar_menu_principal()
        opcion = Prompt.ask("Opción", choices=["1", "2", "3", "4", "5"], show_choices=False)
        if opcion == "1":
            menu_autores()
        elif opcion == "2":
            menu_publicaciones()
        elif opcion == "3":
            menu_comentarios()
        elif opcion == "4":
            menu_sesion()
        elif opcion == "5":
            console.print("\n[bold magenta]¡Hasta luego![/bold magenta]")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[bold red]Programa interrumpido por el usuario. Adiós.[/bold red]")