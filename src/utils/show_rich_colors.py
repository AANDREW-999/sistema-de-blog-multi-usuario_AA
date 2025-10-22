# -*- coding: utf-8 -*-
"""
Muestra en consola con Rich:
- Lista completa de nombres CSS (CSS3) aplicables como color en Rich.
- Paleta básica de terminal (16 colores + bright).
- Paleta de 256 colores por índice.
- Ejemplos de colores truecolor (hex).
Ejecutar: python show_rich_colors.py
Requiere: pip install rich
"""

from rich.console import Console
from rich.table import Table
from rich.columns import Columns
from rich.panel import Panel
from rich.color import Color  # NUEVO: para validar nombres de color

console = Console()

CSS_COLOR_NAMES = [
    "aliceblue","antiquewhite","aqua","aquamarine","azure","beige","bisque","black",
    "blanchedalmond","blue","blueviolet","brown","burlywood","cadetblue","chartreuse",
    "chocolate","coral","cornflowerblue","cornsilk","crimson","cyan","darkblue","darkcyan",
    "darkgoldenrod","darkgray","darkgreen","darkgrey","darkkhaki","darkmagenta",
    "darkolivegreen","darkorange","darkorchid","darkred","darksalmon","darkseagreen",
    "darkslateblue","darkslategray","darkslategrey","darkturquoise","darkviolet",
    "deeppink","deepskyblue","dimgray","dimgrey","dodgerblue","firebrick","floralwhite",
    "forestgreen","fuchsia","gainsboro","ghostwhite","gold","goldenrod","gray","green",
    "greenyellow","grey","honeydew","hotpink","indianred","indigo","ivory","khaki",
    "lavender","lavenderblush","lawngreen","lemonchiffon","lightblue","lightcoral",
    "lightcyan","lightgoldenrodyellow","lightgray","lightgreen","lightgrey","lightpink",
    "lightsalmon","lightseagreen","lightskyblue","lightslategray","lightslategrey",
    "lightsteelblue","lightyellow","lime","limegreen","linen","magenta","maroon",
    "mediumaquamarine","mediumblue","mediumorchid","mediumpurple","mediumseagreen",
    "mediumslateblue","mediumspringgreen","mediumturquoise","mediumvioletred",
    "midnightblue","mintcream","mistyrose","moccasin","navajowhite","navy","oldlace",
    "olive","olivedrab","orange","orangered","orchid","palegoldenrod","palegreen",
    "paleturquoise","palevioletred","papayawhip","peachpuff","peru","pink","plum",
    "powderblue","purple","rebeccapurple","red","rosybrown","royalblue","saddlebrown",
    "salmon","sandybrown","seagreen","seashell","sienna","silver","skyblue","slateblue",
    "slategray","slategrey","snow","springgreen","steelblue","tan","teal","thistle",
    "tomato","turquoise","violet","wheat","white","whitesmoke","yellow","yellowgreen"
]


def section_title(text: str):
    console.print(Panel(f"[bold]{text}[/bold]", border_style="cyan"))


# NUEVO: helpers de compatibilidad
def color_valida(nombre: str) -> bool:
    try:
        return Color.parse(nombre) is not None
    except Exception:
        return False

def soporta_256() -> bool:
    return (console.color_system or "").lower() in {"256", "truecolor"}

def soporta_truecolor() -> bool:
    return (console.color_system or "").lower() == "truecolor"


def mostrar_css_names():
    section_title("Nombres CSS soportados (ejemplos)")
    # Imprimimos en columnas solo colores válidos para Rich
    items = []
    for name in CSS_COLOR_NAMES:
        if not color_valida(name):
            continue  # quitar lo que no funciona (colores no soportados)
        items.append(Panel(f"[{name}]{name}[/{name}]", style=None, padding=(0,1)))
    if not items:
        console.print("[yellow]No hay colores CSS válidos en esta terminal.[/yellow]")
        return
    console.print(Columns(items, equal=True, expand=True))


def mostrar_basic_colors():
    section_title("Paleta básica (16 colores de terminal)")
    basic = [
        "black","red","green","yellow","blue","magenta","cyan","white",
        "bright_black","bright_red","bright_green","bright_yellow",
        "bright_blue","bright_magenta","bright_cyan","bright_white",
    ]
    table = Table(show_header=False, box=None)
    for c in basic:
        table.add_row(f"[{c}]{c}[/{c}]", f"[on {c}]  [/on {c}]  fondo")
    console.print(table)


def mostrar_256_palette():
    section_title("Paleta 256 colores (índices 0..255)")
    if not soporta_256():
        console.print("[yellow]Tu terminal no soporta 256 colores. Omitiendo esta sección.[/yellow]")
        return
    # Haremos filas de 16 bloques para mostrar los 256 colores de fondo
    bloques = []
    for i in range(256):
        bloques.append(f"[on color({i})] {i:3d} [/on color({i})]")
    # Imprimir en filas de 16
    for row in range(0, 256, 16):
        linea = " ".join(bloques[row:row+16])
        console.print(linea)


def mostrar_truecolor_examples():
    section_title("Ejemplos Truecolor (hex) y degradado")
    if not soporta_truecolor():
        console.print("[yellow]Tu terminal no soporta Truecolor (24-bit). Omitiendo esta sección.[/yellow]")
    ejemplo_hex = ["#ff0000", "#00ff00", "#0000ff", "#ffaa00", "#ff00aa", "#00aaff", "#7f7f7f"]
    table = Table(show_header=False, box=None)
    for hx in ejemplo_hex:
        table.add_row(f"[{hx}]{hx}[/{hx}]", f"[on {hx}]     [/on {hx}] fondo")
    console.print(table)

    # Degradado horizontal simple
    console.print("\nDegradado RGB (16 pasos):")
    pasos = 16
    bloques = []
    for i in range(pasos):
        r = int(255 * i / (pasos - 1))
        g = int(255 * (pasos - 1 - i) / (pasos - 1))
        b = 64
        hexc = f"#{r:02x}{g:02x}{b:02x}"
        bloques.append(f"[on {hexc}] {i:2d} [/on {hexc}]")
    console.print(" ".join(bloques))


def main():
    console.clear()
    console.print("[bold underline]Visualizador de colores para Rich[/bold underline]\n")
    mostrar_basic_colors()
    console.print()
    mostrar_css_names()
    console.print()
    mostrar_256_palette()
    console.print()
    mostrar_truecolor_examples()
    console.print("\n[dim]Nota: Si un color (ej. 'white') no se aprecia, prueba cambiar el tema/fondo del terminal.[/dim]")


if __name__ == "__main__":
    main()