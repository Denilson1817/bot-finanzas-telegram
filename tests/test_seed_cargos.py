from app.models import CargoProgramado, Tarjeta
from seed_cargos import CARGOS_MP, CARGOS_NU, sembrar


def test_calendario_mp_tiene_los_montos_del_documento():
    assert len(CARGOS_MP) == 8
    montos = [monto for _, monto, _, _ in CARGOS_MP]
    assert montos == [101_400, 73_000, 53_900] + [18_500] * 5
    numeros = [n for _, _, n, _ in CARGOS_MP[3:]]
    assert numeros == ["6/10", "7/10", "8/10", "9/10", "10/10"]


def test_calendario_nu_tiene_los_montos_del_documento():
    assert len(CARGOS_NU) == 11
    primeros_tres = CARGOS_NU[:3]
    assert all(monto == 80_000 and incluye for _, monto, _, incluye in primeros_tres)
    resto = CARGOS_NU[3:]
    assert all(monto == 42_500 and not incluye for _, monto, _, incluye in resto)
    numeros = [n for _, _, n, _ in resto]
    assert numeros == [f"{i}/12" for i in range(5, 13)]


def test_sembrar_es_idempotente(session):
    nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=170_700)
    session.add(nu)
    session.commit()

    creados_1 = sembrar(session, nu, "Pago Nu", CARGOS_NU)
    session.commit()
    creados_2 = sembrar(session, nu, "Pago Nu", CARGOS_NU)
    session.commit()

    assert creados_1 == len(CARGOS_NU)
    assert creados_2 == 0
    assert session.query(CargoProgramado).count() == len(CARGOS_NU)


def test_sembrar_marca_compras_nuevas_en_el_concepto(session):
    nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=0)
    session.add(nu)
    session.commit()
    sembrar(session, nu, "Pago Nu", CARGOS_NU)
    session.commit()

    primero = (
        session.query(CargoProgramado)
        .filter(CargoProgramado.fecha == CARGOS_NU[0][0])
        .one()
    )
    ultimo = (
        session.query(CargoProgramado)
        .filter(CargoProgramado.fecha == CARGOS_NU[-1][0])
        .one()
    )
    assert "compras nuevas" in primero.concepto
    assert "compras nuevas" not in ultimo.concepto
