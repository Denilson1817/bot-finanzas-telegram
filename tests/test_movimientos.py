from datetime import date

from app.models import Categoria, MedioPago, Tarjeta, TipoMovimiento
from app.services.movimientos import (
    deshacer_por_id,
    parse_captura_rapida,
    registrar_ajuste,
    registrar_gasto,
    registrar_ingreso,
    toggle_categoria,
)
from app.services.semanas import obtener_o_crear_semana_actual


def test_registrar_gasto_sin_tarjeta_registrada_deja_tarjeta_id_nulo(session):
    semana = obtener_o_crear_semana_actual(session)
    parsed = parse_captura_rapida("319 pizza nu")
    mov = registrar_gasto(session, parsed, semana.id, fecha=date(2026, 9, 26))
    assert mov.tarjeta_id is None
    assert mov.medio_pago == MedioPago.CREDITO_NU


def test_registrar_gasto_credito_resuelve_tarjeta(session):
    semana = obtener_o_crear_semana_actual(session)
    nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=170_700)
    session.add(nu)
    session.commit()

    parsed = parse_captura_rapida("319 pizza nu")
    mov = registrar_gasto(session, parsed, semana.id, fecha=date(2026, 9, 26))
    assert mov.tarjeta_id == nu.id


def test_registrar_ingreso_default_es_ingreso(session):
    mov = registrar_ingreso(session, 793_400, "sueldo", fecha=date(2026, 10, 2))
    assert mov.tipo == TipoMovimiento.INGRESO
    assert mov.monto_centavos == 793_400


def test_registrar_ingreso_reembolso(session):
    mov = registrar_ingreso(
        session, 4_000, "reembolso spotify", tipo=TipoMovimiento.REEMBOLSO
    )
    assert mov.tipo == TipoMovimiento.REEMBOLSO


def test_registrar_ajuste(session):
    mov = registrar_ajuste(session, 2_760_400, "Saldo inicial banco (setup)")
    assert mov.tipo == TipoMovimiento.AJUSTE
    assert mov.monto_centavos == 2_760_400


def test_deshacer_por_id_elimina_el_movimiento(session):
    semana = obtener_o_crear_semana_actual(session)
    parsed = parse_captura_rapida("66 pollo")
    mov = registrar_gasto(session, parsed, semana.id)
    mov_id = mov.id

    deshecho = deshacer_por_id(session, mov_id)
    assert deshecho.id == mov_id
    assert deshacer_por_id(session, mov_id) is None


def test_toggle_categoria_cambia_obligatorio_extra(session):
    semana = obtener_o_crear_semana_actual(session)
    parsed = parse_captura_rapida("66 pollo")
    mov = registrar_gasto(session, parsed, semana.id)
    assert mov.categoria == Categoria.OBLIGATORIO

    mov = toggle_categoria(session, mov.id)
    assert mov.categoria == Categoria.EXTRA

    mov = toggle_categoria(session, mov.id)
    assert mov.categoria == Categoria.OBLIGATORIO
