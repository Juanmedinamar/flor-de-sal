"""Backup de la base de datos SQLite (data/flor_desal.db → backups/).

Uso:
    python3 scripts/backup_db.py           # backup simple
    python3 scripts/backup_db.py --keep 10 # conserva solo los 10 más recientes
    python3 scripts/backup_db.py --db data/otra.db --out backups/

Cron sugerido (diario a las 02:00):
    0 2 * * * /usr/bin/python3 /ruta/proyecto/scripts/backup_db.py --keep 30
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def backup_database(
    db_path: Path,
    backup_dir: Path,
    keep: int | None = None,
) -> Path:
    """Copia la BD SQLite usando backup online (consistente).

    Args:
        db_path: Ruta a la BD origen (data/flor_desal.db).
        backup_dir: Directorio donde guardar el backup (backups/).
        keep: Si se especifica, borra backups antiguos conservando solo los N más recientes.

    Returns:
        Ruta al archivo de backup creado.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Base de datos no encontrada: {db_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"flor_desal_{timestamp}.db"
    backup_path = backup_dir / backup_name

    # SQLite online backup (consistente sin bloquear lecturas)
    # https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup
    with sqlite3.connect(db_path) as src, sqlite3.connect(backup_path) as dst:
        src.backup(dst)

    print(f"✅ Backup creado: {backup_path} ({backup_path.stat().st_size:,} bytes)")

    # Limpieza de backups antiguos
    if keep is not None and keep > 0:
        _prune_old_backups(backup_dir, keep)

    return backup_path


def _prune_old_backups(backup_dir: Path, keep: int) -> None:
    """Borra backups más antiguos, conservando solo los `keep` más recientes."""
    backups = sorted(backup_dir.glob("flor_desal_*.db"), key=lambda p: p.stat().st_mtime)
    to_delete = backups[:-keep] if len(backups) > keep else []
    for old in to_delete:
        old.unlink()
        print(f"🗑️  Backup antiguo eliminado: {old.name}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backup de la base de datos SQLite de Flor de Sal.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/flor_desal.db"),
        help="Ruta a la BD origen (default: data/flor_desal.db)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("backups"),
        help="Directorio de salida para backups (default: backups/)",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=None,
        help="Número de backups recientes a conservar (borra los más antiguos)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        backup_database(args.db, args.out, args.keep)
        return 0
    except Exception as exc:
        print(f"❌ Error en backup: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
