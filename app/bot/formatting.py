from app.models import Categoria, MedioPago

NOMBRE_MEDIO_PAGO = {
    MedioPago.DEBITO: "débito",
    MedioPago.EFECTIVO: "efectivo",
    MedioPago.CREDITO_NU: "crédito Nu",
    MedioPago.CREDITO_MP: "crédito Mercado Pago",
}


def fmt_money(centavos: int) -> str:
    signo = "-" if centavos < 0 else ""
    pesos, resto = divmod(abs(centavos), 100)
    pesos_str = f"{pesos:,}"
    if resto == 0:
        return f"{signo}${pesos_str}"
    return f"{signo}${pesos_str}.{resto:02d}"


def color_emoji(categoria: Categoria | None, medio_pago: MedioPago | None) -> str:
    if medio_pago in (MedioPago.CREDITO_NU, MedioPago.CREDITO_MP):
        return "🟠"
    if categoria == Categoria.EXTRA:
        return "🔴"
    return "🟢"
