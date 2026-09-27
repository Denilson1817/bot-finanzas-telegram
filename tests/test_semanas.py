from datetime import date

import app.services.semanas as semanas_mod
from app.services.movimientos import parse_captura_rapida, registrar_gasto


def test_rango_semana_desde_viernes():
    inicio, fin = semanas_mod.rango_semana(date(2026, 10, 2))
    assert inicio == date(2026, 9, 26)
    assert fin == date(2026, 10, 2)


def test_rango_semana_desde_sabado():
    inicio, fin = semanas_mod.rango_semana(date(2026, 9, 26))
    assert inicio == date(2026, 9, 26)
    assert fin == date(2026, 10, 2)


def test_obtener_o_crear_semana_actual_es_idempotente(session, monkeypatch):
    monkeypatch.setattr(semanas_mod, "hoy", lambda: date(2026, 9, 27))
    semana1 = semanas_mod.obtener_o_crear_semana_actual(session)
    semana2 = semanas_mod.obtener_o_crear_semana_actual(session)
    assert semana1.id == semana2.id
    assert semana1.fecha_inicio == date(2026, 9, 26)
    assert semana1.fecha_fin == date(2026, 10, 2)


def test_nueva_semana_hereda_presupuesto_de_la_anterior(session, monkeypatch):
    monkeypatch.setattr(semanas_mod, "hoy", lambda: date(2026, 9, 27))
    semana1 = semanas_mod.obtener_o_crear_semana_actual(session)
    semana1.presupuesto_caja_centavos = 139_200
    session.add(semana1)
    session.commit()

    semanas_mod.cerrar_semana(session, semana1, 0)
    semana2 = semanas_mod.obtener_o_crear_semana_actual(session)
    assert semana2.id != semana1.id
    assert semana2.presupuesto_caja_centavos == 139_200


def test_semana_no_avanza_sola_por_el_calendario(session, monkeypatch):
    """Si no se llama a /cierre, la semana sigue "actual" aunque ya haya
    pasado su fecha_fin: el sobrante no debe perderse silenciosamente."""
    monkeypatch.setattr(semanas_mod, "hoy", lambda: date(2026, 9, 26))
    semana1 = semanas_mod.obtener_o_crear_semana_actual(session)

    monkeypatch.setattr(semanas_mod, "hoy", lambda: date(2026, 10, 20))
    semana_todavia = semanas_mod.obtener_o_crear_semana_actual(session)
    assert semana_todavia.id == semana1.id
    assert semana_todavia.cerrada is False


def test_semana_avanza_exactamente_una_vez_al_cerrar_aunque_hoy_ya_no_coincida(
    session, monkeypatch
):
    monkeypatch.setattr(semanas_mod, "hoy", lambda: date(2026, 9, 26))
    semana1 = semanas_mod.obtener_o_crear_semana_actual(session)

    monkeypatch.setattr(semanas_mod, "hoy", lambda: date(2026, 10, 20))
    semanas_mod.cerrar_semana(session, semana1, 0)

    semana2 = semanas_mod.obtener_o_crear_semana_actual(session)
    assert semana2.id != semana1.id
    assert semana2.fecha_inicio == date(2026, 10, 3)
    assert semana2.fecha_fin == date(2026, 10, 9)


def test_resumen_semana_calcula_totales_por_color_y_sobrante(session, monkeypatch):
    monkeypatch.setattr(semanas_mod, "hoy", lambda: date(2026, 9, 26))
    semana = semanas_mod.obtener_o_crear_semana_actual(session)
    semana.presupuesto_caja_centavos = 125_000
    session.add(semana)
    session.commit()

    verdes = ["66 pollo", "13 tortillas", "114 hamburguesa", "140 viaje ida"]
    rojos = ["250 flores r", "380 flores dos r", "100 envio flores r"]
    naranjas = ["388 cena nu", "319 pizza cena nu"]
    for texto in verdes:
        registrar_gasto(session, parse_captura_rapida(texto), semana.id, fecha=date(2026, 9, 26))
    for texto in rojos:
        registrar_gasto(session, parse_captura_rapida(texto), semana.id, fecha=date(2026, 9, 26))
    for texto in naranjas:
        registrar_gasto(session, parse_captura_rapida(texto), semana.id, fecha=date(2026, 9, 26))

    r = semanas_mod.resumen_semana(session, semana)

    assert r["gastado_verde"] == 6_600 + 1_300 + 11_400 + 14_000
    assert r["gastado_rojo"] == 25_000 + 38_000 + 10_000
    assert r["gastado_naranja"] == 38_800 + 31_900
    assert r["gastado_caja"] == r["gastado_verde"] + r["gastado_rojo"]
    assert r["sobrante"] == 125_000 - r["gastado_caja"]
    assert r["dias_restantes"] == 6


def test_cerrar_semana_registra_ahorro_y_abre_la_siguiente(session, monkeypatch):
    monkeypatch.setattr(semanas_mod, "hoy", lambda: date(2026, 9, 26))
    semana = semanas_mod.obtener_o_crear_semana_actual(session)
    semana.presupuesto_caja_centavos = 125_000
    session.add(semana)
    session.commit()

    nueva = semanas_mod.cerrar_semana(session, semana, 33_600)

    assert semana.cerrada is True
    assert nueva.cerrada is False
    assert nueva.fecha_inicio == date(2026, 10, 3)
    assert nueva.fecha_fin == date(2026, 10, 9)
    assert nueva.presupuesto_caja_centavos == 125_000

    from app.services.saldos import ahorro_acumulado

    assert ahorro_acumulado(session) == 33_600
