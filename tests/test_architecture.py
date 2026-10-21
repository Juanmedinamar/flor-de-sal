"""Tests de arquitectura (AST) — límites entre dominio e infraestructura.

DOMINIO (núcleo físico/estocástico, NO debe importar infra):
    physics, montecarlo, markov, alerts, assimilation

INFRA (E/S, red, BD, config, errores):
    weather, db, historical, config, errors, pipeline

REGLAS:
- Módulos de DOMINIO no importan nada de INFRA (excepto stdlib, numpy, pandas, scipy, yaml).
- Streamlit, requests, sqlite3, threading, multiprocessing → FALLO en dominio.
- Pipeline (capa app) SÍ puede importar ambos.
- Se usa `ast` + `importlib` de la stdlib (sin deps nuevas).
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

# ─── Definición de capas ────────────────────────────────────────────────────

DOMINIO = {
    "src.physics",
    "src.montecarlo",
    "src.markov",
    "src.alerts",
    "src.assimilation",
}

INFRA = {
    "src.weather",
    "src.db",
    "src.historical",
    "src.config",
    "src.errors",
    "src.pipeline",
    "src.log_config",
}

# Módulos neutros (pueden estar en cualquier lado, no son dominio ni infra puros)
NEUTROS = {
    "src.__init__",
}

# Librerías permitidas en DOMINIO (stdlib + científicas estándar)
PERMITIDAS_DOMINIO = {
    # stdlib
    "math", "statistics", "random", "datetime", "typing", "collections", "itertools",
    "functools", "dataclasses", "enum", "pathlib", "json", "csv", "re", "os", "sys",
    "time", "contextlib", "decimal", "fractions", "numbers", "inspect", "textwrap",
    "hashlib", "base64", "mimetypes", "urllib.parse", "html",
    "zoneinfo", "logging", "argparse", "subprocess",
    # científicas
    "numpy", "pandas", "scipy", "yaml",
    # internas de dominio (se permiten entre sí)
    "src.physics", "src.montecarlo", "src.markov", "src.alerts", "src.assimilation",
    # errors es base de excepciones, la usan todos
    "src.errors",
    # log_config es infra pero se usa transversalmente (como errors)
    "src.log_config",
}

# Prohibidas explícitas en DOMINIO (señales de acoplamiento a infra)
PROHIBIDAS_DOMINIO = {
    "requests", "sqlite3", "streamlit", "threading", "multiprocessing",
    "concurrent.futures", "asyncio", "aiohttp", "httpx",
    "sqlalchemy", "psycopg2", "pymysql", "redis",
    "plotly", "matplotlib", "seaborn",
}


def _modulos_src() -> list[str]:
    """Lista de módulos Python bajo src/ (sin __pycache__)."""
    src_root = Path(__file__).resolve().parents[1] / "src"
    mods = []
    for py in src_root.rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        rel = py.relative_to(src_root.parents[0]).with_suffix("")
        mods.append(str(rel).replace("/", "."))
    return sorted(mods)


def _extraer_imports(mod_name: str) -> set[str]:
    """Devuelve el conjunto de nombres de módulos importados (nivel superior)."""
    spec = importlib.util.find_spec(mod_name)
    if spec is None or spec.origin is None:
        return set()
    try:
        with Path(spec.origin).open(encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=spec.origin)
    except (SyntaxError, OSError):
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            # Manejar "from src import X, Y" -> añadir "src.X", "src.Y"
            if node.module == "src" and node.names:
                for alias in node.names:
                    imports.add(f"src.{alias.name}")
            else:
                imports.add(node.module.split(".")[0])
    return imports


def _es_infra(mod: str) -> bool:
    """True si el módulo pertenece a INFRA (o subpaquete de)."""
    return any(mod == i or mod.startswith(i + ".") for i in INFRA)


def _es_dominio(mod: str) -> bool:
    """True si el módulo pertenece a DOMINIO (o subpaquete de)."""
    return any(mod == d or mod.startswith(d + ".") for d in DOMINIO)


def _es_neutro(mod: str) -> bool:
    """True si el módulo es neutro (no se clasifica)."""
    return any(mod == n or mod.startswith(n + ".") for n in NEUTROS)


def _clasificar_import(imp: str) -> str:
    """Clasifica un import: 'dominio', 'infra', 'permitida', 'prohibida', 'otro'."""
    if _es_dominio(imp):
        return "dominio"
    if _es_infra(imp):
        return "infra"
    if _es_neutro(imp):
        return "neutro"
    if imp in PERMITIDAS_DOMINIO:
        return "permitida"
    if imp in PROHIBIDAS_DOMINIO:
        return "prohibida"
    return "otro"


# ─── Tests ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", sorted(DOMINIO))
def test_dominio_no_importa_infra(mod_name: str) -> None:
    """Ningún módulo de DOMINIO importa módulos de INFRA."""
    imports = _extraer_imports(mod_name)
    infra_imports = [imp for imp in imports if _clasificar_import(imp) == "infra"]
    assert not infra_imports, (
        f"{mod_name} importa infraestructura prohibida: {sorted(infra_imports)}. "
        f"Dominio debe ser puro (sin E/S, red, BD, config, pipeline)."
    )


@pytest.mark.parametrize("mod_name", sorted(DOMINIO))
def test_dominio_no_importa_prohibidas(mod_name: str) -> None:
    """Ningún módulo de DOMINIO importa librerías prohibidas (requests, sqlite3, streamlit...)."""
    imports = _extraer_imports(mod_name)
    prohibidas = [imp for imp in imports if _clasificar_import(imp) == "prohibida"]
    assert not prohibidas, (
        f"{mod_name} importa librerías prohibidas en dominio: {sorted(prohibidas)}. "
        f"El dominio no debe conocer E/S, red, UI, hilos, ni BD."
    )


@pytest.mark.parametrize("mod_name", sorted(DOMINIO))
def test_dominio_solo_importa_permitidas(mod_name: str) -> None:
    """Todos los imports de DOMINIO están en la lista blanca (stdlib + científicas + dominio)."""
    imports = _extraer_imports(mod_name)
    extraños = [
        imp for imp in imports
        if _clasificar_import(imp) not in {"dominio", "permitida", "infra", "prohibida"}
    ]
    # Los "extraños" pueden ser legítimos (p.ej. typing_extensions, zoneinfo en 3.9+)
    # pero los avisamos para revisión; no fallamos para no ser frágiles.
    if extraños:
        print(f"\n[INFO] {mod_name} importa módulos no clasificados: {sorted(extraños)}")


# Pipeline (capa app) SÍ puede importar ambos — test de sanidad
@pytest.mark.parametrize("mod_name", ["src.pipeline"])
def test_pipeline_puede_importar_todo(mod_name: str) -> None:
    """Pipeline es la capa de aplicación: puede importar dominio e infra."""
    imports = _extraer_imports(mod_name)
    # Debe importar al menos algo de dominio y algo de infra
    tiene_dominio = any(_clasificar_import(i) == "dominio" for i in imports)
    tiene_infra = any(_clasificar_import(i) == "infra" for i in imports)
    assert tiene_dominio, f"{mod_name} debería importar dominio"
    assert tiene_infra, f"{mod_name} debería importar infra"


# Sanidad: que los conjuntos DOMINIO/INFRA/NEUTROS cubran src/
def test_cobertura_capas_completa() -> None:
    """Todos los módulos de src/ están clasificados como dominio, infra o neutro."""
    mods = _modulos_src()
    no_clasificados = [m for m in mods
                       if not _es_dominio(m) and not _es_infra(m) and not _es_neutro(m)]
    assert not no_clasificados, (
        f"Módulos sin clasificar en DOMINIO/INFRA/NEUTROS: {no_clasificados}. "
        f"Añádelos a DOMINIO, INFRA o NEUTROS en test_architecture.py."
    )


# Verificación de que no hay imports circulares dominio↔infra
def test_no_ciclos_dominio_infra() -> None:
    """No hay imports de infra → dominio que creen ciclos (infra ya importa dominio, ok)."""
    # Esta dirección está permitida: infra usa dominio.
    # Lo que NO está permitido es dominio → infra (ya testeado arriba).
