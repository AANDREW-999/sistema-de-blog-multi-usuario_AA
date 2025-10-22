# -*- coding: utf-8 -*-
"""
Módulo de Persistencia de Datos.

Responsable de leer y escribir datos en archivos planos (CSV y JSON).
No contiene lógica de negocio, solo operaciones de I/O.

Diseñado para trabajar con:
- Autores (CSV): columnas ['id_autor', 'nombre_autor', 'email'].
- Publicaciones (JSON): lista de objetos (posts) según el modelo.

Funciones públicas:
- inicializar_archivo(filepath)
- cargar_datos(filepath) -> List[Dict[str, Any]]
- guardar_datos(filepath, datos) -> None
"""

from typing import Any, Dict, List
import csv
import json
import os
import tempfile

# Constantes de cabeceras para CSV de autores
CAMPOS_AUTORES = ["id_autor", "nombre_autor", "email"]


# ---------------------------
# Utilidades internas
# ---------------------------

def _es_csv(filepath: str) -> bool:
    return filepath.lower().endswith(".csv")


def _es_json(filepath: str) -> bool:
    return filepath.lower().endswith(".json")


def _asegurar_directorio(filepath: str) -> None:
    """Crea el directorio padre si no existe."""
    directorio = os.path.dirname(os.path.abspath(filepath))
    if directorio and not os.path.exists(directorio):
        os.makedirs(directorio, exist_ok=True)


def _campos_csv_para(filepath: str) -> List[str]:
    """
    Determina los campos que se usarán en el CSV.
    En este proyecto solo manejamos 'autores.csv'.
    """
    nombre = os.path.basename(filepath).lower()
    if nombre.endswith("autores.csv"):
        return CAMPOS_AUTORES
    # Fallback genérico: si no es autores.csv, intentamos no fallar.
    return CAMPOS_AUTORES


def _escritura_atomica(path_destino: str, contenido: str, modo_binario: bool = False) -> None:
    """
    Escribe contenido a un archivo de forma atómica:
    - Crea un archivo temporal en el mismo directorio
    - Escribe y luego reemplaza
    """
    _asegurar_directorio(path_destino)
    directorio = os.path.dirname(os.path.abspath(path_destino)) or "."
    suffix = ".tmpjson" if _es_json(path_destino) else ".tmpcsv"
    mode = "wb" if modo_binario else "w"
    encoding = None if modo_binario else "utf-8"

    with tempfile.NamedTemporaryFile(mode=mode, delete=False, dir=directorio, suffix=suffix, encoding=encoding) as tmp:
        tmp.write(contenido)
        tmp_path = tmp.name

    os.replace(tmp_path, path_destino)


# ---------------------------
# API pública
# ---------------------------

def inicializar_archivo(filepath: str) -> None:
    """
    Verifica si un archivo de datos existe. Si no, lo crea vacío con el formato correcto.

    - Para CSV: escribe cabecera.
    - Para JSON: escribe una lista vacía [].
    """
    _asegurar_directorio(filepath)

    if not os.path.exists(filepath):
        if _es_csv(filepath):
            campos = _campos_csv_para(filepath)
            # Escribimos cabeceras
            with open(filepath, mode="w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=campos)
                writer.writeheader()
        elif _es_json(filepath):
            with open(filepath, mode="w", encoding="utf-8") as json_file:
                json.dump([], json_file, ensure_ascii=False, indent=4)


def cargar_datos(filepath: str) -> List[Dict[str, Any]]:
    """
    Carga los datos desde un archivo (CSV o JSON) y los retorna como una lista de diccionarios.

    - Si el archivo no existe, se inicializa y retorna lista vacía.
    - Para CSV, todas las celdas se leen como strings.
    - Para JSON, si el contenido no es una lista válida, retorna [].
    """
    inicializar_archivo(filepath)

    try:
        if _es_csv(filepath):
            with open(filepath, mode="r", newline="", encoding="utf-8") as csv_file:
                lector = csv.DictReader(csv_file)
                # Normalizamos: garantizamos solo las columnas definidas
                campos = lector.fieldnames or _campos_csv_para(filepath)
                datos: List[Dict[str, Any]] = []
                for fila in lector:
                    # Conservar solo campos conocidos y convertir a str
                    limpio = {k: str(fila.get(k, "")).strip() for k in campos}
                    datos.append(limpio)
                return datos

        if _es_json(filepath):
            with open(filepath, mode="r", encoding="utf-8") as json_file:
                datos = json.load(json_file)
                return datos if isinstance(datos, list) else []
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        # En caso de archivo corrupto o ilegible, devolvemos lista vacía.
        return []

    # Formato no soportado
    return []


def guardar_datos(filepath: str, datos: List[Dict[str, Any]]) -> None:
    """
    Guarda una lista de diccionarios en un archivo (CSV o JSON), sobrescribiendo el contenido.

    - Para CSV:
      - Escribe cabeceras fijas para autores.
      - Convierte todos los valores a str.
      - Escritura atómica (archivo temporal + replace).
    - Para JSON:
      - Escritura atómica con identación.
    """
    if _es_csv(filepath):
        campos = _campos_csv_para(filepath)
        # Construimos el contenido CSV en memoria para escritura atómica.
        from io import StringIO

        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=campos)
        writer.writeheader()

        for item in datos or []:
            fila = {k: str(item.get(k, "") if item.get(k, "") is not None else "") for k in campos}
            writer.writerow(fila)

        _escritura_atomica(filepath, buffer.getvalue(), modo_binario=False)
        return

    if _es_json(filepath):
        # Dump JSON con indentación y UTF-8 sin escape
        contenido = json.dumps(datos or [], ensure_ascii=False, indent=4)
        _escritura_atomica(filepath, contenido, modo_binario=False)
        return

    # Si no es CSV ni JSON, no hacemos nada (o podríamos lanzar una excepción si se requiere).