"""Healthcheck para la app Streamlit (Docker HEALTHCHECK + Makefile `health`).

Hace HTTP GET a http://localhost:8501/_stcore/health
- 200 OK → exit 0 (saludable)
- Cualquier otro código / error de conexión / timeout → exit 1 (no saludable)

Uso:
    python3 scripts/healthcheck.py           # CLI / Makefile
    # En Dockerfile: HEALTHCHECK CMD python3 scripts/healthcheck.py
"""

from __future__ import annotations

import sys

import requests


def main() -> int:
    """Ejecuta el healthcheck. Devuelve 0 si OK, 1 si falla."""
    url = "http://localhost:8501/_stcore/health"
    timeout = 5  # segundos

    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            # Streamlit devuelve {"status": "ok"} en 200
            return 0
        print(f"Healthcheck falló: HTTP {resp.status_code}", file=sys.stderr)
        return 1
    except requests.exceptions.Timeout:
        print(f"Healthcheck timeout ({timeout}s)", file=sys.stderr)
        return 1
    except requests.exceptions.ConnectionError:
        print("Healthcheck: conexión rechazada (¿app no arrancada?)", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Healthcheck error inesperado: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
