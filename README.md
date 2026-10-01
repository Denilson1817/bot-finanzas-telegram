# Bot de Telegram — Finanzas personales

Bot personal (un solo usuario) para registrar gastos e ingresos en segundos,
llevar el presupuesto semanal ("caja"), el ahorro para el enganche de un auto
y, en fases siguientes, las deudas de tarjetas de crédito.

Ver `bot-finanzas-telegram-contexto.md` (carpeta padre) para el detalle
completo de las reglas de negocio.

## Estado actual: Fase 1 (MVP) + Fase 2 (tarjetas y pagos)

Implementado:
- Captura rápida de gastos por mensaje libre (`66 pollo`).
- `/setup` — configuración inicial guiada (saldo de banco, deuda de cada
  tarjeta, presupuesto de la caja semanal).
- `/semana` — resumen de la semana actual por color.
- `/saldo` — saldo en banco, caja de la semana y ahorro acumulado.
- `/ingreso` — registrar ingresos y reembolsos.
- `/presupuesto` — ajustar el presupuesto de la caja de la semana actual.
- `/cierre` — cerrar la semana, enviar el sobrante a ahorro y abrir la
  siguiente.
- Botones inline para deshacer el último registro o cambiar su color
  (obligatorio ↔ extra).
- `/deudas` — saldo de cada tarjeta y su próximo pago conocido.
- `/pagar <nu|mp> <monto>` — registrar el pago de una tarjeta (baja el
  banco y la deuda; marca el pago programado correspondiente).
- `/proximos` — pagos de tarjeta programados en los próximos 14 días.
- Recordatorios automáticos diarios (9am): un día antes de cada pago de
  tarjeta, el mismo día del pago, y los viernes para no olvidar `/cierre`.
- `seed_cargos.py` — siembra el calendario de pagos de tarjeta ya conocido
  (los montos de `bot-finanzas-telegram-contexto.md` §2) para que
  `/deudas`, `/proximos` y los recordatorios funcionen sin captura manual.

Pendiente (fases siguientes, ver `bot-finanzas-telegram-contexto.md` §8):
- Cargos programados y recordatorios para los pagos fijos mensuales
  (renta, luz, tv, spotify) — por ahora `/proximos` solo cubre tarjetas.
- `/meta` con proyección hacia la compra del auto, comparativas entre
  semanas, export a Excel/CSV (Fase 3).
- Despliegue 24/7 (Fase 4).

## Requisitos

- Python 3.11+
- Una cuenta de Telegram

## 1. Crear el bot con @BotFather

1. Abre Telegram y busca **@BotFather**.
2. Envía `/newbot` y sigue las instrucciones (nombre y username del bot).
3. BotFather te dará un **token** con este formato:
   `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`. Ese es tu `TELEGRAM_BOT_TOKEN`.

## 2. Obtener tu user ID de Telegram

1. Busca **@userinfobot** en Telegram y envíale cualquier mensaje.
2. Te responderá con tu `Id` numérico. Ese es tu `ALLOWED_USER_ID`.
3. El bot ignora cualquier mensaje que no venga de este ID, así que solo tú
   podrás usarlo aunque el bot sea público.

## 3. Instalación

```bash
cd bot-finanzas-telegram
python3 -m venv .venv
source .venv/bin/activate      # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edita `.env` con tu token y tu user ID:

```
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
ALLOWED_USER_ID=987654321
DB_URL=sqlite:///finanzas.db
```

## 4. Correr el bot

```bash
python -m app.main
```

El bot corre en modo *polling*: mientras este proceso siga corriendo,
responde a tus mensajes en Telegram. La base de datos SQLite
(`finanzas.db`) se crea sola en la primera ejecución.

La primera vez, en Telegram, envía `/setup` y sigue los pasos para capturar
tu saldo real de banco y de cada tarjeta.

Después de eso, corre una sola vez (con el bot detenido o corriendo, es
independiente):

```bash
python seed_cargos.py
```

Esto carga el calendario de pagos de tarjeta ya conocido en la base de
datos. Es idempotente: puedes volver a correrlo si actualizas los montos
en `seed_cargos.py` sin duplicar lo que ya existía.

## 5. Correr las pruebas

```bash
pytest
```

## Uso rápido

- Registrar un gasto: `66 pollo` (obligatorio, débito).
- Sufijos opcionales al final (se pueden combinar): `r` = extra,
  `nu` / `mp` = pagado con crédito Nu / Mercado Pago, `ef` = efectivo.
  Ej: `380 flores r`, `319 pizza nu`, `200 gasolina r nu`.
- `/ingreso 7934 sueldo` — registrar un ingreso.
- `/ingreso 40 reembolso spotify` — registrar un reembolso (no cuenta como
  sueldo).
- `/semana`, `/saldo`, `/presupuesto <monto>`, `/cierre`.
- `/deudas`, `/pagar nu 800`, `/proximos`.
