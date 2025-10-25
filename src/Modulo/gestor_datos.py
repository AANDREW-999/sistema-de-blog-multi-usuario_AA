# -*- coding: utf-8 -*-
"""
Módulo de Persistencia de Datos.
"""
import csv  # Lectura/escritura de archivos CSV
import json  # Manejo de estructuras y archivos JSON
import os  # Operaciones con rutas y sistema de archivos
import tempfile  # Archivos temporales para escritura atómica
from io import StringIO
from typing import Any, Dict, List  # Anotaciones de tipos para claridad

# Constantes de cabeceras para CSV de autores
CAMPOS_AUTORES = ["id_autor", "nombre_autor", "email", "password_hash"]



def _es_csv(filepath: str) -> bool:
    """Indica si la ruta corresponde a un archivo CSV.

    Args:
        filepath: Ruta del archivo.

    Returns:
        bool: True si termina en .csv; False en caso contrario.
    """
    return filepath.lower().endswith(".csv")


def _es_json(filepath: str) -> bool:
    """Indica si la ruta corresponde a un archivo JSON.

    Args:
        filepath: Ruta del archivo.

    Returns:
        bool: True si termina en .json; False en caso contrario.
    """
    return filepath.lower().endswith(".json")


def _asegurar_directorio(filepath: str) -> None:
    """Crea el directorio padre si no existe.

    Args:
        filepath: Ruta del archivo objetivo.

    Returns:
        None
    """
    directorio = os.path.dirname(os.path.abspath(filepath))
    if directorio and not os.path.exists(directorio):
        os.makedirs(directorio, exist_ok=True)


def _campos_csv_para(filepath: str) -> List[str]:
    """Determina los campos que se usarán en el CSV.

    En este proyecto solo manejamos 'autores.csv'.

    Args:
        filepath: Ruta del archivo CSV.

    Returns:
        List[str]: Lista de nombres de columnas.
    """
    nombre = os.path.basename(filepath).lower()
    if nombre.endswith("autores.csv"):
        return CAMPOS_AUTORES
    # Fallback genérico: si no es autores.csv, intentamos no fallar.
    return CAMPOS_AUTORES


def _escritura_atomica(path_destino: str, contenido: str, modo_binario: bool = False) \
        -> None:
    """Escribe contenido a un archivo de forma atómica.

    Crea un archivo temporal en el mismo directorio, escribe y reemplaza.

    Args:
        path_destino: Ruta del archivo destino.
        contenido: Contenido a escribir.
        modo_binario: Indica si se escribe en binario.

    Returns:
        None
    """
    _asegurar_directorio(path_destino)
    directorio = os.path.dirname(os.path.abspath(path_destino)) or "."
    suffix = ".tmpjson" if _es_json(path_destino) else ".tmpcsv"
    mode = "wb" if modo_binario else "w"
    encoding = None if modo_binario else "utf-8"

    with tempfile.NamedTemporaryFile(mode=mode, delete=False, dir=directorio,
                                     suffix=suffix, encoding=encoding) as tmp:
        tmp.write(contenido)
        tmp_path = tmp.name

    os.replace(tmp_path, path_destino)


def inicializar_archivo(filepath: str) -> None:
    """Inicializa un archivo de datos si no existe.

    - Para CSV: escribe cabecera.
    - Para JSON: escribe una lista vacía [].

    Args:
        filepath: Ruta del archivo a inicializar.

    Returns:
        None
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
    """Carga datos desde un archivo CSV o JSON.

    - Si el archivo no existe, se inicializa y retorna lista vacía.
    - CSV: celdas como strings y solo columnas esperadas.
    - JSON: si el contenido no es lista válida, retorna [].

    Args:
        filepath: Ruta del archivo a cargar.

    Returns:
        List[Dict[str, Any]]: Datos cargados como lista de diccionarios.
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
    """Guarda una lista de diccionarios en CSV o JSON.

    - CSV: cabeceras fijas, valores convertidos a str, escritura atómica.
    - JSON: escritura atómica con indentación y UTF-8.

    Args:
        filepath: Ruta del archivo a escribir.
        datos: Lista de diccionarios a persistir.

    Returns:
        None
    """
    if _es_csv(filepath):
        campos = _campos_csv_para(filepath)
        # Construimos el contenido CSV en memoria para escritura atómica.


        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=campos)
        writer.writeheader()

        for item in datos or []:
            fila = {k: str(item.get(k, "") if item.get(k, "") is not None else "")
                    for k in campos}
            writer.writerow(fila)

        _escritura_atomica(filepath, buffer.getvalue(), modo_binario=False)
        return

    if _es_json(filepath):
        # Dump JSON con indentación y UTF-8 sin escape
        contenido = json.dumps(datos or [], ensure_ascii=False, indent=4)
        _escritura_atomica(filepath, contenido, modo_binario=False)
        return
