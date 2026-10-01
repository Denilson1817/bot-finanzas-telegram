from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Movimiento, Tarjeta, TipoMovimiento


def saldo_tarjeta(session: Session, tarjeta_id: int) -> int:
    """Deuda actual: lo que ya debía al empezar a usar el bot, más las
    compras a crédito de esa tarjeta, menos lo que ya se ha pagado."""
    tarjeta = session.get(Tarjeta, tarjeta_id)
    if tarjeta is None:
        return 0

    gastos = (
        session.query(func.coalesce(func.sum(Movimiento.monto_centavos), 0))
        .filter(
            Movimiento.tarjeta_id == tarjeta_id,
            Movimiento.tipo == TipoMovimiento.GASTO,
        )
        .scalar()
        or 0
    )
    pagos = (
        session.query(func.coalesce(func.sum(Movimiento.monto_centavos), 0))
        .filter(
            Movimiento.tarjeta_id == tarjeta_id,
            Movimiento.tipo == TipoMovimiento.PAGO_TARJETA,
        )
        .scalar()
        or 0
    )
    return tarjeta.saldo_inicial_centavos + gastos - pagos
