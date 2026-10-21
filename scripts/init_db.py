"""Crea el esquema de la base de datos (data/flor_desal.db).

CONTRATO — a implementar por data-ingest: llamar a Database().init_schema() e imprimir
la ruta de la DB creada.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db import Database  # noqa: E402


def main() -> None:
    db = Database()
    db.init_schema()
    print(f"Base de datos lista: {db.path}")


if __name__ == "__main__":
    main()
