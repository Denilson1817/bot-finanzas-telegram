from datetime import date

from app.models import CargoProgramado, EstadoCargo, Tarjeta
from app.services.cargos import (
    cargos_proximos,
    cargos_que_vencen_en,
    marcar_pagado_si_corresponde,
    proximo_cargo_pendiente,
)
import app.services.cargos as cargos_mod


def _cargo(tarjeta_id, fecha, monto, numero_pago=None, estado=EstadoCargo.PENDIENTE):
    return CargoProgramado(
        tarjeta_id=tarjeta_id,
        concepto="Pago Nu",
        monto_centavos=monto,
        fecha=fecha,
        numero_pago=numero_pago,
        estado=estado,
    )


def test_cargos_proximos_respeta_la_ventana_de_dias(session, monkeypatch):
    monkeypatch.setattr(cargos_mod, "hoy", lambda: date(2026, 10, 1))
    nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=0)
    session.add(nu)
    session.commit()

    session.add_all(
        [
            _cargo(nu.id, date(2026, 10, 5), 80_000),
            _cargo(nu.id, date(2026, 10, 20), 80_000),  # fuera de la ventana de 14 dias
            _cargo(nu.id, date(2026, 9, 30), 80_000),  # ya paso
        ]
    )
    session.commit()

    resultado = cargos_proximos(session, dias=14)
    assert [c.fecha for c in resultado] == [date(2026, 10, 5)]


def test_cargos_proximos_excluye_los_ya_pagados(session, monkeypatch):
    monkeypatch.setattr(cargos_mod, "hoy", lambda: date(2026, 10, 1))
    nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=0)
    session.add(nu)
    session.commit()
    session.add(_cargo(nu.id, date(2026, 10, 5), 80_000, estado=EstadoCargo.PAGADO))
    session.commit()

    assert cargos_proximos(session, dias=14) == []


def test_cargos_que_vencen_en_filtra_por_fecha_exacta(session, monkeypatch):
    monkeypatch.setattr(cargos_mod, "hoy", lambda: date(2026, 10, 1))
    nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=0)
    session.add(nu)
    session.commit()
    session.add_all(
        [
            _cargo(nu.id, date(2026, 10, 2), 80_000),
            _cargo(nu.id, date(2026, 10, 3), 80_000),
        ]
    )
    session.commit()

    assert [c.fecha for c in cargos_que_vencen_en(session, dias=1)] == [date(2026, 10, 2)]


def test_proximo_cargo_pendiente_toma_el_mas_cercano(session):
    nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=0)
    session.add(nu)
    session.commit()
    session.add_all(
        [
            _cargo(nu.id, date(2027, 1, 25), 42_500, numero_pago="5/12"),
            _cargo(nu.id, date(2026, 12, 25), 80_000),
        ]
    )
    session.commit()

    cargo = proximo_cargo_pendiente(session, nu.id)
    assert cargo.fecha == date(2026, 12, 25)


def test_marcar_pagado_si_corresponde_marca_el_mas_cercano_si_ya_vence_pronto(
    session, monkeypatch
):
    monkeypatch.setattr(cargos_mod, "hoy", lambda: date(2026, 10, 24))
    nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=0)
    session.add(nu)
    session.commit()
    session.add(_cargo(nu.id, date(2026, 10, 25), 80_000))
    session.commit()

    cargo = marcar_pagado_si_corresponde(session, nu.id)
    assert cargo is not None
    assert cargo.estado == EstadoCargo.PAGADO


def test_marcar_pagado_si_corresponde_no_toca_cargos_muy_a_futuro(session, monkeypatch):
    monkeypatch.setattr(cargos_mod, "hoy", lambda: date(2026, 10, 1))
    nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=0)
    session.add(nu)
    session.commit()
    session.add(_cargo(nu.id, date(2026, 12, 25), 80_000))
    session.commit()

    cargo = marcar_pagado_si_corresponde(session, nu.id)
    assert cargo is None
