import enum
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TipoMovimiento(enum.Enum):
    GASTO = "gasto"
    INGRESO = "ingreso"
    PAGO_TARJETA = "pago_tarjeta"
    AHORRO = "ahorro"
    REEMBOLSO = "reembolso"
    AJUSTE = "ajuste"


class Categoria(enum.Enum):
    OBLIGATORIO = "obligatorio"
    EXTRA = "extra"


class MedioPago(enum.Enum):
    DEBITO = "debito"
    EFECTIVO = "efectivo"
    CREDITO_NU = "credito_nu"
    CREDITO_MP = "credito_mp"


class EstadoCargo(enum.Enum):
    PENDIENTE = "pendiente"
    PAGADO = "pagado"


class Semana(Base):
    __tablename__ = "semanas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False)
    presupuesto_caja_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    meta_ahorro_centavos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cerrada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    movimientos: Mapped[list["Movimiento"]] = relationship(back_populates="semana")


class Tarjeta(Base):
    __tablename__ = "tarjetas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    dia_pago: Mapped[int] = mapped_column(Integer, nullable=False)
    saldo_inicial_centavos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    movimientos: Mapped[list["Movimiento"]] = relationship(back_populates="tarjeta")


class CargoProgramado(Base):
    __tablename__ = "cargos_programados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tarjeta_id: Mapped[int | None] = mapped_column(ForeignKey("tarjetas.id"), nullable=True)
    concepto: Mapped[str] = mapped_column(String(200), nullable=False)
    monto_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    numero_pago: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estado: Mapped[EstadoCargo] = mapped_column(
        Enum(EstadoCargo), nullable=False, default=EstadoCargo.PENDIENTE
    )

    tarjeta: Mapped[Tarjeta | None] = relationship()


class Meta(Base):
    __tablename__ = "metas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    monto_objetivo_centavos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fecha_objetivo: Mapped[date | None] = mapped_column(Date, nullable=True)


class Movimiento(Base):
    __tablename__ = "movimientos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    concepto: Mapped[str] = mapped_column(String(200), nullable=False)
    monto_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[TipoMovimiento] = mapped_column(Enum(TipoMovimiento), nullable=False)
    categoria: Mapped[Categoria | None] = mapped_column(Enum(Categoria), nullable=True)
    medio_pago: Mapped[MedioPago | None] = mapped_column(Enum(MedioPago), nullable=True)
    tarjeta_id: Mapped[int | None] = mapped_column(ForeignKey("tarjetas.id"), nullable=True)
    semana_id: Mapped[int | None] = mapped_column(ForeignKey("semanas.id"), nullable=True)
    nota: Mapped[str | None] = mapped_column(String(500), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    semana: Mapped[Semana | None] = relationship(back_populates="movimientos")
    tarjeta: Mapped[Tarjeta | None] = relationship(back_populates="movimientos")
