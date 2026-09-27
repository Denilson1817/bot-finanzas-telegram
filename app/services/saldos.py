from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import MedioPago, Movimiento, TipoMovimiento

_MEDIOS_QUE_SALEN_DEL_BANCO = (MedioPago.DEBITO, MedioPago.EFECTIVO)


def _suma(session: Session, *filtros) -> int:
    total = (
        session.query(func.coalesce(func.sum(Movimiento.monto_centavos), 0))
        .filter(*filtros)
        .scalar()
    )
    return total or 0


def saldo_banco(session: Session) -> int:
    """Dinero total en la cuenta Nu (incluye la caja semanal y el ahorro,
    que son solo "apartados" dentro del mismo banco, no salidas reales)."""
    entradas = _suma(
        session,
        Movimiento.tipo.in_((TipoMovimiento.INGRESO, TipoMovimiento.REEMBOLSO)),
    )
    ajustes = _suma(session, Movimiento.tipo == TipoMovimiento.AJUSTE)
    gastos_banco = _suma(
        session,
        Movimiento.tipo == TipoMovimiento.GASTO,
        Movimiento.medio_pago.in_(_MEDIOS_QUE_SALEN_DEL_BANCO),
    )
    pagos_tarjeta = _suma(session, Movimiento.tipo == TipoMovimiento.PAGO_TARJETA)
    return entradas + ajustes - gastos_banco - pagos_tarjeta


def ahorro_acumulado(session: Session) -> int:
    return _suma(session, Movimiento.tipo == TipoMovimiento.AHORRO)
