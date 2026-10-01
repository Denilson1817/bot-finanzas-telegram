from datetime import date

from app.models import Tarjeta
from app.services.movimientos import (
    parse_captura_rapida,
    registrar_gasto,
    registrar_pago_tarjeta,
)
from app.services.semanas import obtener_o_crear_semana_actual
from app.services.tarjetas import saldo_tarjeta


def test_saldo_tarjeta_parte_del_saldo_inicial(session):
    nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=170_700)
    session.add(nu)
    session.commit()

    assert saldo_tarjeta(session, nu.id) == 170_700


def test_saldo_tarjeta_suma_gastos_a_credito(session):
    nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=170_700)
    session.add(nu)
    session.commit()

    semana = obtener_o_crear_semana_actual(session)
    registrar_gasto(
        session, parse_captura_rapida("319 pizza nu"), semana.id, fecha=date(2026, 9, 26)
    )

    assert saldo_tarjeta(session, nu.id) == 170_700 + 31_900


def test_saldo_tarjeta_resta_pagos(session):
    nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=170_700)
    session.add(nu)
    session.commit()

    registrar_pago_tarjeta(session, nu.id, 80_000, fecha=date(2026, 10, 25))

    assert saldo_tarjeta(session, nu.id) == 90_700


def test_saldo_tarjeta_no_le_pega_a_otra_tarjeta(session):
    nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=100_000)
    mp = Tarjeta(nombre="mp", dia_pago=7, saldo_inicial_centavos=50_000)
    session.add_all([nu, mp])
    session.commit()

    semana = obtener_o_crear_semana_actual(session)
    registrar_gasto(
        session, parse_captura_rapida("185 algo mp"), semana.id, fecha=date(2026, 9, 26)
    )

    assert saldo_tarjeta(session, nu.id) == 100_000
    assert saldo_tarjeta(session, mp.id) == 50_000 + 18_500
