"""Carga de la configuración de la salina (config.yaml) con valores por defecto.

Uso:
    from src.config import load_config
    cfg = load_config()
    cfg.water.entrada_cristalizador_g_l   # 295.0

Validación (auditoría M1): :func:`load_config` valida el esquema con
:func:`validar_config` — secciones/claves requeridas, tipos y rangos físicos —
y lanza :class:`src.errors.ConfigError` con un mensaje claro (un typo en el
YAML falla aquí, no en tiempo de simulación lejano).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import yaml

from src.errors import ConfigError

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "flor_desal.db"


# ------------------------------------------------------------------- tipado estático
# Protocol para que mypy entienda cfg.location, cfg.water, cfg.physics, etc.
# (Config es dinámico vía Section; el Protocol no se usa en runtime, solo type-check).
class _LocationProto(Protocol):
    name: str
    latitude: float
    longitude: float
    timezone: str


class _WaterProto(Protocol):
    entrada_cristalizador_g_l: float
    profundidad_lamina_cm: float
    umbral_sobresaturacion_g_l: float
    umbral_temp_ref_c: float
    umbral_pendiente_g_l_c: float


class _PhysicsProto(Protocol):
    dalton_a: float
    dalton_b: float
    coef_solar_agua: float
    t_extra_manana_c: float


class _SimulationProto(Protocol):
    hora_inicio: int
    hora_fin: int
    minutos_crecimiento: int


class _MonteCarloProto(Protocol):
    iterations: int
    sigma_temp_c: float
    sigma_rh_pct: float
    sigma_wind_ms: float
    seed: int | None


class _LimitsProto(Protocol):
    viento_peligro_ms: float
    viento_seguro_max_ms: float
    hr_peligro_pct: float
    hr_ideal_max_pct: float
    hr_cierre_tarde_pct: float
    hr_rehidratacion_pct: float
    temp_activacion_c: float


class _SeasonProto(Protocol):
    start_date: str
    end_date: str
    iterations: int
    source: str
    workers: int


class _MarkovProto(Protocol):
    estados: list[str]
    margen_critico_g_l: float
    iterations: int


class _AssimilationProto(Protocol):
    max_hours_back: int


class _NetworkProto(Protocol):
    timeout_s: float
    archive_timeout_s: float
    retries: int
    backoff_base_s: float

    def get(self, key: str, default: Any = None) -> Any: ...


class ConfigProto(Protocol):
    location: _LocationProto
    water: _WaterProto
    physics: _PhysicsProto
    simulation: _SimulationProto
    montecarlo: _MonteCarloProto
    limits: _LimitsProto
    season: _SeasonProto
    markov: _MarkovProto
    assimilation: _AssimilationProto
    network: _NetworkProto


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
    """Configuración raíz: cfg.location, cfg.water, cfg.physics, cfg.simulation,
    cfg.montecarlo, cfg.limits, cfg.season, cfg.markov, cfg.assimilation."""


# ------------------------------------------------------------------ validación
# (sección, clave, tipo esperado, mínimo opcional, máximo opcional)
# None = sin límite numérico. Solo se listan campos con valor físico/rango
# relevante; el resto de claves del YAML son libres (documentación/calibración).
_ESPEC: list[tuple[str, str, type | tuple[type, ...], float | None, float | None]] = [
    ("location", "latitude", (int, float), -90.0, 90.0),
    ("location", "longitude", (int, float), -180.0, 180.0),
    ("location", "timezone", str, None, None),
    ("water", "entrada_cristalizador_g_l", (int, float), 0.0, 400.0),
    ("water", "profundidad_lamina_cm", (int, float), 0.1, 50.0),
    ("water", "umbral_sobresaturacion_g_l", (int, float), 0.0, 400.0),
    ("physics", "dalton_a", (int, float), 0.0, None),
    ("physics", "dalton_b", (int, float), 0.0, None),
    ("simulation", "hora_inicio", int, 0, 23),
    ("simulation", "hora_fin", int, 1, 24),
    ("simulation", "minutos_crecimiento", (int, float), 0.0, 24 * 60.0),
    ("montecarlo", "iterations", int, 1, 1_000_000),
    ("montecarlo", "sigma_temp_c", (int, float), 0.0, None),
    ("montecarlo", "sigma_rh_pct", (int, float), 0.0, None),
    ("montecarlo", "sigma_wind_ms", (int, float), 0.0, None),
    ("season", "start_date", str, None, None),
    ("season", "end_date", str, None, None),
    ("season", "iterations", int, 1, 1_000_000),
    ("markov", "margen_critico_g_l", (int, float), 0.0, None),
    ("assimilation", "max_hours_back", int, 1, 24),
    ("network", "timeout_s", (int, float), 1.0, None),
    ("network", "archive_timeout_s", (int, float), 1.0, None),
    ("network", "retries", int, 1, 10),
    ("network", "backoff_base_s", (int, float), 0.0, None),
    ("season", "workers", int, 0, 64),
]

_SECCIONES_REQUERIDAS = ("location", "water", "physics", "simulation",
                         "montecarlo", "limits", "assimilation",
                         "network", "season", "markov")


def validar_config(data: dict[str, Any]) -> None:
    """Valida el dict crudo del YAML. Lanza ConfigError con el primer problema.

    Comprueba: secciones requeridas, tipos/rangos del esquema _ESPEC y la
    coherencia hora_inicio < hora_fin (auditoría M1).
    """
    faltan = [s for s in _SECCIONES_REQUERIDAS if not isinstance(data.get(s), dict)]
    if faltan:
        raise ConfigError(f"config.yaml: faltan secciones requeridas: {faltan}")

    for sec, key, tipo, vmin, vmax in _ESPEC:
        valor = data[sec].get(key)
        if valor is None:
            raise ConfigError(f"config.yaml: falta '{sec}.{key}'.")
        if isinstance(valor, bool) or not isinstance(valor, tipo):
            raise ConfigError(
                f"config.yaml: '{sec}.{key}' debe ser {getattr(tipo, '__name__', tipo)}, "
                f"recibido {valor!r} ({type(valor).__name__}).")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            if vmin is not None and valor < vmin:
                raise ConfigError(
                    f"config.yaml: '{sec}.{key}' = {valor} fuera de rango (mín {vmin}).")
            if vmax is not None and valor > vmax:
                raise ConfigError(
                    f"config.yaml: '{sec}.{key}' = {valor} fuera de rango (máx {vmax}).")

    h0 = data["simulation"]["hora_inicio"]
    h1 = data["simulation"]["hora_fin"]
    if h0 >= h1:
        raise ConfigError(
            f"config.yaml: simulation.hora_inicio ({h0}) debe ser < "
            f"hora_fin ({h1}).")

    inicio, fin = data["season"]["start_date"], data["season"]["end_date"]
    if str(inicio) > str(fin):
        raise ConfigError(
            f"config.yaml: season.start_date ({inicio}) posterior a "
            f"season.end_date ({fin}).")


def load_config(path: str | Path | None = None) -> ConfigProto:
    """Carga y valida config.yaml. ConfigError si falta o es inválido."""
    p = Path(path) if path else CONFIG_PATH
    try:
        with p.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError as exc:
        raise ConfigError(f"No existe el fichero de configuración: {p}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{p}: el contenido no es un mapa YAML.")
    validar_config(data)
    return Config(data)  # type: ignore[return-value]  # Config implementa ConfigProto en runtime
