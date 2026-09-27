from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models import Categoria, MedioPago, Movimiento, Tarjeta, TipoMovimiento
from app.services.semanas import hoy

# Sufijos reconocidos al final de una captura rápida, en cualquier orden:
#   r          -> gasto extra (rojo). Sin sufijo = obligatorio (verde).
#   nu / mp    -> pagado con crédito Nu / Mercado Pago (naranja).
#   ef / efe   -> pagado en efectivo. Sin sufijo de medio = débito.
_SUFIJOS_CATEGORIA = {"r": Categoria.EXTRA}
_SUFIJOS_MEDIO = {
    "nu": MedioPago.CREDITO_NU,
    "mp": MedioPago.CREDITO_MP,
    "ef": MedioPago.EFECTIVO,
    "efe": MedioPago.EFECTIVO,
}

_NOMBRE_TARJETA_POR_MEDIO = {
    MedioPago.CREDITO_NU: "nu",
    MedioPago.CREDITO_MP: "mp",
}


@dataclass
class ParsedGasto:
    monto_centavos: int
    concepto: str
    categoria: Categoria
    medio_pago: MedioPago


def parse_monto_centavos(token: str) -> int | None:
    limpio = token.strip().replace("$", "").replace(",", "")
    if not limpio:
        return None
    try:
        valor = Decimal(limpio)
    except InvalidOperation:
        return None
    if valor <= 0:
        return None
    return int((valor * 100).to_integral_value())


def parse_captura_rapida(texto: str) -> ParsedGasto | None:
    tokens = texto.strip().split()
    if len(tokens) < 2:
        return None

    monto_centavos = parse_monto_centavos(tokens[0])
    if monto_centavos is None:
        return None

    resto = tokens[1:]
    categoria = Categoria.OBLIGATORIO
    medio_pago = MedioPago.DEBITO

    while resto:
        candidato = resto[-1].lower()
        if candidato in _SUFIJOS_CATEGORIA:
            categoria = _SUFIJOS_CATEGORIA[candidato]
            resto.pop()
        elif candidato in _SUFIJOS_MEDIO:
            medio_pago = _SUFIJOS_MEDIO[candidato]
            resto.pop()
        else:
            break

    concepto = " ".join(resto).strip()
    if not concepto:
        return None

    return ParsedGasto(
        monto_centavos=monto_centavos,
        concepto=concepto,
        categoria=categoria,
        medio_pago=medio_pago,
    )


def resolver_tarjeta_id(session: Session, medio_pago: MedioPago) -> int | None:
    nombre = _NOMBRE_TARJETA_POR_MEDIO.get(medio_pago)
    if nombre is None:
        return None
    tarjeta = session.query(Tarjeta).filter(Tarjeta.nombre == nombre).one_or_none()
    return tarjeta.id if tarjeta is not None else None


def registrar_gasto(
    session: Session,
    parsed: ParsedGasto,
    semana_id: int,
    fecha: date | None = None,
) -> Movimiento:
    mov = Movimiento(
        fecha=fecha or hoy(),
        concepto=parsed.concepto,
        monto_centavos=parsed.monto_centavos,
        tipo=TipoMovimiento.GASTO,
        categoria=parsed.categoria,
        medio_pago=parsed.medio_pago,
        tarjeta_id=resolver_tarjeta_id(session, parsed.medio_pago),
        semana_id=semana_id,
    )
    session.add(mov)
    session.commit()
    return mov


def registrar_ingreso(
    session: Session,
    monto_centavos: int,
    concepto: str,
    tipo: TipoMovimiento = TipoMovimiento.INGRESO,
    fecha: date | None = None,
) -> Movimiento:
    mov = Movimiento(
        fecha=fecha or hoy(),
        concepto=concepto,
        monto_centavos=monto_centavos,
        tipo=tipo,
    )
    session.add(mov)
    session.commit()
    return mov


def registrar_ajuste(
    session: Session,
    monto_centavos: int,
    concepto: str,
    fecha: date | None = None,
) -> Movimiento:
    mov = Movimiento(
        fecha=fecha or hoy(),
        concepto=concepto,
        monto_centavos=monto_centavos,
        tipo=TipoMovimiento.AJUSTE,
    )
    session.add(mov)
    session.commit()
    return mov


def registrar_ahorro(
    session: Session,
    monto_centavos: int,
    semana_id: int,
    concepto: str = "Ahorro semanal",
    fecha: date | None = None,
) -> Movimiento:
    mov = Movimiento(
        fecha=fecha or hoy(),
        concepto=concepto,
        monto_centavos=monto_centavos,
        tipo=TipoMovimiento.AHORRO,
        semana_id=semana_id,
    )
    session.add(mov)
    session.commit()
    return mov


def registrar_pago_tarjeta(
    session: Session,
    tarjeta_id: int,
    monto_centavos: int,
    fecha: date | None = None,
) -> Movimiento:
    tarjeta = session.get(Tarjeta, tarjeta_id)
    concepto = f"Pago tarjeta {tarjeta.nombre}" if tarjeta else "Pago tarjeta"
    mov = Movimiento(
        fecha=fecha or hoy(),
        concepto=concepto,
        monto_centavos=monto_centavos,
        tipo=TipoMovimiento.PAGO_TARJETA,
        tarjeta_id=tarjeta_id,
    )
    session.add(mov)
    session.commit()
    return mov


def deshacer_ultimo(session: Session) -> Movimiento | None:
    mov = (
        session.query(Movimiento)
        .order_by(Movimiento.creado_en.desc(), Movimiento.id.desc())
        .first()
    )
    if mov is None:
        return None
    session.delete(mov)
    session.commit()
    return mov


def deshacer_por_id(session: Session, movimiento_id: int) -> Movimiento | None:
    mov = session.get(Movimiento, movimiento_id)
    if mov is None:
        return None
    session.delete(mov)
    session.commit()
    return mov


def toggle_categoria(session: Session, movimiento_id: int) -> Movimiento | None:
    mov = session.get(Movimiento, movimiento_id)
    if mov is None or mov.categoria is None:
        return None
    mov.categoria = (
        Categoria.OBLIGATORIO if mov.categoria == Categoria.EXTRA else Categoria.EXTRA
    )
    session.add(mov)
    session.commit()
    return mov
