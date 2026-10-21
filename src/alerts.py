"""Semáforo de fases y alertas del día (reglas del PDF).

Fases:
  0 — Inactividad:  la salmuera aún no alcanza la sobresaturación superficial.
  1 — Nucleación:   C >= umbral; empiezan los microcristales en superficie.
  2 — Ventana óptima: nucleación + minutos_crecimiento; crece la película.
  3 — Cierre/riesgo: viento > viento_peligro_ms (hundimiento), HR > hr_peligro_pct
      (rehidratación) o repunte de HR tras el mínimo (la película se disuelve).
"""
from __future__ import annotations

from src.config import ConfigProto

FASES = {
    0: "Inactividad (la salmuera aún no está sobresaturada)",
    1: "Nucleación — comienzan los cristales en superficie",
    2: "Ventana óptima — la película crece, es cosechable",
    3: "Cierre/riesgo — la película se hunde o se disuelve",
}


def evaluar_fase(c_g_l: float, umbral_g_l: float, hour: float,
                 hora_nucleacion: float | None, viento_ms: float, hr_pct: float,
                 hr_min_hasta_ahora: float, cfg: ConfigProto) -> int:
    """Devuelve la fase (0-3) para una hora dada del escenario.

    Reglas (cfg.limits):
      - viento > viento_peligro_ms                 -> 3 (hundimiento por turbulencia)
      - hr_pct > hr_peligro_pct                    -> 3 (rehidratación de la película)
      - C >= umbral:
          * hora < nucleación + minutos_crecimiento -> 1
          * HR repunta (>= hr_cierre_tarde_pct y > mínimo del día + 3) -> 3
          * en otro caso                            -> 2
      - resto                                      -> 0
    """
    L = cfg.limits
    growth_h = cfg.simulation.minutos_crecimiento / 60.0

    if viento_ms > L.viento_peligro_ms:
        return 3
    if hr_pct > L.hr_peligro_pct:
        return 3
    if c_g_l >= umbral_g_l:
        if hora_nucleacion is not None and hour >= hora_nucleacion + growth_h:
            hr_repunte = hr_pct >= L.hr_cierre_tarde_pct and hr_pct > hr_min_hasta_ahora + 3
            return 3 if hr_repunte else 2
        return 1
    return 0


def evaluar_riesgos(temp_c: float, rh_pct: float, wind_ms: float, cfg: ConfigProto) -> list[dict]:
    """Alertas del momento actual. Devuelve lista de {'nivel', 'codigo', 'mensaje'}.

    nivel: 'rojo' (no cosechar / peligro), 'amarillo' (precaución), 'verde' (todo bien).
    """
    L = cfg.limits
    alertas: list[dict] = []
    if wind_ms > L.viento_peligro_ms:
        alertas.append({"nivel": "rojo", "codigo": "viento_peligro",
                        "mensaje": f"Peligro de hundimiento de la película: viento "
                                   f"{wind_ms:.1f} m/s > {L.viento_peligro_ms} m/s. "
                                   "Recolocarse en zonas resguardadas o cosechar ya."})
    elif wind_ms > L.viento_seguro_max_ms:
        alertas.append({"nivel": "amarillo", "codigo": "viento_fuerte",
                        "mensaje": f"Viento {wind_ms:.1f} m/s por encima del cómodo "
                                   f"({L.viento_seguro_max_ms} m/s): la lámina se rompe antes."})
    if rh_pct > L.hr_peligro_pct:
        alertas.append({"nivel": "rojo", "codigo": "hr_peligro",
                        "mensaje": f"Humedad relativa {rh_pct:.0f}% > {L.hr_peligro_pct}%: "
                                   "la flor de sal se rehidrata y se disuelve."})
    elif rh_pct > L.hr_ideal_max_pct:
        alertas.append({"nivel": "amarillo", "codigo": "hr_alta",
                        "mensaje": f"HR {rh_pct:.0f}% por encima de lo óptimo "
                                   f"(<{L.hr_ideal_max_pct}%): evaporación frenada."})
    if temp_c < L.temp_activacion_c:
        alertas.append({"nivel": "amarillo", "codigo": "temp_baja",
                        "mensaje": f"Temperatura {temp_c:.1f} °C: proceso lento, "
                                   "la ventana se retrasa."})
    if not alertas:
        alertas.append({"nivel": "verde", "codigo": "ok",
                        "mensaje": "Condiciones favorables para la flor de sal."})
    return alertas


def descripcion_fase(fase: int) -> str:
    return FASES.get(fase, "Desconocida")
