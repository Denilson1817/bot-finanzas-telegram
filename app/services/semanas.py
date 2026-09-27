from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import (
    META_AHORRO_SEMANAL_DEFAULT_CENTAVOS,
    PRESUPUESTO_CAJA_DEFAULT_CENTAVOS,
    TZ,
)
from app.models import Categoria, MedioPago, Movimiento, Semana, TipoMovimiento

SABADO = 5  # date.weekday(): lunes=0 ... domingo=6

MEDIOS_CAJA = (MedioPago.DEBITO, MedioPago.EFECTIVO)


def hoy() -> date:
    return datetime.now(TZ).date()


def inicio_semana(fecha: date) -> date:
    dias_desde_sabado = (fecha.weekday() - SABADO) % 7
    return fecha - timedelta(days=dias_desde_sabado)


def rango_semana(fecha: date) -> tuple[date, date]:
    inicio = inicio_semana(fecha)
    return inicio, inicio + timedelta(days=6)


def _ultima_semana(session: Session) -> Semana | None:
    return session.query(Semana).order_by(Semana.fecha_fin.desc(), Semana.id.desc()).first()


def obtener_semana_actual(session: Session) -> Semana | None:
    """La semana abierta (no cerrada) más reciente, si existe.

    Las semanas avanzan solo mediante /cierre, nunca por el simple paso del
    calendario: si el usuario no ha cerrado la semana, sigue siendo la
    "actual" aunque ya haya pasado su fecha_fin (así no se pierde el ritual
    de mandar el sobrante a ahorro).
    """
    ultima = _ultima_semana(session)
    if ultima is not None and not ultima.cerrada:
        return ultima
    return None


def obtener_o_crear_semana_actual(session: Session) -> Semana:
    semana = obtener_semana_actual(session)
    if semana is not None:
        return semana

    anterior = _ultima_semana(session)
    if anterior is None:
        inicio, fin = rango_semana(hoy())
        presupuesto = PRESUPUESTO_CAJA_DEFAULT_CENTAVOS
        meta = META_AHORRO_SEMANAL_DEFAULT_CENTAVOS
    else:
        inicio = anterior.fecha_fin + timedelta(days=1)
        fin = inicio + timedelta(days=6)
        presupuesto = anterior.presupuesto_caja_centavos
        meta = anterior.meta_ahorro_centavos

    semana = Semana(
        fecha_inicio=inicio,
        fecha_fin=fin,
        presupuesto_caja_centavos=presupuesto,
        meta_ahorro_centavos=meta,
        cerrada=False,
    )
    session.add(semana)
    session.commit()
    return semana


def gastado_caja(session: Session, semana: Semana) -> int:
    total = (
        session.query(func.coalesce(func.sum(Movimiento.monto_centavos), 0))
        .filter(
            Movimiento.semana_id == semana.id,
            Movimiento.tipo == TipoMovimiento.GASTO,
            Movimiento.medio_pago.in_(MEDIOS_CAJA),
        )
        .scalar()
    )
    return total or 0


def _total_categoria_no_credito(session: Session, semana: Semana, categoria: Categoria) -> int:
    total = (
        session.query(func.coalesce(func.sum(Movimiento.monto_centavos), 0))
        .filter(
            Movimiento.semana_id == semana.id,
            Movimiento.tipo == TipoMovimiento.GASTO,
            Movimiento.categoria == categoria,
            Movimiento.medio_pago.in_(MEDIOS_CAJA),
        )
        .scalar()
    )
    return total or 0


def total_credito(session: Session, semana: Semana) -> int:
    total = (
        session.query(func.coalesce(func.sum(Movimiento.monto_centavos), 0))
        .filter(
            Movimiento.semana_id == semana.id,
            Movimiento.tipo == TipoMovimiento.GASTO,
            Movimiento.medio_pago.in_((MedioPago.CREDITO_NU, MedioPago.CREDITO_MP)),
        )
        .scalar()
    )
    return total or 0


def resumen_semana(session: Session, semana: Semana) -> dict:
    verde = _total_categoria_no_credito(session, semana, Categoria.OBLIGATORIO)
    rojo = _total_categoria_no_credito(session, semana, Categoria.EXTRA)
    naranja = total_credito(session, semana)
    gastado_caja_total = gastado_caja(session, semana)
    sobrante = semana.presupuesto_caja_centavos - gastado_caja_total
    dias_restantes = max((semana.fecha_fin - hoy()).days, 0)
    return {
        "presupuesto": semana.presupuesto_caja_centavos,
        "gastado_verde": verde,
        "gastado_rojo": rojo,
        "gastado_naranja": naranja,
        "gastado_caja": gastado_caja_total,
        "sobrante": sobrante,
        "dias_restantes": dias_restantes,
    }


def cerrar_semana(session: Session, semana: Semana, monto_a_ahorro_centavos: int) -> Semana:
    from app.services.movimientos import registrar_ahorro  # evita import circular

    if monto_a_ahorro_centavos > 0:
        registrar_ahorro(session, monto_a_ahorro_centavos, semana.id)

    semana.cerrada = True
    session.add(semana)
    session.commit()

    inicio, fin = rango_semana(semana.fecha_fin + timedelta(days=1))
    nueva = Semana(
        fecha_inicio=inicio,
        fecha_fin=fin,
        presupuesto_caja_centavos=semana.presupuesto_caja_centavos,
        meta_ahorro_centavos=semana.meta_ahorro_centavos,
        cerrada=False,
    )
    session.add(nueva)
    session.commit()
    return nueva
