"""Descarga la previsión meteorológica del día y la guarda en la DB.

CONTRATO — a implementar por data-ingest:

    python3 scripts/ingest_forecast.py            # hoy (tz de config.yaml)
    python3 scripts/ingest_forecast.py 2026-07-15 # fecha concreta YYYY-MM-DD

Debe: init_schema() si hace falta, fetch_forecast(coord de config.location),
db.save_forecast(date, df) e imprimir un resumen por horas (T, HR, V).
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import load_config
from src.db import Database
from src.log_config import get_logger, setup_logging
from src.weather import fetch_forecast

# Logger para este script
log = get_logger(__name__)


def main() -> None:
    """Descarga la previsión del día (argv[1] o hoy en la tz de config) y la guarda en la DB."""
    # Configura logging para CLI (stdout JSON)
    setup_logging(level="INFO", json=True)

    cfg = load_config()
    tz = str(cfg.location.timezone)

    if len(sys.argv) > 1:
        fecha = sys.argv[1]
        try:
            datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            print(f"Fecha inválida {fecha!r}: se espera formato YYYY-MM-DD.")
            sys.exit(1)
    else:
        fecha = datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d")

    log.info("ingest_forecast start", extra={"date": fecha, "location": cfg.location.name})

    db = Database()
    db.init_schema()

    df = fetch_forecast(
        latitude=float(cfg.location.latitude),
        longitude=float(cfg.location.longitude),
        date=fecha,
        timezone=tz,
        cfg=cfg,   # reintentos/timeout de cfg.network (auditoría G5)
    )
    n = db.save_forecast(fecha, df)

    t_max = df["temp_c"].max()
    t_min = df["temp_c"].min()
    hr_min = df["rh_pct"].min()
    v_max = df["wind_ms"].max()

    log.info("ingest_forecast end", extra={
        "date": fecha,
        "rows_saved": n,
        "t_max_c": round(t_max, 1),
        "t_min_c": round(t_min, 1),
        "hr_min_pct": round(hr_min, 1),
        "v_max_ms": round(v_max, 2),
        "db_path": str(db.path),
    })

    # Salida legible por consola (además del JSON log)
    print(f"{'Hora':>5}  {'T (°C)':>7}  {'HR (%)':>7}  {'V (m/s)':>8}  {'Rad (W/m²)':>11}")
    for fila in df.itertuples(index=False):
        print(f"{fila.hour:02d}:00  {fila.temp_c:7.1f}  {fila.rh_pct:7.1f}"
              f"  {fila.wind_ms:8.2f}  {fila.radiation_w_m2:11.1f}")

    print(f"\nResumen: T máx {t_max:.1f} °C · T mín {t_min:.1f} °C · HR mín {hr_min:.1f} % "
          f"· V máx {v_max:.2f} m/s")
    print(f"Guardadas {n} filas de previsión del {fecha} en: {db.path}")


if __name__ == "__main__":
    main()
