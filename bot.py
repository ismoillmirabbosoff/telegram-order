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
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8367165107:AAFmfC0gKHZiBjbO_-SDPCOtroypIy3fUKc")
TARGET_CHAT_ID = int(os.environ.get("TARGET_CHAT_ID", "-1003166932796"))
IMAGE_PATH = "image.jpg"  # put product image / logo here if available
PDF_PATH = "privacy_policy.pdf"  # not used but kept

# price per bottle (currency: UZS)
PRICE_PER_BOTTLE = 7000
CURRENCY = "UZS"

# ===== logging =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== STATES =====
LANG, PERSON_TYPE, PHONE, NAME, QUANTITY, COMMENT, COMMENT_INPUT, LOCATION, DELIVERY_DATE, PAYMENT = range(10)

# ===== TEXTS (uz/ru/en) =====
TEXTS = {
    "uz": {
        "welcome": "Xush kelibsiz! Iltimos, tilni tanlang:",
        "ask_person": "Iltimos, shaxs turini tanlang:",
        "person_buttons": ["👤 Jismoniy shaxs", "🏢 Yuridik shaxs"],
        "ask_phone": "Kontaktni ulashing (telefon):",
        "ask_name": "Ismingizni kiriting:",
        "ask_quantity": "Nechta suv olmoqchisiz? (Eng kam 2 ta)",
        "ask_location": "Manzilingizni yuboring:",
        "ask_delivery": "Qachon yetkazib berish kerak? (sana tanlang)",
        "ask_payment": "To‘lov turini tanlang:",
        "thanks": "Rahmat! Buyurtmangiz qabul qilindi ✅",
        "order_button": "📦 Buyurtma berish",
        "continue": "➡️ Davom etish",
        "back": "⬅️ Orqaga",
        "plus": "➕",
        "minus": "➖",
        "yes": "✅ Ha",
        "no": "❌ Yo'q",
        "card": "💳 Kartada",
        "cash": "💵 Naqd",
        "ask_comment_question": "Buyurtmaga izoh qo'shasizmi?",
        "ask_comment": "Iltimos, izohni kiriting:",
        "price_line": "Narx: {unit} {currency} / dona — Jami: {total} {currency}",
        "home": "🏠 Bosh sahifa",
        "share_contact": "📞 Kontaktni ulashish",
    },
    "ru": {
        "welcome": "Добро пожаловать! Пожалуйста, выберите язык:",
        "ask_person": "Выберите тип клиента:",
        "person_buttons": ["👤 Физическое лицо", "🏢 Юридическое лицо"],
        "ask_phone": "Поделитесь контактом (номер телефона):",
        "ask_name": "Введите ваше имя:",
        "ask_quantity": "Сколько бутылок воды хотите заказать? (Минимум 2)",
        "ask_location": "Отправьте вашу локацию:",
        "ask_delivery": "Когда доставить заказ? (выберите дату)",
        "ask_payment": "Выберите способ оплаты:",
        "thanks": "Спасибо! Ваш заказ принят ✅",
        "order_button": "📦 Сделать заказ",
        "continue": "➡️ Продолжить",
        "back": "⬅️ Назад",
        "plus": "➕",
        "minus": "➖",
        "yes": "✅ Да",
        "no": "❌ Нет",
        "card": "💳 Карта",
        "cash": "💵 Наличными",
        "ask_comment_question": "Добавите ли вы комментарий к заказу?",
        "ask_comment": "Пожалуйста, введите комментарий:",
        "price_line": "Цена: {unit} {currency} / шт — Итого: {total} {currency}",
        "home": "🏠 Главная",
        "share_contact": "📞 Поделиться контактом",
    },
    "en": {
        "welcome": "Welcome! Please select your language:",
        "ask_person": "Please select your customer type:",
        "person_buttons": ["👤 Individual", "🏢 Company"],
        "ask_phone": "Please share your contact (phone):",
        "ask_name": "Enter your name:",
        "ask_quantity": "How many bottles of water do you want? (Minimum 2)",
        "ask_location": "Please share your location:",
        "ask_delivery": "When should we deliver? (choose a date)",
        "ask_payment": "Choose your payment method:",
        "thanks": "Thank you! Your order has been received ✅",
        "order_button": "📦 Place Order",
        "continue": "➡️ Continue",
        "back": "⬅️ Back",
        "plus": "➕",
        "minus": "➖",
        "yes": "✅ Yes",
        "no": "❌ No",
        "card": "💳 Card",
        "cash": "💵 Cash",
        "ask_comment_question": "Would you like to add a comment to the order?",
        "ask_comment": "Please enter the comment:",
        "price_line": "Price: {unit} {currency} / pc — Total: {total} {currency}",
        "home": "🏠 Home",
        "share_contact": "📞 Share Contact",
    },
}


# ===== helpers =====
def get_text_for_lang(lang: str, key: str) -> str:
    return TEXTS.get(lang, TEXTS["uz"]).get(key, key)


def get_text(user_data: dict, key: str) -> str:
    lang = user_data.get("lang", "uz") if isinstance(user_data, dict) else "uz"
    return get_text_for_lang(lang, key)


def safe_normalize_phone(text: str):
    if not text:
        return None
    s = re.sub(r"[^\d+]", "", text)
    digits = re.sub(r"\D", "", s)
    return s if len(digits) >= 6 else None


def is_home_text(text: str) -> bool:
    """Check if the provided text matches any localized 'home' label."""
    if not text:
        return False
    t = text.strip()
    for lang in TEXTS:
        if TEXTS[lang].get("home") == t:
            return True
    return False


# load static assets (optional)
IMAGE_BYTES = None
try:
    with open(IMAGE_PATH, "rb") as f:
        IMAGE_BYTES = f.read()
except Exception:
    logger.info("image not found; continuing without image")


# ===== price caption builder =====
def build_price_caption(qty: int, lang: str) -> str:
    txt = get_text_for_lang(lang, "price_line")
    total = PRICE_PER_BOTTLE * qty
    return txt.format(unit=PRICE_PER_BOTTLE, total=total, currency=CURRENCY)


# ===== quantity UI builder (plus/minus + current count + continue) =====
def build_qty_markup(count: int, lang: str):
    plus = get_text_for_lang(lang, "plus")
    minus = get_text_for_lang(lang, "minus")
    cont = get_text_for_lang(lang, "continue")
    row1 = [
        InlineKeyboardButton(minus, callback_data="decr"),
        InlineKeyboardButton(str(count), callback_data="count"),
        InlineKeyboardButton(plus, callback_data="incr"),
    ]
    row2 = [InlineKeyboardButton(cont, callback_data="continue_qty")]
    return InlineKeyboardMarkup([row1, row2])


# ===== Handlers =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show product image (if available) and language keyboard. Start fresh."""
    # reset user_data for fresh flow
    context.user_data.clear()
    context.user_data.setdefault("_history", [])

    # send image first so user sees product
    if IMAGE_BYTES:
        bio = io.BytesIO(IMAGE_BYTES)
        bio.name = "image.jpg"
        if getattr(update, "message", None):
            await update.message.reply_photo(photo=bio)
        else:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=bio)

    # language buttons row only (reply keyboard)
    lang_row = ["🇺🇿 Uzbek", "🇷🇺 Russian", "🇬🇧 English"]
    keyboard = [lang_row]
    if getattr(update, "message", None):
        await update.message.reply_text(TEXTS["uz"]["welcome"], reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=TEXTS["uz"]["welcome"], reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return LANG


async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    # If user pressed Home (reply keyboard) — detect across languages
    if is_home_text(text):
        # restart fresh
        return await start(update, context)

    # language detection
    low = text.lower()
    if "рус" in low or "ru" in low or "russian" in low or "рос" in low:
        context.user_data["lang"] = "ru"
    elif "uz" in low or "ўз" in low or "uzbek" in low or "uz" in low:
        context.user_data["lang"] = "uz"
    else:
        context.user_data["lang"] = "en"

    # push history
    history = context.user_data.setdefault("_history", [])
    history.append(LANG)

    # show person type keyboard + back always at bottom
    buttons = [[b] for b in get_text(context.user_data, "person_buttons")]
    buttons.append([get_text(context.user_data, "back")])
    await update.message.reply_text(get_text(context.user_data, "ask_person"), reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return PERSON_TYPE


async def person_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == get_text(context.user_data, "back"):
        return await render_state_from_history(update, context)

    context.user_data.setdefault("_history", []).append(PERSON_TYPE)
    context.user_data["person_type"] = text

    # localized share contact button + back
    contact_button = KeyboardButton(text=get_text(context.user_data, "share_contact"), request_contact=True)
    keyboard = [[contact_button], [get_text(context.user_data, "back")]]
    await update.message.reply_text(get_text(context.user_data, "ask_phone"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return PHONE


async def received_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    # ask name (remove reply keyboard)
    await update.message.reply_text(get_text(context.user_data, "ask_name"), reply_markup=ReplyKeyboardRemove())
    return NAME


async def received_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text or ""
    if t == get_text(context.user_data, "back"):
        return await render_state_from_history(update, context)

    context.user_data.setdefault("_history", []).append(NAME)
    context.user_data["name"] = (update.message.text or "").strip()
    context.user_data["quantity"] = context.user_data.get("quantity", 2)

    # now show product image with quantity selector + price caption
    qty = context.user_data["quantity"]
    price_caption = build_price_caption(qty, context.user_data["lang"])
    markup = build_qty_markup(qty, context.user_data["lang"])
    prompt = f"{get_text(context.user_data, 'ask_quantity')}\n\n{price_caption}"

    if IMAGE_BYTES:
        bio = io.BytesIO(IMAGE_BYTES)
        bio.name = "image.jpg"
        await update.message.reply_photo(photo=bio, caption=prompt, reply_markup=markup)
    else:
        await update.message.reply_text(prompt, reply_markup=markup)

    return QUANTITY


async def quantity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

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
        # ask comment question (inline)
        await query.message.reply_text(get_text(context.user_data, "ask_comment_question"), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(context.user_data, "yes"), callback_data="comment_yes"),
             InlineKeyboardButton(get_text(context.user_data, "no"), callback_data="comment_no")],
            [InlineKeyboardButton(get_text(context.user_data, "back"), callback_data="back_any")],
        ]))
        return COMMENT

    # update UI (caption + markup)
    new_markup = build_qty_markup(qty, context.user_data["lang"])
    price_caption = build_price_caption(qty, context.user_data["lang"])
    try:
        if query.message.photo:
            await query.edit_message_caption(caption=f"{get_text(context.user_data, 'ask_quantity')}\n\n{price_caption}", reply_markup=new_markup)
        else:
            await query.edit_message_text(text=f"{get_text(context.user_data, 'ask_quantity')}\n\n{price_caption}", reply_markup=new_markup)
    except BadRequest as e:
        if "Message is not modified" in str(e):
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


async def comment_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_any":
        return await render_state_from_history(update, context)

    if data == "comment_no":
        # go to location
        context.user_data.setdefault("_history", []).append(COMMENT)
        loc_button = KeyboardButton("📍 Send Location", request_location=True)
        await query.message.reply_text(get_text(context.user_data, "ask_location"), reply_markup=ReplyKeyboardMarkup([[loc_button], [get_text(context.user_data, "back")]], resize_keyboard=True))
        return LOCATION

    if data == "comment_yes":
        context.user_data.setdefault("_history", []).append(COMMENT)
        await query.message.reply_text(get_text(context.user_data, "ask_comment"), reply_markup=ReplyKeyboardRemove())
        return COMMENT_INPUT

    return COMMENT


async def comment_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text or ""
    if t == get_text(context.user_data, "back"):
        return await render_state_from_history(update, context)

    context.user_data.setdefault("_history", []).append(COMMENT_INPUT)
    context.user_data["comment"] = (update.message.text or "").strip()

    loc_button = KeyboardButton("📍 Send Location", request_location=True)
    await update.message.reply_text(get_text(context.user_data, "ask_location"), reply_markup=ReplyKeyboardMarkup([[loc_button], [get_text(context.user_data, "back")]], resize_keyboard=True))
    return LOCATION


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

    # delivery date options: tomorrow .. tomorrow+4 (5 days)
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

        # show payment choice localized
        buttons = [
            [InlineKeyboardButton(get_text(context.user_data, "card"), callback_data="card"),
             InlineKeyboardButton(get_text(context.user_data, "cash"), callback_data="cash")],
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
        context.user_data["payment"] = get_text(context.user_data, "card") if data == "card" else get_text(context.user_data, "cash")

        # show final place order inline button
        await query.message.reply_text(get_text(context.user_data, "order_button"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(context.user_data, "order_button"), callback_data="place_order")]]))
        return PAYMENT

    return PAYMENT


from telegram import KeyboardButton  # agar yuqorida import qilinmagan bo'lsa

async def final_place_order_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    When user presses 'place_order' inline button:
    - send order to TARGET_CHAT_ID
    - notify user with thank-you
    - then show a reply keyboard with a single "/start" button so that when user
      presses it Telegram automatically sends /start and your CommandHandler will run.
    - Return LANG so ConversationHandler stays active (optional), but /start will re-trigger start().
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_any":
        return await render_state_from_history(update, context)

    if data == "place_order":
        ud = context.user_data
        qty = ud.get("quantity", 0)
        total = PRICE_PER_BOTTLE * qty

        # build order text
        text = (
            f"📦 Yangi buyurtma\n\n"
            f"👤 Ism: {ud.get('name')}\n"
            f"📞 Telefon: {ud.get('phone')}\n"
            f"🏷 Shaxs turi: {ud.get('person_type')}\n"
            f"💧 Miqdor: {qty}\n"
            f"🧾 Jami summa: {total} {CURRENCY}\n"
            f"📅 Yetkazib berish: {ud.get('delivery_date')}\n"
            f"💰 To‘lov: {ud.get('payment')}\n"
        )
        if ud.get("comment"):
            text += f"📝 Izoh: {ud.get('comment')}\n"
        if ud.get("location"):
            text += f"🌍 Manzil: https://maps.google.com/?q={ud['location']['lat']},{ud['location']['lon']}\n"

        # send order to target chat
        try:
            await context.bot.send_message(chat_id=TARGET_CHAT_ID, text=text)
        except Exception:
            logger.exception("Failed to send order to target chat")

        # notify user with localized thanks
        try:
            await query.message.reply_text(get_text(context.user_data, "thanks"))
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=get_text(context.user_data, "thanks"))

        # --- prepare reply keyboard that will automatically send /start when pressed ---
        # Use a single button that contains "/start" so Telegram sends the command automatically.
        start_button = KeyboardButton("/start")
        reply_kb = ReplyKeyboardMarkup([[start_button]], resize_keyboard=True)

        # Optionally keep language stored or clear data; here we clear to ensure fresh start.
        context.user_data.clear()
        context.user_data.setdefault("_history", [])

        # send the keyboard with /start button
        await context.bot.send_message(chat_id=update.effective_chat.id, text="🏠 " + "Back to start — press the button below", reply_markup=reply_kb)

        # returning LANG is optional because /start will trigger start() via CommandHandler.
        # But returning LANG keeps ConversationHandler active; still /start will re-run start handler.
        return LANG

    return PAYMENT


# ===== simple history renderer (Back) =====
async def render_state_from_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hist = context.user_data.get("_history", [])
    if not hist:
        return await start(update, context)
    prev_state = hist.pop()
    context.user_data["_history"] = hist

    target = update.message if update.message else update.callback_query.message

    if prev_state == LANG:
        kb = [["🇺🇿 Uzbek", "🇷🇺 Russian", "🇬🇧 English"]]
        await target.reply_text(TEXTS["uz"]["welcome"], reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return LANG

    if prev_state == PERSON_TYPE:
        buttons = [[b] for b in get_text(context.user_data, "person_buttons")]
        buttons.append([get_text(context.user_data, "back")])
        await target.reply_text(get_text(context.user_data, "ask_person"), reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return PERSON_TYPE

    if prev_state == PHONE:
        contact_button = KeyboardButton(text=get_text(context.user_data, "share_contact"), request_contact=True)
        await target.reply_text(get_text(context.user_data, "ask_phone"), reply_markup=ReplyKeyboardMarkup([[contact_button], [get_text(context.user_data, "back")]], resize_keyboard=True))
        return PHONE

    if prev_state == NAME:
        await target.reply_text(get_text(context.user_data, "ask_name"), reply_markup=ReplyKeyboardRemove())
        return NAME

    if prev_state == QUANTITY:
        cnt = context.user_data.get("quantity", 2)
        markup = build_qty_markup(cnt, context.user_data["lang"])
        price_caption = build_price_caption(cnt, context.user_data["lang"])
        if IMAGE_BYTES:
            bio = io.BytesIO(IMAGE_BYTES)
            bio.name = "image.jpg"
            await target.reply_photo(photo=bio, caption=f"{get_text(context.user_data, 'ask_quantity')}\n\n{price_caption}", reply_markup=markup)
        else:
            await target.reply_text(f"{get_text(context.user_data, 'ask_quantity')}\n\n{price_caption}", reply_markup=markup)
        return QUANTITY

    if prev_state == COMMENT or prev_state == COMMENT_INPUT:
        await target.reply_text(get_text(context.user_data, "ask_comment_question"), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(context.user_data, "yes"), callback_data="comment_yes"), InlineKeyboardButton(get_text(context.user_data, "no"), callback_data="comment_no")],
            [InlineKeyboardButton(get_text(context.user_data, "back"), callback_data="back_any")],
        ]))
        return COMMENT

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
            [InlineKeyboardButton(get_text(context.user_data, "card"), callback_data="card"), InlineKeyboardButton(get_text(context.user_data, "cash"), callback_data="cash")],
            [InlineKeyboardButton(get_text(context.user_data, "back"), callback_data="back_any")],
        ]
        await target.reply_text(get_text(context.user_data, "ask_payment"), reply_markup=InlineKeyboardMarkup(buttons))
        return PAYMENT

    return await start(update, context)


# ===== MAIN =====
def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
        raise SystemExit("Please set BOT_TOKEN environment variable.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, lang_chosen)],
            PERSON_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, person_chosen)],
            PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), received_phone)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_name)],
            QUANTITY: [CallbackQueryHandler(quantity_handler, pattern=r"^(incr|decr|count|continue_qty)$")],
            COMMENT: [CallbackQueryHandler(comment_choice_handler, pattern=r"^(comment_yes|comment_no|back_any)$")],
            COMMENT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, comment_input_handler)],
            LOCATION: [MessageHandler(filters.LOCATION | (filters.TEXT & ~filters.COMMAND), received_location)],
            DELIVERY_DATE: [CallbackQueryHandler(delivery_handler, pattern=r"^date_.*|back_any$")],
            PAYMENT: [CallbackQueryHandler(payment_handler, pattern=r"^(card|cash|back_any)$")],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    # final place order handler (inline)
    app.add_handler(CallbackQueryHandler(final_place_order_handler, pattern=r"^place_order$"))
    # generic back handler for inline "back_any"
    app.add_handler(CallbackQueryHandler(lambda u, c: render_state_from_history(u, c), pattern=r"^back_any$"))

    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
