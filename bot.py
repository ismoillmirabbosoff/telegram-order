#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import re
import io
from datetime import datetime, timedelta
from telegram.error import BadRequest, RetryAfter
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
    CallbackQueryHandler,
)

# ===== CONFIG =====
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8393578554:AAEv33BC7pCE4YO_aoJ0cONx99glxqKZ8Fw")
TARGET_CHAT_ID = int(os.environ.get("TARGET_CHAT_ID", "-1003166932796"))
IMAGE_PATH = "image.jpg"
PDF_PATH = "privacy_policy.pdf"

# ===== logging =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== STATES =====
LANG, PERSON_TYPE, PHONE, NAME, QUANTITY, LOCATION, DELIVERY_DATE, PAYMENT, POLICY = range(9)

# ===== TEXTS (uz/ru/en) =====
TEXTS = {
    "uz": {
        "welcome": "Xush kelibsiz! Iltimos, tilni tanlang:",
        "ask_person": "Iltimos, shaxs turini tanlang:",
        "person_buttons": ["👤 Jismoniy shaxs", "🏢 Yuridik shaxs"],
        "ask_phone": "Telefon raqamingizni yuboring:",
        "ask_name": "Ismingizni kiriting:",
        "ask_quantity": "Nechta suv olmoqchisiz? Eng kamida 2 ta.",
        "ask_location": "Manzilingizni yuboring:",
        "ask_delivery": "Qachon yetkazib berish kerak?",
        "ask_payment": "To‘lov turini tanlang:",
        "thanks": "Rahmat! Buyurtmangiz qabul qilindi ✅",
        "policy": "Iltimos, quyidagi shartnoma bilan tanishing 👇",
        "policy_question": "Shartlarga rozimisiz?",
        "yes": "✅ Ha",
        "no": "❌ Yo‘q",
        "order_button": "📦 Buyurtma berish",
        "continue": "➡️ Davom etish",
        "back": "⬅️ Orqaga",
        "plus": "➕",
        "minus": "➖",
    },
    "ru": {
        "welcome": "Добро пожаловать! Пожалуйста, выберите язык:",
        "ask_person": "Выберите тип клиента:",
        "person_buttons": ["👤 Физическое лицо", "🏢 Юридическое лицо"],
        "ask_phone": "Отправьте свой номер телефона:",
        "ask_name": "Введите ваше имя:",
        "ask_quantity": "Сколько бутылок воды хотите заказать? Минимум 2.",
        "ask_location": "Отправьте вашу локацию:",
        "ask_delivery": "Когда доставить заказ?",
        "ask_payment": "Выберите способ оплаты:",
        "thanks": "Спасибо! Ваш заказ принят ✅",
        "policy": "Ознакомьтесь с условиями ниже 👇",
        "policy_question": "Вы согласны с условиями?",
        "yes": "✅ Да",
        "no": "❌ Нет",
        "order_button": "📦 Сделать заказ",
        "continue": "➡️ Продолжить",
        "back": "⬅️ Назад",
        "plus": "➕",
        "minus": "➖",
    },
    "en": {
        "welcome": "Welcome! Please select your language:",
        "ask_person": "Please select your customer type:",
        "person_buttons": ["👤 Individual", "🏢 Company"],
        "ask_phone": "Please share your phone number:",
        "ask_name": "Enter your name:",
        "ask_quantity": "How many bottles of water do you want? Minimum 2.",
        "ask_location": "Please share your location:",
        "ask_delivery": "When should we deliver your order?",
        "ask_payment": "Choose your payment method:",
        "thanks": "Thank you! Your order has been received ✅",
        "policy": "Please review the policy below 👇",
        "policy_question": "Do you agree with the terms?",
        "yes": "✅ Yes",
        "no": "❌ No",
        "order_button": "📦 Place Order",
        "continue": "➡️ Continue",
        "back": "⬅️ Back",
        "plus": "➕",
        "minus": "➖",
    },
}


# ===== helpers =====
def get_text(user_data, key):
    try:
        lang = user_data.get("lang", "uz")
    except Exception:
        lang = "uz"
    return TEXTS.get(lang, TEXTS["uz"]).get(key, key)


def safe_normalize_phone(text: str):
    if not text:
        return None
    s = re.sub(r"[^\d+]", "", text)
    digits = re.sub(r"\D", "", s)
    return s if len(digits) >= 6 else None


# load static assets (optional)
IMAGE_BYTES = None
PDF_BYTES = None
try:
    with open(IMAGE_PATH, "rb") as f:
        IMAGE_BYTES = f.read()
except Exception:
    logger.info("image.jpg not found; skipping image send.")

try:
    with open(PDF_PATH, "rb") as f:
        PDF_BYTES = f.read()
except Exception:
    logger.info("privacy_policy.pdf not found; skipping PDF send.")


# ===== quantity UI builder (plus/minus + current count + continue) =====
def build_qty_markup(count: int, user_data):
    plus = get_text(user_data, "plus")
    minus = get_text(user_data, "minus")
    cont = get_text(user_data, "continue")
    row1 = [
        InlineKeyboardButton(minus, callback_data="decr"),
        InlineKeyboardButton(str(count), callback_data="count"),
        InlineKeyboardButton(plus, callback_data="incr"),
    ]
    row2 = [InlineKeyboardButton(cont, callback_data="continue_qty")]
    return InlineKeyboardMarkup([row1, row2])


# ===== Handlers =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # reset user data and set default language
    context.user_data.clear()
    context.user_data["_history"] = []
    # show language options (use neutral EN welcome)
    keyboard = [["🇺🇿 Uzbek", "🇷🇺 Russian", "🇬🇧 English"]]
    welcome_text = TEXTS["uz"]["welcome"]
    # support being called from callback_query or message
    if getattr(update, "message", None):
        await update.message.reply_text(welcome_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    else:
        # fallback if called from callback_query
        await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return LANG


async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").lower()
    if "рус" in text or "ru" in text or "russian" in text:
        context.user_data["lang"] = "ru"
    elif "uz" in text or "ўз" in text or "uzbek" in text or "uz" in text:
        context.user_data["lang"] = "uz"
    else:
        context.user_data["lang"] = "en"

    # push history
    history = context.user_data.setdefault("_history", [])
    history.append(LANG)

    # show person type keyboard + back
    buttons = [[b] for b in get_text(context.user_data, "person_buttons")]
    buttons.append([get_text(context.user_data, "back")])
    await update.message.reply_text(get_text(context.user_data, "ask_person"), reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return PERSON_TYPE


async def person_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == get_text(context.user_data, "back"):
        # go back to LANG - simply restart
        return await start(update, context)

    context.user_data.setdefault("_history", []).append(PERSON_TYPE)
    context.user_data["person_type"] = text

    contact_button = KeyboardButton(text="📞 Share Contact", request_contact=True)
    await update.message.reply_text(get_text(context.user_data, "ask_phone"), reply_markup=ReplyKeyboardMarkup([[contact_button], [get_text(context.user_data, "back")]], resize_keyboard=True))
    return PHONE


async def received_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # back pressed
    t = update.message.text or ""
    if t == get_text(context.user_data, "back"):
        return await render_state_from_history(update, context)

    phone = None
    if update.message.contact and getattr(update.message.contact, "phone_number", None):
        phone = update.message.contact.phone_number
    else:
        phone = safe_normalize_phone(update.message.text or "")

    if not phone:
        await update.message.reply_text(get_text(context.user_data, "ask_phone"))
        return PHONE

    context.user_data.setdefault("_history", []).append(PHONE)
    context.user_data["phone"] = phone
    await update.message.reply_text(get_text(context.user_data, "ask_name"), reply_markup=ReplyKeyboardRemove())
    return NAME


async def ask_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # back from NAME via reply keyboard?
    t = update.message.text or ""
    if t == get_text(context.user_data, "back"):
        return await render_state_from_history(update, context)

    # save name
    context.user_data["name"] = (update.message.text or "").strip()
    context.user_data["quantity"] = context.user_data.get("quantity", 2)

    # push history so back works
    context.user_data.setdefault("_history", []).append(NAME)

    # send photo if available
    markup = build_qty_markup(context.user_data["quantity"], context.user_data)
    if IMAGE_BYTES:
        bio = io.BytesIO(IMAGE_BYTES)
        bio.name = "image.jpg"
        await update.message.reply_photo(photo=bio, caption=get_text(context.user_data, "ask_quantity"), reply_markup=markup)
    else:
        await update.message.reply_text(get_text(context.user_data, "ask_quantity"), reply_markup=markup)
    return QUANTITY


async def quantity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # stop spinner quickly

    data = query.data
    qty = context.user_data.get("quantity", 2)

    if data == "incr":
        qty += 1
        context.user_data["quantity"] = qty
    elif data == "decr":
        if qty > 2:
            qty -= 1
            context.user_data["quantity"] = qty
        else:
            qty = 2
            context.user_data["quantity"] = qty
    elif data == "count":
        return QUANTITY
    elif data == "continue_qty":
        qty = context.user_data.get("quantity", 2)
        if qty < 2:
            await query.answer("Please choose at least 2.", show_alert=True)
            return QUANTITY
        context.user_data.setdefault("_history", []).append(QUANTITY)
        loc_button = KeyboardButton("📍 Send Location", request_location=True)
        await query.message.reply_text(get_text(context.user_data, "ask_location"), reply_markup=ReplyKeyboardMarkup([[loc_button], [get_text(context.user_data, "back")]], resize_keyboard=True))
        return LOCATION

    # update markup quickly
    new_markup = build_qty_markup(qty, context.user_data)
    try:
        await query.edit_message_reply_markup(reply_markup=new_markup)
    except BadRequest as e:
        msg = str(e)
        if "Message is not modified" in msg:
            return QUANTITY
        if "Too Many Requests" in msg:
            logger.warning("Rate limited editing markup: %s", msg)
            return QUANTITY
        logger.exception("BadRequest while editing markup: %s", e)
        return QUANTITY
    except RetryAfter as e:
        logger.warning("RetryAfter while editing markup: %s", e)
        return QUANTITY
    except Exception as e:
        logger.exception("Unexpected error editing markup: %s", e)
        return QUANTITY

    return QUANTITY


async def received_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text or ""
    if t == get_text(context.user_data, "back"):
        return await render_state_from_history(update, context)

    if not update.message.location:
        await update.message.reply_text(get_text(context.user_data, "ask_location"))
        return LOCATION

    context.user_data.setdefault("_history", []).append(LOCATION)
    loc = update.message.location
    context.user_data["location"] = {"lat": loc.latitude, "lon": loc.longitude}

    # show delivery date options
    today = datetime.now().date()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 6)]
    buttons = [[InlineKeyboardButton(d, callback_data=f"date_{d}")] for d in dates]
    buttons.append([InlineKeyboardButton(get_text(context.user_data, "back"), callback_data="back_any")])
    await update.message.reply_text(get_text(context.user_data, "ask_delivery"), reply_markup=InlineKeyboardMarkup(buttons))
    return DELIVERY_DATE


async def delivery_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_any":
        return await render_state_from_history(update, context)

    if data.startswith("date_"):
        date = data.split("_", 1)[1]
        context.user_data.setdefault("_history", []).append(DELIVERY_DATE)
        context.user_data["delivery_date"] = date
        buttons = [
            [InlineKeyboardButton("💳 Card", callback_data="card"), InlineKeyboardButton("💵 Cash", callback_data="cash")],
            [InlineKeyboardButton(get_text(context.user_data, "back"), callback_data="back_any")],
        ]
        await query.message.reply_text(get_text(context.user_data, "ask_payment"), reply_markup=InlineKeyboardMarkup(buttons))
        return PAYMENT

    return DELIVERY_DATE


async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back_any":
        return await render_state_from_history(update, context)

    if data in ("card", "cash"):
        context.user_data.setdefault("_history", []).append(PAYMENT)
        context.user_data["payment"] = "Card" if data == "card" else "Cash"

        # send policy
        await query.message.reply_text(get_text(context.user_data, "policy"))
        if PDF_BYTES:
            bio = io.BytesIO(PDF_BYTES)
            bio.name = "privacy_policy.pdf"
            await query.message.reply_document(document=InputFile(bio, filename="privacy_policy.pdf"))
        await query.message.reply_text(get_text(context.user_data, "policy_question"), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(context.user_data, "yes"), callback_data="agree_yes"),
             InlineKeyboardButton(get_text(context.user_data, "no"), callback_data="agree_no")],
            [InlineKeyboardButton(get_text(context.user_data, "back"), callback_data="back_any")],
        ]))
        return POLICY

    return PAYMENT


async def policy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_any":
        return await render_state_from_history(update, context)

    if data == "agree_no":
        await query.message.reply_text("Buyurtma bekor qilindi ❌", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END

    if data == "agree_yes":
        context.user_data.setdefault("_history", []).append(POLICY)
        # show final order button
        await query.message.reply_text("✅ Barcha ma’lumotlar tayyor.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(context.user_data, "order_button"), callback_data="place_order")]]))
        return POLICY

    if data == "place_order":
        ud = context.user_data
        text = (
            f"📦 Yangi buyurtma\n\n"
            f"👤 Ism: {ud.get('name')}\n"
            f"📞 Telefon: {ud.get('phone')}\n"
            f"🏷 Shaxs turi: {ud.get('person_type')}\n"
            f"💧 Miqdor: {ud.get('quantity')}\n"
            f"📅 Yetkazib berish: {ud.get('delivery_date')}\n"
            f"💰 To‘lov: {ud.get('payment')}\n"
            f"🌍 Manzil: https://maps.google.com/?q={ud['location']['lat']},{ud['location']['lon']}"
        )
        # send order to target chat
        await context.bot.send_message(chat_id=TARGET_CHAT_ID, text=text)
        # notify user
        await query.message.reply_text(get_text(context.user_data, "thanks"), reply_markup=ReplyKeyboardRemove())
        # clear user data, history
        context.user_data.clear()
        # automatically go to start (language choose)
        # call start with same update so user sees language keyboard
        return await start(update, context)

    return POLICY


# ===== simple history renderer =====
async def render_state_from_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hist = context.user_data.get("_history", [])
    if not hist:
        return await start(update, context)
    prev_state = hist.pop()
    context.user_data["_history"] = hist

    target = update.message if update.message else update.callback_query.message

    if prev_state == LANG:
        kb = [["🇺🇿 Uzbek", "🇷🇺 Russian", "🇬🇧 English"]]
        await target.reply_text(TEXTS["en"]["welcome"], reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return LANG

    if prev_state == PERSON_TYPE:
        buttons = [[b] for b in get_text(context.user_data, "person_buttons")]
        buttons.append([get_text(context.user_data, "back")])
        await target.reply_text(get_text(context.user_data, "ask_person"), reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return PERSON_TYPE

    if prev_state == PHONE:
        contact_button = KeyboardButton(text="📞 Share Contact", request_contact=True)
        await target.reply_text(get_text(context.user_data, "ask_phone"), reply_markup=ReplyKeyboardMarkup([[contact_button], [get_text(context.user_data, "back")]], resize_keyboard=True))
        return PHONE

    if prev_state == NAME:
        await target.reply_text(get_text(context.user_data, "ask_name"), reply_markup=ReplyKeyboardRemove())
        return NAME

    if prev_state == QUANTITY:
        cnt = context.user_data.get("quantity", 2)
        markup = build_qty_markup(cnt, context.user_data)
        if IMAGE_BYTES:
            bio = io.BytesIO(IMAGE_BYTES)
            bio.name = "image.jpg"
            await target.reply_photo(photo=bio, caption=get_text(context.user_data, "ask_quantity"), reply_markup=markup)
        else:
            await target.reply_text(get_text(context.user_data, "ask_quantity"), reply_markup=markup)
        return QUANTITY

    if prev_state == LOCATION:
        loc_button = KeyboardButton("📍 Send Location", request_location=True)
        await target.reply_text(get_text(context.user_data, "ask_location"), reply_markup=ReplyKeyboardMarkup([[loc_button], [get_text(context.user_data, "back")]], resize_keyboard=True))
        return LOCATION

    if prev_state == DELIVERY_DATE:
        today = datetime.now().date()
        dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 6)]
        buttons = [[InlineKeyboardButton(d, callback_data=f"date_{d}")] for d in dates]
        buttons.append([InlineKeyboardButton(get_text(context.user_data, "back"), callback_data="back_any")])
        await target.reply_text(get_text(context.user_data, "ask_delivery"), reply_markup=InlineKeyboardMarkup(buttons))
        return DELIVERY_DATE

    if prev_state == PAYMENT:
        buttons = [
            [InlineKeyboardButton("💳 Card", callback_data="card"), InlineKeyboardButton("💵 Cash", callback_data="cash")],
            [InlineKeyboardButton(get_text(context.user_data, "back"), callback_data="back_any")],
        ]
        await target.reply_text(get_text(context.user_data, "ask_payment"), reply_markup=InlineKeyboardMarkup(buttons))
        return PAYMENT

    if prev_state == POLICY:
        await target.reply_text(get_text(context.user_data, "policy"))
        if PDF_BYTES:
            bio = io.BytesIO(PDF_BYTES)
            bio.name = "privacy_policy.pdf"
            await target.reply_document(document=InputFile(bio, filename="privacy_policy.pdf"))
        await target.reply_text(get_text(context.user_data, "policy_question"), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(context.user_data, "yes"), callback_data="agree_yes"),
             InlineKeyboardButton(get_text(context.user_data, "no"), callback_data="agree_no")],
            [InlineKeyboardButton(get_text(context.user_data, "back"), callback_data="back_any")],
        ]))
        return POLICY

    return await start(update, context)


# ===== MAIN =====
def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise SystemExit("Please set BOT_TOKEN environment variable.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, lang_chosen)],
            PERSON_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, person_chosen)],
            PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), received_phone)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_quantity)],
            QUANTITY: [CallbackQueryHandler(quantity_handler, pattern=r"^(incr|decr|count|continue_qty)$")],
            LOCATION: [MessageHandler(filters.LOCATION | (filters.TEXT & ~filters.COMMAND), received_location)],
            DELIVERY_DATE: [CallbackQueryHandler(delivery_handler, pattern=r"^date_.*|back_any$")],
            PAYMENT: [CallbackQueryHandler(payment_handler, pattern=r"^(card|cash|back_any)$")],
            POLICY: [CallbackQueryHandler(policy_handler, pattern=r"^(agree_yes|agree_no|place_order|back_any)$")],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)
    # generic back handler for inline "back_any"
    app.add_handler(CallbackQueryHandler(lambda u, c: render_state_from_history(u, c), pattern=r"^back_any$"))

    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
