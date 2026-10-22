"""Fixtures compartidas de tests — día típico de verano en Córdoba (del PDF).

NO tocar por subagentes: es contrato compartido (coordinador).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import load_config


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: prueba que necesita red real (saltar con -m 'not integration')")


@pytest.fixture(scope="session")
def cfg():
    """Configuración real del proyecto (config.yaml)."""
    return load_config()


def _day(rows: list[tuple]) -> pd.DataFrame:
    hours, t, hr, v, rad = zip(*rows, strict=False)
    return pd.DataFrame({
        "hour": list(hours),
        "temp_c": list(t),
        "rh_pct": list(hr),
        "wind_ms": list(v),
        "wind_dir_deg": [90.0] * len(hours),
        "radiation_w_m2": list(rad),
    })


@pytest.fixture(scope="session")
def dia_verano_cordoba() -> pd.DataFrame:
    """Día típico de verano en Córdoba (escenario del PDF):
    amanecer húmedo y frío, mediodía seco y caluroso, ventana 13-17h, cosecha 16-19h."""
    return _day([
        # hour, T(°C), HR(%), V(m/s), rad(W/m²)
        (6,  18.0, 85.0, 0.5,  50),
        (7,  20.0, 75.0, 0.8, 150),
        (8,  22.0, 65.0, 1.0, 300),
        (9,  24.0, 60.0, 1.25, 450),
        (10, 26.0, 55.0, 1.5, 600),
        (11, 28.5, 47.5, 2.0, 720),
        (12, 31.0, 40.0, 2.5, 820),
        (13, 32.5, 35.0, 2.75, 860),
        (14, 34.0, 30.0, 3.0, 830),
        (15, 34.5, 29.0, 3.0, 750),
        (16, 35.0, 28.0, 3.0, 620),
        (17, 33.5, 30.5, 2.75, 450),
        (18, 32.0, 33.0, 2.5, 280),
        (19, 29.0, 39.0, 2.0, 120),
        (20, 26.0, 45.0, 1.5,  30),
        (21, 24.0, 52.0, 1.0,   0),
    ])


@pytest.fixture(scope="session")
def dia_nublado_humedo() -> pd.DataFrame:
    """Día desfavorable (nublado, HR alta): NO debe abrir ventana de flor de sal."""
    return _day([
        (6,  17.0, 92.0, 0.5,  20),
        (7,  18.0, 90.0, 0.8,  40),
        (8,  19.0, 88.0, 1.0,  60),
        (9,  20.0, 86.0, 1.0,  80),
        (10, 21.0, 84.0, 1.2, 100),
        (11, 22.0, 82.0, 1.5, 120),
        (12, 23.0, 80.0, 1.5, 140),
        (13, 23.5, 79.0, 1.8, 150),
        (14, 24.0, 78.0, 2.0, 140),
        (15, 24.0, 78.0, 2.0, 120),
        (16, 23.5, 80.0, 1.8, 100),
        (17, 23.0, 82.0, 1.5,  70),
        (18, 22.0, 84.0, 1.2,  40),
        (19, 21.0, 86.0, 1.0,  15),
        (20, 20.0, 88.0, 0.8,   5),
        (21, 19.0, 90.0, 0.5,   0),
    ])
