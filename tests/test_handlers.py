import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.bot import handlers as h


class FakeApplication:
    def __init__(self, bot_data):
        self.bot_data = bot_data


def make_context(session_factory, args=None, user_data=None, allowed_user_id=1):
    application = FakeApplication(
        {"Session": session_factory, "allowed_user_id": allowed_user_id}
    )
    return SimpleNamespace(
        application=application,
        args=args or [],
        user_data=user_data if user_data is not None else {},
    )


def make_message_update(text, user_id=1, fecha=None):
    message = SimpleNamespace(
        text=text, date=fecha or datetime.now(timezone.utc), reply_text=AsyncMock()
    )
    return SimpleNamespace(
        message=message, effective_user=SimpleNamespace(id=user_id), callback_query=None
    )


def make_callback_update(data, user_id=1):
    query = SimpleNamespace(data=data, answer=AsyncMock(), edit_message_text=AsyncMock())
    return SimpleNamespace(
        message=None, callback_query=query, effective_user=SimpleNamespace(id=user_id)
    )


def run(coro):
    return asyncio.run(coro)


def test_captura_rapida_coincide_con_el_ejemplo_del_documento(session_factory):
    # Presupuesto por defecto $1,250; "66 pollo" es débito/obligatorio ->
    # la caja debe quedar en $1,250 - $66 = $1,184.
    ctx = make_context(session_factory)
    update = make_message_update("66 pollo")

    run(h.on_text_message(update, ctx))

    texto = update.message.reply_text.call_args[0][0]
    assert "pollo" in texto
    assert "$66" in texto
    assert "🟢" in texto
    assert "$1,184 restantes" in texto
    reply_markup = update.message.reply_text.call_args.kwargs["reply_markup"]
    assert reply_markup.inline_keyboard[0][0].callback_data.startswith("deshacer:")
    assert reply_markup.inline_keyboard[0][1].callback_data.startswith("toggle:")


def test_captura_usa_la_fecha_real_del_mensaje_no_la_de_procesamiento(session_factory):
    """Si el bot estuvo apagado y Telegram entrega el mensaje atrasado, el
    gasto debe quedar fechado el día en que se escribió, no el día en que el
    bot finalmente lo procesó."""
    from app.models import Movimiento

    fecha_envio = datetime(2026, 9, 20, 14, 30, tzinfo=timezone.utc)
    ctx = make_context(session_factory)
    update = make_message_update("66 pollo", fecha=fecha_envio)

    run(h.on_text_message(update, ctx))

    with session_factory() as session:
        mov = session.query(Movimiento).one()
        assert mov.fecha == fecha_envio.astimezone(h.TZ).date()


def test_captura_con_credito_no_descuenta_la_caja(session_factory):
    ctx = make_context(session_factory)
    update = make_message_update("319 pizza cena nu")

    run(h.on_text_message(update, ctx))

    texto = update.message.reply_text.call_args[0][0]
    assert "$319" in texto
    assert "🟠" in texto
    assert "no afecta tu caja" in texto


def test_flujo_ingreso_gasto_saldo_y_cierre(session_factory):
    ctx = make_context(session_factory, args=["7934", "sueldo"])
    ingreso_upd = make_message_update("/ingreso 7934 sueldo")
    run(h.cmd_ingreso(ingreso_upd, ctx))
    assert "$7,934" in ingreso_upd.message.reply_text.call_args[0][0]

    gasto_upd = make_message_update("66 pollo")
    run(h.on_text_message(gasto_upd, make_context(session_factory)))

    saldo_upd = make_message_update("/saldo")
    run(h.cmd_saldo(saldo_upd, make_context(session_factory)))
    texto_saldo = saldo_upd.message.reply_text.call_args[0][0]
    assert "🏦 Banco: $7,868" in texto_saldo
    assert "📦 Caja de esta semana: $1,184" in texto_saldo

    cierre_upd = make_message_update("/cierre")
    ctx_cierre = make_context(session_factory)
    run(h.cmd_cierre(cierre_upd, ctx_cierre))
    texto_cierre = cierre_upd.message.reply_text.call_args[0][0]
    assert "Cierre de semana" in texto_cierre
    reply_markup = cierre_upd.message.reply_text.call_args.kwargs["reply_markup"]
    callback_sobrante = reply_markup.inline_keyboard[0][0].callback_data
    assert callback_sobrante == "cierre:1:118400"

    cb_upd = make_callback_update(callback_sobrante)
    run(h.cb_botones(cb_upd, make_context(session_factory)))
    texto_cb = cb_upd.callback_query.edit_message_text.call_args[0][0]
    assert "Semana cerrada" in texto_cb
    assert "Ahorro enviado: $1,184" in texto_cb

    saldo_final_upd = make_message_update("/saldo")
    run(h.cmd_saldo(saldo_final_upd, make_context(session_factory)))
    texto_saldo_final = saldo_final_upd.message.reply_text.call_args[0][0]
    assert "🚗 Ahorro enganche: $1,184" in texto_saldo_final
    assert "📦 Caja de esta semana: $1,250" in texto_saldo_final


def test_boton_deshacer(session_factory):
    ctx = make_context(session_factory)
    update = make_message_update("66 pollo")
    run(h.on_text_message(update, ctx))
    reply_markup = update.message.reply_text.call_args.kwargs["reply_markup"]
    deshacer_cb = reply_markup.inline_keyboard[0][0].callback_data

    cb_upd = make_callback_update(deshacer_cb)
    run(h.cb_botones(cb_upd, make_context(session_factory)))
    texto = cb_upd.callback_query.edit_message_text.call_args[0][0]
    assert "Deshecho" in texto
    assert "pollo" in texto


def test_boton_cambiar_color(session_factory):
    ctx = make_context(session_factory)
    update = make_message_update("66 pollo")
    run(h.on_text_message(update, ctx))
    reply_markup = update.message.reply_text.call_args.kwargs["reply_markup"]
    toggle_cb = reply_markup.inline_keyboard[0][1].callback_data

    cb_upd = make_callback_update(toggle_cb)
    run(h.cb_botones(cb_upd, make_context(session_factory)))
    texto = cb_upd.callback_query.edit_message_text.call_args[0][0]
    assert "🔴" in texto


def test_setup_flujo_completo_guarda_saldos_reales(session_factory):
    ctx = make_context(session_factory)
    run(h.cmd_setup_start(make_message_update("/setup"), ctx))
    run(h.setup_banco(make_message_update("27604"), ctx))
    run(h.setup_nu(make_message_update("1707"), ctx))
    run(h.setup_mp(make_message_update("0"), ctx))
    final_upd = make_message_update("1250")
    run(h.setup_presupuesto(final_upd, ctx))

    texto = final_upd.message.reply_text.call_args[0][0]
    assert "$27,604" in texto
    assert "$1,707" in texto
    assert "$1,250" in texto
    assert ctx.user_data == {}

    from app.models import Tarjeta
    from app.services.saldos import saldo_banco

    with session_factory() as session:
        nu = session.query(Tarjeta).filter(Tarjeta.nombre == "nu").one()
        mp = session.query(Tarjeta).filter(Tarjeta.nombre == "mp").one()
        assert nu.saldo_inicial_centavos == 170_700
        assert mp.saldo_inicial_centavos == 0
        assert saldo_banco(session) == 2_760_400

    saldo_upd = make_message_update("/saldo")
    run(h.cmd_saldo(saldo_upd, make_context(session_factory)))
    texto_saldo = saldo_upd.message.reply_text.call_args[0][0]
    assert "🏦 Banco: $27,604" in texto_saldo
    assert "📦 Caja de esta semana: $1,250" in texto_saldo


def test_usuario_no_autorizado_es_ignorado_en_botones(session_factory):
    ctx = make_context(session_factory)
    update = make_message_update("66 pollo")
    run(h.on_text_message(update, ctx))
    reply_markup = update.message.reply_text.call_args.kwargs["reply_markup"]
    deshacer_cb = reply_markup.inline_keyboard[0][0].callback_data

    cb_upd = make_callback_update(deshacer_cb, user_id=999)
    run(h.cb_botones(cb_upd, make_context(session_factory)))
    cb_upd.callback_query.edit_message_text.assert_not_awaited()
    cb_upd.callback_query.answer.assert_awaited_once()
