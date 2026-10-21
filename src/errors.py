"""Jerarquía de excepciones del proyecto (auditoría M7).

Todas las excepciones propias heredan de :class:`FlorDeSalError`, que a su vez
hereda de :class:`Exception` (adiós a los ``RuntimeError`` genéricos): los
llamantes pueden capturar por dominio (``FlorDeSalError``) o por situación
concreta y reaccionar en consecuencia (reintentar vs. avisar al usuario).

Clases:
    FlorDeSalError        — base de todo lo del proyecto.
      ConfigError         — config.yaml ausente, incompleto o fuera de rango.
      WeatherError        — base de los fallos de datos meteorológicos.
        WeatherNetworkError — red caída, HTTP >= 400, timeout (reintentable).
        WeatherDataError    — respuesta válida pero sin datos utilizables
                              (día fuera de rango, serie incompleta…).
"""
from __future__ import annotations


class FlorDeSalError(Exception):
    """Base de todas las excepciones propias del proyecto."""


class ConfigError(FlorDeSalError):
    """config.yaml ausente, con claves faltantes o valores fuera de rango."""


class WeatherError(FlorDeSalError):
    """Base de los fallos al obtener datos meteorológicos."""


class WeatherNetworkError(WeatherError):
    """Fallo de red/HTTP/timeout: reintentable (auditoría G5)."""


class WeatherDataError(WeatherError):
    """La respuesta no contiene datos utilizables del día/rango pedido."""
