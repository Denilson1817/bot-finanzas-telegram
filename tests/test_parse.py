from app.models import Categoria, MedioPago
from app.services.movimientos import parse_captura_rapida, parse_monto_centavos


def test_parse_monto_entero():
    assert parse_monto_centavos("66") == 6600


def test_parse_monto_con_decimales():
    assert parse_monto_centavos("66.50") == 6650


def test_parse_monto_con_comas_de_miles():
    assert parse_monto_centavos("1,250") == 125_000


def test_parse_monto_con_signo_pesos():
    assert parse_monto_centavos("$200") == 20_000


def test_parse_monto_invalido():
    assert parse_monto_centavos("abc") is None
    assert parse_monto_centavos("-10") is None
    assert parse_monto_centavos("0") is None


def test_captura_simple_es_obligatorio_debito():
    parsed = parse_captura_rapida("66 pollo")
    assert parsed is not None
    assert parsed.monto_centavos == 6600
    assert parsed.concepto == "pollo"
    assert parsed.categoria == Categoria.OBLIGATORIO
    assert parsed.medio_pago == MedioPago.DEBITO


def test_captura_con_sufijo_extra():
    parsed = parse_captura_rapida("380 flores r")
    assert parsed.concepto == "flores"
    assert parsed.categoria == Categoria.EXTRA
    assert parsed.medio_pago == MedioPago.DEBITO


def test_captura_con_sufijo_credito_nu():
    parsed = parse_captura_rapida("319 pizza cena nu")
    assert parsed.concepto == "pizza cena"
    assert parsed.categoria == Categoria.OBLIGATORIO
    assert parsed.medio_pago == MedioPago.CREDITO_NU


def test_captura_con_sufijo_credito_mp():
    parsed = parse_captura_rapida("185 algo mp")
    assert parsed.medio_pago == MedioPago.CREDITO_MP


def test_captura_con_sufijo_efectivo():
    parsed = parse_captura_rapida("100 taxi ef")
    assert parsed.medio_pago == MedioPago.EFECTIVO


def test_captura_combina_sufijos_en_cualquier_orden():
    parsed = parse_captura_rapida("200 gasolina nu r")
    assert parsed.concepto == "gasolina"
    assert parsed.categoria == Categoria.EXTRA
    assert parsed.medio_pago == MedioPago.CREDITO_NU


def test_captura_sin_concepto_es_invalida():
    assert parse_captura_rapida("66") is None
    assert parse_captura_rapida("66 r") is None


def test_captura_sin_monto_es_invalida():
    assert parse_captura_rapida("pollo 66") is None
