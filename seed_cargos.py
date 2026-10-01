"""Siembra el calendario de pagos de tarjeta ya conocido (ver
bot-finanzas-telegram-contexto.md, seccion 2) como filas en
cargos_programados, para que /deudas, /proximos y los recordatorios
funcionen sin que captures cada mes las mismas fechas a mano.

Es idempotente: si ya existe una fila para la misma tarjeta+fecha no la
duplica, asi que se puede volver a correr sin miedo (por ejemplo si se
confirma que el pago de diciembre se adelanta por dia festivo, edita la
lista de abajo y vuelve a correr el script).

Uso:
    python seed_cargos.py

Requiere que ya hayas corrido /setup en el bot (para que existan las
tarjetas "nu" y "mp").
"""

from datetime import date

from app.config import get_db_url
from app.db import create_session_factory
from app.models import CargoProgramado, EstadoCargo, Tarjeta

# (fecha, monto_centavos, numero_pago, incluye_compras_nuevas)
CARGOS_MP = [
    (date(2026, 10, 7), 101_400, None, False),
    (date(2026, 11, 7), 73_000, None, False),
    (date(2026, 12, 7), 53_900, None, False),
    (date(2027, 1, 7), 18_500, "6/10", False),
    (date(2027, 2, 7), 18_500, "7/10", False),
    (date(2027, 3, 7), 18_500, "8/10", False),
    (date(2027, 4, 7), 18_500, "9/10", False),
    (date(2027, 5, 7), 18_500, "10/10", False),
]

CARGOS_NU = [
    (date(2026, 10, 25), 80_000, None, True),
    (date(2026, 11, 25), 80_000, None, True),
    (date(2026, 12, 25), 80_000, None, True),
    (date(2027, 1, 25), 42_500, "5/12", False),
    (date(2027, 2, 25), 42_500, "6/12", False),
    (date(2027, 3, 25), 42_500, "7/12", False),
    (date(2027, 4, 25), 42_500, "8/12", False),
    (date(2027, 5, 25), 42_500, "9/12", False),
    (date(2027, 6, 25), 42_500, "10/12", False),
    (date(2027, 7, 25), 42_500, "11/12", False),
    (date(2027, 8, 25), 42_500, "12/12", False),
]


def sembrar(session, tarjeta: Tarjeta, concepto_base: str, filas: list[tuple]) -> int:
    creados = 0
    for fecha, monto, numero_pago, incluye_compras in filas:
        existe = (
            session.query(CargoProgramado)
            .filter(CargoProgramado.tarjeta_id == tarjeta.id, CargoProgramado.fecha == fecha)
            .one_or_none()
        )
        if existe is not None:
            continue
        concepto = concepto_base
        if incluye_compras:
            concepto += " (+ compras nuevas del periodo)"
        session.add(
            CargoProgramado(
                tarjeta_id=tarjeta.id,
                concepto=concepto,
                monto_centavos=monto,
                fecha=fecha,
                numero_pago=numero_pago,
                estado=EstadoCargo.PENDIENTE,
            )
        )
        creados += 1
    return creados


def main() -> None:
    Session = create_session_factory(get_db_url())
    with Session() as session:
        nu = session.query(Tarjeta).filter(Tarjeta.nombre == "nu").one_or_none()
        mp = session.query(Tarjeta).filter(Tarjeta.nombre == "mp").one_or_none()
        if nu is None or mp is None:
            print(
                "Todavia no tienes las tarjetas configuradas. "
                "Corre /setup en el bot primero y vuelve a intentar."
            )
            return

        total = sembrar(session, mp, "Pago Mercado Pago", CARGOS_MP)
        total += sembrar(session, nu, "Pago Nu", CARGOS_NU)
        session.commit()

    print(f"Listo: {total} pagos programados nuevos agregados (los que ya existian se dejaron igual).")


if __name__ == "__main__":
    main()
