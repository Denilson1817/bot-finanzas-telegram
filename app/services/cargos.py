from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import CargoProgramado, EstadoCargo
from app.services.semanas import hoy


def cargos_proximos(session: Session, dias: int = 14) -> list[CargoProgramado]:
    hoy_ = hoy()
    limite = hoy_ + timedelta(days=dias)
    return (
        session.query(CargoProgramado)
        .filter(
            CargoProgramado.estado == EstadoCargo.PENDIENTE,
            CargoProgramado.fecha >= hoy_,
            CargoProgramado.fecha <= limite,
        )
        .order_by(CargoProgramado.fecha)
        .all()
    )


def cargos_que_vencen_en(session: Session, dias: int) -> list[CargoProgramado]:
    fecha_objetivo = hoy() + timedelta(days=dias)
    return (
        session.query(CargoProgramado)
        .filter(
            CargoProgramado.estado == EstadoCargo.PENDIENTE,
            CargoProgramado.fecha == fecha_objetivo,
        )
        .order_by(CargoProgramado.id)
        .all()
    )


def proximo_cargo_pendiente(session: Session, tarjeta_id: int) -> CargoProgramado | None:
    return (
        session.query(CargoProgramado)
        .filter(
            CargoProgramado.tarjeta_id == tarjeta_id,
            CargoProgramado.estado == EstadoCargo.PENDIENTE,
        )
        .order_by(CargoProgramado.fecha)
        .first()
    )


def marcar_pagado_si_corresponde(
    session: Session, tarjeta_id: int, dentro_de_dias: int = 5
) -> CargoProgramado | None:
    """Marca como pagado el cargo pendiente más próximo de esta tarjeta,
    solo si ya está vencido o vence pronto (para no marcar por error un pago
    programado muy a futuro cuando el usuario hace un abono extra)."""
    limite = hoy() + timedelta(days=dentro_de_dias)
    cargo = (
        session.query(CargoProgramado)
        .filter(
            CargoProgramado.tarjeta_id == tarjeta_id,
            CargoProgramado.estado == EstadoCargo.PENDIENTE,
            CargoProgramado.fecha <= limite,
        )
        .order_by(CargoProgramado.fecha)
        .first()
    )
    if cargo is None:
        return None
    cargo.estado = EstadoCargo.PAGADO
    session.add(cargo)
    session.commit()
    return cargo
