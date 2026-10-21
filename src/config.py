"""Carga de la configuración de la salina (config.yaml) con valores por defecto.

Uso:
    from src.config import load_config
    cfg = load_config()
    cfg.water.entrada_cristalizador_g_l   # 295.0
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "flor_desal.db"


class Section:
    """Acceso por atributo a una sección del YAML (dict anidado)."""

    def __init__(self, data: dict[str, Any]):
        for k, v in data.items():
            if isinstance(v, dict):
                setattr(self, k, Section(v))
            else:
                setattr(self, k, v)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in self.__dict__.items():
            out[k] = v.as_dict() if isinstance(v, Section) else v
        return out


class Config(Section):
    """Configuración raíz: cfg.location, cfg.water, cfg.physics, cfg.simulation, cfg.montecarlo, cfg.limits."""


def load_config(path: str | Path | None = None) -> Config:
    """Carga config.yaml. Si no existe, lanza FileNotFoundError (el archivo es parte del proyecto)."""
    p = Path(path) if path else CONFIG_PATH
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Config(data)
