#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import re
import io
import zoneinfo
from datetime import datetime, timedelta
from telegram.error import BadRequest, RetryAfter, TimedOut
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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

# === Support multiple PTB installations for Request ===
try:
    from telegram.request import Request
except Exception:
    try:
        from telegram.utils.request import Request
    except Exception:
        Request = None  # we'll handle None in main()

# ===== CONFIG =====
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8367165107:AAFmfC0gKHZiBjbO_-SDPCOtroypIy3fUKc")
TARGET_CHAT_ID = int(os.environ.get("TARGET_CHAT_ID", "-1003166932796"))
IMAGE_PATH = "image.jpg"  # optional
PRICE_PER_BOTTLE = 20000
CURRENCY = "UZS"

# timezone (use zoneinfo to ensure bot uses Asia/Tashkent consistently)
TZ = zoneinfo.ZoneInfo("Asia/Tashkent")

# ===== logging =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== STATES =====
# REGION bosqichi olib tashlandi.
LANG, PERSON_TYPE, PHONE, NAME, QUANTITY, COMMENT, COMMENT_INPUT, CITY_OR_PROVINCE, DISTRICT, ADDRESS_TEXT, AWAIT_GEOLOCATION, DELIVERY_DATE, PAYMENT = range(13)

# ===== TEXTS (uz/ru/en) =====
TEXTS = {
    "uz": {
        "welcome": "Xush kelibsiz! Iltimos, tilni tanlang:",
        "ask_person": "Iltimos, shaxs turini tanlang:",
        "person_buttons": ["👤 Jismoniy shaxs", "🏢 Yuridik shaxs"],
        "ask_phone": "Kontaktni ulashing (telefon):",
        "ask_name": "Ismingizni kiriting:",
        "ask_quantity": "Nechta suv olmoqchisiz? (Eng kam 2 ta)",
        "ask_city_or_province": "Toshkent shahar yoki viloyatni tanlang:",
        "tashkent_city_button": "🏙 Toshkent shahar",
        "tashkent_province_button": "🏞 Toshkent viloyati",
        "ask_district": "Iltimos, tumanni tanlang:",
        "ask_address_text": "Uy manzilingizni yozing (ko'cha, uy, kvartira ...):",
        "ask_location": "Iltimos, joylashuvingizni yuboring (📍 Send Location tugmasi orqali):",
        "ask_delivery": "Qachon yetkazib berish kerak? (quyidagi mavjud sanalardan tanlang)",
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
        "back_to_start": "🏠 Bosh sahifa — pastdagi tugmani bosing",
        "sunday_unavailable": "Eslatma: Yakshanba kuni ishlamaymiz — yakshanbalarni yetkazib berish sanalari orasida ko'rsatmaymiz.",
    },
    "ru": {
        "welcome": "Добро пожаловать! Пожалуйста, выберите язык:",
        "ask_person": "Выберите тип клиента:",
        "person_buttons": ["👤 Физическое лицо", "🏢 Юридическое лицо"],
        "ask_phone": "Поделитесь контактом (номер телефона):",
        "ask_name": "Введите ваше имя:",
        "ask_quantity": "Сколько бутылок воды хотите заказать? (Минимум 2)",
        "ask_city_or_province": "Выберите Ташкент город или область:",
        "tashkent_city_button": "🏙 Город Ташкент",
        "tashkent_province_button": "🏞 Ташкентская область",
        "ask_district": "Пожалуйста, выберите район:",
        "ask_address_text": "Введите ваш домашний адрес (улица, дом, кв ...):",
        "ask_location": "Пожалуйста, отправьте вашу локацию (кнопкой 📍):",
        "ask_delivery": "Когда доставить заказ? (выберите доступную дату)",
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
        "back_to_start": "🏠 Главная — нажмите кнопку ниже",
        "sunday_unavailable": "Примечание: по воскресеньям мы не работаем — воскресенья не доступны для доставки.",
    },
    "en": {
        "welcome": "Welcome! Please select your language:",
        "ask_person": "Please select your customer type:",
        "person_buttons": ["👤 Individual", "🏢 Company"],
        "ask_phone": "Please share your contact (phone):",
        "ask_name": "Enter your name:",
        "ask_quantity": "How many bottles of water do you want? (Minimum 2)",
        "ask_city_or_province": "Choose Tashkent City or Province:",
        "tashkent_city_button": "🏙 Tashkent City",
        "tashkent_province_button": "🏞 Tashkent Province",
        "ask_district": "Please select a district:",
        "ask_address_text": "Please enter your home address (street, house, apt ...):",
        "ask_location": "Please send your location (use the 📍 Send Location button):",
        "ask_delivery": "When should we deliver? (choose an available date)",
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
        "back_to_start": "🏠 Back to start — press the button below",
        "sunday_unavailable": "Note: We don't work on Sundays — Sundays are not available for delivery.",
    },
}

# ===== Districts (Tashkent city only) =====
DISTRICTS = {
    "tashkent_city": {
        "uz": [
            "Bektemir tumani",
            "Yashnobod tumani",
            "Mirzo Ulugʻbek tumani",
            "Mirobod tumani",
            "Sergeli tumani",
            "Shayxontohur tumani",
            "Olmazor tumani",
            "Uchtepa tumani",
            "Yakkasaroy tumani",
            "Yunusobod tumani",
            "Yangihayot tumani",
        ],
        "ru": [
            "Бектемирский район",
            "Яшнабадский район",
            "Мирзо-Улугбекский район",
            "Мирободский район",
            "Сергели район",
            "Шайхантохурский район",
            "Алмазарский район",
            "Учтепинский район",
            "Яккасарайский район",
            "Юнусабадский район",
            "Янгихаёт район",
        ],
        "en": [
            "Bektemir district",
            "Yashnobod district",
            "Mirzo Ulugbek district",
            "Mirobod district",
            "Sergeli district",
            "Shaykhontokhur district",
            "Olmazor district",
            "Uchtepa district",
            "Yakkasaroy district",
            "Yunusobod district",
            "Yangihayot district",
        ],
    }
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
    if not text:
        return False
    t = text.strip()
    for lang in TEXTS:
        if TEXTS[lang].get("home") == t:
            return True
    return False

# load optional image bytes
IMAGE_BYTES = None
try:
    with open(IMAGE_PATH, "rb") as f:
        IMAGE_BYTES = f.read()
except Exception:
    logger.info("image not found; continuing without image")

# price caption builder
def build_price_caption(qty: int, lang: str) -> str:
    txt = get_text_for_lang(lang, "price_line")
    total = PRICE_PER_BOTTLE * qty
    return txt.format(unit=PRICE_PER_BOTTLE, total=total, currency=CURRENCY)

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

def districts_keyboard_for_lang(lang: str):
    arr = DISTRICTS["tashkent_city"].get(lang) or DISTRICTS["tashkent_city"]["uz"]
    rows = [[d] for d in arr]
    rows.append([get_text_for_lang(lang, "back")])
    return rows

# ===== Handlers =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data.setdefault("_history", [])

    if IMAGE_BYTES:
        bio = io.BytesIO(IMAGE_BYTES)
        bio.name = "image.jpg"
        if getattr(update, "message", None):
            await update.message.reply_photo(photo=bio)
        else:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=bio)

    lang_row = ["🇺🇿 Uzbek", "🇷🇺 Russian", "🇬🇧 English"]
    keyboard = [lang_row]
    if getattr(update, "message", None):
        await update.message.reply_text(TEXTS["uz"]["welcome"], reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=TEXTS["uz"]["welcome"], reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return LANG

async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if is_home_text(text):
        return await start(update, context)

    low = text.lower()
    if "рус" in low or "ru" in low or "russian" in low or "рос" in low:
        context.user_data["lang"] = "ru"
    elif "uz" in low or "ўz" in low or "uzbek" in low or "uz" in low or "ўз" in low:
        context.user_data["lang"] = "uz"
    else:
        context.user_data["lang"] = "en"

    history = context.user_data.setdefault("_history", [])
    history.append(LANG)

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

    await update.message.reply_text(get_text(context.user_data, "ask_name"), reply_markup=ReplyKeyboardRemove())
    return NAME

async def received_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text or ""
    if t == get_text(context.user_data, "back"):
        return await render_state_from_history(update, context)

    context.user_data.setdefault("_history", []).append(NAME)
    context.user_data["name"] = (update.message.text or "").strip()
    context.user_data["quantity"] = context.user_data.get("quantity", 2)

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
        await query.message.reply_text(get_text(context.user_data, "ask_comment_question"), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(context.user_data, "yes"), callback_data="comment_yes"),
             InlineKeyboardButton(get_text(context.user_data, "no"), callback_data="comment_no")],
            [InlineKeyboardButton(get_text(context.user_data, "back"), callback_data="back_any")],
        ]))
        return COMMENT

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
        context.user_data.setdefault("_history", []).append(COMMENT)
        # Izoh yo'q → darhol shahar/viloyat tanlash
        lang = context.user_data.get("lang", "uz")
        buttons = [
            [get_text_for_lang(lang, "tashkent_city_button")],
            [get_text_for_lang(lang, "tashkent_province_button")],
            [get_text_for_lang(lang, "back")],
        ]
        await query.message.reply_text(
            get_text_for_lang(lang, "ask_city_or_province"),
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True),
        )
        return CITY_OR_PROVINCE

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

    # Izohdan keyin → shahar/viloyat tanlash
    lang = context.user_data.get("lang", "uz")
    buttons = [
        [get_text_for_lang(lang, "tashkent_city_button")],
        [get_text_for_lang(lang, "tashkent_province_button")],
        [get_text_for_lang(lang, "back")],
    ]
    await update.message.reply_text(
        get_text_for_lang(lang, "ask_city_or_province"),
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True),
    )
    return CITY_OR_PROVINCE

async def choose_city_or_province(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = (update.message.text or "").strip()
    lang = context.user_data.get("lang", "uz")

    if t == get_text_for_lang(lang, "back"):
        return await render_state_from_history(update, context)

    city_btn = get_text_for_lang(lang, "tashkent_city_button")
    province_btn = get_text_for_lang(lang, "tashkent_province_button")

    if t == city_btn:
        # User chose Tashkent City -> show districts
        context.user_data.setdefault("_history", []).append(CITY_OR_PROVINCE)
        context.user_data["area_choice"] = "city"

        rows = districts_keyboard_for_lang(lang)
        await update.message.reply_text(
            get_text_for_lang(lang, "ask_district"),
            reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True),
        )
        return DISTRICT

    if t == province_btn:
        # User chose Tashkent Province -> skip district step
        context.user_data.setdefault("_history", []).append(CITY_OR_PROVINCE)
        context.user_data["area_choice"] = "province"
        await update.message.reply_text(get_text_for_lang(lang, "ask_address_text"), reply_markup=ReplyKeyboardRemove())
        return ADDRESS_TEXT

    # If unexpected text, re-ask
    buttons = [
        [city_btn],
        [province_btn],
        [get_text_for_lang(lang, "back")],
    ]
    await update.message.reply_text(
        get_text_for_lang(lang, "ask_city_or_province"),
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True),
    )
    return CITY_OR_PROVINCE

async def received_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = (update.message.text or "").strip()
    if t == get_text(context.user_data, "back"):
        return await render_state_from_history(update, context)

    context.user_data.setdefault("_history", []).append(DISTRICT)
    context.user_data["district"] = t

    await update.message.reply_text(get_text(context.user_data, "ask_address_text"), reply_markup=ReplyKeyboardRemove())
    return ADDRESS_TEXT

async def received_address_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = (update.message.text or "").strip()
    if t == get_text(context.user_data, "back"):
        return await render_state_from_history(update, context)

    context.user_data.setdefault("_history", []).append(ADDRESS_TEXT)
    context.user_data["address_text"] = t

    loc_button = KeyboardButton("📍 Send Location", request_location=True)
    keyboard = [[loc_button], [get_text(context.user_data, "back")]]
    await update.message.reply_text(get_text(context.user_data, "ask_location"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return AWAIT_GEOLOCATION

async def received_geo_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text or ""
    if t == get_text(context.user_data, "back"):
        return await render_state_from_history(update, context)

    if not update.message.location:
        await update.message.reply_text(get_text(context.user_data, "ask_location"))
        return AWAIT_GEOLOCATION

    context.user_data.setdefault("_history", []).append(AWAIT_GEOLOCATION)
    loc = update.message.location
    context.user_data["location"] = {"lat": loc.latitude, "lon": loc.longitude}

    # Generate next 5 available delivery dates starting from tomorrow excluding Sundays (use TZ)
    lang = context.user_data.get("lang", "uz")
    today = datetime.now(TZ).date()
    options = []
    d = today + timedelta(days=1)
    while len(options) < 5:
        # weekday(): Monday=0 ... Sunday=6
        if d.weekday() == 6:
            d += timedelta(days=1)
            continue
        options.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    try:
        await update.message.reply_text(get_text_for_lang(lang, "sunday_unavailable"))
    except Exception:
        logger.exception("Failed to send sunday_unavailable message (ignored)")

    buttons = [[InlineKeyboardButton(x, callback_data=f"date_{x}")] for x in options]
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

        await query.message.reply_text(get_text(context.user_data, "order_button"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(context.user_data, "order_button"), callback_data="place_order")]]))
        return PAYMENT

    return PAYMENT

async def final_place_order_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_any":
        return await render_state_from_history(update, context)

    if data == "place_order":
        ud = context.user_data
        qty = ud.get("quantity", 0)
        total = PRICE_PER_BOTTLE * qty

        # Area display text
        lang = ud.get("lang", "uz")
        area_choice = ud.get("area_choice")
        if area_choice == "city":
            area_display = get_text_for_lang(lang, "tashkent_city_button").replace("🏙 ", "")
        elif area_choice == "province":
            area_display = get_text_for_lang(lang, "tashkent_province_button").replace("🏞 ", "")
        else:
            area_display = ""

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
        if area_display:
            text += f"📌 Hudud: {area_display}\n"
        if ud.get("district"):
            text += f"🏘 Tuman: {ud.get('district')}\n"
        if ud.get("address_text"):
            text += f"🏠 Manzil (matn): {ud.get('address_text')}\n"
        if ud.get("location"):
            text += f"🌍 Manzil: https://maps.google.com/?q={ud['location']['lat']},{ud['location']['lon']}\n"

        # send order to target chat with retry-on-timeout/backoff behavior
        try:
            await context.bot.send_message(chat_id=TARGET_CHAT_ID, text=text)
        except TimedOut:
            logger.warning("TimedOut while sending order to target chat - ignored (will not crash).")
        except Exception:
            logger.exception("Failed to send order to target chat")

        try:
            await query.message.reply_text(get_text(context.user_data, "thanks"))
        except Exception:
            try:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=get_text(context.user_data, "thanks"))
            except Exception:
                logger.exception("Failed to notify user about successful order (ignored)")

        start_button = KeyboardButton("/start")
        reply_kb = ReplyKeyboardMarkup([[start_button]], resize_keyboard=True)

        lang = context.user_data.get("lang", "uz")
        context.user_data.clear()
        context.user_data.setdefault("_history", [])
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=get_text_for_lang(lang, "back_to_start"), reply_markup=reply_kb)
        except Exception:
            logger.exception("Failed to send back_to_start (ignored)")

        return LANG

    return PAYMENT

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

    if prev_state in (COMMENT, COMMENT_INPUT):
        # Qaytishda: shahar/viloyat tanlovini qayta ko'rsatamiz
        lang = context.user_data.get("lang", "uz")
        buttons = [
            [get_text_for_lang(lang, "tashkent_city_button")],
            [get_text_for_lang(lang, "tashkent_province_button")],
            [get_text_for_lang(lang, "back")],
        ]
        await target.reply_text(get_text_for_lang(lang, "ask_city_or_province"),
                                reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return CITY_OR_PROVINCE

    if prev_state == CITY_OR_PROVINCE:
        # Qaytishda – izoh bosqichiga qaytish o‘rniga shu tanlovni qayta beramiz
        lang = context.user_data.get("lang", "uz")
        buttons = [
            [get_text_for_lang(lang, "tashkent_city_button")],
            [get_text_for_lang(lang, "tashkent_province_button")],
            [get_text_for_lang(lang, "back")],
        ]
        await target.reply_text(get_text_for_lang(lang, "ask_city_or_province"),
                                reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return CITY_OR_PROVINCE

    if prev_state == DISTRICT:
        # Agar city tanlangan bo'lsa — tumanlarni qayta ko'rsatamiz, aks holda manzilga o'tamiz
        lang = context.user_data.get("lang", "uz")
        if context.user_data.get("area_choice") == "city":
            rows = districts_keyboard_for_lang(lang)
            await target.reply_text(get_text_for_lang(lang, "ask_district"), reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True))
            return DISTRICT
        else:
            await target.reply_text(get_text_for_lang(lang, "ask_address_text"), reply_markup=ReplyKeyboardRemove())
            return ADDRESS_TEXT

    if prev_state == ADDRESS_TEXT:
        await target.reply_text(get_text(context.user_data, "ask_address_text"), reply_markup=ReplyKeyboardRemove())
        return ADDRESS_TEXT

    if prev_state == AWAIT_GEOLOCATION:
        loc_button = KeyboardButton("📍 Send Location", request_location=True)
        await target.reply_text(get_text(context.user_data, "ask_location"), reply_markup=ReplyKeyboardMarkup([[loc_button], [get_text(context.user_data, "back")]], resize_keyboard=True))
        return AWAIT_GEOLOCATION

    if prev_state == DELIVERY_DATE:
        # use TZ-aware date here as well
        today = datetime.now(TZ).date()
        options = []
        d = today + timedelta(days=1)
        while len(options) < 5:
            if d.weekday() == 6:
                d += timedelta(days=1)
                continue
            options.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
        buttons = [[InlineKeyboardButton(x, callback_data=f"date_{x}")] for x in options]
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
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise SystemExit("Please set BOT_TOKEN environment variable.")

    # Configure Request (if available) to make the bot faster and more robust
    request = None
    if Request:
        try:
            request = Request(
                con_pool_size=8,
                connect_timeout=5.0,
                read_timeout=20.0,
                pool_timeout=5.0,
            )
        except Exception:
            logger.exception("Request() creation failed, falling back to default ApplicationBuilder request")

    # Build application: with custom request if available
    try:
        if request:
            app = ApplicationBuilder().token(BOT_TOKEN).request(request).build()
        else:
            app = ApplicationBuilder().token(BOT_TOKEN).build()
    except Exception:
        logger.exception("ApplicationBuilder build failed; retrying without custom request")
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
            CITY_OR_PROVINCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_city_or_province)],
            DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_district)],
            ADDRESS_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_address_text)],
            AWAIT_GEOLOCATION: [MessageHandler(filters.LOCATION | (filters.TEXT & ~filters.COMMAND), received_geo_location)],
            DELIVERY_DATE: [CallbackQueryHandler(delivery_handler, pattern=r"^date_.*|back_any$")],
            PAYMENT: [CallbackQueryHandler(payment_handler, pattern=r"^(card|cash|back_any)$")],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(final_place_order_handler, pattern=r"^place_order$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: render_state_from_history(u, c), pattern=r"^back_any$"))

    logger.info("Bot started")
    try:
        app.run_polling()
    except KeyboardInterrupt:
        logger.info("Stopping bot (KeyboardInterrupt)")
    except Exception:
        logger.exception("Unexpected error in run_polling")


if __name__ == "__main__":
    main()
