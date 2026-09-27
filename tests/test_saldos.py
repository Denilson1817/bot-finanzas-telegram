from datetime import date

from app.models import Tarjeta, TipoMovimiento
from app.services.movimientos import (
    parse_captura_rapida,
    registrar_ahorro,
    registrar_ajuste,
    registrar_gasto,
    registrar_ingreso,
    registrar_pago_tarjeta,
)
from app.services.saldos import ahorro_acumulado, saldo_banco
from app.services.semanas import obtener_o_crear_semana_actual


def test_saldo_banco_con_ajuste_inicial(session):
    registrar_ajuste(session, 2_760_400, "Saldo inicial banco (setup)")
    assert saldo_banco(session) == 2_760_400


def test_gasto_debito_y_efectivo_bajan_el_banco(session):
    registrar_ajuste(session, 100_000, "Saldo inicial banco (setup)")
    semana = obtener_o_crear_semana_actual(session)
    registrar_gasto(session, parse_captura_rapida("66 pollo"), semana.id, fecha=date(2026, 9, 26))
    registrar_gasto(session, parse_captura_rapida("100 taxi ef"), semana.id, fecha=date(2026, 9, 26))
    assert saldo_banco(session) == 100_000 - 6_600 - 10_000


def test_gasto_credito_no_afecta_el_banco(session):
    registrar_ajuste(session, 100_000, "Saldo inicial banco (setup)")
    semana = obtener_o_crear_semana_actual(session)
    registrar_gasto(session, parse_captura_rapida("319 pizza nu"), semana.id, fecha=date(2026, 9, 26))
    assert saldo_banco(session) == 100_000


def test_pago_tarjeta_baja_el_banco(session):
    registrar_ajuste(session, 100_000, "Saldo inicial banco (setup)")
    nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=170_700)
    session.add(nu)
    session.commit()

    registrar_pago_tarjeta(session, nu.id, 80_000, fecha=date(2026, 10, 25))
    assert saldo_banco(session) == 20_000


def test_ingresos_y_reembolsos_suben_el_banco(session):
    registrar_ingreso(session, 793_400, "sueldo", fecha=date(2026, 10, 2))
    registrar_ingreso(session, 4_000, "reembolso spotify", tipo=TipoMovimiento.REEMBOLSO)
    assert saldo_banco(session) == 797_400


def test_ahorro_no_sale_del_banco_pero_se_acumula(session):
    registrar_ajuste(session, 100_000, "Saldo inicial banco (setup)")
    semana = obtener_o_crear_semana_actual(session)
    registrar_ahorro(session, 33_600, semana.id)
    assert saldo_banco(session) == 100_000
    assert ahorro_acumulado(session) == 33_600
