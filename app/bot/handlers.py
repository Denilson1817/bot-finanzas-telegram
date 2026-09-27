from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.bot.formatting import NOMBRE_MEDIO_PAGO, color_emoji, fmt_money
from app.config import TZ
from app.models import MedioPago, Semana, Tarjeta, TipoMovimiento
from app.services.movimientos import (
    deshacer_por_id,
    parse_captura_rapida,
    parse_monto_centavos,
    registrar_ajuste,
    registrar_gasto,
    registrar_ingreso,
    toggle_categoria,
)
from app.services.saldos import ahorro_acumulado, saldo_banco
from app.services.semanas import (
    cerrar_semana,
    gastado_caja,
    obtener_o_crear_semana_actual,
    obtener_semana_actual,
    resumen_semana,
)

SETUP_BANCO, SETUP_NU, SETUP_MP, SETUP_PRESUPUESTO = range(4)


def _session_factory(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data["Session"]


def _fecha_del_mensaje(update: Update):
    """Fecha real en que se escribió el mensaje (zona MX), no la fecha en que
    el bot lo procesó. Importante si el bot estuvo apagado y Telegram entrega
    mensajes atrasados al reconectar: el gasto debe quedar en el día en que
    de verdad ocurrió."""
    return update.message.date.astimezone(TZ).date()


def _parse_monto_o_cero(texto: str) -> int | None:
    limpio = texto.strip().lower()
    if limpio in ("0", "no", "nada", "ninguno"):
        return 0
    return parse_monto_centavos(texto)


def _botones_movimiento(mov_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("↩️ Deshacer", callback_data=f"deshacer:{mov_id}"),
                InlineKeyboardButton("🔁 Cambiar color", callback_data=f"toggle:{mov_id}"),
            ]
        ]
    )


def _texto_confirmacion_gasto(session, mov, semana) -> str:
    emoji = color_emoji(mov.categoria, mov.medio_pago)
    if mov.medio_pago in (MedioPago.DEBITO, MedioPago.EFECTIVO) and semana is not None:
        restante = semana.presupuesto_caja_centavos - gastado_caja(session, semana)
        return f"✅ {mov.concepto} {fmt_money(mov.monto_centavos)} {emoji} · Caja: {fmt_money(restante)} restantes"
    nombre_medio = NOMBRE_MEDIO_PAGO[mov.medio_pago]
    return f"✅ {mov.concepto} {fmt_money(mov.monto_centavos)} {emoji} · {nombre_medio}, no afecta tu caja"


# --- Comandos básicos -------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Bot de finanzas personales.\n\n"
        "Para empezar usa /setup.\n"
        "Para registrar un gasto solo escribe: monto concepto (ej. 66 pollo).\n"
        "Sufijos: r = extra, nu/mp = crédito, ef = efectivo. Ej: 380 flores r\n\n"
        "Comandos: /semana /saldo /ingreso /presupuesto /cierre"
    )


async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parsed = parse_captura_rapida(update.message.text)
    if parsed is None:
        await update.message.reply_text(
            "No entendí ese mensaje. Formato: monto concepto [r] [nu|mp|ef]\nEj: 66 pollo"
        )
        return

    Session = _session_factory(context)
    with Session() as session:
        semana = obtener_o_crear_semana_actual(session)
        mov = registrar_gasto(session, parsed, semana.id, fecha=_fecha_del_mensaje(update))
        texto = _texto_confirmacion_gasto(session, mov, semana)
        mov_id = mov.id

    await update.message.reply_text(texto, reply_markup=_botones_movimiento(mov_id))


async def cmd_semana(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    Session = _session_factory(context)
    with Session() as session:
        semana = obtener_o_crear_semana_actual(session)
        r = resumen_semana(session, semana)

    texto = (
        f"📅 Semana {semana.fecha_inicio:%d-%b} a {semana.fecha_fin:%d-%b}\n"
        f"Presupuesto caja: {fmt_money(r['presupuesto'])}\n"
        f"🟢 Obligatorio: {fmt_money(r['gastado_verde'])}\n"
        f"🔴 Extra: {fmt_money(r['gastado_rojo'])}\n"
        f"🟠 Crédito: {fmt_money(r['gastado_naranja'])}\n"
        f"💰 Sobrante caja: {fmt_money(r['sobrante'])}\n"
        f"⏳ Días restantes: {r['dias_restantes']}"
    )
    await update.message.reply_text(texto)


async def cmd_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    Session = _session_factory(context)
    with Session() as session:
        banco = saldo_banco(session)
        ahorro = ahorro_acumulado(session)
        semana = obtener_o_crear_semana_actual(session)
        caja_restante = semana.presupuesto_caja_centavos - gastado_caja(session, semana)

    texto = (
        f"🏦 Banco: {fmt_money(banco)}\n"
        f"📦 Caja de esta semana: {fmt_money(caja_restante)}\n"
        f"🚗 Ahorro enganche: {fmt_money(ahorro)}"
    )
    await update.message.reply_text(texto)


async def cmd_ingreso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /ingreso <monto> <concepto>\n"
            "Ej: /ingreso 7934 sueldo\n"
            "Ej: /ingreso 40 reembolso spotify"
        )
        return

    monto = parse_monto_centavos(context.args[0])
    if monto is None:
        await update.message.reply_text("El monto no es válido.")
        return

    palabras = list(context.args[1:])
    tipo = TipoMovimiento.INGRESO
    if palabras[0].lower() == "reembolso":
        tipo = TipoMovimiento.REEMBOLSO
        palabras = palabras[1:] or ["reembolso"]
    concepto = " ".join(palabras)

    Session = _session_factory(context)
    with Session() as session:
        registrar_ingreso(session, monto, concepto, tipo=tipo, fecha=_fecha_del_mensaje(update))

    etiqueta = "Reembolso" if tipo == TipoMovimiento.REEMBOLSO else "Ingreso"
    await update.message.reply_text(f"✅ {etiqueta} {fmt_money(monto)} · {concepto}")


async def cmd_presupuesto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /presupuesto <monto>\nEj: /presupuesto 1392")
        return

    monto = parse_monto_centavos(context.args[0])
    if monto is None:
        await update.message.reply_text("El monto no es válido.")
        return

    Session = _session_factory(context)
    with Session() as session:
        semana = obtener_o_crear_semana_actual(session)
        semana.presupuesto_caja_centavos = monto
        session.add(semana)
        session.commit()
        restante = monto - gastado_caja(session, semana)

    await update.message.reply_text(
        f"✅ Presupuesto actualizado a {fmt_money(monto)} · Restan {fmt_money(restante)}"
    )


async def cmd_cierre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    Session = _session_factory(context)
    with Session() as session:
        semana = obtener_semana_actual(session)
        if semana is None or semana.cerrada:
            await update.message.reply_text("No hay una semana abierta para cerrar.")
            return
        r = resumen_semana(session, semana)
        semana_id = semana.id
        fecha_inicio, fecha_fin = semana.fecha_inicio, semana.fecha_fin
        sobrante = max(r["sobrante"], 0)

    if context.args:
        monto = parse_monto_centavos(context.args[0])
        if monto is None:
            if context.args[0].strip().lower() in ("0", "nada"):
                monto = 0
            else:
                await update.message.reply_text("El monto de ahorro no es válido.")
                return
        with Session() as session:
            semana = session.get(Semana, semana_id)
            nueva = cerrar_semana(session, semana, monto)
        await update.message.reply_text(
            f"🔒 Semana cerrada. Ahorro enviado: {fmt_money(monto)}\n"
            f"📅 Nueva semana: {nueva.fecha_inicio:%d-%b} a {nueva.fecha_fin:%d-%b}\n"
            f"Presupuesto caja: {fmt_money(nueva.presupuesto_caja_centavos)}"
        )
        return

    texto = (
        f"📅 Cierre de semana {fecha_inicio:%d-%b} a {fecha_fin:%d-%b}\n"
        f"Presupuesto: {fmt_money(r['presupuesto'])}\n"
        f"Gastado en caja: {fmt_money(r['gastado_caja'])}\n"
        f"Sobrante: {fmt_money(r['sobrante'])}\n\n"
        "¿Cuánto mandamos a ahorro?"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"Todo el sobrante ({fmt_money(sobrante)})",
                    callback_data=f"cierre:{semana_id}:{sobrante}",
                ),
                InlineKeyboardButton("Nada", callback_data=f"cierre:{semana_id}:0"),
            ]
        ]
    )
    await update.message.reply_text(texto, reply_markup=keyboard)


# --- Botones inline ----------------------------------------------------


async def cb_botones(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_user is None or (
        update.effective_user.id != context.application.bot_data["allowed_user_id"]
    ):
        await query.answer()
        return
    await query.answer()
    accion, _, resto = query.data.partition(":")
    Session = _session_factory(context)

    if accion == "deshacer":
        mov_id = int(resto)
        with Session() as session:
            mov = deshacer_por_id(session, mov_id)
        if mov is None:
            await query.edit_message_text("Ese movimiento ya no existe (¿ya lo deshiciste?).")
        else:
            await query.edit_message_text(f"↩️ Deshecho: {mov.concepto} {fmt_money(mov.monto_centavos)}")

    elif accion == "toggle":
        mov_id = int(resto)
        with Session() as session:
            mov = toggle_categoria(session, mov_id)
            if mov is None:
                texto = None
            else:
                semana = session.get(Semana, mov.semana_id) if mov.semana_id else None
                texto = _texto_confirmacion_gasto(session, mov, semana)
        if texto is None:
            await query.edit_message_text("Ese movimiento ya no existe.")
        else:
            await query.edit_message_text(texto, reply_markup=_botones_movimiento(mov_id))

    elif accion == "cierre":
        semana_id_str, monto_str = resto.split(":")
        semana_id, monto = int(semana_id_str), int(monto_str)
        with Session() as session:
            semana = session.get(Semana, semana_id)
            if semana is None or semana.cerrada:
                await query.edit_message_text("Esta semana ya fue cerrada.")
                return
            nueva = cerrar_semana(session, semana, monto)
        await query.edit_message_text(
            f"🔒 Semana cerrada. Ahorro enviado: {fmt_money(monto)}\n"
            f"📅 Nueva semana: {nueva.fecha_inicio:%d-%b} a {nueva.fecha_fin:%d-%b}\n"
            f"Presupuesto caja: {fmt_money(nueva.presupuesto_caja_centavos)}"
        )


# --- /setup: conversación guiada ---------------------------------------


async def cmd_setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Vamos a configurar tus datos iniciales (puedes cancelar con /cancelar).\n\n"
        "¿Cuál es tu saldo actual en el banco (Nu)? Escribe solo el número."
    )
    return SETUP_BANCO


async def setup_banco(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    monto = _parse_monto_o_cero(update.message.text)
    if monto is None:
        await update.message.reply_text("No entendí el monto. Escribe solo un número, ej: 27604")
        return SETUP_BANCO
    context.user_data["setup_banco"] = monto
    await update.message.reply_text(
        "¿Cuánto debes ahora mismo en tu tarjeta Nu (lo que falta por pagar)? Escribe 0 si no debes nada."
    )
    return SETUP_NU


async def setup_nu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    monto = _parse_monto_o_cero(update.message.text)
    if monto is None:
        await update.message.reply_text("Escribe solo un número (puede ser 0).")
        return SETUP_NU
    context.user_data["setup_nu"] = monto
    await update.message.reply_text("¿Cuánto debes en Mercado Pago? Escribe 0 si no debes nada.")
    return SETUP_MP


async def setup_mp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    monto = _parse_monto_o_cero(update.message.text)
    if monto is None:
        await update.message.reply_text("Escribe solo un número (puede ser 0).")
        return SETUP_MP
    context.user_data["setup_mp"] = monto
    await update.message.reply_text(
        "¿Con cuánto quieres iniciar tu caja semanal? (sugerido $1,250)"
    )
    return SETUP_PRESUPUESTO


async def setup_presupuesto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    monto = parse_monto_centavos(update.message.text)
    if monto is None:
        await update.message.reply_text("Escribe solo un número mayor a 0.")
        return SETUP_PRESUPUESTO

    saldo_banco_inicial = context.user_data["setup_banco"]
    saldo_nu = context.user_data["setup_nu"]
    saldo_mp = context.user_data["setup_mp"]

    Session = _session_factory(context)
    with Session() as session:
        nu = session.query(Tarjeta).filter(Tarjeta.nombre == "nu").one_or_none()
        if nu is None:
            nu = Tarjeta(nombre="nu", dia_pago=25, saldo_inicial_centavos=saldo_nu)
        else:
            nu.saldo_inicial_centavos = saldo_nu
        mp = session.query(Tarjeta).filter(Tarjeta.nombre == "mp").one_or_none()
        if mp is None:
            mp = Tarjeta(nombre="mp", dia_pago=7, saldo_inicial_centavos=saldo_mp)
        else:
            mp.saldo_inicial_centavos = saldo_mp
        session.add_all([nu, mp])
        session.commit()

        registrar_ajuste(session, saldo_banco_inicial, "Saldo inicial banco (setup)")

        semana = obtener_o_crear_semana_actual(session)
        semana.presupuesto_caja_centavos = monto
        session.add(semana)
        session.commit()

    context.user_data.clear()
    await update.message.reply_text(
        "✅ Configuración guardada.\n"
        f"🏦 Banco: {fmt_money(saldo_banco_inicial)}\n"
        f"💳 Nu: {fmt_money(saldo_nu)} · Mercado Pago: {fmt_money(saldo_mp)}\n"
        f"📦 Caja semanal: {fmt_money(monto)}\n\n"
        "Ya puedes registrar gastos escribiendo, por ejemplo: 66 pollo"
    )
    return ConversationHandler.END


async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Configuración cancelada.")
    return ConversationHandler.END


def register_handlers(application: Application, allowed_user_id: int) -> None:
    application.bot_data["allowed_user_id"] = allowed_user_id
    solo_dueno = filters.User(user_id=allowed_user_id)

    setup_conv = ConversationHandler(
        entry_points=[CommandHandler("setup", cmd_setup_start, filters=solo_dueno)],
        states={
            SETUP_BANCO: [MessageHandler(solo_dueno & filters.TEXT & ~filters.COMMAND, setup_banco)],
            SETUP_NU: [MessageHandler(solo_dueno & filters.TEXT & ~filters.COMMAND, setup_nu)],
            SETUP_MP: [MessageHandler(solo_dueno & filters.TEXT & ~filters.COMMAND, setup_mp)],
            SETUP_PRESUPUESTO: [
                MessageHandler(solo_dueno & filters.TEXT & ~filters.COMMAND, setup_presupuesto)
            ],
        },
        fallbacks=[CommandHandler("cancelar", cmd_cancelar, filters=solo_dueno)],
    )

    application.add_handler(setup_conv)
    application.add_handler(CommandHandler("start", cmd_start, filters=solo_dueno))
    application.add_handler(CommandHandler("semana", cmd_semana, filters=solo_dueno))
    application.add_handler(CommandHandler("saldo", cmd_saldo, filters=solo_dueno))
    application.add_handler(CommandHandler("ingreso", cmd_ingreso, filters=solo_dueno))
    application.add_handler(CommandHandler("presupuesto", cmd_presupuesto, filters=solo_dueno))
    application.add_handler(CommandHandler("cierre", cmd_cierre, filters=solo_dueno))
    application.add_handler(CallbackQueryHandler(cb_botones))
    application.add_handler(
        MessageHandler(solo_dueno & filters.TEXT & ~filters.COMMAND, on_text_message)
    )
