# Sistema de Blog Multi-usuario (CLI con Rich)

## Requisitos
- Python 3.10+ (recomendado 3.13 si lo tienes)
- Windows (cmd.exe)

## Instalación de dependencias

Desde la raíz del proyecto, instala las dependencias declaradas en `pyproject.toml`:

```cmd
python -m pip install --upgrade pip
python -m pip install -e .
```

Esto instalará `rich` (para la UI), y utilidades de desarrollo (`pytest`, `ruff`).

## Ejecutar la aplicación

Puedes ejecutar el programa desde la raíz (gracias a rutas de datos robustas):

```cmd
python src\Modulo\main.py
```

Se crearán/usarán automáticamente estos archivos de datos:
- `data\autores.csv`
- `data\posts.json`

## Notas
- El modelo no maneja contraseñas: el inicio de sesión es por email (único). Si el email no existe, puedes crear la cuenta desde la propia UI.
- Los caminos a `data/` ya no dependen del directorio actual; se resuelven relativos a la raíz del proyecto para evitar errores al ejecutar desde diferentes carpetas.

## Pruebas rápidas
Si quieres ejecutar pruebas (cuando existan en el directorio `tests/` o `test/`):

```cmd
python -m pytest -q
```

## Solución de problemas
- Si `python src\Modulo\main.py` falla por imports, asegúrate de estar ejecutando con Python desde la raíz del repo (donde está `pyproject.toml`).
- Si `data` no existe, la app lo creará en el primer arranque.

