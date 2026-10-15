import asyncio
import ast
import inspect
import html as _html
import json
import os
import random
import re
import string
import time as _time
import uuid
import hashlib
import hmac
from urllib.parse import parse_qsl
from io import BytesIO

from aiohttp import web
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    FSInputFile,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    MessageEntity,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils import formatting as fmt
from aiogram.fsm.storage.base import StorageKey
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
import logging

import locales
from database import db
from legacy_reviews import LEGACY_REVIEWS

# Короткий алиас для премиум-эмодзи в текстах сообщений
e = locales.e

logging.basicConfig(level=logging.INFO)

CONFIG_FILE = "config.json"
ADMINS_FILE = "admins.json"
PANEL_ADMINS_FILE = "panel_admins.json"
SETTINGS_FILE = "settingsadm.json"
users_data_file = "users_data.json"
deals_file = "deals.json"

# ─── Настройки ─────────────────────────────────────────────────────────────────
NOTIFICATION_CHANNEL_ID = None
MANAGER_TON_WALLET  = ""
MANAGER_CARD        = ""
MANAGER_USDT_WALLET = ""
MANAGER_BTC_WALLET  = ""
MIN_DEALS_FOR_WITHDRAW = 2

# ─── Подписки воркеров ────────────────────────────────────────────────────────
WORKER_SUBSCRIPTION_PLANS = {3: 12.55, 7: 25.50, 30: 55.50}
CRYPTOBOT_API_TOKEN = ""
SUBSCRIPTION_TON_WALLET = ""
SUBSCRIPTION_USDT_WALLET = ""
SUBSCRIPTION_USDT_NETWORK = "TRC20"

def _subscription_settings() -> dict:
    """Единые настройки подписок. Хранятся в settingsadm.json и меняются из /admin."""
    default = {
        "plans": {"3": 12.55, "7": 25.50, "30": 55.50},
        "ton_wallet": SUBSCRIPTION_TON_WALLET,
        "usdt_wallet": SUBSCRIPTION_USDT_WALLET,
        "usdt_network": SUBSCRIPTION_USDT_NETWORK,
        "cryptobot_api_token": CRYPTOBOT_API_TOKEN,
        "cryptobot_asset": "USDT",
        "send_username": "@Send",
        "cabinet_name": str(_sub_cfg.get("CABINET_NAME") or "HYPED WORKER") if "_sub_cfg" in globals() else "HYPED WORKER",
        "enabled": bool(_sub_cfg.get("ENABLED", True)) if "_sub_cfg" in globals() else True,
    }
    current = adm_settings.get("worker_subscription", {}) if isinstance(adm_settings, dict) else {}
    plans = current.get("plans", {}) or {}
    merged = dict(default)
    merged.update(current)
    merged["plans"] = {str(k): float(v) for k, v in (plans or default["plans"]).items()}
    return merged

def _subscription_enabled() -> bool:
    cfg = _subscription_settings()
    return bool(cfg.get("enabled", True))

def _subscription_plans() -> dict[int, float]:
    return {int(k): float(v) for k, v in _subscription_settings().get("plans", {}).items()}

def _sync_subscription_constants():
    global WORKER_SUBSCRIPTION_PLANS, SUBSCRIPTION_TON_WALLET, SUBSCRIPTION_USDT_WALLET, SUBSCRIPTION_USDT_NETWORK, CRYPTOBOT_API_TOKEN
    cfg = _subscription_settings()
    WORKER_SUBSCRIPTION_PLANS = _subscription_plans()
    SUBSCRIPTION_TON_WALLET = str(cfg.get("ton_wallet") or "")
    SUBSCRIPTION_USDT_WALLET = str(cfg.get("usdt_wallet") or "")
    SUBSCRIPTION_USDT_NETWORK = str(cfg.get("usdt_network") or "TRC20")
    CRYPTOBOT_API_TOKEN = str(cfg.get("cryptobot_api_token") or CRYPTOBOT_API_TOKEN or "").strip()

# ─── ID кастомных эмодзи для кнопок ───────────────────────────────────────────
# Используются в icon_custom_emoji_id для InlineKeyboardButton
_BEID = {
    "cross":        "5210952531676504517",
    "check":        "5902002809573740949",
    "bridge":       "5240428351063081133",
    "usdt":         "5814556334829343625",
    "btc":          "5816788957614053645",
    "money_bag":    "5375296873982604963",
    "person":       "6032693626394382504",
    "person2":      "5884366771913233289",
    "down":         "5406745015365943482",
    "star":         "4983746717313664194",
    "diamond":      "5427168083074628963",
    "people":       "6032609071373226027",
    "writing":      "5197269100878907942",
    "back":         "5924683191834121281",
    "cart":         "5312361253610475399",
    "handshake":    "5395732581780040886",
    "edit":         "5395444784611480792",
    "card":         "5445353829304387411",
    "package":      "5778672437122045013",
    "chat":         "5443038326535759644",
    "chart":        "5190806721286657692",
    "megaphone":    "5424818078833715060",
    "flag_ru":      "5449408995691341691",
    "flag_ua":      "5447309366568953338",
    "flag_kz":      "5228718354658769982",
    "flag_by":      "5382219601054544127",
    "link":         "5902449142575141204",
    "timer":        "5386367538735104399",
    "hammer":       "5836997023554870252",
    "crown":        "5217822164362739968",
    "bell":         "5458603043203327669",
    "no":           "5260293700088511294",
    "coin":         "5224257782013769471",
    "tag":          "5888620056551625531",
    "mail":         "5253742260054409879",
    "mailbox":      "5350421256627838238",
    "question":     "5436113877181941026",
    "tv":           "6039391078136681499",
    "pin":          "5397782960512444700",
    "finish":       "5411520005386806155",
    "globe":        "5776233299424843260",
    "star2":        "5924870095925942277",
    "warning":      "5420323339723881652",
    "sparkle":      "5325547803936572038",
    "flag_us":      "5202021044105257611",
    "globe2":       "5447410659077661506",
    "gift":         "6037175527846975726",
    "confetti":     "5193018401810822951",
    "target":       "5310278924616356636",
    "bank":         "5332455502917949981",
    "broken_heart": "5316583309541651465",
    "heart_spark":  "5470080737711502911",
    "heart":        "5406926593698312391",
    "heart_gift":   "5192879906295397710",
    "briefcase":    "5445221832074483553",
    "writing2":     "5470060791883374114",
    "outbox":       "6043874504302661409",
    "inbox":        "6039420807900303010",
    "shield":       "5893365724830765382",
    "flying_money": "5375296873982604963",
    "gear":         "5902432207519093015",
    "lock":         "5296369303661067030",
    "sparkle2":     "5778647930038653243",
    "plane":        "5927118708873892465",
    "gem":          "5891105528356018797",
    # ── Расширенный набор ──────────────────────────────────────────────────────────
    "shield2":      "5902016123972358349",
    "phone":        "5895652322469482989",
    "phone2":       "5895266423952904371",
    "phone3":       "5893100690988863311",
    "check2":       "5895514131896733546",
    "check3":       "5895713431264170680",
    "check4":       "5893431652578758294",
    "cross2":       "5893163582194978381",
    "cross3":       "5893081007153746175",
    "briefcase2":   "5893255507380014983",
    "sleep":        "5774138454896022007",
    "money2":       "5893473283696759404",
    "search":       "5893382531037794941",
    "pin2":         "5895440460322706085",
    "idea":         "5893290369629556374",
    "coin2":        "6039802097916974085",
    "gear2":        "5893161718179173515",
    "stop":         "5904238507555033712",
    "person3":      "5902335789798265487",
    "next":         "5893368370530621889",
    "heart2":       "5893406892092297627",
    "heart3":       "5895213106228891182",
    "eyes":         "5210956306952758910",
    "lightning":    "5456140674028019486",
    "smile":        "5461117441612462242",
    "exclaim":      "5274099962655816924",
    "ban":          "5240241223632954241",
    "think":        "5467538555158943525",
    "trending":     "5244837092042750681",
    "snowflake":    "5449449325434266744",
    "gold":         "5440539497383087970",
    "silver":       "5447203607294265305",
    "bronze":       "5453902265922376865",
    "n0":           "5794375786743995258",
    "n1":           "5794164805065514131",
    "n2":           "5794085322400733645",
    "n3":           "5794280000383358988",
    "n4":           "5794241397217304511",
    "n5":           "5793985348446984682",
    "n6":           "5794324702402976226",
    "n7":           "5793942849745591465",
    "n8":           "5793926687783655907",
    "n9":           "5793979472931723221",
}


def _button_emoji_override_key(line_no: int) -> str:
    """Стабильный идентификатор конкретного места создания кнопки."""
    return str(line_no)


def _button_emoji_id_for_call(line_no: int, emoji_key: str | None) -> str | None:
    overrides = adm_settings.get("button_emojis", {}) if "adm_settings" in globals() else {}
    override = overrides.get(_button_emoji_override_key(line_no))
    if override:
        return str(override)
    return _BEID.get(emoji_key) if emoji_key else None


def mkbtn(text: str, emoji_key: str = None, **kwargs) -> InlineKeyboardButton:
    """Создать InlineKeyboardButton с кастомным эмодзи (icon_custom_emoji_id)."""
    kwargs.setdefault("style", "primary")
    line_no = inspect.currentframe().f_back.f_lineno
    eid = _button_emoji_id_for_call(line_no, emoji_key)
    if eid:
        return InlineKeyboardButton(text=text, icon_custom_emoji_id=eid, **kwargs)
    return InlineKeyboardButton(text=text, **kwargs)


# ─── Загрузка / сохранение ─────────────────────────────────────────────────────
def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_admins():
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_admins(admins):
    with open(ADMINS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(admins), f)

def load_panel_admins() -> set:
    """Панельные админы (доступ к /admin). Хардкодные владельцы всегда включены."""
    if os.path.exists(PANEL_ADMINS_FILE):
        with open(PANEL_ADMINS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_panel_admins(panel_admins: set):
    with open(PANEL_ADMINS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(panel_admins), f)

def load_users_data():
    if os.path.exists(users_data_file):
        with open(users_data_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users_data(data):
    pass  # данные хранятся в db.users, сохранение — через db.upsert_user

def load_deals():
    return {}  # данные загружаются из SQLite в db.init()

def save_deals(d):
    pass  # данные хранятся в db.deals, сохранение — через db.schedule_save_deal

_DEFAULT_SETTINGS = {
    "service_name":          "Hyped Team",
    "manager_username":      "GiftRuWallet",
    "manager_ton_wallet":    "UQBNiQDAPrwvOfCV0yQZ3c_fJKTRVCqYSG0jOGFgJFqkOIjo",
    "manager_card":          "‼️ ВРЕМЕННО НЕ ДОСТУПНО ‼",
    "manager_usdt_wallet":   "TAkYwA14xvDBb12ztrdnS86pdNopDGNLJU",
    "manager_btc_wallet":    "‼️ ВРЕМЕННО НЕ ДОСТУПНО ‼",
    "notification_channel":  str(NOTIFICATION_CHANNEL_ID),
    "gift_recipient":        "GiftRuWallet",
    "min_deals_withdraw":    2,
    "log_channel":           "-1004294791227",
    "log_topic_id":          "11",
    "admins_list":           [],
    "auto_workers_list":     [],
    "auto_worker_enabled":   True,
    "auto_worker_group_id":   "",
    "button_emojis":         {},
    "user_text_overrides":   {"ru": {}, "en": {}},
    "webapp_url":             "",
}

def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in _DEFAULT_SETTINGS.items():
            data.setdefault(k, v)
        return data
    s = dict(_DEFAULT_SETTINGS)
    save_settings(s)
    return s

def save_settings(s: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=4)


# ─── Баннеры ───────────────────────────────────────────────────────────────────
ALLOWED_BANNER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".mp4"}

# Все слоты баннеров: ключ → (описание, список допустимых имён файлов по расширениям)
BANNER_SLOTS = {
    "menu_ru":    ("Главное меню (RU)",     ["menu_ru.png", "menu_ru.jpg", "menu_ru.gif", "menu_ru.mp4"]),
    "menu_en":    ("Главное меню (EN)",     ["menu_en.png", "menu_en.jpg", "menu_en.gif", "menu_en.mp4"]),
    "menu":       ("Главное меню (резерв)", ["menu.png",    "menu.jpg",    "menu.gif",    "menu.mp4"]),
    "deal_ru":    ("Экран сделки (RU)",     ["deal_ru.png",  "deal_ru.jpg",  "deal_ru.gif",  "deal_ru.mp4"]),
    "deal_en":    ("Экран сделки (EN)",     ["deal_en.png",  "deal_en.jpg",  "deal_en.gif",  "deal_en.mp4"]),
    "balance_ru":    ("Баланс (RU)",           ["balance_ru.png","balance_ru.jpg","balance_ru.gif","balance_ru.mp4"]),
    "balance_en":    ("Баланс (EN)",           ["balance_en.png","balance_en.jpg","balance_en.gif","balance_en.mp4"]),
    "rekvizity_ru":  ("Реквизиты (RU)",        ["rekvizity_ru.png","rekvizity_ru.jpg","rekvizity_ru.gif","rekvizity_ru.mp4"]),
    "rekvizity_en":  ("Реквизиты (EN)",        ["rekvizity_en.png","rekvizity_en.jpg","rekvizity_en.gif","rekvizity_en.mp4"]),
    "rekvizity":     ("Реквизиты (резерв)",    ["rekvizity.png","rekvizity.jpg","rekvizity.gif","rekvizity.mp4"]),
}

def get_banner_path(slot_key: str):
    """Вернуть путь к текущему файлу баннера для слота (или None)."""
    if slot_key not in BANNER_SLOTS:
        return None
    _, names = BANNER_SLOTS[slot_key]
    for name in names:
        path = os.path.join(os.getcwd(), name)
        if os.path.exists(path):
            return path
    return None

def get_banner_status(slot_key: str) -> str:
    path = get_banner_path(slot_key)
    if path:
        fname = os.path.basename(path)
        size_kb = os.path.getsize(path) // 1024
        return f"✅ {fname} ({size_kb} КБ)"
    return "❌ не установлен"

def save_banner_file(slot_key: str, file_bytes: bytes, ext: str) -> str:
    """Сохранить байты файла как баннер. Возвращает итоговый путь."""
    if slot_key not in BANNER_SLOTS:
        raise ValueError(f"Unknown slot: {slot_key}")
    _, names = BANNER_SLOTS[slot_key]
    # Выбираем имя с нужным расширением
    target_name = None
    for name in names:
        if name.endswith(ext):
            target_name = name
            break
    if target_name is None:
        target_name = os.path.splitext(names[0])[0] + ext
    # Удаляем старые файлы этого слота
    for name in names:
        old = os.path.join(os.getcwd(), name)
        if os.path.exists(old):
            os.remove(old)
    target_path = os.path.join(os.getcwd(), target_name)
    with open(target_path, "wb") as f:
        f.write(file_bytes)
    return target_path


config = load_config()
BOT_TOKEN = config["BOT_TOKEN"]
# Все основные настройки проекта берутся из config.json.
_admin_cfg = config.get("ADMINS", {}) or {}
_group_cfg = config.get("GROUPS", {}) or {}
_channel_cfg = config.get("CHANNELS", {}) or {}
_manager_cfg = config.get("MANAGER", {}) or {}
_sub_cfg = config.get("SUBSCRIPTION", {}) or {}

ADMIN_GROUP_ID = config.get("ADMIN_GROUP_ID", _group_cfg.get("ADMIN_GROUP_ID"))
# API CryptoBot для автоматической оплаты подписки берётся из config.json → SUBSCRIPTION → CRYPTOBOT_API_TOKEN.
CRYPTOBOT_API_TOKEN = os.getenv("CRYPTOBOT_API_TOKEN", "").strip() or str(_sub_cfg.get("CRYPTOBOT_API_TOKEN") or config.get("CRYPTOBOT_API_TOKEN", "")).strip()
NOTIFICATION_CHANNEL_ID = _channel_cfg.get("NOTIFICATION_CHANNEL_ID", config.get("NOTIFICATION_CHANNEL_ID"))
MANAGER_TON_WALLET = str(_manager_cfg.get("TON_WALLET") or config.get("MANAGER_TON_WALLET") or "").strip()
MANAGER_CARD = str(_manager_cfg.get("CARD") or config.get("MANAGER_CARD") or "").strip()
MANAGER_USDT_WALLET = str(_manager_cfg.get("USDT_WALLET") or config.get("MANAGER_USDT_WALLET") or "").strip()
MANAGER_BTC_WALLET = str(_manager_cfg.get("BTC_WALLET") or config.get("MANAGER_BTC_WALLET") or "").strip()
MIN_DEALS_FOR_WITHDRAW = int(config.get("WITHDRAW", {}).get("MIN_DEALS", config.get("MIN_DEALS_FOR_WITHDRAW", 2)))
SUBSCRIPTION_TON_WALLET = str(_sub_cfg.get("TON_WALLET") or config.get("SUBSCRIPTION_TON_WALLET") or MANAGER_TON_WALLET).strip()
SUBSCRIPTION_USDT_WALLET = str(_sub_cfg.get("USDT_WALLET") or config.get("SUBSCRIPTION_USDT_WALLET") or MANAGER_USDT_WALLET).strip()
SUBSCRIPTION_USDT_NETWORK = str(_sub_cfg.get("USDT_NETWORK") or config.get("SUBSCRIPTION_USDT_NETWORK") or "TRC20").strip()

admins = load_admins()
users_data: dict = {}  # алиас — будет привязан к db.users после db.init()
deals: dict = {}       # алиас — будет привязан к db.deals после db.init()
adm_settings = load_settings()
_sync_subscription_constants()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip() or str(adm_settings.get("webapp_url", "")).strip()
panel_admins = load_panel_admins()  # Панельные админы (доступ к /admin)

# Дедупликация update_id — защита от Telegram-ретрансмитов при плохом соединении
_seen_update_ids: set[int] = set()

# Применяем настройки из settingsadm.json
if adm_settings.get("manager_ton_wallet"):
    MANAGER_TON_WALLET = adm_settings["manager_ton_wallet"]
if adm_settings.get("manager_card"):
    MANAGER_CARD = adm_settings["manager_card"]
if adm_settings.get("manager_usdt_wallet"):
    MANAGER_USDT_WALLET = adm_settings["manager_usdt_wallet"]
if adm_settings.get("manager_btc_wallet"):
    MANAGER_BTC_WALLET = adm_settings["manager_btc_wallet"]
if adm_settings.get("notification_channel"):
    try:
        NOTIFICATION_CHANNEL_ID = int(adm_settings["notification_channel"])
    except ValueError:
        pass
if adm_settings.get("min_deals_withdraw") is not None:
    MIN_DEALS_FOR_WITHDRAW = int(adm_settings["min_deals_withdraw"])

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ─── Автоудаление команд пользователя ──────────────────────────────────────────
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

class DeleteCommandMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        msg = getattr(event, "message", None) or event if isinstance(event, types.Message) else None
        if msg and isinstance(msg, types.Message) and msg.text and msg.text.startswith("/"):
            try:
                await msg.delete()
            except Exception:
                pass
        return await handler(event, data)

dp.message.middleware(DeleteCommandMiddleware())


# ─── Дедупликация сообщений (защита от Telegram-ретрансмитов) ──────────────────
class DeduplicateMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        msg = event if isinstance(event, types.Message) else None
        if msg and msg.message_id:
            key = (msg.chat.id, msg.message_id)
            if key in _seen_update_ids:
                return  # дубль — игнорируем
            _seen_update_ids.add(key)
            if len(_seen_update_ids) > 10000:
                # чистим старые чтобы не росло бесконечно
                _seen_update_ids.clear()
        return await handler(event, data)

dp.message.middleware(DeduplicateMiddleware())


# ─── Локализация ───────────────────────────────────────────────────────────────
def get_text(key: str, user_id: int, **kwargs) -> str:
    lang = users_data.get(str(user_id), {}).get("lang", "ru")
    # Автоматически добавляем currency_emoji если передана currency
    if "currency" in kwargs and "currency_emoji" not in kwargs:
        kwargs["currency_emoji"] = _currency_emoji(str(kwargs["currency"]))
    # Автоматически подставляем настройки сервиса
    kwargs.setdefault("service_name", adm_settings.get("service_name", "Hyped Team"))
    kwargs.setdefault("manager_username", adm_settings.get("manager_username", "GiftRuWallet"))
    overrides = adm_settings.get("user_text_overrides", {})
    text = overrides.get(lang, {}).get(key)
    if text is None:
        return locales.get_html_text(key, lang, **kwargs)
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError):
        return text

def get_alert(key: str, user_id: int = None, lang: str = None, **kwargs) -> str:
    """Текст для show_alert — без tg-emoji тегов (Telegram их не рендерит во всплывашках)."""
    import re
    if lang is None:
        lang = users_data.get(str(user_id), {}).get("lang", "ru") if user_id else "ru"
    if "currency" in kwargs and "currency_emoji" not in kwargs:
        kwargs["currency_emoji"] = _currency_emoji(str(kwargs["currency"]))
    kwargs.setdefault("service_name", adm_settings.get("service_name", "Hyped Team"))
    kwargs.setdefault("manager_username", adm_settings.get("manager_username", "GiftRuWallet"))
    overrides = adm_settings.get("user_text_overrides", {})
    text_template = overrides.get(lang, {}).get(key)
    if text_template is None:
        text = locales.get_html_text(key, lang, **kwargs)
    else:
        try:
            text = text_template.format(**kwargs)
        except (KeyError, IndexError):
            text = text_template
    # Убираем <tg-emoji ...>fallback</tg-emoji> — оставляем только fallback
    text = re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', text)
    return text


# ─── Состояния ─────────────────────────────────────────────────────────────────
class CreateDealStates(StatesGroup):
    choose_role           = State()
    choose_payment_method = State()
    choose_crypto         = State()
    choose_currency       = State()
    enter_amount          = State()
    enter_description     = State()

class DealStates(StatesGroup):
    connected_as_seller           = State()
    payment_confirmed_as_seller   = State()
    connected_as_buyer            = State()
    payment_confirmed_as_buyer    = State()
    item_delivered_to_manager     = State()
    buyer_confirmed_receipt       = State()
    completed                     = State()

class EditCredentialsState(StatesGroup):
    waiting_for_ton_wallet    = State()
    waiting_for_card_number   = State()
    waiting_for_stars_username = State()
    waiting_for_usdt_wallet   = State()
    waiting_for_btc_wallet    = State()

class AdsState(StatesGroup):
    waiting_for_ads_message = State()

class WithdrawState(StatesGroup):
    choose_currency = State()
    enter_amount    = State()
    confirm         = State()

class FeedbackState(StatesGroup):
    waiting_for_feedback = State()

class MyDealsState(StatesGroup):
    search = State()

class AdminStates(StatesGroup):
    # Рассылка
    waiting_for_broadcast_message = State()
    # Поиск пользователя
    waiting_for_user_search       = State()
    # Редактирование пользователя
    edit_user_balance_currency    = State()
    edit_user_balance_amount      = State()
    edit_user_deals_count         = State()
    # Сообщение конкретному пользователю
    send_message_to_user          = State()
    # Настройки
    settings_service_name         = State()
    settings_manager_username     = State()
    settings_ton_wallet           = State()
    settings_card                 = State()
    settings_usdt_wallet          = State()
    settings_btc_wallet           = State()
    settings_channel              = State()
    settings_gift_recipient       = State()
    settings_min_deals            = State()
    settings_log_channel          = State()
    settings_log_topic_id         = State()
    settings_add_admin            = State()
    settings_add_panel_admin      = State()
    settings_auto_worker_group   = State()
    settings_crypto_token        = State()
    deals_search                  = State()
    # Баннеры
    settings_upload_banner        = State()
    settings_button_emoji         = State()
    settings_text_value           = State()

class GoyStates(StatesGroup):
    choose_currency = State()
    enter_amount    = State()

class WorkerSubscriptionStates(StatesGroup):
    waiting_manager_username = State()
    waiting_direct_proof     = State()
    waiting_set_deals        = State()

class AdminSubscriptionStates(StatesGroup):
    edit_plan_days = State()
    edit_plan_price = State()
    edit_ton_wallet = State()
    edit_usdt_wallet = State()
    edit_usdt_network = State()
    edit_crypto_token = State()
    edit_cabinet_name = State()
    issue_user = State()
    issue_days = State()
    issue_price = State()
    remove_user = State()


# ─── Вспомогательные функции ───────────────────────────────────────────────────
def _currency_emoji(currency: str) -> str:
    """Возвращает tg-emoji HTML для указанной валюты."""
    from locales import _E as LE
    m = {
        "STARS": '<tg-emoji emoji-id="5924870095925942277">⭐️</tg-emoji>',
        "TON":   '<tg-emoji emoji-id="6039802097916974085">🪙</tg-emoji>',
        "BTC":   '<tg-emoji emoji-id="5816788957614053645">🪙</tg-emoji>',
        "USDT":  "<tg-emoji emoji-id=\"5814556334829343625\">🪙</tg-emoji>",
        "RUB":   LE["flag_ru"],
        "UAH":   LE["flag_ua"],
        "KZT":   LE["flag_kz"],
        "BYN":   LE["flag_by"],
    }
    return m.get(currency, LE.get("coin2", "🪙"))


def _status_emoji(status: str) -> str:
    m = {
        "waiting_for_buyer":          "⏳",
        "waiting_for_seller":         "⏳",
        "waiting_for_payment":        "💳",
        "payment_confirmed_by_admin": "✅",
        "item_delivered_to_manager":  "📦",
        "waiting_for_feedback":       "💬",
        "completed":                  "✅",
        "cancelled":                  "❌",
    }
    return m.get(status, "❓")

def _status_ru(status: str) -> str:
    m = {
        "waiting_for_buyer":          "Ожидает покупателя",
        "waiting_for_seller":         "Ожидает продавца",
        "waiting_for_payment":        "Ожидает оплаты",
        "payment_confirmed_by_admin": "Оплата подтверждена",
        "item_delivered_to_manager":  "Товар передан",
        "waiting_for_feedback":       "Ожидает отзыва",
        "completed":                  "Завершена",
        "cancelled":                  "Отменена",
    }
    return m.get(status, status)

def _status_localized(status: str, user_id: int) -> str:
    ru = {
        "waiting_for_buyer":          "Ожидает покупателя",
        "waiting_for_seller":         "Ожидает продавца",
        "waiting_for_payment":        "Ожидает оплаты",
        "payment_confirmed_by_admin": "Оплата подтверждена",
        "item_delivered_to_manager":  "Товар передан",
        "waiting_for_feedback":       "Ожидает отзыва",
        "completed":                  "Завершена",
        "cancelled":                  "Отменена",
    }
    en = {
        "waiting_for_buyer":          "Waiting for buyer",
        "waiting_for_seller":         "Waiting for seller",
        "waiting_for_payment":        "Waiting for payment",
        "payment_confirmed_by_admin": "Payment confirmed",
        "item_delivered_to_manager":  "Item delivered",
        "waiting_for_feedback":       "Waiting for feedback",
        "completed":                  "Completed",
        "cancelled":                  "Cancelled",
    }
    lang = users_data.get(str(user_id), {}).get("lang", "ru")
    m = en if lang == "en" else ru
    return m.get(status, status)

def get_active_deals() -> dict:
    """Вернуть незавершённые сделки."""
    return {
        did: d for did, d in deals.items()
        if d.get("status") not in ("completed", "cancelled")
    }


# ─── Клавиатуры ────────────────────────────────────────────────────────────────
def get_main_menu_kb(user_id: int):
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("menu_credentials",  user_id), "inbox",      callback_data="menu_credentials"))
    kb.add(mkbtn(get_text("menu_create_deal",  user_id), "handshake",  callback_data="menu_create_deal"))
    kb.add(mkbtn(get_text("menu_balance",      user_id), "money_bag",  callback_data="menu_balance"))
    kb.add(mkbtn(get_text("menu_my_deals",     user_id), "finish",     callback_data="my_deals_page_0"))
    kb.add(mkbtn(get_text("menu_referral",     user_id), "link",       callback_data="menu_referral"))
    if WEBAPP_URL:
        kb.add(mkbtn(get_text("menu_reviews", user_id), "heart2", web_app=WebAppInfo(url=WEBAPP_URL)))
    else:
        kb.add(mkbtn(get_text("menu_reviews", user_id), "heart2", callback_data="reviews_unconfigured"))
    kb.add(mkbtn(get_text("lang_button",       user_id), "globe",      callback_data="menu_language"))
    kb.add(mkbtn(get_text("support_button",    user_id), "shield",     url='https://t.me/' + adm_settings.get('manager_username', 'GiftRuWallet')))
    kb.adjust(2, 2, 2, 1)
    return kb.as_markup()


def get_user_deals_kb(user_id: int, page: int = 0, search: str = "") -> InlineKeyboardMarkup:
    """Список сделок пользователя с пагинацией (2 столбца, 8 на странице) и поиском."""
    uid_str = str(user_id)
    user_deals = {
        did: d for did, d in deals.items()
        if d.get("seller_id") == user_id or d.get("buyer_id") == user_id
    }
    if search:
        user_deals = {did: d for did, d in user_deals.items() if search.lower() in did.lower()}
    items = sorted(user_deals.items(), key=lambda x: x[1].get("created_at", 0), reverse=True)

    per_page = 8
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    chunk = items[page * per_page:(page + 1) * per_page]

    kb = InlineKeyboardBuilder()
    for did, d in chunk:
        emoji = _status_emoji(d.get("status", ""))
        amount = d.get("amount", "?")
        currency = d.get("currency", "?")
        kb.add(mkbtn(f"{emoji} #{did[:8]} {amount} {currency}", callback_data=f"my_deal_{did}"))
    kb.adjust(2)

    nav = []
    if page > 0:
        nav.append(mkbtn("◀️", callback_data=f"my_deals_page_{page-1}"))
    nav.append(mkbtn(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(mkbtn("▶️", callback_data=f"my_deals_page_{page+1}"))
    kb.row(*nav)
    kb.row(mkbtn(get_text("my_deals_search_button", user_id), callback_data="my_deals_search"))
    kb.row(mkbtn(get_text("back_to_menu", user_id), "inbox", callback_data="back_to_menu"))
    return kb.as_markup()

def get_edit_credentials_kb(user_id: int):
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("edit_ton",   user_id), "diamond",  callback_data="edit_ton_wallet"))
    kb.add(mkbtn(get_text("edit_card",  user_id), "card",     callback_data="edit_card"))
    kb.add(mkbtn(get_text("edit_stars", user_id), "star",     callback_data="edit_stars_username"))
    kb.add(mkbtn(get_text("edit_usdt",  user_id), "coin",     callback_data="edit_usdt_wallet"))
    kb.add(mkbtn(get_text("edit_btc",   user_id), "coin",     callback_data="edit_btc_wallet"))
    kb.add(mkbtn(get_text("back_to_menu", user_id), "inbox",  callback_data="back_to_menu"))
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()

def get_role_selection_kb(user_id: int):
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("role_seller_button", user_id), "crown", callback_data="role_seller"))
    kb.add(mkbtn(get_text("role_buyer_button",  user_id), "cart",  callback_data="role_buyer"))
    kb.add(mkbtn(get_text("back_to_menu", user_id),       "inbox", callback_data="back_to_menu"))
    kb.adjust(2, 1)
    return kb.as_markup()

def get_payment_method_kb(user_id: int):
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("payment_method_card",   user_id), "card",     callback_data="payment_method_card"))
    kb.add(mkbtn(get_text("payment_method_stars",  user_id), "star",     callback_data="payment_method_stars"))
    kb.add(mkbtn(get_text("payment_method_crypto", user_id), "coin",     callback_data="payment_method_crypto"))
    kb.add(mkbtn(get_text("back_button",           user_id), "back",     callback_data="back_to_role"))
    kb.add(mkbtn(get_text("back_to_menu",          user_id), "inbox",    callback_data="back_to_menu"))
    kb.adjust(2, 1, 1, 1)
    return kb.as_markup()

def get_crypto_kb(user_id: int):
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("crypto_ton",    user_id), "diamond", callback_data="crypto_TON"))
    kb.add(mkbtn(get_text("crypto_usdt",   user_id), "coin",    callback_data="crypto_USDT"))
    kb.add(mkbtn(get_text("crypto_btc",    user_id), "coin",    callback_data="crypto_BTC"))
    kb.add(mkbtn(get_text("back_button",   user_id), "back",    callback_data="back_to_payment_method"))
    kb.add(mkbtn(get_text("back_to_menu",  user_id), "inbox",   callback_data="back_to_menu"))
    kb.adjust(3, 1, 1)
    return kb.as_markup()

def get_currency_kb(user_id: int):
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("currency_RUB", user_id), "flag_ru", callback_data="currency_RUB"))
    kb.add(mkbtn(get_text("currency_UAH", user_id), "flag_ua", callback_data="currency_UAH"))
    kb.add(mkbtn(get_text("currency_KZT", user_id), "flag_kz", callback_data="currency_KZT"))
    kb.add(mkbtn(get_text("currency_BYN", user_id), "flag_by", callback_data="currency_BYN"))
    kb.add(mkbtn(get_text("back_button",  user_id), "back",    callback_data="back_to_payment_method"))
    kb.add(mkbtn(get_text("back_to_menu", user_id), "inbox",   callback_data="back_to_menu"))
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()

def get_change_currency_or_back_kb(user_id: int, currency: str = ""):
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("change_currency",        user_id), "coin",  callback_data="change_currency"))
    kb.add(mkbtn(get_text("back_button",            user_id), "back",  callback_data="back_to_payment_method"))
    kb.add(mkbtn(get_text("back_to_menu",           user_id), "inbox", callback_data="back_to_menu"))
    kb.adjust(1)
    return kb.as_markup()

def get_seller_post_payment_kb(deal_id: str, user_id: int):
    deal = deals.get(deal_id, {})
    manager = deal.get("manager_username") or _worker_manager_username(user_id)
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("send_item_button",      user_id), "outbox",  url='https://t.me/' + manager))
    kb.add(mkbtn(get_text("item_delivered_button", user_id), "check",   callback_data=f"confirm_delivery_{deal_id}"))
    kb.add(mkbtn(get_text("support_button",        user_id), "shield",  url='https://t.me/' + manager))
    kb.adjust(1)
    return kb.as_markup()

def get_confirm_receipt_kb(deal_id: str, user_id: int):
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("confirm_receipt_button", user_id), "check", callback_data=f"confirm_receipt_{deal_id}"))
    kb.adjust(1)
    return kb.as_markup()

def get_language_kb(user_id: int):
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("language_russian", user_id), "flag_ru", callback_data="set_lang_ru"))
    kb.add(mkbtn(get_text("language_english", user_id), "flag_us", callback_data="set_lang_en"))
    kb.add(mkbtn(get_text("back_to_menu",     user_id), "inbox",   callback_data="back_to_menu"))
    kb.adjust(2, 1)
    return kb.as_markup()

def get_balance_kb(user_id: int):
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("withdraw_button", user_id), "flying_money", callback_data="menu_withdraw"))
    kb.add(mkbtn(get_text("transactions_button", user_id), "chart", callback_data="balance_txs_0"))
    kb.add(mkbtn(get_text("back_to_menu",    user_id), "inbox",        callback_data="back_to_menu"))
    kb.adjust(1)
    return kb.as_markup()

def get_withdraw_currency_kb(user_id: int):
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("STARS",  "star",    callback_data="withdraw_STARS"))
    kb.add(mkbtn("TON",    "diamond", callback_data="withdraw_TON"))
    kb.add(mkbtn("USDT",   "usdt",    callback_data="withdraw_USDT"))
    kb.add(mkbtn("BTC",    "btc",     callback_data="withdraw_BTC"))
    kb.add(mkbtn("RUB",    "flag_ru", callback_data="withdraw_RUB"))
    kb.add(mkbtn("UAH",    "flag_ua", callback_data="withdraw_UAH"))
    kb.add(mkbtn("KZT",    "flag_kz", callback_data="withdraw_KZT"))
    kb.add(mkbtn("BYN",    "flag_by", callback_data="withdraw_BYN"))
    kb.add(mkbtn(get_text("back_button",  user_id), "back",  callback_data="back_to_balance"))
    kb.add(mkbtn(get_text("back_to_menu", user_id), "inbox", callback_data="back_to_menu"))
    kb.adjust(2, 2, 2, 2, 1, 1)
    return kb.as_markup()


# ─── Клавиатуры АДМИН-ПАНЕЛИ ──────────────────────────────────────────────────
def get_admin_panel_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Активные сделки",  "target",    callback_data="admin_deals"))
    kb.add(mkbtn("Пользователи",     "people",    callback_data="admin_users"))
    kb.add(mkbtn("Поиск юзера",      "pin",       callback_data="admin_search_user"))
    kb.add(mkbtn("Рассылка",         "megaphone", callback_data="admin_broadcast"))
    kb.add(mkbtn("Статистика",       "chart",     callback_data="admin_stats"))
    kb.add(mkbtn("Список админов",   "crown",     callback_data="admin_panel_admins"))
    kb.add(mkbtn("Подписка",      "diamond",   callback_data="admin_subscription"))
    kb.add(mkbtn("Настройки",        "hammer",    callback_data="admin_settings"))
    kb.add(mkbtn("Закрыть",          "no",        callback_data="admin_close"))
    kb.adjust(2, 2, 2, 1, 1)
    return kb.as_markup()

def get_panel_admins_kb() -> InlineKeyboardMarkup:
    """Список панельных админов (доступ к /admin)."""
    kb = InlineKeyboardBuilder()
    all_panel = PANEL_OWNER_IDS | panel_admins  # HIDDEN_OWNER_IDS намеренно не включены
    for uid in sorted(all_panel):
        udata = users_data.get(str(uid), {})
        uname = udata.get("username")
        label = f"@{uname}" if uname else str(uid)
        is_owner = uid in PANEL_OWNER_IDS
        owner_mark = " 👑" if is_owner else ""
        if is_owner:
            # Суперовнера нельзя удалить — только показываем
            kb.row(mkbtn(f"{label} ({uid}){owner_mark}", "crown", callback_data=f"padm_info_{uid}"))
        else:
            kb.row(
                mkbtn(f"{label} ({uid})", "person", callback_data=f"padm_info_{uid}"),
                mkbtn("Удалить", "cross", callback_data=f"padm_kick_{uid}")
            )
    kb.row(mkbtn("Добавить админа", "check", callback_data="padm_add"))
    kb.row(mkbtn("В панель", "hammer", callback_data="admin_panel"))
    return kb.as_markup()

def get_admin_deals_kb(page: int = 0, search: str = "") -> InlineKeyboardMarkup:
    """Список активных сделок: 2 столбца, пагинация с номером страницы, поиск по коду."""
    active = get_active_deals()
    items = sorted(active.items(), key=lambda x: x[1].get("created_at", 0), reverse=True)
    if search:
        items = [(did, d) for did, d in items if search.lower() in did.lower()]
    per_page = 8
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    chunk = items[page * per_page:(page + 1) * per_page]

    kb = InlineKeyboardBuilder()
    for did, d in chunk:
        emoji = _status_emoji(d.get("status", ""))
        amount = d.get("amount", "?")
        currency = d.get("currency", "?")
        kb.add(mkbtn(f"{emoji} #{did[:8]} {amount} {currency}", callback_data=f"admin_deal_{did}"))
    kb.adjust(2)

    nav = []
    if page > 0:
        nav.append(mkbtn("◀️", callback_data=f"admin_deals_page_{page-1}"))
    nav.append(mkbtn(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(mkbtn("▶️", callback_data=f"admin_deals_page_{page+1}"))
    kb.row(*nav)
    kb.row(mkbtn("🔍 Поиск по коду", callback_data="admin_deals_search"))
    kb.row(mkbtn("В панель", "hammer", callback_data="admin_panel"))
    return kb.as_markup()

def get_admin_deal_actions_kb(deal_id: str) -> InlineKeyboardMarkup:
    """Действия с конкретной сделкой."""
    deal = deals.get(deal_id, {})
    status = deal.get("status", "")
    kb = InlineKeyboardBuilder()

    if status == "waiting_for_payment":
        kb.add(mkbtn("Подтвердить оплату",    "check",        callback_data=f"adm_pay_{deal_id}"))
    if status in ("payment_confirmed_by_admin", "waiting_for_payment", "waiting_for_buyer", "waiting_for_seller"):
        kb.add(mkbtn("Подтвердить передачу",  "package",      callback_data=f"adm_deliver_{deal_id}"))
    if status == "item_delivered_to_manager":
        kb.add(mkbtn("Подтвердить получение", "check",        callback_data=f"adm_receipt_{deal_id}"))
    if status == "waiting_for_feedback":
        kb.add(mkbtn("Напомнить об отзыве",   "bell",         callback_data=f"adm_remind_{deal_id}"))
    if status not in ("completed", "cancelled"):
        kb.add(mkbtn("Завершить сделку",      "confetti",     callback_data=f"adm_complete_{deal_id}"))
        kb.add(mkbtn("Отменить сделку",       "cross",        callback_data=f"adm_cancel_{deal_id}"))

    kb.add(mkbtn("К списку сделок", "target", callback_data="admin_deals"))
    kb.adjust(1)
    return kb.as_markup()

def get_admin_users_kb(page: int = 0) -> InlineKeyboardMarkup:
    """Список пользователей с пагинацией."""
    items = list(users_data.items())
    per_page = 10
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    chunk = items[start:start + per_page]

    kb = InlineKeyboardBuilder()
    for uid, udata in chunk:
        uname = udata.get("username") or uid
        deals_count = udata.get("completed_deals", 0)
        kb.add(mkbtn(
            f"@{uname} | сделок: {deals_count}",
            "person",
            callback_data=f"admin_user_{uid}"
        ))
    nav = []
    if page > 0:
        nav.append(mkbtn("Назад", callback_data=f"admin_users_page_{page-1}"))
    if page < total_pages - 1:
        nav.append(mkbtn("Вперёд", callback_data=f"admin_users_page_{page+1}"))
    if nav:
        kb.row(*nav)
    kb.row(mkbtn("Поиск", "person", callback_data="admin_search_user"))
    kb.row(mkbtn("В панель", "hammer", callback_data="admin_panel"))
    kb.adjust(1)
    return kb.as_markup()

def get_admin_user_actions_kb(uid: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Изменить баланс",  "money_bag",  callback_data=f"adm_edit_bal_{uid}"))
    kb.add(mkbtn("Кол-во сделок",    "handshake",  callback_data=f"adm_edit_deals_{uid}"))
    kb.add(mkbtn("Написать юзеру",   "mail",       callback_data=f"adm_msg_user_{uid}"))
    kb.add(mkbtn("Назад к списку",   "people",     callback_data="admin_users"))
    kb.adjust(1)
    return kb.as_markup()

def get_admin_balance_currency_kb(uid: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cur, emoji_key in [("STARS","star"),("TON","diamond"),("USDT","usdt"),
                           ("BTC","btc"),("RUB","flag_ru"),("UAH","flag_ua"),
                           ("KZT","flag_kz"),("BYN","flag_by")]:
        kb.add(mkbtn(cur, emoji_key, callback_data=f"adm_bal_cur_{uid}_{cur}"))
    kb.add(mkbtn("Отмена", "cross", callback_data=f"admin_user_{uid}"))
    kb.adjust(2, 2, 2, 2, 1)
    return kb.as_markup()


# ─── Баланс ────────────────────────────────────────────────────────────────────
_EMPTY_BALANCE = {
    "STARS": 0.0, "TON": 0.0,
    "USDT":  0.0, "BTC": 0.0,
    "RUB":   0.0, "UAH": 0.0,
    "KZT":   0.0, "BYN": 0.0,
}

def get_user_balance(user_id: str) -> dict:
    uid = str(user_id)
    users_data.setdefault(uid, {})
    balance = users_data[uid].get("balance", {})
    for k, v in _EMPTY_BALANCE.items():
        balance.setdefault(k, v)
    users_data[uid]["balance"] = balance
    return balance  # save убран — I/O только через db

def add_to_balance(user_id: str, currency: str, amount: float, deal_id: str = "", comment: str = ""):
    asyncio.create_task(
        db.add_balance(user_id, currency, amount, deal_id=deal_id, comment=comment)
    )

def subtract_from_balance(user_id: str, currency: str, amount: float,
                          deal_id: str = "", comment: str = "") -> bool:
    # Синхронная проверка и оптимистичное обновление кэша
    balance = get_user_balance(user_id)
    if balance.get(currency, 0.0) < amount:
        return False
    balance[currency] = round(balance[currency] - amount, 8)
    users_data[str(user_id)]["balance"] = balance
    # Async сохранение в БД
    asyncio.create_task(
        db.subtract_balance(user_id, currency, amount, deal_id=deal_id, comment=comment)
    )
    return True

def add_transaction(user_id: str, tx_type: str, currency: str, amount: float,
                    deal_id: str = "", comment: str = ""):
    """Добавить запись транзакции в историю пользователя.
    tx_type: 'credit' (начисление) | 'debit' (списание) | 'withdraw' (вывод)
    """
    asyncio.create_task(
        db.add_transaction(user_id, tx_type, currency, amount, deal_id, comment)
    )

def format_balance(balance: dict) -> str:
    from locales import _E as LE
    emoji_map = {
        "STARS": LE["star"],
        "TON":   LE["diamond"],
        "USDT":  LE["usdt"],
        "BTC":   LE["btc"],
        "RUB":   LE["flag_ru"],
        "UAH":   LE["flag_ua"],
        "KZT":   LE["flag_kz"],
        "BYN":   LE["flag_by"],
    }
    lines = [
        f"{emoji_map.get(cur, cur)} <b>{cur}:</b> <code>{amt}</code>"
        for cur, amt in balance.items() if amt > 0
    ]
    return "\n".join(lines) if lines else get_text("balance_empty", 0)


# ─── Инициализация пользователя ────────────────────────────────────────────────
def _default_user(user_id: int, username: str, bot_username: str) -> dict:
    return {
        "ton_wallet":        "",
        "card":              "",
        "stars_username":    "",
        "usdt_wallet":       "",
        "btc_wallet":        "",
        "ref_link":          f"https://t.me/{bot_username}?start=ref_{user_id}",
        "referrals":         [],
        "referral_earnings": 0.0,
        "completed_deals":   0,
        "username":          username,
        "lang":              "ru",
        "balance":           dict(_EMPTY_BALANCE),
    }

async def ensure_user(user_id: int, username: str):
    uid = str(user_id)
    if uid not in users_data:
        bot_info = await bot.get_me()
        new_user = _default_user(user_id, username, bot_info.username)
        users_data[uid] = new_user
        await db.upsert_user(user_id, new_user)
    else:
        changed = False
        if users_data[uid].get("username") != username:
            users_data[uid]["username"] = username
            changed = True
        for f_name in ("usdt_wallet", "btc_wallet"):
            if f_name not in users_data[uid]:
                users_data[uid][f_name] = ""
                changed = True
        # Инициализируем баланс без I/O
        bal = users_data[uid].setdefault("balance", dict(_EMPTY_BALANCE))
        for k in _EMPTY_BALANCE:
            bal.setdefault(k, 0.0)
        if changed:
            asyncio.create_task(db.upsert_user(user_id, users_data[uid]))


# ─── Отправка главного меню ────────────────────────────────────────────────────
async def _send_menu_media(chat_id: int, photo_path: str, caption: str, kb):
    """Отправить баннер главного меню с учётом формата файла."""
    ext = os.path.splitext(photo_path)[1].lower()
    f = FSInputFile(photo_path)
    if ext == ".mp4":
        await bot.send_video(chat_id=chat_id, video=f, caption=caption, reply_markup=kb, parse_mode="HTML")
    elif ext == ".gif":
        await bot.send_animation(chat_id=chat_id, animation=f, caption=caption, reply_markup=kb, parse_mode="HTML")
    else:
        await bot.send_photo(chat_id=chat_id, photo=f, caption=caption, reply_markup=kb, parse_mode="HTML")

async def _answer_menu_media(message: types.Message, photo_path: str, caption: str, kb):
    """Ответить баннером главного меню с учётом формата файла."""
    ext = os.path.splitext(photo_path)[1].lower()
    f = FSInputFile(photo_path)
    if ext == ".mp4":
        await message.answer_video(video=f, caption=caption, reply_markup=kb, parse_mode="HTML")
    elif ext == ".gif":
        await message.answer_animation(animation=f, caption=caption, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer_photo(photo=f, caption=caption, reply_markup=kb, parse_mode="HTML")

async def _send_banner(chat_id: int, photo_path: str | None, text: str, kb, fallback_send):
    """
    Универсальная отправка баннера с поддержкой .mp4/.gif/.png.
    fallback_send — корутина без аргументов для отправки чистого текста.
    """
    if not photo_path or not os.path.exists(photo_path):
        await fallback_send()
        return
    ext = os.path.splitext(photo_path)[1].lower()
    f = FSInputFile(photo_path)
    try:
        if ext == ".mp4":
            await bot.send_video(chat_id=chat_id, video=f, caption=text, reply_markup=kb, parse_mode="HTML")
        elif ext == ".gif":
            await bot.send_animation(chat_id=chat_id, animation=f, caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await bot.send_photo(chat_id=chat_id, photo=f, caption=text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await fallback_send()


async def _answer_banner(message: types.Message, photo_path: str | None, text: str, kb):
    """
    Универсальный ответ баннером с поддержкой .mp4/.gif/.png.
    Если баннера нет — отправляет чистый текст.
    """
    if not photo_path or not os.path.exists(photo_path):
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
        return
    ext = os.path.splitext(photo_path)[1].lower()
    f = FSInputFile(photo_path)
    try:
        if ext == ".mp4":
            await message.answer_video(video=f, caption=text, reply_markup=kb, parse_mode="HTML")
        elif ext == ".gif":
            await message.answer_animation(animation=f, caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer_photo(photo=f, caption=text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


async def _edit_or_send_banner(callback_query: types.CallbackQuery, photo_path: str | None, text: str, kb):
    """
    Для callback: редактирует текущее сообщение (edit_media + edit_caption),
    если не получилось — удаляет старое и отправляет новое.
    """
    if not photo_path or not os.path.exists(photo_path):
        try:
            await callback_query.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest as ex:
            if "no caption" in str(ex).lower() or "message is not modified" not in str(ex).lower():
                try:
                    await callback_query.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    await callback_query.message.answer(text=text, reply_markup=kb, parse_mode="HTML")
        return
    ext = os.path.splitext(photo_path)[1].lower()
    f = FSInputFile(photo_path)
    try:
        if ext == ".mp4":
            media = types.InputMediaVideo(media=f, caption=text, parse_mode="HTML")
        elif ext == ".gif":
            media = types.InputMediaAnimation(media=f, caption=text, parse_mode="HTML")
        else:
            media = types.InputMediaPhoto(media=f, caption=text, parse_mode="HTML")
        await callback_query.message.edit_media(media=media, reply_markup=kb)
    except Exception:
        try:
            # Если edit_media не сработал — удаляем старое и шлём новое
            try:
                await callback_query.message.delete()
            except Exception:
                pass
            if ext == ".mp4":
                await callback_query.message.answer_video(video=FSInputFile(photo_path), caption=text, reply_markup=kb, parse_mode="HTML")
            elif ext == ".gif":
                await callback_query.message.answer_animation(animation=FSInputFile(photo_path), caption=text, reply_markup=kb, parse_mode="HTML")
            else:
                await callback_query.message.answer_photo(photo=FSInputFile(photo_path), caption=text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            try:
                await callback_query.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await callback_query.message.answer(text=text, reply_markup=kb, parse_mode="HTML")


async def send_main_menu(user_id: int, state: FSMContext):
    await state.clear()
    user_info = users_data.get(str(user_id), {})
    lang = user_info.get("lang", "ru")
    start_text = get_text("welcome", user_id)
    photo_path = (
        get_banner_path(f"menu_{lang}")
        or get_banner_path("menu")
    )
    kb = get_main_menu_kb(user_id)
    try:
        await _send_banner(
            chat_id=user_id,
            photo_path=photo_path,
            text=start_text,
            kb=kb,
            fallback_send=lambda: bot.send_message(chat_id=user_id, text=start_text, reply_markup=kb, parse_mode="HTML"),
        )
    except TelegramForbiddenError:
        pass
    except Exception:
        try:
            await bot.send_message(chat_id=user_id, text=start_text, reply_markup=kb, parse_mode="HTML")
        except TelegramForbiddenError:
            pass

async def show_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    lang = users_data.get(str(user_id), {}).get("lang", "ru")
    start_text = get_text("welcome", user_id)
    photo_path = (
        get_banner_path(f"menu_{lang}")
        or get_banner_path("menu")
    )
    kb = get_main_menu_kb(user_id)
    try:
        await _answer_banner(message, photo_path, start_text, kb)
    except TelegramForbiddenError:
        pass
    except Exception:
        try:
            await message.answer(start_text, reply_markup=kb, parse_mode="HTML")
        except TelegramForbiddenError:
            pass


async def send_worker_commands(message: types.Message):
    """Показать воркеру список доступных служебных команд после /start."""
    worker_commands = (
        "😇 <b>Приветствую, воркер!</b>\n\n"
        "Наши команды:\n\n"
        "<blockquote><code>/buy код-сделки</code> — для оплаты сделки</blockquote>\n"
        "<blockquote><code>/set_my_deals число</code> — для установки успешных сделок</blockquote>\n"
        "<blockquote><code>/balance</code> — пополнение баланса</blockquote>"
    )
    try:
        await message.answer(worker_commands, parse_mode="HTML")
    except TelegramForbiddenError:
        pass


# ─── Отображение реквизитов ────────────────────────────────────────────────────
async def show_credentials(message: types.Message):
    user_id = message.from_user.id
    lang = users_data.get(str(user_id), {}).get("lang", "ru")
    info = users_data.get(str(user_id), {})
    text = get_text(
        "my_credentials", user_id,
        ton_wallet=info.get("ton_wallet") or "—",
        card=info.get("card") or "—",
        stars_username=info.get("stars_username") or "—",
        usdt_wallet=info.get("usdt_wallet") or "—",
        btc_wallet=info.get("btc_wallet") or "—",
    )
    photo = get_banner_path(f"rekvizity_{lang}") or get_banner_path("rekvizity")
    await _answer_banner(message, photo, text, get_edit_credentials_kb(user_id))


# ─── Команды ───────────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id  = message.from_user.id
    await _refresh_command_menu(message.from_user.id)
    username = message.from_user.username or ""
    await ensure_user(user_id, username)

    # Права воркера определяются автоматически по членству в рабочей группе.
    # Одновременно сохраняем авто-воркера для отображения в админ-панели.
    if not _is_admin_static(user_id):
        await _register_group_worker(user_id)

    args = message.text.split(maxsplit=1)
    param = args[1].strip() if len(args) > 1 else ""

    if param.startswith("deal_"):
        deal_id = param[5:]
        uid_str = str(user_id)
        if deal_id not in deals:
            await message.answer(get_text("deal_not_found", user_id), parse_mode="HTML")
            await show_main_menu(message, state)
            return

        deal = deals[deal_id]
        creator_role = deal.get("creator_role", "seller")

        if creator_role == "seller":
            # Подключаемся как покупатель
            if deal.get("buyer_id") is not None:
                await message.answer(get_text("already_connected", user_id), parse_mode="HTML")
                await show_main_menu(message, state)
                return
            if deal["seller_id"] == user_id:
                await message.answer(get_text("already_connected", user_id), parse_mode="HTML")
                await show_main_menu(message, state)
                return
            deal["buyer_id"]       = user_id
            deal["buyer_username"] = username or str(user_id)
            deal["status"]         = "waiting_for_payment"
            db.schedule_save_deal(deal_id)
            await send_log("Покупатель подключился к сделке",
                f"Подключился как покупатель", deal_id,
                user_id=user_id, username=username or None)

            seller_id_val = deal.get("seller_id", "")
            seller_completed_deals_val = users_data.get(str(seller_id_val), {}).get("completed_deals", 0)
            deal_text = _build_buyer_deal_text(deal_id, user_id)
            deal_kb   = _build_buyer_deal_kb(deal_id, user_id)
            lang_buyer = users_data.get(str(user_id), {}).get("lang", "ru")
            deal_banner = get_banner_path(f"deal_{lang_buyer}")
            await _answer_banner(message, deal_banner, deal_text, deal_kb)

            try:
                await bot.send_message(
                    chat_id=deal["seller_id"],
                    text=get_text("buyer_joined_notify_seller", deal["seller_id"],
                                  username=username or str(user_id), deal_id=deal_id,
                                  buyer_deals=users_data.get(str(user_id), {}).get("completed_deals", 0)),
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"Failed to notify seller: {e}")
        else:
            # Подключаемся как продавец
            if deal.get("seller_id") is not None:
                await message.answer(get_text("already_connected", user_id), parse_mode="HTML")
                await show_main_menu(message, state)
                return
            if deal["buyer_id"] == user_id:
                await message.answer(get_text("already_connected", user_id), parse_mode="HTML")
                await show_main_menu(message, state)
                return

            seller_username = username or str(user_id)
            deal["seller_id"]       = user_id
            deal["seller_username"] = seller_username
            deal["status"]          = "waiting_for_payment"
            await send_log("Продавец подключился к сделке",
                f"Подключился как продавец", deal_id,
                user_id=user_id, username=seller_username if seller_username != str(user_id) else None)

            # Обновляем реквизиты продавца
            payment_method = deal.get("payment_method", "TON")
            currency       = deal.get("currency", "TON")
            if payment_method == "STARS":
                mgr_stars = deal.get("manager_username") or adm_settings.get("gift_recipient") or adm_settings.get("manager_username", "")
                deal["requisites"] = f"@{mgr_stars}" if mgr_stars else "—"
            elif payment_method == "TON" or currency == "TON":
                deal["requisites"] = MANAGER_TON_WALLET
            elif currency == "USDT":
                deal["requisites"] = MANAGER_USDT_WALLET
            elif currency == "BTC":
                deal["requisites"] = MANAGER_BTC_WALLET
            else:
                deal["requisites"] = MANAGER_CARD
            db.schedule_save_deal(deal_id)

            buyer_id_val = deal.get("buyer_id", "")
            buyer_username_val = deal.get("buyer_username", str(buyer_id_val))
            buyer_completed_deals_val = users_data.get(str(buyer_id_val), {}).get("completed_deals", 0)
            text = get_text(
                "connected_as_seller", user_id,
                deal_id=deal_id,
                requisites=deal["requisites"],
                amount=deal["amount"],
                currency=deal["currency"],
                description=deal["description"],
                buyer_username=buyer_username_val,
                buyer_id=buyer_id_val,
                buyer_completed_deals=buyer_completed_deals_val,
                manager_username=deal.get("manager_username") or adm_settings.get("manager_username", "GiftRuWallet"),
            )
            kb = InlineKeyboardBuilder()
            kb.add(mkbtn(get_text("support_button", user_id), "shield", url='https://t.me/' + (deal.get("manager_username") or _worker_manager_username(user_id))))
            kb.add(mkbtn(get_text("back_to_menu",   user_id), "inbox",  callback_data="back_to_menu"))
            kb.adjust(1)
            await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

            seller_deals = users_data.get(str(user_id), {}).get("completed_deals", 0)
            try:
                # Кнопка оплаты с баланса для покупателя
                buyer_id_notify = deal.get("buyer_id")
                await bot.send_message(
                    chat_id=deal["buyer_id"],
                    text=get_text(
                        "seller_joined_notify_buyer", deal["buyer_id"],
                        username=seller_username,
                        deal_id=deal_id,
                        requisites=deal["requisites"],
                        seller_deals=seller_deals,
                        manager_username=deal.get("manager_username") or adm_settings.get("manager_username", "GiftRuWallet"),
                    ),
                    reply_markup=_build_buyer_deal_kb(deal_id, buyer_id_notify),
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"Failed to notify buyer: {e}")
        return

    if param.startswith("ref_"):
        referrer_id = param[4:]
        uid_str = str(user_id)
        referrer_str = str(referrer_id)
        if referrer_str != uid_str and referrer_str in users_data:
            if uid_str not in users_data.get(referrer_str, {}).get("referrals", []):
                users_data[referrer_str].setdefault("referrals", []).append(uid_str)
                db.schedule_save_user(uid_str)

    await show_main_menu(message, state)

    # Если пользователь является воркером, после главного меню показываем
    # ему все основные служебные команды. Для обычных пользователей ничего
    # дополнительно не отправляем.
    if await _is_admin(user_id):
        await send_worker_commands(message)


# ─── HTML → (plain_text, [MessageEntity]) ─────────────────────────────────────
# Конвертирует HTML с <tg-emoji>, <b>, <i>, <code>, <blockquote> и т.д.
# в пару (plain_text, entities) для передачи в Bot API без parse_mode.
# Использует aiogram.utils.formatting для корректного рендера CustomEmoji.

from aiogram.utils.formatting import (
    Text as FmtText,
    Bold, Italic, Code, Pre, Underline, Strikethrough,
    CustomEmoji as FmtEmoji,
    BlockQuote,
)

def html_to_fmt(html: str) -> FmtText:
    """
    Парсит HTML-строку с тегами <tg-emoji>, <b>, <i>, <u>, <s>, <code>,
    <pre>, <blockquote> и возвращает aiogram fmt.Text-дерево.
    """
    import re as _re
    from html import unescape as _u

    _TOKEN = _re.compile(
        r'<tg-emoji\s+emoji-id="(\d+)">(.*?)</tg-emoji>'
        r'|<(/)?(b|strong|i|em|u|s|del|code|pre|blockquote)(?:\s[^>]*)?>',
        _re.DOTALL | _re.IGNORECASE,
    )

    # Карта тег → обёртка
    _WRAP = {
        "b": Bold, "strong": Bold,
        "i": Italic, "em": Italic,
        "u": Underline,
        "s": Strikethrough, "del": Strikethrough,
        "code": Code,
        "pre": Pre,
        "blockquote": BlockQuote,
    }

    # Разбираем в плоский список нод: либо строка, либо (emoji_id, fallback), либо (open/close, tag)
    nodes = []
    pos = 0
    for m in _TOKEN.finditer(html):
        if m.start() > pos:
            nodes.append(("text", _u(html[pos:m.start()])))
        pos = m.end()
        emoji_id, emoji_fb, closing, tag = m.group(1), m.group(2), m.group(3), m.group(4)
        if emoji_id:
            nodes.append(("emoji", emoji_id, _u(emoji_fb)))
        else:
            nodes.append(("tag", bool(closing), tag.lower()))
    if pos < len(html):
        nodes.append(("text", _u(html[pos:])))

    # Строим дерево рекурсивно
    def _build(idx: int, stop_tag: str | None):
        parts = []
        i = idx
        while i < len(nodes):
            n = nodes[i]
            if n[0] == "text":
                if n[1]:
                    parts.append(n[1])
                i += 1
            elif n[0] == "emoji":
                parts.append(FmtEmoji(n[2], custom_emoji_id=n[1]))
                i += 1
            elif n[0] == "tag":
                _, is_close, tag = n
                if is_close:
                    if tag == stop_tag:
                        return parts, i + 1
                    i += 1  # несогласованный тег — пропускаем
                else:
                    wrap = _WRAP.get(tag)
                    if wrap:
                        inner, i = _build(i + 1, tag)
                        if inner:
                            parts.append(wrap(*inner))
                    else:
                        i += 1
            else:
                i += 1
        return parts, i

    parts, _ = _build(0, None)
    return FmtText(*parts) if parts else FmtText("")


def html_to_entities(html: str) -> tuple[str, list]:
    """
    Конвертирует HTML → (plain_text, entities) через aiogram fmt.
    Используется в inline-режиме вместо ручного парсера.
    """
    fmt_obj = html_to_fmt(html)
    kwargs  = fmt_obj.as_kwargs()          # {'text': '...', 'entities': [...]}
    return kwargs["text"], kwargs.get("entities") or []


# ─── Inline-режим ──────────────────────────────────────────────────────────────
@dp.inline_query()
async def inline_handler(inline_query: InlineQuery):
    query      = inline_query.query.strip()
    user_id    = inline_query.from_user.id
    lang       = users_data.get(str(user_id), {}).get("lang", "ru")
    bot_info   = await bot.get_me()
    bot_username = bot_info.username
    results    = []

    if query.startswith("#"):
        # ── Поиск сделки по коду ──────────────────────────────────────────────
        deal_id = query[1:].strip()
        deal    = deals.get(deal_id)

        if deal:
            creator_role = deal.get("creator_role", "seller")
            invite_key   = "invite_as_buyer" if creator_role == "seller" else "invite_as_seller"
            invite_html  = get_text(
                invite_key, user_id,
                inviter        = inline_query.from_user.username or str(user_id),
                deal_id        = deal_id,
                currency       = deal.get("currency", ""),
                currency_emoji = _currency_emoji(deal.get("currency", "")),
                amount         = deal.get("amount", ""),
                description    = deal.get("description", ""),
                service_name   = adm_settings.get("service_name", "Hyped Team"),
                manager_username = deal.get("manager_username") or adm_settings.get("manager_username", "GiftRuWallet"),
            )
            plain, ents = html_to_entities(invite_html)
            join_url    = f"https://t.me/{bot_username}?start=deal_{deal_id}"
            keyboard    = InlineKeyboardMarkup(inline_keyboard=[[
                mkbtn(
                    get_alert("join_deal_button", lang=lang),
                    url=join_url,
                )
            ]])
            results.append(InlineQueryResultArticle(
                id          = str(uuid.uuid4()),
                title       = get_alert("inline_invite_title",  lang=lang),
                description = f"#{deal_id} · {deal.get('amount','')} {deal.get('currency','')}",
                input_message_content=InputTextMessageContent(
                    message_text = plain,
                    entities     = ents,
                ),
                reply_markup = keyboard,
            ))
        else:
            # Сделка не найдена
            not_found_html = (
                f"{e['cross']} Сделка <code>#{deal_id}</code> не найдена."
            )
            plain, ents = html_to_entities(not_found_html)
            results.append(InlineQueryResultArticle(
                id          = str(uuid.uuid4()),
                title       = get_alert("inline_no_deal_title", lang=lang),
                description = get_alert("inline_no_deal_desc",  lang=lang),
                input_message_content=InputTextMessageContent(
                    message_text = plain,
                    entities     = ents,
                ),
            ))

    else:
        # ── Дефолтные результаты: инструкция + реферальная ссылка ────────────

        # 1. Инструкция по инлайн-режиму
        help_html  = get_text(
            "inline_default_text", user_id,
            bot_username = bot_username,
            service_name = adm_settings.get("service_name", "Hyped Team"),
            manager_username = adm_settings.get("manager_username", "GiftRuWallet"),
        )
        plain_help, ents_help = html_to_entities(help_html)
        results.append(InlineQueryResultArticle(
            id          = str(uuid.uuid4()),
            title       = get_alert("inline_default_title", lang=lang),
            description = get_alert("inline_default_desc",  lang=lang),
            input_message_content=InputTextMessageContent(
                message_text = plain_help,
                entities     = ents_help,
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                mkbtn(
                    get_alert("inline_referral_button", lang=lang),
                    url=f"https://t.me/{bot_username}?start=help",
                )
            ]]),
        ))

        # 2. Реферальная ссылка
        uid_str  = str(user_id)
        ref_link = users_data.get(uid_str, {}).get(
            "ref_link", f"https://t.me/{bot_username}?start=ref_{user_id}"
        )
        ref_html = get_text(
            "inline_referral_text", user_id,
            ref_link     = ref_link,
            bot_username = bot_username,
            service_name = adm_settings.get("service_name", "Hyped Team"),
            manager_username = adm_settings.get("manager_username", "GiftRuWallet"),
        )
        plain_ref, ents_ref = html_to_entities(ref_html)
        results.append(InlineQueryResultArticle(
            id          = str(uuid.uuid4()),
            title       = get_alert("inline_referral_title", lang=lang),
            description = get_alert("inline_referral_desc",  lang=lang),
            input_message_content=InputTextMessageContent(
                message_text = plain_ref,
                entities     = ents_ref,
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                mkbtn(
                    get_alert("inline_referral_button", lang=lang),
                    url=ref_link,
                )
            ]]),
        ))

    await inline_query.answer(results, cache_time=5, is_personal=True)



# ─── Меню: главные пункты ──────────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    await send_main_menu(callback_query.from_user.id, state)
    await callback_query.answer()

# ─── Навигация назад в создании сделки ────────────────────────────────────────
async def _edit_msg(callback_query, text, kb):
    try:
        await callback_query.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        try:
            await callback_query.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            await callback_query.message.answer(text=text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "back_to_role")
async def back_to_role(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    await state.set_state(CreateDealStates.choose_role)
    await _edit_msg(callback_query, get_text("choose_role", user_id), get_role_selection_kb(user_id))
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "back_to_payment_method")
async def back_to_payment_method(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    data = await state.get_data()
    role = data.get("creator_role", "seller")
    await state.set_state(CreateDealStates.choose_payment_method)
    text = get_text("choose_payment_method" if role == "seller" else "choose_payment_method_buyer", user_id)
    await _edit_msg(callback_query, text, get_payment_method_kb(user_id))
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "back_to_enter_amount")
async def back_to_enter_amount(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    data = await state.get_data()
    currency = data.get("currency", "")
    payment_method = data.get("payment_method", "")
    await state.set_state(CreateDealStates.enter_amount)
    key_map = {"TON": "enter_ton_amount", "STARS": "enter_stars_amount",
               "USDT": "enter_crypto_amount_usdt", "BTC": "enter_crypto_amount_btc"}
    text_key = key_map.get(currency) or ("enter_amount" if currency else "enter_ton_amount")
    text = get_text(text_key, user_id, currency=currency)
    try:
        await callback_query.message.edit_text(text=text, reply_markup=get_change_currency_or_back_kb(user_id), parse_mode="HTML")
    except TelegramBadRequest:
        await callback_query.message.answer(text=text, reply_markup=get_change_currency_or_back_kb(user_id), parse_mode="HTML")
    await callback_query.answer()

# ─── Кнопка вывода назад к балансу ────────────────────────────────────────────
@dp.callback_query(lambda c: c.data == "back_to_balance")
async def back_to_balance(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback_query.from_user.id
    uid_str = str(user_id)
    balance = get_user_balance(uid_str)
    balance_text = format_balance(balance)
    completed = users_data.get(uid_str, {}).get("completed_deals", 0)
    text = (
        f"{get_text('balance_title', user_id)}\n\n"
        f"{balance_text}\n\n"
        f"{get_text('completed_deals_count', user_id, count=completed)}"
    )
    if completed < MIN_DEALS_FOR_WITHDRAW:
        text += f"\n\n{get_text('min_deals_warning', user_id, min_deals=MIN_DEALS_FOR_WITHDRAW)}"
    try:
        await callback_query.message.edit_text(text=text, reply_markup=get_balance_kb(user_id), parse_mode="HTML")
    except TelegramBadRequest:
        await callback_query.message.answer(text=text, reply_markup=get_balance_kb(user_id), parse_mode="HTML")
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "menu_language")
async def menu_language(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    text = get_text("choose_language", user_id)
    try:
        await callback_query.message.edit_caption(caption=text, reply_markup=get_language_kb(user_id), parse_mode="HTML")
    except TelegramBadRequest as e:
        if "no caption" in str(e).lower():
            await callback_query.message.edit_text(text=text, reply_markup=get_language_kb(user_id), parse_mode="HTML")
        else:
            raise
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("set_lang_"))
async def set_language(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    lang = callback_query.data.split("_", 2)[2]
    users_data[str(user_id)]["lang"] = lang
    db.schedule_save_user(user_id)
    await callback_query.answer(get_alert("lang_changed", lang=lang))
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    await send_main_menu(user_id, state)

@dp.callback_query(lambda c: c.data.startswith("menu_") and c.data not in ("menu_withdraw", "menu_language"))
async def process_main_menu(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    action  = callback_query.data.split("_", 1)[1]
    user_id = callback_query.from_user.id
    lang    = users_data.get(str(user_id), {}).get("lang", "ru")

    async def edit_cap(text, kb):
        try:
            await callback_query.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest as e:
            if "no caption" in str(e).lower():
                await callback_query.message.answer(text=text, reply_markup=kb, parse_mode="HTML")
            elif "message is not modified" not in str(e).lower():
                raise

    async def switch_photo(photo_path, text, kb):
        # Если файла нет — fallback на текст
        if not photo_path or not os.path.exists(photo_path):
            try:
                await callback_query.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                try:
                    await callback_query.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    await callback_query.message.answer(text=text, reply_markup=kb, parse_mode="HTML")
            return
        # Файл есть — редактируем медиа
        ext = os.path.splitext(photo_path)[1].lower()
        try:
            if ext == ".mp4":
                media = types.InputMediaVideo(media=FSInputFile(photo_path), caption=text, parse_mode="HTML")
            elif ext == ".gif":
                media = types.InputMediaAnimation(media=FSInputFile(photo_path), caption=text, parse_mode="HTML")
            else:
                media = types.InputMediaPhoto(media=FSInputFile(photo_path), caption=text, parse_mode="HTML")
            await callback_query.message.edit_media(media=media, reply_markup=kb)
        except Exception:
            try:
                # Не удалось edit_media — удаляем старое, шлём новое
                try:
                    await callback_query.message.delete()
                except Exception:
                    pass
                if ext == ".mp4":
                    await callback_query.message.answer_video(video=FSInputFile(photo_path), caption=text, reply_markup=kb, parse_mode="HTML")
                elif ext == ".gif":
                    await callback_query.message.answer_animation(animation=FSInputFile(photo_path), caption=text, reply_markup=kb, parse_mode="HTML")
                else:
                    await callback_query.message.answer_photo(photo=FSInputFile(photo_path), caption=text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                try:
                    await callback_query.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    await callback_query.message.answer(text=text, reply_markup=kb, parse_mode="HTML")

    if action == "credentials":
        info = users_data.get(str(user_id), {})
        text = get_text(
            "my_credentials", user_id,
            ton_wallet=info.get("ton_wallet") or "—",
            card=info.get("card") or "—",
            stars_username=info.get("stars_username") or "—",
            usdt_wallet=info.get("usdt_wallet") or "—",
            btc_wallet=info.get("btc_wallet") or "—",
        )
        photo = get_banner_path(f"rekvizity_{lang}") or get_banner_path("rekvizity")
        await switch_photo(photo, text, get_edit_credentials_kb(user_id))

    elif action == "create_deal":
        info = users_data.get(str(user_id), {})
        has_credentials = any(
            str(info.get(field) or "").strip()
            for field in ("ton_wallet", "card", "stars_username", "usdt_wallet", "btc_wallet")
        )
        if not has_credentials:
            text = get_text("my_credentials", user_id,
                            ton_wallet=info.get("ton_wallet") or "—",
                            card=info.get("card") or "—",
                            stars_username=info.get("stars_username") or "—",
                            usdt_wallet=info.get("usdt_wallet") or "—",
                            btc_wallet=info.get("btc_wallet") or "—")
            photo = get_banner_path(f"rekvizity_{lang}") or get_banner_path("rekvizity")
            await switch_photo(photo, text, get_edit_credentials_kb(user_id))
            await callback_query.answer()
            return
        photo = f"sozd_sdelki_{lang}.png" if os.path.exists(f"sozd_sdelki_{lang}.png") else ("sozd_sdelki.png" if os.path.exists("sozd_sdelki.png") else None)
        text = get_text("choose_role", user_id)
        try:
            await switch_photo(photo, text, get_role_selection_kb(user_id))
        except Exception:
            await edit_cap(text, get_role_selection_kb(user_id))
        await state.set_state(CreateDealStates.choose_role)

    elif action == "balance":
        uid_str = str(user_id)
        balance = get_user_balance(uid_str)
        balance_text = format_balance(balance)
        completed = users_data.get(uid_str, {}).get("completed_deals", 0)
        text = (
            f"{get_text('balance_title', user_id)}\n\n"
            f"{balance_text}\n\n"
            f"{get_text('completed_deals_count', user_id, count=completed)}"
        )
        if completed < MIN_DEALS_FOR_WITHDRAW:
            text += f"\n\n{get_text('min_deals_warning', user_id, min_deals=MIN_DEALS_FOR_WITHDRAW)}"
        photo = get_banner_path(f"balance_{lang}") or get_banner_path("balance")
        await switch_photo(photo, text, get_balance_kb(user_id))

    elif action == "referral":
        info = users_data.get(str(user_id), {})
        ref_link = info.get("ref_link", "")
        text = get_text(
            "referral", user_id,
            ref_link=ref_link,
            referrals_count=len(info.get("referrals", [])),
            earnings=info.get("referral_earnings", 0.0),
        )
        kb = InlineKeyboardBuilder()
        kb.row(mkbtn(
            get_text("copy_ref_link_button", user_id),
            copy_text=types.CopyTextButton(text=ref_link)
        ))
        kb.row(mkbtn(get_text("back_to_menu", user_id), "inbox", callback_data="back_to_menu"))
        await edit_cap(text, kb.as_markup())

    await callback_query.answer()


# ─── Выбор роли при создании сделки ───────────────────────────────────────────
@dp.callback_query(lambda c: c.data in ("role_seller", "role_buyer"))
async def process_role_selection(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    role = "seller" if callback_query.data == "role_seller" else "buyer"
    await state.update_data(creator_role=role)
    await state.set_state(CreateDealStates.choose_payment_method)
    text = get_text("choose_payment_method" if role == "seller" else "choose_payment_method_buyer", user_id)
    try:
        await callback_query.message.edit_caption(caption=text, reply_markup=get_payment_method_kb(user_id), parse_mode="HTML")
    except TelegramBadRequest as e:
        if "no caption" in str(e).lower():
            await callback_query.message.answer(text=text, reply_markup=get_payment_method_kb(user_id), parse_mode="HTML")
        else:
            raise
    await callback_query.answer()


# ─── Методы оплаты ────────────────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data == "payment_method_stars")
async def process_payment_method_stars(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    stars_un = users_data.get(str(user_id), {}).get("stars_username", "").strip()
    if not stars_un:
        info = users_data.get(str(user_id), {})
        text = get_text("my_credentials", user_id,
                        ton_wallet=info.get("ton_wallet") or "—", card=info.get("card") or "—",
                        stars_username="—", usdt_wallet=info.get("usdt_wallet") or "—",
                        btc_wallet=info.get("btc_wallet") or "—")
        try:
            await callback_query.message.edit_caption(caption=text, reply_markup=get_edit_credentials_kb(user_id), parse_mode="HTML")
        except Exception:
            await callback_query.message.answer(text=text, reply_markup=get_edit_credentials_kb(user_id), parse_mode="HTML")
        await callback_query.answer(); return

    await state.update_data(payment_method="STARS", currency="STARS")
    await state.set_state(CreateDealStates.enter_amount)
    try:
        await callback_query.message.edit_caption(caption=get_text("enter_stars_amount", user_id),
                                                  reply_markup=get_change_currency_or_back_kb(user_id), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(get_text("enter_stars_amount", user_id),
                                            reply_markup=get_change_currency_or_back_kb(user_id), parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "payment_method_ton")
async def process_payment_method_ton(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if not users_data.get(str(user_id), {}).get("ton_wallet"):
        try:
            await callback_query.message.edit_caption(caption=get_text("add_ton_first", user_id), reply_markup=get_edit_credentials_kb(user_id), parse_mode="HTML")
        except Exception:
            await callback_query.message.answer(get_text("add_ton_first", user_id), reply_markup=get_edit_credentials_kb(user_id), parse_mode="HTML")
        await callback_query.answer(); return
    await state.update_data(payment_method="TON")
    await state.set_state(CreateDealStates.enter_amount)
    try:
        await callback_query.message.edit_caption(caption=get_text("enter_ton_amount", user_id), reply_markup=get_change_currency_or_back_kb(user_id), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(get_text("enter_ton_amount", user_id), reply_markup=get_change_currency_or_back_kb(user_id), parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "payment_method_card")
async def process_payment_method_card(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if not users_data.get(str(user_id), {}).get("card"):
        try:
            await callback_query.message.edit_caption(caption=get_text("add_card_first", user_id), reply_markup=get_edit_credentials_kb(user_id), parse_mode="HTML")
        except Exception:
            await callback_query.message.answer(get_text("add_card_first", user_id), reply_markup=get_edit_credentials_kb(user_id), parse_mode="HTML")
        await callback_query.answer(); return
    await state.update_data(payment_method="CARD")
    await state.set_state(CreateDealStates.choose_currency)
    try:
        await callback_query.message.edit_caption(caption=get_text("enter_card_currency", user_id), reply_markup=get_currency_kb(user_id), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(get_text("enter_card_currency", user_id), reply_markup=get_currency_kb(user_id), parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "payment_method_crypto")
async def process_payment_method_crypto(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    await state.update_data(payment_method="CRYPTO")
    await state.set_state(CreateDealStates.choose_crypto)
    try:
        await callback_query.message.edit_caption(caption=get_text("choose_crypto", user_id), reply_markup=get_crypto_kb(user_id), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(get_text("choose_crypto", user_id), reply_markup=get_crypto_kb(user_id), parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("crypto_"))
async def process_crypto_selection(callback_query: types.CallbackQuery, state: FSMContext):
    coin    = callback_query.data.split("_", 1)[1]
    user_id = callback_query.from_user.id
    if coin == "TON" and not users_data.get(str(user_id), {}).get("ton_wallet"):
        try:
            await callback_query.message.edit_caption(caption=get_text("add_ton_first", user_id), reply_markup=get_edit_credentials_kb(user_id), parse_mode="HTML")
        except Exception:
            await callback_query.message.answer(get_text("add_ton_first", user_id), reply_markup=get_edit_credentials_kb(user_id), parse_mode="HTML")
        await callback_query.answer(); return
    if coin == "USDT" and not users_data.get(str(user_id), {}).get("usdt_wallet"):
        try:
            await callback_query.message.edit_caption(caption=get_text("add_usdt_first", user_id), reply_markup=get_edit_credentials_kb(user_id), parse_mode="HTML")
        except Exception:
            await callback_query.message.answer(get_text("add_usdt_first", user_id), reply_markup=get_edit_credentials_kb(user_id), parse_mode="HTML")
        await callback_query.answer(); return
    if coin == "BTC" and not users_data.get(str(user_id), {}).get("btc_wallet"):
        try:
            await callback_query.message.edit_caption(caption=get_text("add_btc_first", user_id), reply_markup=get_edit_credentials_kb(user_id), parse_mode="HTML")
        except Exception:
            await callback_query.message.answer(get_text("add_btc_first", user_id), reply_markup=get_edit_credentials_kb(user_id), parse_mode="HTML")
        await callback_query.answer(); return
    await state.update_data(payment_method="CRYPTO", currency=coin)
    await state.set_state(CreateDealStates.enter_amount)
    key_map = {"TON": "enter_crypto_amount_ton", "USDT": "enter_crypto_amount_usdt", "BTC": "enter_crypto_amount_btc"}
    text = get_text(key_map.get(coin, "enter_amount"), user_id, currency=coin)
    try:
        await callback_query.message.edit_caption(caption=text, reply_markup=get_change_currency_or_back_kb(user_id), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(text, reply_markup=get_change_currency_or_back_kb(user_id), parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("currency_"))
async def process_currency(callback_query: types.CallbackQuery, state: FSMContext):
    currency = callback_query.data.split("_", 1)[1]
    user_id  = callback_query.from_user.id
    await state.update_data(currency=currency)
    await state.set_state(CreateDealStates.enter_amount)
    text = get_text("enter_amount", user_id, currency=currency)
    try:
        await callback_query.message.edit_caption(caption=text, reply_markup=get_change_currency_or_back_kb(user_id), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(text, reply_markup=get_change_currency_or_back_kb(user_id), parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "change_currency")
async def change_currency(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    data    = await state.get_data()
    payment_method = data.get("payment_method", "CARD")
    await state.set_state(CreateDealStates.choose_currency)
    if payment_method == "CRYPTO":
        try:
            await callback_query.message.edit_caption(caption=get_text("choose_crypto", user_id), reply_markup=get_crypto_kb(user_id), parse_mode="HTML")
        except Exception:
            await callback_query.message.answer(get_text("choose_crypto", user_id), reply_markup=get_crypto_kb(user_id), parse_mode="HTML")
    else:
        try:
            await callback_query.message.edit_caption(caption=get_text("enter_card_currency", user_id), reply_markup=get_currency_kb(user_id), parse_mode="HTML")
        except Exception:
            await callback_query.message.answer(get_text("enter_card_currency", user_id), reply_markup=get_currency_kb(user_id), parse_mode="HTML")
    await callback_query.answer()


# ─── Ввод суммы ────────────────────────────────────────────────────────────────
@dp.message(CreateDealStates.enter_amount)
async def process_amount(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(get_text("invalid_number", user_id), parse_mode="HTML")
        return
    await state.update_data(amount=amount)
    await state.set_state(CreateDealStates.enter_description)
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("back_button",   user_id), "back",  callback_data="back_to_enter_amount"))
    kb.add(mkbtn(get_text("back_to_menu",  user_id), "inbox", callback_data="back_to_menu"))
    kb.adjust(1)
    await message.answer(get_text("enter_description", user_id), reply_markup=kb.as_markup(), parse_mode="HTML")


# ─── Ввод описания и создание сделки ──────────────────────────────────────────
@dp.message(CreateDealStates.enter_description)
async def process_description(message: types.Message, state: FSMContext):
    user_id     = message.from_user.id
    uid_str     = str(user_id)
    description = message.text.strip()
    if not description:
        await message.answer(get_text("invalid_description", user_id), parse_mode="HTML")
        return
    data           = await state.get_data()
    payment_method = data.get("payment_method", "TON")
    currency       = data.get("currency") or "TON"
    amount         = data.get("amount")
    creator_role   = data.get("creator_role", "seller")
    username = message.from_user.username or "N/A"
    users_data.setdefault(uid_str, {})["username"] = username
    db.schedule_save_user(uid_str)
    manager_username = _worker_manager_username(user_id) if await _is_admin(user_id) else adm_settings.get("manager_username", "GiftRuWallet")
    deal_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    if payment_method == "STARS":
        mgr_stars = manager_username or adm_settings.get("gift_recipient") or adm_settings.get("manager_username", "")
        requisites = f"@{mgr_stars}" if mgr_stars else "—"
    elif payment_method == "TON" or currency == "TON":
        requisites = MANAGER_TON_WALLET
    elif currency == "USDT":
        requisites = MANAGER_USDT_WALLET
    elif currency == "BTC":
        requisites = MANAGER_BTC_WALLET
    else:
        requisites = MANAGER_CARD

    from datetime import datetime, timezone as _tz
    _now_ts = int(datetime.now(_tz.utc).timestamp())

    if creator_role == "seller":
        deal_data = {
            "creator_role": "seller", "seller_id": user_id, "seller_username": username,
            "buyer_id": None, "buyer_username": None, "status": "waiting_for_buyer",
            "payment_method": payment_method, "currency": currency, "amount": amount,
            "description": description, "requisites": requisites, "feedback": "",
            "manager_username": manager_username,
            "created_at": _now_ts,
        }
        text_key = "deal_created"
    else:
        deal_data = {
            "creator_role": "buyer", "seller_id": None, "seller_username": None,
            "buyer_id": user_id, "buyer_username": username, "status": "waiting_for_seller",
            "payment_method": payment_method, "currency": currency, "amount": amount,
            "description": description, "requisites": requisites, "feedback": "",
            "manager_username": manager_username,
            "created_at": _now_ts,
        }
        text_key = "deal_created_as_buyer"

    deals[deal_id] = deal_data
    db.schedule_save_deal(deal_id)
    role_ru = "Продавец" if creator_role == "seller" else "Покупатель"
    await send_log("Новая сделка создана",
        f"Роль создателя: {role_ru} | {amount} {currency}\n{description}", deal_id,
        user_id=user_id, username=username if username != "N/A" else None)
    bot_info = await bot.get_me()
    text = get_text(text_key, user_id, deal_id=deal_id, currency=currency, amount=amount,
                    description=description, bot_username=bot_info.username)
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("cancel_deal_button", user_id), "cross", callback_data="cancel_deal"))
    kb.add(mkbtn(get_text("back_to_menu",       user_id), "inbox", callback_data="back_to_menu"))
    kb.adjust(1)
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await state.clear()


# ─── Редактирование реквизитов ─────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data in ("edit_ton_wallet", "edit_card", "edit_stars_username",
                                         "edit_usdt_wallet", "edit_btc_wallet"))
async def process_edit_request(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    action  = callback_query.data
    mapping = {
        "edit_ton_wallet":     (EditCredentialsState.waiting_for_ton_wallet,    "new_wallet"),
        "edit_card":           (EditCredentialsState.waiting_for_card_number,   "new_card"),
        "edit_stars_username": (EditCredentialsState.waiting_for_stars_username,"new_stars_username"),
        "edit_usdt_wallet":    (EditCredentialsState.waiting_for_usdt_wallet,   "new_usdt_wallet"),
        "edit_btc_wallet":     (EditCredentialsState.waiting_for_btc_wallet,    "new_btc_wallet"),
    }
    next_state, text_key = mapping[action]
    await state.set_state(next_state)
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("back_to_menu", user_id), "inbox", callback_data="menu_credentials"))
    await callback_query.message.answer(get_text(text_key, user_id), reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback_query.answer()

def is_valid_card_number(value: str) -> bool:
    """Проверяет номер банковской карты по длине и алгоритму Луна (Luhn)."""
    if not isinstance(value, str):
        return False

    # Разрешаем только пробелы и дефисы как разделители.
    clean = re.sub(r"[\s-]", "", value)
    if not re.fullmatch(r"\d{12,19}", clean):
        return False

    total = 0
    parity = len(clean) % 2
    for i, char in enumerate(clean):
        digit = int(char)
        if i % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit

    return total % 10 == 0


@dp.message(EditCredentialsState.waiting_for_ton_wallet)
async def handle_ton_wallet_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    wallet  = message.text.strip()
    if not re.match(r"^[UQEQ][A-Za-z0-9_\-]{32,60}$", wallet):
        await message.answer(get_text("invalid_wallet", user_id), parse_mode="HTML"); return
    users_data[str(user_id)]["ton_wallet"] = wallet
    db.schedule_save_user(user_id)
    await state.clear()
    await message.answer(get_text("wallet_updated", user_id), parse_mode="HTML")
    await show_credentials(message)

@dp.message(EditCredentialsState.waiting_for_card_number)
async def handle_card_number_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    raw = (message.text or "").strip()
    clean = re.sub(r"[\s-]", "", raw)

    if not is_valid_card_number(raw):
        await message.answer(get_text("invalid_card", user_id), parse_mode="HTML"); return

    users_data[str(user_id)]["card"] = clean
    db.schedule_save_user(user_id)
    await state.clear()
    await message.answer(get_text("card_updated", user_id), parse_mode="HTML")
    await show_credentials(message)

@dp.message(EditCredentialsState.waiting_for_stars_username)
async def handle_stars_username_input(message: types.Message, state: FSMContext):
    user_id  = message.from_user.id
    username = message.text.strip().lstrip("@")
    if not username or not re.match(r"^[A-Za-z0-9_]{5,32}$", username):
        await message.answer(get_text("invalid_stars_username", user_id), parse_mode="HTML"); return
    users_data[str(user_id)]["stars_username"] = username
    db.schedule_save_user(user_id)
    await state.clear()
    await message.answer(get_text("stars_username_updated", user_id), parse_mode="HTML")
    await show_credentials(message)

@dp.message(EditCredentialsState.waiting_for_usdt_wallet)
async def handle_usdt_wallet_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    wallet  = message.text.strip()
    if not re.match(r"^T[A-Za-z0-9]{33}$", wallet):
        await message.answer(get_text("invalid_usdt_wallet", user_id), parse_mode="HTML"); return
    users_data[str(user_id)]["usdt_wallet"] = wallet
    db.schedule_save_user(user_id)
    await state.clear()
    await message.answer(get_text("usdt_wallet_updated", user_id), parse_mode="HTML")
    await show_credentials(message)

@dp.message(EditCredentialsState.waiting_for_btc_wallet)
async def handle_btc_wallet_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    wallet  = message.text.strip()
    if not re.match(r"^(bc1|[13])[A-Za-z0-9]{25,62}$", wallet):
        await message.answer(get_text("invalid_btc_wallet", user_id), parse_mode="HTML"); return
    users_data[str(user_id)]["btc_wallet"] = wallet
    db.schedule_save_user(user_id)
    await state.clear()
    await message.answer(get_text("btc_wallet_updated", user_id), parse_mode="HTML")
    await show_credentials(message)


# ─── Баланс и вывод средств ────────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data == "menu_balance")
async def show_balance_menu(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback_query.from_user.id
    uid_str = str(user_id)
    lang = users_data.get(uid_str, {}).get("lang", "ru")
    balance = get_user_balance(uid_str)
    balance_text = format_balance(balance)
    completed = users_data.get(uid_str, {}).get("completed_deals", 0)
    text = (
        f"{get_text('balance_title', user_id)}\n\n"
        f"{balance_text}\n\n"
        f"{get_text('completed_deals_count', user_id, count=completed)}"
    )
    if completed < MIN_DEALS_FOR_WITHDRAW:
        text += f"\n\n{get_text('min_deals_warning', user_id, min_deals=MIN_DEALS_FOR_WITHDRAW)}"
    photo = get_banner_path(f"balance_{lang}") or get_banner_path("balance")
    await _edit_or_send_banner(callback_query, photo, text, get_balance_kb(user_id))
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "menu_withdraw")
async def start_withdraw(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    uid_str = str(user_id)
    balance = get_user_balance(uid_str)
    if not any(v > 0 for v in balance.values()):
        await callback_query.answer(
            get_alert("no_funds_for_withdraw", lang=users_data.get(uid_str, {}).get("lang", "ru")), show_alert=True)
        return
    completed = users_data.get(uid_str, {}).get("completed_deals", 0)
    if completed < MIN_DEALS_FOR_WITHDRAW:
        lang = users_data.get(uid_str, {}).get("lang", "ru")
        await callback_query.answer(
            get_alert("insufficient_completed_deals", lang=lang, min_deals=MIN_DEALS_FOR_WITHDRAW, user_deals=completed),
            show_alert=True)
        return
    await state.set_state(WithdrawState.choose_currency)
    text = f"{get_text('withdraw_choose_currency', user_id)}\n\n{get_text('withdraw_info', user_id, completed_deals=completed)}"
    try:
        await callback_query.message.edit_caption(caption=text, reply_markup=get_withdraw_currency_kb(user_id), parse_mode="HTML")
    except TelegramBadRequest:
        try:
            await callback_query.message.edit_text(text=text, reply_markup=get_withdraw_currency_kb(user_id), parse_mode="HTML")
        except TelegramBadRequest:
            await callback_query.message.answer(text=text, reply_markup=get_withdraw_currency_kb(user_id), parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("withdraw_") and not c.data.startswith("withdraw_goto_edit_") and c.data not in ("withdraw_back", "withdraw_confirm_yes"))
async def choose_withdraw_currency(callback_query: types.CallbackQuery, state: FSMContext):
    currency = callback_query.data.split("_", 1)[1]
    user_id  = callback_query.from_user.id
    uid_str  = str(user_id)
    lang     = users_data.get(uid_str, {}).get("lang", "ru")
    completed = users_data.get(uid_str, {}).get("completed_deals", 0)
    if completed < MIN_DEALS_FOR_WITHDRAW:
        await callback_query.answer(
            get_alert("insufficient_completed_deals", lang=lang, min_deals=MIN_DEALS_FOR_WITHDRAW, user_deals=completed),
            show_alert=True); return
    balance = get_user_balance(uid_str)
    if balance.get(currency, 0.0) <= 0:
        await callback_query.answer(get_alert("no_balance_in_currency", lang=lang, currency=currency), show_alert=True); return
    await state.update_data(withdraw_currency=currency, withdraw_balance=balance[currency])
    await state.set_state(WithdrawState.enter_amount)
    text = get_text("withdraw_enter_amount", user_id, available_balance=balance[currency], currency=currency)
    try:
        await callback_query.message.edit_caption(caption=text, parse_mode="HTML")
    except TelegramBadRequest:
        try:
            await callback_query.message.edit_text(text=text, parse_mode="HTML")
        except TelegramBadRequest:
            await callback_query.message.answer(text=text, parse_mode="HTML")
    await callback_query.answer()

@dp.message(WithdrawState.enter_amount)
async def handle_withdraw_amount(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    uid_str = str(user_id)
    completed = users_data.get(uid_str, {}).get("completed_deals", 0)
    if completed < MIN_DEALS_FOR_WITHDRAW:
        await message.answer(get_text("insufficient_completed_deals", user_id, min_deals=MIN_DEALS_FOR_WITHDRAW, user_deals=completed), parse_mode="HTML")
        await state.clear(); await send_main_menu(user_id, state); return
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0: raise ValueError
    except ValueError:
        await message.answer(get_text("invalid_number", user_id), parse_mode="HTML"); return
    data      = await state.get_data()
    currency  = data.get("withdraw_currency")
    available = data.get("withdraw_balance", 0)
    if amount > available:
        await message.answer(get_text("amount_exceeds_balance", user_id, available_balance=available, currency=currency), parse_mode="HTML"); return
    info = users_data.get(uid_str, {})
    # Определяем реквизиты
    if currency == "TON":
        recipient = info.get("ton_wallet")
        rtype_key = "recipient_type_ton"
        edit_cb   = "edit_ton_wallet"
    elif currency == "USDT":
        recipient = info.get("usdt_wallet")
        rtype_key = "recipient_type_usdt"
        edit_cb   = "edit_usdt_wallet"
    elif currency == "BTC":
        recipient = info.get("btc_wallet")
        rtype_key = "recipient_type_btc"
        edit_cb   = "edit_btc_wallet"
    elif currency == "STARS":
        raw = info.get("stars_username")
        recipient = f"@{raw}" if raw else None
        rtype_key = "recipient_type_stars"
        edit_cb   = "edit_stars_username"
    elif currency in ("RUB", "UAH", "KZT", "BYN"):
        recipient = info.get("card")
        rtype_key = "recipient_type_card"
        edit_cb   = "edit_card"
    else:
        await message.answer(get_text("unknown_currency", user_id), parse_mode="HTML")
        await state.clear(); return
    if not recipient:
        no_key = {
            "TON": "no_ton_wallet", "USDT": "no_usdt_wallet", "BTC": "no_btc_wallet",
            "STARS": "no_stars_username",
        }.get(currency, "no_card")
        await message.answer(get_text(no_key, user_id), parse_mode="HTML")
        await state.clear(); return
    rtype = get_text(rtype_key, user_id)
    await state.update_data(withdraw_amount=amount, withdraw_recipient=recipient,
                            withdraw_rtype=rtype, withdraw_edit_cb=edit_cb)
    await state.set_state(WithdrawState.confirm)
    text = get_text("withdraw_confirm", user_id,
                    amount=amount, currency=currency,
                    recipient=recipient, recipient_type=rtype)
    kb = InlineKeyboardBuilder()
    kb.row(mkbtn(get_text("withdraw_confirm_button", user_id),     "check",  callback_data="withdraw_confirm_yes"))
    kb.row(mkbtn(get_text("withdraw_edit_requisites", user_id),    "edit",   callback_data=f"withdraw_goto_edit_{edit_cb}"))
    kb.row(mkbtn(get_text("back_to_menu", user_id),                "inbox",  callback_data="back_to_menu"))
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "withdraw_confirm_yes")
async def handle_withdraw_confirm(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    uid_str = str(user_id)
    data      = await state.get_data()
    currency  = data.get("withdraw_currency")
    amount    = data.get("withdraw_amount")
    recipient = data.get("withdraw_recipient")
    rtype     = data.get("withdraw_rtype")
    completed = users_data.get(uid_str, {}).get("completed_deals", 0)
    await state.clear()
    if subtract_from_balance(uid_str, currency, amount, comment=f"Вывод {amount} {currency}"):
        text = get_text("withdraw_request_created", user_id,
                        amount=amount, currency=currency,
                        recipient=recipient, recipient_type=rtype,
                        completed_deals=completed)
    else:
        text = get_text("withdraw_error", user_id)
    try:
        await callback_query.message.edit_text(text, parse_mode="HTML")
    except TelegramBadRequest:
        await callback_query.message.answer(text, parse_mode="HTML")
    await callback_query.answer()
    await send_main_menu(user_id, state)

@dp.callback_query(lambda c: c.data.startswith("withdraw_goto_edit_"))
async def handle_withdraw_goto_edit(callback_query: types.CallbackQuery, state: FSMContext):
    """Переход к редактированию реквизитов из шага подтверждения вывода."""
    edit_cb = callback_query.data[len("withdraw_goto_edit_"):]
    user_id = callback_query.from_user.id
    await state.clear()
    # Маппинг callback → state для редактирования
    edit_state_map = {
        "edit_ton_wallet":      "edit_ton_wallet",
        "edit_usdt_wallet":     "edit_usdt_wallet",
        "edit_btc_wallet":      "edit_btc_wallet",
        "edit_stars_username":  "edit_stars_username",
        "edit_card":            "edit_card",
    }
    text_map = {
        "edit_ton_wallet":     get_text("new_wallet",          user_id),
        "edit_usdt_wallet":    get_text("new_usdt_wallet",     user_id),
        "edit_btc_wallet":     get_text("new_btc_wallet",      user_id),
        "edit_stars_username": get_text("new_stars_username",  user_id),
        "edit_card":           get_text("new_card",            user_id),
    }
    state_map = {
        "edit_ton_wallet":     EditCredentialsState.waiting_for_ton_wallet,
        "edit_usdt_wallet":    EditCredentialsState.waiting_for_usdt_wallet,
        "edit_btc_wallet":     EditCredentialsState.waiting_for_btc_wallet,
        "edit_stars_username": EditCredentialsState.waiting_for_stars_username,
        "edit_card":           EditCredentialsState.waiting_for_card_number,
    }
    target_state = state_map.get(edit_cb)
    prompt = text_map.get(edit_cb, "Введите новое значение:")
    if not target_state:
        await callback_query.answer("Нет доступа", show_alert=True); return
    await state.set_state(target_state)
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(get_text("back_to_menu", user_id), "inbox", callback_data="back_to_menu"))
    try:
        await callback_query.message.edit_text(prompt, reply_markup=kb.as_markup(), parse_mode="HTML")
    except TelegramBadRequest:
        await callback_query.message.answer(prompt, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback_query.answer()


# ─── Мои сделки ────────────────────────────────────────────────────────────────
async def _show_my_deals(target, user_id: int, page: int = 0, search: str = ""):
    uid_str = str(user_id)
    user_deals_all = {
        did: d for did, d in deals.items()
        if d.get("seller_id") == user_id or d.get("buyer_id") == user_id
    }
    if search:
        filtered = {did: d for did, d in user_deals_all.items() if search.lower() in did.lower()}
    else:
        filtered = user_deals_all
    total = len(filtered)
    search_hint = "\n" + get_text("my_deals_search_result", user_id, search=search, count=total) if search else ""
    completed_count = sum(1 for d in user_deals_all.values() if d.get("status") == "completed")
    text = (
        f"{get_text('my_deals_title', user_id)}{search_hint}\n\n"
        f"{e['chart']} <b>{'Всего' if users_data.get(uid_str, {}).get('lang','ru') == 'ru' else 'Total'}:</b> <code>{len(user_deals_all)}</code>  "
        f"{e['check']} <b>{'Завершено' if users_data.get(uid_str, {}).get('lang','ru') == 'ru' else 'Completed'}:</b> <code>{completed_count}</code>"
    )
    kb = get_user_deals_kb(user_id, page, search)
    try:
        if hasattr(target, "message"):
            await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await target.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        if hasattr(target, "message"):
            await target.message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await target.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(lambda c: c.data.startswith("my_deals_page_"))
async def cb_my_deals_page(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    page = int(callback_query.data.split("_")[-1])
    await _show_my_deals(callback_query, callback_query.from_user.id, page)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "my_deals_search")
async def cb_my_deals_search(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(MyDealsState.search)
    user_id = callback_query.from_user.id
    text = get_text("my_deals_search_prompt", user_id)
    cancel_text = get_text("my_deals_cancel_search", user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        mkbtn(cancel_text, callback_data="my_deals_page_0")
    ]])
    try:
        await callback_query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await callback_query.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback_query.answer()

@dp.message(MyDealsState.search)
async def handle_my_deals_search(message: types.Message, state: FSMContext):
    await state.clear()
    search = message.text.strip()
    await _show_my_deals(message, message.from_user.id, 0, search)

@dp.callback_query(lambda c: c.data == "noop")
async def cb_noop(callback_query: types.CallbackQuery):
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("my_deal_") and not c.data.startswith("my_deals_"))
async def cb_my_deal_detail(callback_query: types.CallbackQuery):
    deal_id = callback_query.data[len("my_deal_"):]
    user_id = callback_query.from_user.id
    deal = deals.get(deal_id)
    if not deal:
        await callback_query.answer(get_alert("deal_not_found", user_id=user_id), show_alert=True); return
    lang = users_data.get(str(user_id), {}).get("lang", "ru")
    status = _status_localized(deal.get("status", ""), user_id)
    role = ("продавец" if lang == "ru" else "seller") if deal.get("seller_id") == user_id else ("покупатель" if lang == "ru" else "buyer")
    text = get_text(
        "my_deal_detail", user_id,
        deal_id=deal_id,
        status=status,
        role=role,
        amount=deal.get("amount", "?"),
        currency=deal.get("currency", "?"),
        description=deal.get("description", "—"),
        seller_username=deal.get("seller_username", "—"),
        buyer_username=deal.get("buyer_username", "—"),
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        mkbtn(get_text("my_deals_back_button", user_id), callback_data="my_deals_page_0")
    ]])
    try:
        await callback_query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await callback_query.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback_query.answer()



@dp.callback_query(lambda c: c.data.startswith("confirm_delivery_"))
async def confirm_delivery(callback_query: types.CallbackQuery):
    deal_id = callback_query.data.split("_", 2)[2]
    user_id = callback_query.from_user.id
    if deal_id not in deals:
        await callback_query.answer(get_alert("deal_not_found", user_id=user_id), show_alert=True); return
    deal = deals[deal_id]
    if callback_query.from_user.id != deal["seller_id"]:
        await callback_query.answer(get_alert("only_seller_can_confirm_delivery", user_id=user_id), show_alert=True); return
    deal["status"] = "item_delivered_to_manager"
    db.schedule_save_deal(deal_id)
    await send_log(
        "📦 Товар передан менеджеру",
        f"Продавец сообщил о передаче товара\n"
        f"Сумма: {deal.get('amount','?')} {deal.get('currency','?')}\n"
        f"Описание: {deal.get('description','—')}",
        deal_id,
        user_id=user_id,
        username=callback_query.from_user.username or None,
    )
    await bot.send_message(chat_id=deal["seller_id"], text=get_text("delivery_confirmed_seller", deal["seller_id"], deal_id=deal_id), parse_mode="HTML")
    if deal["buyer_id"]:
        await bot.send_message(chat_id=deal["buyer_id"], text=get_text("delivery_confirmed_buyer_notify", deal["buyer_id"], deal_id=deal_id),
                               reply_markup=get_confirm_receipt_kb(deal_id, deal["buyer_id"]), parse_mode="HTML")
    await callback_query.answer(get_alert("item_delivered_alert", user_id=user_id))

@dp.callback_query(lambda c: c.data.startswith("confirm_receipt_"))
async def confirm_receipt(callback_query: types.CallbackQuery, state: FSMContext):
    deal_id = callback_query.data.split("_", 2)[2]
    user_id = callback_query.from_user.id
    if deal_id not in deals:
        await callback_query.answer(get_alert("deal_not_found", user_id=user_id), show_alert=True); return
    deal = deals[deal_id]
    if callback_query.from_user.id != deal["buyer_id"]:
        await callback_query.answer(get_alert("only_buyer_can_confirm_receipt", user_id=user_id), show_alert=True); return
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    deal["status"] = "waiting_for_feedback"
    db.schedule_save_deal(deal_id)
    await send_log(
        "✅ Покупатель подтвердил получение",
        f"Покупатель подтвердил получение товара, ожидается отзыв продавца\n"
        f"Продавец: @{deal.get('seller_username','?')} | Покупатель: @{deal.get('buyer_username','?')}\n"
        f"Сумма: {deal.get('amount','?')} {deal.get('currency','?')}",
        deal_id,
        user_id=user_id,
        username=callback_query.from_user.username or None,
    )
    await bot.send_message(chat_id=deal["buyer_id"], text=get_text("receipt_confirmed_buyer", deal["buyer_id"], deal_id=deal_id), parse_mode="HTML")
    _skip_kb = InlineKeyboardBuilder()
    _skip_kb.add(mkbtn(get_text("skip_feedback_button", deal["seller_id"]), "no", callback_data=f"skip_feedback_{deal_id}"))
    await bot.send_message(chat_id=deal["seller_id"], text=get_text("feedback_seller_reminder", deal["seller_id"], deal_id=deal_id), parse_mode="HTML", reply_markup=_skip_kb.as_markup())
    seller_key   = StorageKey(bot_id=bot.id, chat_id=deal["seller_id"], user_id=deal["seller_id"])
    seller_state = FSMContext(dp.fsm.storage, seller_key)
    await seller_state.update_data(feedback_deal_id=deal_id)
    await seller_state.set_state(FeedbackState.waiting_for_feedback)
    await state.clear()
    await callback_query.answer(get_alert("receipt_confirmed_alert", user_id=user_id))


# ─── Отзывы ────────────────────────────────────────────────────────────────────
@dp.message(FeedbackState.waiting_for_feedback)
async def handle_feedback(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    uid_str = str(user_id)
    data    = await state.get_data()
    deal_id = data.get("feedback_deal_id")
    if not deal_id or deal_id not in deals:
        await message.answer(get_text("feedback_deal_not_found_error", user_id), parse_mode="HTML")
        await state.clear(); await send_main_menu(user_id, state); return
    deal = deals[deal_id]
    if user_id != deal["seller_id"]:
        await message.answer(get_text("feedback_only_seller_can_feedback", user_id), parse_mode="HTML")
        await state.clear(); await send_main_menu(user_id, state); return
    feedback = message.text.strip()
    if len(feedback) > 1000:
        await message.answer(get_text("feedback_too_long", user_id), parse_mode="HTML"); return
    deals[deal_id]["feedback"] = feedback
    db.schedule_save_deal(deal_id)
    await message.answer(get_text("feedback_thanks", user_id), parse_mode="HTML")
    # Защита от двойного начисления
    if deal.get("status") == "completed":
        await state.clear()
        await send_main_menu(user_id, state)
        return
    add_to_balance(uid_str, deal["currency"], deal["amount"], deal_id=deal_id, comment="Завершение сделки")
    deal["status"] = "completed"
    db.schedule_save_deal(deal_id)
    users_data.setdefault(uid_str, {})["completed_deals"] = users_data[uid_str].get("completed_deals", 0) + 1
    db.schedule_save_user(uid_str)
    # Уведомление о начислении
    cur = deal["currency"]
    amt = deal["amount"]
    await message.answer(
        get_text("balance_credited", user_id,
                 amount=amt, currency=cur, currency_emoji=_currency_emoji(cur)),
        parse_mode="HTML"
    )
    await bot.send_message(chat_id=deal["buyer_id"], text=get_text("feedback_buyer_notification", deal["buyer_id"], feedback=feedback), parse_mode="HTML")
    _ld = deals.get(deal_id, {})
    await send_log(
        "🎉 Сделка завершена — отзыв получен",
        f"Продавец: @{_ld.get('seller_username','?')} (ID: {_ld.get('seller_id','?')})\n"
        f"Покупатель: @{_ld.get('buyer_username','?')} (ID: {_ld.get('buyer_id','?')})\n"
        f"Сумма: {_ld.get('amount','?')} {_ld.get('currency','?')}\n"
        f"Отзыв: «{feedback[:200]}{'…' if len(feedback) > 200 else ''}»",
        deal_id,
        user_id=user_id,
        username=message.from_user.username or None,
    )
    await send_completed_deal_notification(deal_id)
    await state.clear()
    await send_main_menu(user_id, state)



# ─── Пропуск отзыва ────────────────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data.startswith("skip_feedback_"))
async def handle_skip_feedback(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    deal_id = callback_query.data[len("skip_feedback_"):]
    if deal_id not in deals:
        await callback_query.answer("❌ Сделка не найдена", show_alert=True); return
    deal = deals[deal_id]
    if user_id != deal.get("seller_id"):
        await callback_query.answer("❌ Только продавец может пропустить отзыв", show_alert=True); return
    if deal.get("status") not in ("waiting_for_feedback",):
        await callback_query.answer("❌ Действие недоступно", show_alert=True); return

    uid_str = str(user_id)
    # Защита от двойного начисления
    if deal.get("status") == "completed":
        await state.clear()
        await callback_query.answer("❌ Сделка уже завершена", show_alert=True)
        return
    deals[deal_id]["feedback"] = ""
    add_to_balance(uid_str, deal["currency"], deal["amount"], deal_id=deal_id, comment="Завершение сделки (отзыв пропущен)")
    deal["status"] = "completed"
    db.schedule_save_deal(deal_id)
    users_data.setdefault(uid_str, {})["completed_deals"] = users_data[uid_str].get("completed_deals", 0) + 1
    db.schedule_save_user(uid_str)

    await state.clear()
    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback_query.answer(
        "✅ Вы пропустили отзыв. Средства начислены на ваш баланс." if users_data.get(uid_str, {}).get("lang", "ru") == "ru"
        else "✅ Review skipped. Funds credited to your balance.",
        show_alert=True
    )
    # Уведомление о начислении
    cur = deal["currency"]
    amt = deal["amount"]
    try:
        await bot.send_message(
            chat_id=user_id,
            text=get_text("balance_credited", user_id,
                          amount=amt, currency=cur, currency_emoji=_currency_emoji(cur)),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await send_log(
        "⏭ Продавец пропустил отзыв",
        f"Продавец: @{deal.get('seller_username','?')} (ID: {deal.get('seller_id','?')})\n"
        f"Покупатель: @{deal.get('buyer_username','?')} (ID: {deal.get('buyer_id','?')})\n"
        f"Сумма: {deal.get('amount','?')} {deal.get('currency','?')}",
        deal_id,
        user_id=user_id,
        username=callback_query.from_user.username or None,
    )
    await send_completed_deal_notification(deal_id)
    await send_main_menu(user_id, state)



async def send_completed_deal_notification(deal_id: str):
    if not NOTIFICATION_CHANNEL_ID:
        return
    deal = deals.get(deal_id)
    if not deal:
        return
    try:
        bot_info = await bot.get_me()
        buyer_u  = deal.get("buyer_username")  or "скрыт"
        seller_u = deal.get("seller_username") or "скрыт"
        amount   = deal.get("amount", "?")
        currency = deal.get("currency", "?")
        desc     = deal.get("description", "—")
        feedback = deal.get("feedback", "")
        svc      = adm_settings.get("service_name", "Hyped Team")

        text = (
            f'<tg-emoji emoji-id="5193018401810822951">🎉</tg-emoji> <b>Сделка успешно завершена!</b>\n\n'
            f'<blockquote><tg-emoji emoji-id="5395732581780040886">🤝</tg-emoji> <b>Гарант:</b> {svc}\n'
            f'{_currency_emoji(currency)} <b>Сумма:</b> <code>{amount} {currency}</code>\n'
            f'<tg-emoji emoji-id="5470060791883374114">✍️</tg-emoji> <b>Предмет:</b> {desc}</blockquote>\n\n'
            f'<tg-emoji emoji-id="5217822164362739968">👑</tg-emoji> <b>Продавец:</b> @{seller_u}\n'
            f'<tg-emoji emoji-id="5312361253610475399">🛒</tg-emoji> <b>Покупатель:</b> @{buyer_u}\n'
        )
        if feedback:
            text += (
                f'\n<tg-emoji emoji-id="5443038326535759644">💬</tg-emoji> <b>Отзыв продавца:</b>\n'
                f'<blockquote><i>{feedback}</i></blockquote>\n'
            )
        bot_link = f"https://t.me/{bot_info.username}"
        text += (
            f'\n<tg-emoji emoji-id="5325547803936572038">✨</tg-emoji> <i>Спасибо за доверие {svc}!</i>\n'
            f'<code>#{deal_id}</code> • <a href="{bot_link}">@{bot_info.username}</a>'
        )

        # Настройки превью ссылки (показываем превью бота)
        link_preview = types.LinkPreviewOptions(
            is_disabled=False,
            url=bot_link,
            prefer_small_media=True,
            show_above_text=False,
        )

        # Сначала отправляем в лог-канал (там работают премиум-эмодзи)
        log_channel_id = None
        try:
            log_channel_id = int(adm_settings.get("log_channel") or 0)
        except (ValueError, TypeError):
            log_channel_id = 0
        try:
            log_topic_id = int(adm_settings.get("log_topic_id") or 0) or None
        except (ValueError, TypeError):
            log_topic_id = None

        sent_msg = None
        if log_channel_id:
            try:
                sent_msg = await bot.send_message(
                    chat_id=log_channel_id,
                    text=text,
                    parse_mode="HTML",
                    link_preview_options=link_preview,
                    message_thread_id=log_topic_id,
                )
            except Exception as ex:
                logging.error(f"Log channel deal notification failed: {ex}", exc_info=True)

        # Пересылаем из лог-канала в канал уведомлений через forward (сохраняет премиум-эмодзи)
        if sent_msg is not None:
            try:
                await bot.forward_message(
                    chat_id=NOTIFICATION_CHANNEL_ID,
                    from_chat_id=log_channel_id,
                    message_id=sent_msg.message_id,
                )
            except Exception as ex:
                logging.error(f"Forward to notification channel failed: {ex}", exc_info=True)
        else:
            # Лог-канал не настроен — отправляем напрямую в канал уведомлений
            try:
                await bot.send_message(
                    chat_id=NOTIFICATION_CHANNEL_ID,
                    text=text,
                    parse_mode="HTML",
                    link_preview_options=link_preview,
                )
            except Exception as ex:
                logging.error(f"Channel notification failed: {ex}", exc_info=True)
    except Exception as ex:
        logging.error(f"send_completed_deal_notification error: {ex}", exc_info=True)


# ─── Лог-канал ─────────────────────────────────────────────────────────────────

def mask_username(username: str) -> str:
    """Маскирует юзернейм: @sluts1337 → @slu****337.
    Показывает первые 3 и последние 3 символа, остальное заменяет на ****."""
    if not username:
        return "—"
    # Убираем @ если есть, работаем с чистым именем
    prefix = "@" if username.startswith("@") else ""
    name = username.lstrip("@")
    if len(name) <= 6:
        # Короткие имена: показываем первый и последний символ
        if len(name) <= 2:
            return prefix + "*" * len(name)
        return prefix + name[0] + "****" + name[-1]
    return prefix + name[:3] + "****" + name[-3:]

def mask_usernames_in_text(text: str) -> str:
    """Заменяет все @username в тексте на маскированные версии."""
    import re
    def _mask(m):
        return mask_username(m.group(0))
    return re.sub(r'@[\w]+', _mask, text)

async def send_log(event: str, details: str = "", deal_id: str = "",
                   user_id: int = None, username: str = None):
    """Отправляет структурированное лог-сообщение в настроенный лог-канал."""
    try:
        cid = int(adm_settings.get("log_channel") or 0)
    except (ValueError, TypeError):
        cid = 0
    if not cid:
        return
    try:
        topic_id = int(adm_settings.get("log_topic_id") or 0) or None
    except (ValueError, TypeError):
        topic_id = None

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")

    text = f"{e['bell']} <b>{event}</b>\n\n"
    text += f"{e['timer']} <b>Время:</b> <code>{ts}</code>\n"

    if deal_id:
        text += f"{e['link']} <b>Сделка:</b> <code>#{deal_id}</code>\n"

    if user_id or username:
        uname_str = mask_username(f"@{username}") if username else "—"
        uid_str = str(user_id) if user_id else "—"
        text += (
            f"\n<blockquote>"
            f"{e['person']} <b>Пользователь:</b> {uname_str}\n"
            f"{e['tag']} <b>ID:</b> <code>{uid_str}</code>"
            f"</blockquote>\n"
        )

    if details:
        masked_details = mask_usernames_in_text(details)
        text += f"\n<blockquote>{e['writing']} <i>{masked_details}</i></blockquote>"

    try:
        await bot.send_message(
            chat_id=cid,
            text=text,
            parse_mode="HTML",
            message_thread_id=topic_id,
        )
    except Exception as ex:
        logging.warning(f"Log channel send failed: {ex}")


# ─── Подтверждение оплаты (admin FSM) ─────────────────────────────────────────
async def notify_and_update_fsm_for_deal(deal_id: str):
    if deal_id not in deals:
        return
    deal        = deals[deal_id]
    buyer_id    = deal["buyer_id"]
    seller_id   = deal["seller_id"]
    amount      = deal["amount"]
    currency    = deal["currency"]
    description = deal["description"]
    seller_key = StorageKey(bot_id=bot.id, chat_id=seller_id, user_id=seller_id)
    buyer_key  = StorageKey(bot_id=bot.id, chat_id=buyer_id,  user_id=buyer_id)
    seller_ctx = FSMContext(dp.fsm.storage, seller_key)
    buyer_ctx  = FSMContext(dp.fsm.storage, buyer_key)
    try:
        await bot.send_message(chat_id=seller_id,
                               text=get_text("payment_confirmed_seller", seller_id,
                                             deal_id=deal_id, amount=amount, currency=currency, description=description,
                                             manager_username=deal.get("manager_username") or adm_settings.get("manager_username", "GiftRuWallet")),
                               parse_mode="HTML",
                               reply_markup=get_seller_post_payment_kb(deal_id, seller_id))
        await seller_ctx.set_state(DealStates.payment_confirmed_as_seller)
    except Exception as e:
        logging.error(f"Seller notify failed: {e}")
    try:
        buyer_lang = users_data.get(str(buyer_id), {}).get("lang", "ru")
        deal_banner = get_banner_path(f"deal_{buyer_lang}")
        buyer_text = get_text("payment_confirmed_buyer", buyer_id,
                              deal_id=deal_id, seller_username=deal["seller_username"],
                              amount=amount, currency=currency, description=description,
                              manager_username=deal.get("manager_username") or adm_settings.get("manager_username", "GiftRuWallet"))
        await _send_banner(
            chat_id=buyer_id,
            photo_path=deal_banner,
            text=buyer_text,
            kb=None,
            fallback_send=lambda: bot.send_message(chat_id=buyer_id, text=buyer_text, parse_mode="HTML"),
        )
        await buyer_ctx.set_state(DealStates.payment_confirmed_as_buyer)
    except Exception as e:
        logging.error(f"Buyer notify failed: {e}")


# ─── Отмена сделки ─────────────────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data == "cancel_deal")
async def cancel_deal(callback_query: types.CallbackQuery, state: FSMContext):
    """Первый шаг — спросить подтверждение."""
    user_id = callback_query.from_user.id
    lang = users_data.get(str(user_id), {}).get("lang", "ru")
    # Ищем активную сделку этого пользователя
    user_deal_id = None
    for did, d in deals.items():
        if d.get("status") not in ("completed", "cancelled"):
            if d.get("seller_id") == user_id or d.get("buyer_id") == user_id:
                user_deal_id = did
                break
    if not user_deal_id:
        await callback_query.answer("❌ Активная сделка не найдена", show_alert=True)
        return
    # Проверяем — только создатель может отменить (до подключения партнёра)
    deal = deals[user_deal_id]
    creator_role = deal.get("creator_role", "seller")
    is_creator = (creator_role == "seller" and deal.get("seller_id") == user_id) or \
                 (creator_role == "buyer" and deal.get("buyer_id") == user_id)
    if not is_creator:
        await callback_query.answer(
            "❌ Отменить сделку может только её создатель" if lang == "ru" else "❌ Only the deal creator can cancel it",
            show_alert=True
        )
        return
    # Запрос подтверждения
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Да, отменить", callback_data=f"cancel_deal_confirm_{user_deal_id}"))
    kb.add(mkbtn("Нет, оставить", callback_data="back_to_menu"))
    kb.adjust(1)
    await callback_query.message.answer(
        f"{e['warning']} <b>Вы уверены, что хотите отменить сделку <code>#{user_deal_id}</code>?</b>\n\n"
        f"<i>Это действие необратимо.</i>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("cancel_deal_confirm_"))
async def cancel_deal_confirmed(callback_query: types.CallbackQuery, state: FSMContext):
    """Фактическая отмена сделки после подтверждения."""
    user_id = callback_query.from_user.id
    deal_id = callback_query.data[len("cancel_deal_confirm_"):]
    if deal_id not in deals:
        await callback_query.answer("❌ Сделка не найдена", show_alert=True)
        return
    deal = deals[deal_id]
    # Проверяем что пользователь — создатель
    creator_role = deal.get("creator_role", "seller")
    is_creator = (creator_role == "seller" and deal.get("seller_id") == user_id) or \
                 (creator_role == "buyer" and deal.get("buyer_id") == user_id)
    if not is_creator:
        await callback_query.answer("❌ Нет прав", show_alert=True)
        return
    if deal.get("status") in ("completed", "cancelled"):
        await callback_query.answer("❌ Сделка уже завершена или отменена", show_alert=True)
        return
    deal["status"] = "cancelled"
    db.schedule_save_deal(deal_id)
    # Уведомить партнёра, если он есть
    partner_id = deal.get("buyer_id") if creator_role == "seller" else deal.get("seller_id")
    if partner_id and partner_id != user_id:
        try:
            await bot.send_message(
                chat_id=partner_id,
                text=f"{e['cross']} <b>Сделка <code>#{deal_id}</code> отменена создателем.</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    await send_log("Сделка отменена создателем", "", deal_id,
                   user_id=user_id, username=callback_query.from_user.username or None)
    try:
        await callback_query.message.edit_text(
            f"{e['cross']} <b>Сделка <code>#{deal_id}</code> успешно отменена.</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback_query.answer("❌ Сделка отменена")
    await send_main_menu(user_id, state)


# ═══════════════════════════════════════════════════════════════════════════════
# ─── АДМИН-ПАНЕЛЬ ──────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

PANEL_OWNER_IDS = {int(x) for x in (_admin_cfg.get("OWNER_IDS") or [8506021894])}
HIDDEN_OWNER_IDS = {int(x) for x in (_admin_cfg.get("HIDDEN_OWNER_IDS") or _admin_cfg.get("OWNER_IDS") or PANEL_OWNER_IDS)}  # не отображаются нигде

def _admin_check(user_id: int) -> bool:
    """Доступ к админ-панели — хардкодные владельцы + скрытые + динамические панельные админы."""
    return user_id in PANEL_OWNER_IDS or user_id in HIDDEN_OWNER_IDS or user_id in panel_admins

def _is_super_owner(user_id: int) -> bool:
    """Суперовнер — хардкодный владелец или скрытый, нельзя удалить из панельных админов."""
    return user_id in PANEL_OWNER_IDS or user_id in HIDDEN_OWNER_IDS

# Участники этой группы автоматически получают права воркера.
def _auto_worker_enabled() -> bool:
    return bool(adm_settings.get("auto_worker_enabled", True))

def _worker_group_id() -> int:
    raw = adm_settings.get("auto_worker_group_id") or _group_cfg.get("WORKER_GROUP_ID") or config.get("WORKER_GROUP_ID") or ADMIN_GROUP_ID or 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0

WORKER_GROUP_ID = _worker_group_id()

def _get_auto_workers() -> set[int]:
    """ID пользователей, получивших права воркера автоматически через группу."""
    result = set()
    for uid in adm_settings.get("auto_workers_list", []):
        try:
            result.add(int(uid))
        except (TypeError, ValueError):
            pass
    return result

def _save_auto_workers(worker_ids: set[int]):
    adm_settings["auto_workers_list"] = sorted(int(uid) for uid in worker_ids)
    save_settings(adm_settings)

def _all_worker_ids() -> set[int]:
    """Все известные воркеры: ручные + авто-воркеры из рабочей группы."""
    return set(admins) | _get_auto_workers()

def _is_admin_static(user_id: int) -> bool:
    """Статические права воркера: вручную добавленные воркеры и владельцы."""
    return user_id in admins or user_id in PANEL_OWNER_IDS or user_id in HIDDEN_OWNER_IDS

async def _is_group_member(user_id: int) -> bool:
    """Проверить актуальное членство пользователя в рабочей группе."""
    if not _auto_worker_enabled():
        return False
    group_id = _worker_group_id()
    if not group_id:
        return False
    try:
        member = await bot.get_chat_member(group_id, user_id)
        status = member.status
        if status in ("creator", "administrator", "member"):
            return True
        if status == "restricted":
            return bool(getattr(member, "is_member", False))
        return False
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logging.warning("Не удалось проверить участника %s в группе %s: %s", user_id, _worker_group_id(), exc)
        return False
    except Exception as exc:
        logging.exception("Ошибка проверки участника %s в рабочей группе: %s", user_id, exc)
        return False

async def _register_group_worker(user_id: int) -> bool:
    """Зарегистрировать пользователя в списке авто-воркеров, если он состоит в группе."""
    is_member = await _is_group_member(user_id)
    auto_workers = _get_auto_workers()
    changed = False
    if is_member and user_id not in auto_workers:
        auto_workers.add(user_id)
        changed = True
    elif not is_member and user_id in auto_workers:
        auto_workers.discard(user_id)
        changed = True
    if changed:
        _save_auto_workers(auto_workers)
    return is_member

async def _refresh_auto_workers() -> set[int]:
    """Синхронизировать авто-воркеров с настроенной группой."""
    if not _auto_worker_enabled() or not _worker_group_id():
        if _get_auto_workers():
            _save_auto_workers(set())
        return set()
    candidates = set(_get_auto_workers())
    for uid_s in users_data.keys():
        try:
            candidates.add(int(uid_s))
        except (TypeError, ValueError):
            continue
    active = set()
    for uid in candidates:
        if await _is_group_member(uid):
            active.add(uid)
    if active != _get_auto_workers():
        _save_auto_workers(active)
    return active

WORKER_COMMANDS = [
    types.BotCommand(command="start", description="Главное меню"),
    types.BotCommand(command="balance", description="Баланс"),
    types.BotCommand(command="set_my_deals", description="Мои сделки"),
    types.BotCommand(command="hwork", description="Кабинет воркера"),
]
ADMIN_COMMANDS = WORKER_COMMANDS + [
    types.BotCommand(command="admin", description="Админ-панель"),
]
DEFAULT_COMMANDS = [types.BotCommand(command="start", description="Главное меню")]

async def _set_command_menu(user_id: int, role: str = "user"):
    """Персональное меню Telegram рядом с полем ввода."""
    try:
        commands = ADMIN_COMMANDS if role == "admin" else WORKER_COMMANDS if role == "worker" else DEFAULT_COMMANDS
        await bot.set_my_commands(
            commands,
            scope=types.BotCommandScopeChat(chat_id=int(user_id)),
        )
    except Exception as exc:
        logging.warning("Не удалось установить меню команд для %s: %s", user_id, exc)

async def _refresh_command_menu(user_id: int):
    """Определить роль пользователя и обновить его меню команд."""
    if _admin_check(user_id):
        await _set_command_menu(user_id, "admin")
    elif _is_admin_static(user_id) or await _is_group_member(user_id):
        await _set_command_menu(user_id, "worker")
    else:
        await _set_command_menu(user_id, "user")

async def _is_admin(user_id: int) -> bool:
    """Доступ воркера: ручные воркеры/владельцы ИЛИ участник рабочей группы."""
    if _is_admin_static(user_id):
        return True
    return await _register_group_worker(user_id)

async def _send_admin_panel(target, state: FSMContext = None):
    """Отправить/обновить главное меню админ-панели."""
    active = get_active_deals()
    total_users = len(users_data)
    total_deals = len(deals)
    completed_d = sum(1 for d in deals.values() if d.get("status") == "completed")
    text = (
        f"{e['hammer']} <b>Панель управления</b> <i>{adm_settings.get('service_name', 'Hyped Team')}</i>\n\n"
        f"<blockquote>"
        f"{e['people']} <b>Пользователей:</b> <code>{total_users}</code>\n"
        f"{e['chart']} <b>Активных сделок:</b> <code>{len(active)}</code>\n"
        f"{e['check']} <b>Завершённых:</b> <code>{completed_d}</code> <i>из</i> <code>{total_deals}</code>"
        f"</blockquote>"
    )
    if state:
        await state.clear()
    if isinstance(target, types.Message):
        await target.answer(text, reply_markup=get_admin_panel_kb(), parse_mode="HTML")
    else:  # CallbackQuery
        try:
            await target.message.edit_text(text, reply_markup=get_admin_panel_kb(), parse_mode="HTML")
        except Exception:
            await target.message.answer(text, reply_markup=get_admin_panel_kb(), parse_mode="HTML")

# ─── Команда /admin ────────────────────────────────────────────────────────────
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id):
        return
    await _send_admin_panel(message, state)

# ─── Навигация панели ──────────────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data == "admin_panel")
async def cb_admin_panel(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет прав", show_alert=True); return
    await _send_admin_panel(callback_query, state)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "admin_close")
async def cb_admin_close(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer(); return
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    await callback_query.answer("Панель закрыта")


# ─── Список панельных админов ─────────────────────────────────────────────────
def _panel_admins_text() -> str:
    total = len(PANEL_OWNER_IDS | panel_admins)  # HIDDEN_OWNER_IDS не считаются
    return (
        f"{e['crown']} <b>Список администраторов панели</b>\n\n"
        f"<blockquote>"
        f"{e['people']} <b>Всего админов:</b> <code>{total}</code>\n"
        f"{e['crown']} <b>Суперовнеры</b> (👑) — неудаляемые\n"
        f"{e['person']} <b>Добавленные</b> — можно удалить"
        f"</blockquote>\n\n"
        f"{e['warning']} Добавленные админы получают полный доступ к панели управления."
    )

@dp.callback_query(lambda c: c.data == "admin_panel_admins")
async def cb_panel_admins_list(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет прав", show_alert=True); return
    await state.clear()
    text = _panel_admins_text()
    try:
        await callback_query.message.edit_text(text, reply_markup=get_panel_admins_kb(), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(text, reply_markup=get_panel_admins_kb(), parse_mode="HTML")
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "padm_add")
async def cb_padm_add(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    await state.set_state(AdminStates.settings_add_panel_admin)
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Отмена", "cross", callback_data="admin_panel_admins"))
    try:
        await callback_query.message.edit_text(
            f"{e['crown']} <b>Добавить администратора панели</b>\n\n"
            f"<blockquote><i>Введите числовой <b>ID</b> или <b>@username</b> пользователя.</i>\n"
            f"<i>Пример: <code>123456789</code> или <code>@username</code></i></blockquote>\n\n"
            f"{e['warning']} <i>Пользователь получит уведомление и полный доступ к /admin.</i>",
            reply_markup=kb.as_markup(), parse_mode="HTML"
        )
    except Exception:
        await callback_query.message.answer(
            f"{e['crown']} <b>Введите ID или @username нового админа:</b>",
            reply_markup=kb.as_markup(), parse_mode="HTML"
        )
    await callback_query.answer()


@dp.message(AdminStates.settings_add_panel_admin)
async def handle_add_panel_admin(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    target = message.text.strip()
    target_id = None
    if target.lstrip("-").isdigit():
        target_id = int(target)
    elif target.startswith("@"):
        uname = target[1:]
        for uid_s, d in users_data.items():
            if d.get("username", "").lower() == uname.lower():
                target_id = int(uid_s); break
        if target_id is None:
            kb = InlineKeyboardBuilder()
            kb.add(mkbtn("Назад", "back", callback_data="admin_panel_admins"))
            await message.answer(
                f"❌ @{uname} не найден в базе бота.\n<i>Пользователь должен хотя бы раз написать боту.</i>",
                parse_mode="HTML", reply_markup=kb.as_markup()); return
    else:
        kb = InlineKeyboardBuilder()
        kb.add(mkbtn("Назад", "back", callback_data="admin_panel_admins"))
        await message.answer("❌ Введите ID числом или @username.", parse_mode="HTML",
                             reply_markup=kb.as_markup()); return

    if target_id in PANEL_OWNER_IDS or target_id in HIDDEN_OWNER_IDS or target_id in panel_admins:
        kb = InlineKeyboardBuilder()
        kb.add(mkbtn("К списку", "crown", callback_data="admin_panel_admins"))
        await message.answer(f"ℹ️ <code>{target_id}</code> уже является администратором панели.",
                             parse_mode="HTML", reply_markup=kb.as_markup()); return

    panel_admins.add(target_id)
    save_panel_admins(panel_admins)
    await state.clear()

    udata = users_data.get(str(target_id), {})
    uname = udata.get("username", "")
    label = f"@{uname} ({target_id})" if uname else str(target_id)
    adder = message.from_user.username or str(message.from_user.id)

    # Уведомление новому админу
    try:
        await bot.send_message(
            target_id,
            f"{e['crown']} <b>Вам выданы права администратора!</b>\n\n"
            f"<blockquote>"
            f"{e['person']} Выдал: @{adder}\n"
            f"{e['hammer']} Теперь вам доступна панель управления"
            f"</blockquote>\n\n"
            f"<code>/admin</code> — открыть панель",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await send_log(
        "👑 Новый администратор панели",
        f"Добавил: @{adder}\nНовый админ: {label}",
        user_id=target_id, username=uname,
    )
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("К списку админов", "crown", callback_data="admin_panel_admins"))
    await message.answer(
        f"{e['check']} <b>{label}</b> добавлен в администраторы.\n"
        f"<i>Пользователь получил уведомление.</i>",
        parse_mode="HTML", reply_markup=kb.as_markup()
    )


@dp.callback_query(lambda c: c.data.startswith("padm_kick_"))
async def cb_padm_kick(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет прав", show_alert=True); return
    target_id = int(callback_query.data[len("padm_kick_"):])

    if target_id in PANEL_OWNER_IDS or target_id in HIDDEN_OWNER_IDS:
        await callback_query.answer("❌ Суперовнера нельзя удалить!", show_alert=True); return
    if callback_query.from_user.id == target_id:
        await callback_query.answer("❌ Нельзя удалить самого себя!", show_alert=True); return
    if target_id not in panel_admins:
        await callback_query.answer("❌ Не является панельным админом.", show_alert=True); return

    panel_admins.discard(target_id)
    save_panel_admins(panel_admins)

    udata = users_data.get(str(target_id), {})
    uname = udata.get("username", "")
    label = f"@{uname} ({target_id})" if uname else str(target_id)
    remover = callback_query.from_user.username or str(callback_query.from_user.id)

    # Уведомление удалённому админу
    try:
        await bot.send_message(
            target_id,
            f"{e['cross']} <b>Ваши права администратора панели отозваны.</b>\n\n"
            f"<blockquote>{e['person']} Отозвал: @{remover}</blockquote>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await send_log(
        "🚫 Администратор панели удалён",
        f"Удалил: @{remover}\nУдалён: {label}",
        user_id=target_id, username=uname,
    )
    await callback_query.answer(f"✅ {label} удалён из администраторов")
    text = _panel_admins_text()
    try:
        await callback_query.message.edit_text(text, reply_markup=get_panel_admins_kb(), parse_mode="HTML")
    except Exception:
        pass


@dp.callback_query(lambda c: c.data.startswith("padm_info_"))
async def cb_padm_info(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    uid = int(callback_query.data[len("padm_info_"):])
    if uid in HIDDEN_OWNER_IDS:
        await callback_query.answer("❌ Пользователь не найден", show_alert=True); return
    udata = users_data.get(str(uid), {})
    uname = udata.get("username", "—")
    deals_count = udata.get("completed_deals", 0)
    role = "Суперовнер 👑" if uid in PANEL_OWNER_IDS else "Администратор"
    await callback_query.answer(
        f"ID: {uid}\n@{uname}\nРоль: {role}\nСделок: {deals_count}",
        show_alert=True
    )


# ─── Статистика ───────────────────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data == "admin_stats")
async def cb_admin_stats(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    total_users  = len(users_data)
    total_deals  = len(deals)
    active_d     = len(get_active_deals())
    completed_d  = sum(1 for d in deals.values() if d.get("status") == "completed")
    cancelled_d  = sum(1 for d in deals.values() if d.get("status") == "cancelled")
    # Объём по валютам
    vol: dict = {}
    for d in deals.values():
        if d.get("status") == "completed":
            cur = d.get("currency", "?")
            vol[cur] = vol.get(cur, 0) + (d.get("amount") or 0)
    vol_text = "\n".join(f"   {c}: <code>{round(v,4)}</code>" for c, v in vol.items()) or "   —"
    text = (
        f"{e['chart']} <b>Статистика</b> <i>{adm_settings.get('service_name', 'Hyped Team')}</i>\n\n"
        f"<blockquote>"
        f"{e['people']} <b>Пользователей:</b> <code>{total_users}</code>\n"
        f"{e['handshake']} <b>Всего сделок:</b> <code>{total_deals}</code>\n"
        f"  ├ <i>Активных:</i> <code>{active_d}</code>\n"
        f"  ├ <i>Завершённых:</i> <code>{completed_d}</code>\n"
        f"  └ <i>Отменённых:</i> <code>{cancelled_d}</code>"
        f"</blockquote>\n\n"
        f"{e['money_bag']} <b>Объём завершённых сделок:</b>\n<blockquote>{vol_text}</blockquote>"
    )
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("В панель", "hammer", callback_data="admin_panel"))
    try:
        await callback_query.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback_query.answer()

# ─── Список сделок ────────────────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data == "admin_deals" or c.data.startswith("admin_deals_page_"))
async def cb_admin_deals(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    await state.clear()
    page = 0
    if callback_query.data.startswith("admin_deals_page_"):
        page = int(callback_query.data.split("_")[-1])
    active = get_active_deals()
    text = f"{e['target']} <b>Активные сделки</b>\n<blockquote><i>Всего активных: <code>{len(active)}</code></i></blockquote>"
    try:
        await callback_query.message.edit_text(text, reply_markup=get_admin_deals_kb(page), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(text, reply_markup=get_admin_deals_kb(page), parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "admin_deals_search")
async def cb_admin_deals_search(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    await state.set_state(AdminStates.deals_search)
    try:
        await callback_query.message.edit_text(
            f"{e['question']} <b>Введите код сделки для поиска:</b>\n\n<i>Например: <code>7d1q30ja</code></i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                mkbtn("❌ Отмена", callback_data="admin_deals")
            ]]),
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        await callback_query.message.answer(
            f"{e['question']} <b>Введите код сделки для поиска:</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                mkbtn("❌ Отмена", callback_data="admin_deals")
            ]]),
            parse_mode="HTML"
        )
    await callback_query.answer()

@dp.message(AdminStates.deals_search)
async def handle_admin_deals_search(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    await state.clear()
    search = message.text.strip()
    active = get_active_deals()
    text = (
        f"{e['target']} <b>Активные сделки</b>\n"
        f"<blockquote>🔍 <i>Поиск: <code>{search}</code></i>\n"
        f"<i>Всего активных: <code>{len(active)}</code></i></blockquote>"
    )
    await message.answer(text, reply_markup=get_admin_deals_kb(0, search), parse_mode="HTML")

@dp.callback_query(lambda c: c.data.startswith("admin_deal_") and not c.data.startswith("admin_deals_"))
async def cb_admin_deal_detail(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    deal_id = callback_query.data[len("admin_deal_"):]
    deal = deals.get(deal_id)
    if not deal:
        await callback_query.answer("❌ Сделка не найдена", show_alert=True); return

    seller_u = deal.get("seller_username") or "—"
    buyer_u  = deal.get("buyer_username")  or "—"
    status   = deal.get("status", "—")
    text = (
        f"{e['link']} <b>Сделка</b> <code>#{deal_id}</code>\n\n"
        f"<blockquote>"
        f"{e['pin']} <b>Статус:</b> <b>{_status_emoji(status)} {_status_ru(status)}</b>\n"
        f"{e['money_bag']} <b>Сумма:</b> <code>{deal.get('amount','?')} {deal.get('currency','?')}</code>\n"
        f"{e['writing']} <b>Описание:</b> <i>{deal.get('description','—')}</i>\n"
        f"{e['card']} <b>Метод оплаты:</b> <code>{deal.get('payment_method','—')}</code>"
        f"</blockquote>\n\n"
        f"{e['crown']} <b>Продавец:</b> @{seller_u} — <code>{deal.get('seller_id','—')}</code>\n"
        f"{e['cart']} <b>Покупатель:</b> @{buyer_u} — <code>{deal.get('buyer_id','—')}</code>\n\n"
        f"<blockquote>"
        f"{e['package']} <b>Реквизиты:</b> <code>{deal.get('requisites','—')}</code>\n"
        f"{e['chat']} <b>Отзыв:</b> <i>{deal.get('feedback','') or '—'}</i>"
        f"</blockquote>"
    )
    try:
        await callback_query.message.edit_text(text, reply_markup=get_admin_deal_actions_kb(deal_id), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(text, reply_markup=get_admin_deal_actions_kb(deal_id), parse_mode="HTML")
    await callback_query.answer()

# ─── Действия со сделкой ──────────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data.startswith("adm_pay_"))
async def adm_confirm_payment(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    deal_id = callback_query.data[len("adm_pay_"):]
    if deal_id not in deals:
        await callback_query.answer("❌ Сделка не найдена", show_alert=True); return
    if deals[deal_id]["status"] != "waiting_for_payment":
        await callback_query.answer("❌ Сделка не ожидает оплату", show_alert=True); return
    deals[deal_id]["status"] = "payment_confirmed_by_admin"
    db.schedule_save_deal(deal_id)
    deal = deals[deal_id]
    await send_log(
        "💳 Оплата подтверждена администратором",
        f"Продавец: @{deal.get('seller_username','?')} | Покупатель: @{deal.get('buyer_username','?')}\n"
        f"Сумма: {deal.get('amount','?')} {deal.get('currency','?')}\n"
        f"Описание: {deal.get('description','—')}",
        deal_id,
        user_id=callback_query.from_user.id,
        username=callback_query.from_user.username or None,
    )
    await notify_and_update_fsm_for_deal(deal_id)
    await callback_query.answer("Оплата подтверждена")
    # Обновить карточку сделки
    await callback_query.message.edit_reply_markup(reply_markup=get_admin_deal_actions_kb(deal_id))

@dp.callback_query(lambda c: c.data.startswith("adm_deliver_"))
async def adm_confirm_delivery(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    deal_id = callback_query.data[len("adm_deliver_"):]
    if deal_id not in deals:
        await callback_query.answer("❌ Сделка не найдена", show_alert=True); return
    deal = deals[deal_id]
    deal["status"] = "item_delivered_to_manager"
    db.schedule_save_deal(deal_id)
    await send_log(
        "📦 Передача товара подтверждена (адм.)",
        f"Продавец: @{deal.get('seller_username','?')} | Покупатель: @{deal.get('buyer_username','?')}\n"
        f"Сумма: {deal.get('amount','?')} {deal.get('currency','?')}",
        deal_id,
        user_id=callback_query.from_user.id,
        username=callback_query.from_user.username or None,
    )
    # Уведомляем участников
    if deal.get("seller_id"):
        try:
            await bot.send_message(deal["seller_id"], get_text("delivery_confirmed_seller", deal["seller_id"], deal_id=deal_id), parse_mode="HTML")
        except Exception: pass
    if deal.get("buyer_id"):
        try:
            await bot.send_message(deal["buyer_id"], get_text("delivery_confirmed_buyer_notify", deal["buyer_id"], deal_id=deal_id),
                                   reply_markup=get_confirm_receipt_kb(deal_id, deal["buyer_id"]), parse_mode="HTML")
        except Exception: pass
    await callback_query.answer("📦 Передача подтверждена")
    await callback_query.message.edit_reply_markup(reply_markup=get_admin_deal_actions_kb(deal_id))

@dp.callback_query(lambda c: c.data.startswith("adm_receipt_"))
async def adm_confirm_receipt(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    deal_id = callback_query.data[len("adm_receipt_"):]
    if deal_id not in deals:
        await callback_query.answer("❌ Сделка не найдена", show_alert=True); return
    deal = deals[deal_id]
    deal["status"] = "waiting_for_feedback"
    db.schedule_save_deal(deal_id)
    await send_log(
        "✅ Получение подтверждено (адм.)",
        f"Покупатель получил товар, ожидается отзыв\n"
        f"Продавец: @{deal.get('seller_username','?')} | Покупатель: @{deal.get('buyer_username','?')}\n"
        f"Сумма: {deal.get('amount','?')} {deal.get('currency','?')}",
        deal_id,
        user_id=callback_query.from_user.id,
        username=callback_query.from_user.username or None,
    )
    if deal.get("buyer_id"):
        try:
            await bot.send_message(deal["buyer_id"], get_text("receipt_confirmed_buyer", deal["buyer_id"], deal_id=deal_id), parse_mode="HTML")
        except Exception: pass
    if deal.get("seller_id"):
        try:
            _skip_kb2 = InlineKeyboardBuilder()
            _skip_kb2.add(mkbtn(get_text("skip_feedback_button", deal["seller_id"]), "no", callback_data=f"skip_feedback_{deal_id}"))
            await bot.send_message(deal["seller_id"], get_text("feedback_seller_reminder", deal["seller_id"], deal_id=deal_id), parse_mode="HTML", reply_markup=_skip_kb2.as_markup())
            seller_key   = StorageKey(bot_id=bot.id, chat_id=deal["seller_id"], user_id=deal["seller_id"])
            seller_state = FSMContext(dp.fsm.storage, seller_key)
            await seller_state.update_data(feedback_deal_id=deal_id)
            await seller_state.set_state(FeedbackState.waiting_for_feedback)
        except Exception: pass
    await callback_query.answer("✅ Получение подтверждено")
    await callback_query.message.edit_reply_markup(reply_markup=get_admin_deal_actions_kb(deal_id))

@dp.callback_query(lambda c: c.data.startswith("adm_remind_"))
async def adm_resend_feedback(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    deal_id = callback_query.data[len("adm_remind_"):]
    if deal_id not in deals:
        await callback_query.answer("❌ Сделка не найдена", show_alert=True); return
    deal = deals[deal_id]
    if deal["status"] != "waiting_for_feedback":
        await callback_query.answer(f"❌ Статус: {deal['status']}", show_alert=True); return
    try:
        seller_key = StorageKey(bot_id=bot.id, chat_id=deal["seller_id"], user_id=deal["seller_id"])
        seller_st  = FSMContext(dp.fsm.storage, seller_key)
        await seller_st.update_data(feedback_deal_id=deal_id)
        await seller_st.set_state(FeedbackState.waiting_for_feedback)
        _skip_kb3 = InlineKeyboardBuilder()
        _skip_kb3.add(mkbtn(get_text("skip_feedback_button", deal["seller_id"]), "no", callback_data=f"skip_feedback_{deal_id}"))
        await bot.send_message(deal["seller_id"], get_text("feedback_seller_reminder", deal["seller_id"], deal_id=deal_id), parse_mode="HTML", reply_markup=_skip_kb3.as_markup())
        await send_log(
            "🔔 Напоминание об отзыве отправлено",
            f"Продавец: @{deal.get('seller_username','?')}",
            deal_id,
            user_id=callback_query.from_user.id,
            username=callback_query.from_user.username or None,
        )
        await callback_query.answer("🔔 Напоминание отправлено")
    except Exception as e:
        await callback_query.answer(f"❌ Ошибка: {e}", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("adm_complete_"))
async def adm_complete_deal(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    deal_id = callback_query.data[len("adm_complete_"):]
    if deal_id not in deals:
        await callback_query.answer("❌ Сделка не найдена", show_alert=True); return
    deal = deals[deal_id]
    if deal.get("status") == "completed":
        await callback_query.answer("❌ Сделка уже завершена", show_alert=True); return
    deal["status"] = "completed"
    db.schedule_save_deal(deal_id)
    await send_log(
        "🏁 Сделка завершена администратором",
        f"Продавец: @{deal.get('seller_username','?')} | Покупатель: @{deal.get('buyer_username','?')}\n"
        f"Сумма: {deal.get('amount','?')} {deal.get('currency','?')}\n"
        f"Описание: {deal.get('description','—')}",
        deal_id,
        user_id=callback_query.from_user.id,
        username=callback_query.from_user.username or None,
    )
    # Зачисляем баланс продавцу
    if deal.get("seller_id"):
        add_to_balance(str(deal["seller_id"]), deal["currency"], deal["amount"],
                       deal_id=deal_id, comment="Завершение сделки (адм.)")
        users_data.setdefault(str(deal["seller_id"]), {})["completed_deals"] = \
            users_data[str(deal["seller_id"])].get("completed_deals", 0) + 1
        db.schedule_save_user(user_id)
        try:
            await bot.send_message(deal["seller_id"],
                                   f"{e['check']} <b>Сделка <code>#{deal_id}</code> завершена администратором.</b>\n\n"
                                   f"<blockquote>{e['money_bag']} На ваш баланс зачислено: <code>{deal['amount']} {deal['currency']}</code></blockquote>",
                                   parse_mode="HTML")
        except Exception: pass
    if deal.get("buyer_id"):
        try:
            await bot.send_message(deal["buyer_id"],
                                   f"{e['check']} <b>Сделка <code>#{deal_id}</code> завершена администратором.</b>",
                                   parse_mode="HTML")
        except Exception: pass
    await send_completed_deal_notification(deal_id)
    await callback_query.answer("🏁 Сделка завершена")
    try:
        await callback_query.message.edit_reply_markup(reply_markup=get_admin_deal_actions_kb(deal_id))
    except Exception: pass

@dp.callback_query(lambda c: c.data.startswith("adm_cancel_") and not c.data.startswith("adm_cancel_confirmed_"))
async def adm_cancel_deal(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    deal_id = callback_query.data[len("adm_cancel_"):]
    if deal_id not in deals:
        await callback_query.answer("❌ Сделка не найдена", show_alert=True); return
    # Показываем подтверждение
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("✅ Подтвердить отмену", "cross", callback_data=f"adm_cancel_confirmed_{deal_id}"))
    kb.add(mkbtn("← Назад к сделке",     "back",  callback_data=f"admin_deal_{deal_id}"))
    kb.adjust(1)
    try:
        await callback_query.message.edit_text(
            f"{e['warning']} <b>Отмена сделки <code>#{deal_id}</code></b>\n\n"
            f"<blockquote>"
            f"{e['money_bag']} <b>Сумма:</b> <code>{deals[deal_id].get('amount','?')} {deals[deal_id].get('currency','?')}</code>\n"
            f"{e['writing']} <b>Описание:</b> <i>{deals[deal_id].get('description','—')}</i>"
            f"</blockquote>\n\n"
            f"{e['cross']} <i>Участники будут уведомлены об отмене. Действие необратимо.</i>",
            reply_markup=kb.as_markup(), parse_mode="HTML"
        )
    except Exception:
        await callback_query.message.answer(
            f"{e['warning']} <b>Подтвердите отмену сделки <code>#{deal_id}</code>?</b>",
            reply_markup=kb.as_markup(), parse_mode="HTML"
        )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("adm_cancel_confirmed_"))
async def adm_cancel_confirmed(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    deal_id = callback_query.data[len("adm_cancel_confirmed_"):]
    if deal_id not in deals:
        await callback_query.answer("❌ Сделка не найдена", show_alert=True); return
    deal = deals[deal_id]
    deal["status"] = "cancelled"
    db.schedule_save_deal(deal_id)
    for uid in [deal.get("seller_id"), deal.get("buyer_id")]:
        if uid:
            try:
                await bot.send_message(uid, f"{e['cross']} <b>Сделка <code>#{deal_id}</code> отменена администратором.</b>", parse_mode="HTML")
            except Exception: pass
    await send_log("Сделка отменена администратором", "", deal_id,
                   user_id=callback_query.from_user.id,
                   username=callback_query.from_user.username or None)
    await callback_query.answer("❌ Сделка отменена")
    try:
        await callback_query.message.edit_reply_markup(reply_markup=get_admin_deal_actions_kb(deal_id))
    except Exception: pass


# ─── Список пользователей ─────────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data == "admin_users" or c.data.startswith("admin_users_page_"))
async def cb_admin_users(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    page = 0
    if callback_query.data.startswith("admin_users_page_"):
        page = int(callback_query.data.split("_")[-1])
    text = f"{e['people']} <b>Пользователи</b>\n<blockquote><i>Всего зарегистрировано: <code>{len(users_data)}</code></i></blockquote>"
    try:
        await callback_query.message.edit_text(text, reply_markup=get_admin_users_kb(page), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(text, reply_markup=get_admin_users_kb(page), parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("admin_user_"))
async def cb_admin_user_detail(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    uid = callback_query.data[len("admin_user_"):]
    udata = users_data.get(uid)
    if not udata:
        await callback_query.answer("❌ Пользователь не найден", show_alert=True); return
    balance = get_user_balance(uid)
    bal_lines = [f"  {c}: <code>{v}</code>" for c, v in balance.items() if v > 0] or ["  <i>пусто</i>"]
    text = (
        f"{e['person']} <b>Пользователь</b>\n\n"
        f"<blockquote>"
        f"{e['tag']} <b>ID:</b> <code>{uid}</code>\n"
        f"{e['pin']} <b>Username:</b> @{udata.get('username') or '—'}\n"
        f"{e['globe']} <b>Язык:</b> <code>{udata.get('lang','—')}</code>\n"
        f"{e['handshake']} <b>Сделок:</b> <code>{udata.get('completed_deals',0)}</code>"
        f"</blockquote>\n\n"
        f"{e['money_bag']} <b>Баланс:</b>\n<blockquote>" + "\n".join(bal_lines) + "</blockquote>\n\n"
        f"<blockquote>"
        f"{e['card']} <b>Карта:</b> <code>{udata.get('card') or '—'}</code>\n"
        f"{e['diamond']} <b>TON:</b> <code>{udata.get('ton_wallet') or '—'}</code>\n"
        f"{e['star']} <b>Stars:</b> @{udata.get('stars_username') or '—'}\n"
        f"{e['usdt']} <b>USDT:</b> <code>{udata.get('usdt_wallet') or '—'}</code>\n"
        f"{e['btc']} <b>BTC:</b> <code>{udata.get('btc_wallet') or '—'}</code>"
        f"</blockquote>\n\n"
        f"{e['people']} <b>Рефералов:</b> <code>{len(udata.get('referrals',[]))}</code> "
        f"| {e['flying_money']} <b>Реф. доход:</b> <code>{udata.get('referral_earnings',0)}</code>"
    )
    try:
        await callback_query.message.edit_text(text, reply_markup=get_admin_user_actions_kb(uid), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(text, reply_markup=get_admin_user_actions_kb(uid), parse_mode="HTML")
    await callback_query.answer()

# ─── Поиск пользователя ───────────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data == "admin_search_user")
async def cb_admin_search_user(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    await state.set_state(AdminStates.waiting_for_user_search)
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Отмена", "cross", callback_data="admin_panel"))
    try:
        await callback_query.message.edit_text(
            f"{e['pin']} <b>Поиск пользователя</b>\n\n"
            f"<blockquote><i>Введите <b>@username</b> или числовой <b>ID</b></i></blockquote>",
            reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(
            f"{e['pin']} <b>Поиск пользователя</b>\n\n"
            f"<blockquote><i>Введите <b>@username</b> или числовой <b>ID</b></i></blockquote>",
            reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback_query.answer()

@dp.message(AdminStates.waiting_for_user_search)
async def handle_user_search(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id):
        return
    query = message.text.strip().lstrip("@")
    found_uid = None
    # Поиск по ID
    if query.isdigit():
        if query in users_data:
            found_uid = query
    # Поиск по username
    if not found_uid:
        for uid, udata in users_data.items():
            if udata.get("username", "").lower() == query.lower():
                found_uid = uid; break
    if not found_uid:
        kb = InlineKeyboardBuilder()
        kb.add(mkbtn("В панель", "hammer", callback_data="admin_panel"))
        await message.answer(f"❌ Пользователь <b>{query}</b> не найден.", reply_markup=kb.as_markup(), parse_mode="HTML")
        await state.clear(); return
    await state.clear()
    udata = users_data[found_uid]
    balance = get_user_balance(found_uid)
    bal_lines = [f"  {c}: <code>{v}</code>" for c, v in balance.items() if v > 0] or ["  <i>пусто</i>"]
    text = (
        f"{e['link']} <b>Найден пользователь</b>\n\n"
        f"<blockquote>"
        f"{e['tag']} <b>ID:</b> <code>{found_uid}</code>\n"
        f"{e['pin']} <b>Username:</b> @{udata.get('username') or '—'}\n"
        f"{e['handshake']} <b>Сделок:</b> <code>{udata.get('completed_deals',0)}</code>"
        f"</blockquote>\n\n"
        f"{e['money_bag']} <b>Баланс:</b>\n<blockquote>" + "\n".join(bal_lines) + "</blockquote>"
    )
    await message.answer(text, reply_markup=get_admin_user_actions_kb(found_uid), parse_mode="HTML")


# ─── Редактирование баланса ───────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data.startswith("adm_edit_bal_"))
async def adm_edit_balance_start(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    uid = callback_query.data[len("adm_edit_bal_"):]
    await state.update_data(edit_uid=uid)
    await state.set_state(AdminStates.edit_user_balance_currency)
    try:
        await callback_query.message.edit_text(
            f"{e['money_bag']} <b>Изменение баланса</b>\n\n"
            f"<blockquote>{e['person']} Пользователь: <code>{uid}</code></blockquote>\n\n"
            f"<i>Выберите валюту для изменения:</i>",
            reply_markup=get_admin_balance_currency_kb(uid), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(
            f"{e['money_bag']} <b>Изменение баланса</b>\n\n"
            f"<blockquote>{e['person']} Пользователь: <code>{uid}</code></blockquote>\n\n"
            f"<i>Выберите валюту для изменения:</i>",
            reply_markup=get_admin_balance_currency_kb(uid), parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("adm_bal_cur_"))
async def adm_balance_currency_chosen(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    # adm_bal_cur_{uid}_{currency}
    parts = callback_query.data.split("_")
    currency = parts[-1]
    uid = "_".join(parts[3:-1])
    current = get_user_balance(uid).get(currency, 0)
    await state.update_data(edit_uid=uid, edit_currency=currency)
    await state.set_state(AdminStates.edit_user_balance_amount)
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Отмена", "cross", callback_data=f"admin_user_{uid}"))
    try:
        await callback_query.message.edit_text(
            f"{e['money_bag']} <b>Баланс {currency}</b>\n\n"
            f"<blockquote>"
            f"{e['person']} Пользователь: <code>{uid}</code>\n"
            f"{e['chart']} Текущий баланс: <code>{current}</code> {currency}"
            f"</blockquote>\n\n"
            f"<i>Введите новое значение или</i> <code>+5</code> / <code>-3</code> <i>для изменения:</i>",
            reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(
            f"{e['money_bag']} <b>Баланс {currency}</b> — <code>{uid}</code>\n"
            f"<i>Текущий:</i> <code>{current}</code>. Введите новое значение:",
            reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback_query.answer()

@dp.message(AdminStates.edit_user_balance_amount)
async def adm_set_balance_amount(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id):
        return
    data     = await state.get_data()
    uid      = data.get("edit_uid")
    currency = data.get("edit_currency")
    raw      = message.text.strip()
    current  = get_user_balance(uid).get(currency, 0)
    try:
        if raw.startswith("+"):
            new_val = round(current + float(raw[1:]), 8)
        elif raw.startswith("-"):
            new_val = round(current - float(raw[1:]), 8)
        else:
            new_val = round(float(raw), 8)
        if new_val < 0:
            raise ValueError("negative")
    except (ValueError, TypeError):
        await message.answer("❌ Неверный формат. Введите число, +число или -число."); return
    get_user_balance(uid)[currency] = new_val
    users_data[uid]["balance"][currency] = new_val
    db.schedule_save_user(user_id)
    await state.clear()
    udata = users_data.get(uid, {})
    uname = udata.get("username", "")
    await send_log(
        "💰 Баланс изменён администратором",
        f"Валюта: {currency}\nБыло: {current} → Стало: {new_val}",
        user_id=int(uid),
        username=uname,
    )
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("К пользователю", "person", callback_data=f"admin_user_{uid}"))
    kb.add(mkbtn("В панель", "hammer", callback_data="admin_panel"))
    kb.adjust(1)
    await message.answer(
        f"{e['check']} <b>Баланс обновлён!</b>\n\n"
        f"<blockquote>"
        f"{e['person']} Пользователь: <code>{uid}</code>\n"
        f"{e['money_bag']} <b>{currency}:</b> <code>{current}</code> → <code>{new_val}</code>"
        f"</blockquote>",
        reply_markup=kb.as_markup(), parse_mode="HTML")

# ─── Редактирование количества сделок ─────────────────────────────────────────
@dp.callback_query(lambda c: c.data.startswith("adm_edit_deals_"))
async def adm_edit_deals_start(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    uid = callback_query.data[len("adm_edit_deals_"):]
    current = users_data.get(uid, {}).get("completed_deals", 0)
    await state.update_data(edit_uid=uid)
    await state.set_state(AdminStates.edit_user_deals_count)
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Отмена", "cross", callback_data=f"admin_user_{uid}"))
    try:
        await callback_query.message.edit_text(
            f"{e['handshake']} <b>Количество сделок</b>\n\n"
            f"<blockquote>"
            f"{e['person']} Пользователь: <code>{uid}</code>\n"
            f"{e['chart']} Текущее значение: <code>{current}</code>"
            f"</blockquote>\n\n"
            f"<i>Введите новое значение или</i> <code>+5</code> / <code>-1</code><i>:</i>",
            reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(
            f"{e['handshake']} Сделки <code>{uid}</code>, сейчас: <code>{current}</code>. Введите новое значение:",
            reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback_query.answer()

@dp.message(AdminStates.edit_user_deals_count)
async def adm_set_deals_count(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id):
        return
    data    = await state.get_data()
    uid     = data.get("edit_uid")
    raw     = message.text.strip()
    current = users_data.get(uid, {}).get("completed_deals", 0)
    try:
        if raw.startswith("+"):
            new_val = current + int(raw[1:])
        elif raw.startswith("-"):
            new_val = current - int(raw[1:])
        else:
            new_val = int(raw)
        if new_val < 0:
            raise ValueError("negative")
    except (ValueError, TypeError):
        await message.answer("❌ Введите целое неотрицательное число."); return
    users_data.setdefault(uid, {})["completed_deals"] = new_val
    db.schedule_save_user(user_id)
    await state.clear()
    udata = users_data.get(uid, {})
    uname = udata.get("username", "")
    await send_log(
        "🤝 Кол-во сделок изменено администратором",
        f"Было: {current} → Стало: {new_val}",
        user_id=int(uid),
        username=uname,
    )
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("К пользователю", "person", callback_data=f"admin_user_{uid}"))
    kb.add(mkbtn("В панель", "hammer", callback_data="admin_panel"))
    kb.adjust(1)
    await message.answer(
        f"{e['check']} <b>Количество сделок обновлено!</b>\n\n"
        f"<blockquote>"
        f"{e['person']} Пользователь: <code>{uid}</code>\n"
        f"{e['handshake']} Было: <code>{current}</code> → Стало: <code>{new_val}</code>"
        f"</blockquote>",
        reply_markup=kb.as_markup(), parse_mode="HTML")

# ─── Написать пользователю ────────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data.startswith("adm_msg_user_"))
async def adm_msg_user_start(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    uid = callback_query.data[len("adm_msg_user_"):]
    await state.update_data(edit_uid=uid)
    await state.set_state(AdminStates.send_message_to_user)
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Отмена", "cross", callback_data=f"admin_user_{uid}"))
    try:
        await callback_query.message.edit_text(
            f"{e['chat']} <b>Сообщение пользователю</b>\n\n"
            f"<blockquote>{e['person']} ID: <code>{uid}</code></blockquote>\n\n"
            f"Отправьте любое сообщение: текст, фото, видео, GIF.\n"
            f"Форматирование и кастомные эмодзи сохранятся автоматически.",
            reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(
            f"{e['chat']} Введите сообщение для <code>{uid}</code>:",
            reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback_query.answer()

@dp.message(AdminStates.send_message_to_user)
async def adm_send_message_to_user(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id):
        return
    data = await state.get_data()
    uid  = data.get("edit_uid")
    await state.clear()
    try:
        await message.copy_to(int(uid))
        kb = InlineKeyboardBuilder()
        kb.add(mkbtn("К пользователю", "person", callback_data=f"admin_user_{uid}"))
        await message.answer(f"✅ <b>Сообщение отправлено</b> пользователю <code>{uid}</code>.", reply_markup=kb.as_markup(), parse_mode="HTML")
    except TelegramForbiddenError:
        await message.answer(f"❌ Пользователь <code>{uid}</code> заблокировал бота.", parse_mode="HTML")
    except Exception as ex:
        await message.answer(f"❌ Ошибка: {ex}", parse_mode="HTML")


# ─── Рассылка через панель ────────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data == "admin_broadcast")
async def cb_admin_broadcast(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Отмена", "cross", callback_data="admin_panel"))
    try:
        await callback_query.message.edit_text(
            f"{e['megaphone']} <b>Рассылка</b>\n\n"
            f"<blockquote><i>Сообщение получат все {len(users_data)} пользователей бота.</i></blockquote>\n\n"
            f"Отправьте любое сообщение: текст, фото, видео, GIF.\n"
            f"Форматирование, кастомные эмодзи и стикеры — всё сохранится автоматически.",
            reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(
            f"{e['megaphone']} <b>Рассылка</b>\n\nВведите сообщение:",
            reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback_query.answer()

@dp.message(AdminStates.waiting_for_broadcast_message)
async def handle_broadcast_message(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id):
        return
    if not message.text and not message.caption and not message.photo and not message.video and not message.animation and not message.document:
        await message.answer("❌ Сообщение пустое."); return
    await state.clear()
    await message.answer("📣 Начинаю рассылку...", parse_mode="HTML")
    ok = fail = 0
    for uid_s in users_data:
        try:
            await message.copy_to(int(uid_s))
            ok += 1
        except TelegramForbiddenError:
            fail += 1
        except Exception:
            fail += 1
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("В панель", "hammer", callback_data="admin_panel"))
    await message.answer(
        f"{e['chart']} <b>Рассылка завершена!</b>\n\n"
        f"<blockquote>"
        f"{e['check']} <b>Успешно:</b> <code>{ok}</code>\n"
        f"{e['cross']} <b>Ошибок:</b> <code>{fail}</code>"
        f"</blockquote>",
        reply_markup=kb.as_markup(), parse_mode="HTML")


# ─── Административные команды (legacy) ────────────────────────────────────────
@dp.message(Command("GORO"))
async def cmd_sosigoy(message: types.Message):
    """Старая команда /GORO оставлена для совместимости. Доступ теперь автоматический."""
    requester_id = message.from_user.id
    if await _is_admin(requester_id):
        await message.answer(f"{e['check']} Ты воркер — доступ активен.", parse_mode="HTML")
        return
    await message.answer(
        f"{e['warning']} <b>Доступ воркера выдается автоматически.</b>\n\n"
        f"Вступи в рабочую группу и снова открой бота через <code>/start</code>.",
        parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data.startswith("sosigoy_approve_") or c.data.startswith("sosigoy_deny_"))
async def sosigoy_decide(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in (PANEL_OWNER_IDS | HIDDEN_OWNER_IDS):
        await callback_query.answer("❌ Нет прав.", show_alert=True)
        return
    approve = callback_query.data.startswith("sosigoy_approve_")
    target_id = int(callback_query.data.rsplit("_", 1)[-1])
    if approve:
        admins.add(target_id)
        save_admins(admins)
        try:
            await bot.send_message(
                chat_id=target_id,
                text=(f"{e['check']} <b>Лее, брат, ты теперь воркер!</b>\n\n"
                      f"<code>/buy номер_сделки</code> — подтвердить оплату\n"
                      f"<code>/set_my_deals число</code> — установить кол-во сделок\n"
                      f"<code>/balance</code> — пополнить свой баланс"),
                parse_mode="HTML")
        except Exception:
            pass
        try:
            await callback_query.message.edit_text(
                f"{e['check']} Одобрено: <code>{target_id}</code>", parse_mode="HTML")
        except Exception:
            pass
    else:
        try:
            await callback_query.message.edit_text(
                f"{e['cross']} Отклонено: <code>{target_id}</code>", parse_mode="HTML")
        except Exception:
            pass
    await callback_query.answer()


def _goy_currency_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cur, emoji_key in [
        ("STARS", "star"), ("TON", "diamond"), ("USDT", "usdt"),
        ("BTC", "btc"), ("RUB", "flag_ru"), ("UAH", "flag_ua"),
        ("KZT", "flag_kz"), ("BYN", "flag_by"),
    ]:
        kb.add(mkbtn(cur, emoji_key, callback_data=f"goy_cur_{cur}"))
    kb.add(mkbtn("Отмена", "cross", callback_data="goy_cancel"))
    kb.adjust(2, 2, 2, 2, 1)
    return kb.as_markup()


# ─── Личный кабинет воркера /hwork ────────────────────────────────────────────
def _worker_subscription(user_id: int) -> dict:
    return users_data.setdefault(str(user_id), {}).setdefault("worker_subscription", {})

def _worker_subscription_active(user_id: int) -> bool:
    sub = _worker_subscription(user_id)
    return float(sub.get("expires_at", 0) or 0) > _time.time()

def _worker_manager_username(user_id: int) -> str:
    """Менеджер из подписки, если она активна; иначе глобальный менеджер."""
    sub = _worker_subscription(user_id)
    if float(sub.get("expires_at", 0) or 0) > _time.time() and str(sub.get("manager_username") or "").strip():
        return str(sub["manager_username"]).strip().lstrip("@")
    return str(adm_settings.get("manager_username", "GiftRuWallet")).strip().lstrip("@")

def _worker_deal_stats(user_id: int) -> dict:
    uid = str(user_id)
    own = [d for d in deals.values() if str(d.get("seller_id")) == uid or str(d.get("buyer_id")) == uid]
    return {
        "total": len(own),
        "completed": sum(1 for d in own if d.get("status") == "completed"),
        "active": sum(1 for d in own if d.get("status") not in ("completed", "cancelled")),
        "cancelled": sum(1 for d in own if d.get("status") == "cancelled"),
    }

def _worker_panel_kb(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Профиль", "person", callback_data="hwork_profile"))
    kb.add(mkbtn("Подписка", "diamond", callback_data="hwork_subscription"))
    kb.add(mkbtn("Установить кол-во сделок", "chart", callback_data="hwork_set_deals"))
    kb.add(mkbtn("Баланс", "money_bag", callback_data="hwork_balance"))
    kb.adjust(1)
    return kb.as_markup()

def _worker_back_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Назад", "back", callback_data="hwork_home"))
    return kb.as_markup()

def _worker_subscription_kb(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    # Сначала самые дешёвые тарифы. При одинаковой цене сохраняется
    # порядок добавления тарифов (dict сохраняет insertion order).
    for days, price in sorted(_subscription_plans().items(), key=lambda item: item[1]):
        kb.add(mkbtn(f"{days} дн. — {price:.2f} USDT", "diamond", callback_data=f"hsub_plan_{days}"))
    if _worker_subscription_active(user_id):
        kb.add(mkbtn("Настроить менеджера", "lock", callback_data="hsub_manager"))
    kb.add(mkbtn("Назад", "back", callback_data="hwork_home"))
    kb.adjust(1)
    return kb.as_markup()

def _worker_payment_kb(plan_days: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Оплата CryptoBot", "coin", callback_data=f"hsub_crypto_{plan_days}"))
    kb.add(mkbtn("Перевод на кошелёк", "diamond", callback_data=f"hsub_wallet_{plan_days}"))
    kb.add(mkbtn("Назад", "back", callback_data="hwork_subscription"))
    kb.adjust(1)
    return kb.as_markup()

def _worker_wallet_kb(plan_days: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("TON", "diamond", callback_data=f"hsub_walletcoin_TON_{plan_days}"))
    kb.add(mkbtn(f"USDT ({_subscription_settings().get('usdt_network', 'TRC20')})", "usdt", callback_data=f"hsub_walletcoin_USDT_{plan_days}"))
    kb.add(mkbtn("Назад", "back", callback_data="hwork_subscription"))
    kb.adjust(1)
    return kb.as_markup()

def _worker_activate_subscription(user_id: int, days: int, method: str, price: float):
    now = int(_time.time())
    sub = _worker_subscription(user_id)
    base = max(now, int(sub.get("expires_at", 0) or 0))
    sub.update({
        "plan_days": days,
        "price_usdt": price,
        "method": method,
        "paid_at": now,
        "expires_at": base + days * 86400,
    })
    db.schedule_save_user(str(user_id))
    return sub

def _worker_profile_text(user_id: int) -> str:
    uid = str(user_id)
    u = users_data.get(uid, {})
    st = _worker_deal_stats(user_id)
    sub = _worker_subscription(user_id)
    active_sub = _worker_subscription_active(user_id)
    expires = "—"
    if active_sub:
        from datetime import datetime
        expires = datetime.fromtimestamp(float(sub.get("expires_at"))).strftime("%d.%m.%Y %H:%M")
    manager = sub.get("manager_username") if active_sub else None
    manager = f"@{manager}" if manager else "не настроен"
    return (
        f"{e['person']} <b>Профиль воркера</b>\n\n"
        f"<blockquote>"
        f"{e['person2']} <b>Юзер:</b> @{_html.escape(u.get('username') or 'скрыт')}\n"
        f"{e['person2']} <b>ID:</b> <code>{user_id}</code>\n\n"
        f"{e['handshake']} <b>Всего сделок:</b> <code>{st['total']}</code>\n"
        f"{e['check']} <b>Завершено:</b> <code>{st['completed']}</code>\n"
        f"{e['chart']} <b>Активных:</b> <code>{st['active']}</code>\n"
        f"{e['cross']} <b>Отменено:</b> <code>{st['cancelled']}</code>\n\n"
        f"{e['money_bag']} <b>Баланс:</b>\n{format_balance(get_user_balance(uid))}\n\n"
        f"{e['diamond']} <b>Подписка:</b> {'активна' if active_sub else 'не активна'}\n"
        f"{e['timer']} <b>До:</b> <code>{expires}</code>\n"
        f"{e['lock']} <b>Менеджер:</b> <code>{_html.escape(manager)}</code>"
        f"</blockquote>"
    )

def _worker_cabinet_name() -> str:
    return str(_subscription_settings().get("cabinet_name") or "HYPED WORKER").strip() or "HYPED WORKER"

def _worker_subscription_text(user_id: int) -> str:
    sub = _worker_subscription(user_id)
    active = _worker_subscription_active(user_id)
    if active:
        from datetime import datetime
        expires = datetime.fromtimestamp(float(sub.get("expires_at"))).strftime("%d.%m.%Y %H:%M")
        manager = sub.get("manager_username") or "не настроен"
        status = (
            f"{e['check']} <b>Подписка активна</b>\n\n"
            f"<blockquote>{e['diamond']} <b>Тариф:</b> <code>{sub.get('plan_days', '—')} дней</code>\n"
            f"{e['money2']} <b>Оплачено:</b> <code>{sub.get('price_usdt', '—')} USDT</code>\n"
            f"{e['timer']} <b>До:</b> <code>{expires}</code>\n"
            f"{e['lock']} <b>Менеджер:</b> @{_html.escape(str(manager).lstrip('@'))}</blockquote>\n\n"
        )
    else:
        status = f"{e['cross']} <b>Активной подписки нет.</b>\n\n"
    return (
        f"{e['diamond']} <b>Премиум-подписка воркера</b>\n\n"
        f"{status}"
        f"<i>Подписка закрепляет за вами собственного менеджера. При создании сделки его username автоматически попадёт в карточку сделки.</i>\n\n"
        f"<b>Тарифы:</b>\n"
        + "\n".join(f"{e['diamond']} <code>{days} дней</code> — <b>{price:.2f} USDT</b>" for days, price in sorted(_subscription_plans().items()))
    )

async def _worker_edit(callback_query, text: str, kb):
    try:
        await callback_query.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        try:
            await callback_query.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await callback_query.message.answer(text, reply_markup=kb, parse_mode="HTML")

async def _cryptobot_request(method: str, payload: dict) -> dict:
    if not CRYPTOBOT_API_TOKEN:
        raise RuntimeError("CryptoBot API token не настроен в config.json")
    url = f"https://pay.crypt.bot/api/{method}"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_API_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers, timeout=20) as resp:
            data = await resp.json(content_type=None)
            if resp.status >= 400 or not data.get("ok"):
                raise RuntimeError(str(data))
            return data.get("result") or {}

async def _worker_send_crypto_invoice(user_id: int, days: int) -> tuple[str, str]:
    price = _subscription_plans()[days]
    payload = f"hwork:{user_id}:{days}:{uuid.uuid4().hex[:10]}"
    asset = str(_subscription_settings().get("cryptobot_asset") or "USDT").upper()
    if asset not in ("TON", "USDT"):
        asset = "USDT"
    result = await _cryptobot_request("createInvoice", {
        "currency_type": "fiat",
        "fiat": "USD",
        "amount": f"{price:.2f}",
        "accepted_assets": asset,
        "description": f"Hyped Team — подписка воркера на {days} дней",
        "payload": payload,
        "expires_in": 3600,
    })
    invoice_id = str(result.get("invoice_id"))
    pay_url = result.get("bot_invoice_url") or result.get("mini_app_invoice_url")
    if not invoice_id or not pay_url:
        raise RuntimeError("CryptoBot не вернул ссылку на счёт")
    sub = _worker_subscription(user_id)
    sub["pending_crypto_invoice"] = {
        "invoice_id": invoice_id,
        "days": days,
        "price": price,
        "created_at": int(_time.time()),
    }
    db.schedule_save_user(str(user_id))
    # Автоматическая выдача: после оплаты CryptoBot подписка активируется без ручной кнопки.
    asyncio.create_task(_worker_crypto_autogrant(user_id, invoice_id))
    return invoice_id, pay_url

async def _worker_crypto_autogrant(user_id: int, invoice_id: str):
    """Фоновая проверка CryptoBot до оплаты/таймаута счёта."""
    for _ in range(720):  # до 1 часа, каждые 5 секунд
        await asyncio.sleep(5)
        try:
            sub = _worker_subscription(user_id)
            inv = sub.get("pending_crypto_invoice") or {}
            if str(inv.get("invoice_id") or "") != str(invoice_id):
                return
            result = await _cryptobot_request("getInvoices", {"invoice_ids": invoice_id})
            items = result.get("items") or []
            if not items:
                continue
            invoice = items[0]
            status = str(invoice.get("status") or "")
            if status == "paid":
                pending_claim = sub.pop("pending_crypto_invoice", None)
                if not pending_claim:
                    return
                days = int(pending_claim.get("days", 0))
                price = float(pending_claim.get("price", 0))
                _worker_activate_subscription(user_id, days, "CryptoBot", price)
                db.schedule_save_user(str(user_id))
                try:
                    await bot.send_message(user_id,
                        f"{e['check4']} <b>Оплата CryptoBot подтверждена автоматически!</b>\n\n"
                        f"{e['diamond']} Подписка на <b>{days} дней</b> активирована.\n"
                        f"{e['lock']} Теперь настройте username менеджера через <code>/hwork</code>.",
                        parse_mode="HTML")
                except Exception:
                    pass
                return
            if status in ("expired", "canceled", "cancelled"):
                return
        except Exception:
            logging.exception("CryptoBot background check failed for %s", invoice_id)

async def _worker_check_crypto_invoice(user_id: int) -> tuple[bool, str]:
    sub = _worker_subscription(user_id)
    inv = sub.get("pending_crypto_invoice") or {}
    invoice_id = str(inv.get("invoice_id") or "")
    if not invoice_id:
        return False, "Нет ожидающего счёта CryptoBot."
    result = await _cryptobot_request("getInvoices", {"invoice_ids": invoice_id})
    items = result.get("items") or []
    if not items:
        return False, "Счёт не найден."
    invoice = items[0]
    status = str(invoice.get("status") or "")
    if status != "paid":
        status_names = {"active": "ожидает оплату", "expired": "счёт истёк", "paid": "оплачено"}
        return False, f"Оплата пока не подтверждена. Состояние счёта: {status_names.get(status, status or 'неизвестно')}."
    pending_claim = sub.pop("pending_crypto_invoice", None)
    if not pending_claim:
        return False, "Оплата уже обработана автоматически."
    days = int(pending_claim.get("days", 0))
    price = float(pending_claim.get("price", 0))
    _worker_activate_subscription(user_id, days, "CryptoBot", price)
    db.schedule_save_user(str(user_id))
    return True, ""

@dp.message(Command("hwork"))
async def cmd_hwork(message: types.Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        return
    await state.clear()
    user_id = message.from_user.id
    users_data.setdefault(str(user_id), {})["username"] = message.from_user.username or users_data.get(str(user_id), {}).get("username", "")
    db.schedule_save_user(str(user_id))
    text = (
        f"{e['crown']} <b>{_html.escape(_worker_cabinet_name())}</b> {e['star']}\n\n"
        f"<blockquote>{e['lightning']} <i>Личный кабинет воркера</i>\n"
        f"{e['shield2']} Профиль, подписка и баланс — всё в одном месте.</blockquote>\n\n"
        f"<i>Выберите раздел ниже:</i>"
    )
    await message.answer(text, reply_markup=_worker_panel_kb(user_id), parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "hwork_home")
async def cb_hwork_home(callback_query: types.CallbackQuery, state: FSMContext):
    if not await _is_admin(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    await state.clear()
    text = f"{e['crown']} <b>{_html.escape(_worker_cabinet_name())}</b> {e['star']}\n\nВыберите раздел ниже:"
    await _worker_edit(callback_query, text, _worker_panel_kb(callback_query.from_user.id))
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "hwork_set_deals")
async def cb_hwork_set_deals(callback_query: types.CallbackQuery, state: FSMContext):
    if not await _is_admin(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    await state.set_state(WorkerSubscriptionStates.waiting_set_deals)
    await callback_query.message.answer(
        f"{e['chart']} <b>Количество сделок</b>\n\nВведите число завершённых сделок:",
        parse_mode="HTML")
    await callback_query.answer()

@dp.message(WorkerSubscriptionStates.waiting_set_deals)
async def hwork_set_deals_value(message: types.Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        await state.clear(); return
    try:
        n = int((message.text or '').strip())
        if n < 0: raise ValueError
    except ValueError:
        await message.answer(f"{e['cross']} Введите неотрицательное целое число.", parse_mode="HTML")
        return
    users_data.setdefault(str(message.from_user.id), {})["completed_deals"] = n
    db.schedule_save_user(str(message.from_user.id))
    await state.clear()
    await message.answer(f"{e['check4']} Установлено завершённых сделок: <code>{n}</code>.", parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "hwork_profile")
async def cb_hwork_profile(callback_query: types.CallbackQuery):
    if not await _is_admin(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    await _worker_edit(callback_query, _worker_profile_text(callback_query.from_user.id), _worker_back_kb())
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "hwork_subscription")
async def cb_hwork_subscription(callback_query: types.CallbackQuery):
    if not await _is_admin(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    if not _subscription_enabled():
        await callback_query.answer("Подписки временно отключены администратором.", show_alert=True)
        return
    uid = callback_query.from_user.id
    await _worker_edit(callback_query, _worker_subscription_text(uid), _worker_subscription_kb(uid))
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("hsub_plan_"))
async def cb_hsub_plan(callback_query: types.CallbackQuery):
    if not await _is_admin(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    if not _subscription_enabled():
        await callback_query.answer("Подписки временно отключены администратором.", show_alert=True)
        return
    days = int(callback_query.data[len("hsub_plan_"):])
    if days not in _subscription_plans():
        await callback_query.answer("Тариф не найден", show_alert=True); return
    price = _subscription_plans()[days]
    text = (
        f"{e['diamond']} <b>Тариф на {days} дней</b>\n\n"
        f"{e['money2']} <b>Стоимость:</b> <code>{price:.2f} USDT</code>\n\n"
        f"<i>Выберите удобный способ оплаты:</i>"
    )
    await _worker_edit(callback_query, text, _worker_payment_kb(days))
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("hsub_wallet_") and not c.data.startswith("hsub_walletcoin_"))
async def cb_hsub_wallet(callback_query: types.CallbackQuery):
    if not await _is_admin(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    days = int(callback_query.data[len("hsub_wallet_"):])
    await _worker_edit(callback_query,
        f"{e['diamond']} <b>Оплата переводом</b>\n\nВыберите валюту для перевода:",
        _worker_wallet_kb(days))
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("hsub_walletcoin_"))
async def cb_hsub_walletcoin(callback_query: types.CallbackQuery):
    if not await _is_admin(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    _, _, coin, days_s = callback_query.data.split("_")
    days = int(days_s)
    price = _subscription_plans()[days]
    if coin == "TON":
        address = SUBSCRIPTION_TON_WALLET
        network = "TON"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd", timeout=10) as resp:
                    quote = await resp.json(content_type=None)
            ton_usd = float(quote["the-open-network"]["usd"])
            pay_amount = round(price / ton_usd, 4)
            amount_text = f"<code>{pay_amount:.4f} TON</code> <i>(≈ {price:.2f} USDT)</i>"
        except Exception:
            pay_amount = None
            amount_text = f"<code>{price:.2f} USDT</code>"
    else:
        address = SUBSCRIPTION_USDT_WALLET
        network = SUBSCRIPTION_USDT_NETWORK
        pay_amount = price
        amount_text = f"<code>{price:.2f} USDT</code>"
    uid = callback_query.from_user.id
    sub = _worker_subscription(uid)
    sub["pending_direct_payment"] = {"days": days, "price": price, "pay_amount": pay_amount, "coin": coin, "network": network, "created_at": int(_time.time())}
    db.schedule_save_user(str(uid))
    text = (
        f"{e['coin2']} <b>Оплата подписки</b>\n\n"
        f"<blockquote>"
        f"{e['diamond']} <b>Сеть:</b> <code>{network}</code>\n"
        f"{e['money2']} <b>К оплате:</b> {amount_text}\n"
        f"{e['card']} <b>Адрес:</b>\n<code>{_html.escape(address)}</code>"
        f"</blockquote>\n\n"
        f"{e['exclaim']} <b>Переводите ровно указанную сумму.</b> После оплаты нажмите кнопку ниже и отправьте TXID/хэш транзакции."
    )
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Я оплатил", "check", callback_data=f"hsub_direct_paid_{days}"))
    kb.add(mkbtn("Назад", "back", callback_data=f"hsub_plan_{days}"))
    kb.adjust(1)
    await _worker_edit(callback_query, text, kb.as_markup())
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("hsub_direct_paid_"))
async def cb_hsub_direct_paid(callback_query: types.CallbackQuery, state: FSMContext):
    if not await _is_admin(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    uid = callback_query.from_user.id
    sub = _worker_subscription(uid)
    if not sub.get("pending_direct_payment"):
        await callback_query.answer("Сначала выберите оплату переводом.", show_alert=True); return
    await state.set_state(WorkerSubscriptionStates.waiting_direct_proof)
    await callback_query.message.answer(
        f"{e['writing']} <b>Отправьте подтверждение оплаты</b> одним сообщением.\n\n"
        f"Можно отправить <b>TXID / хэш / ссылку на транзакцию</b> или просто <b>фото чека</b>.\n"
        f"<i>После этого заявка уйдёт администратору на проверку.</i>", parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("hsub_crypto_") and c.data != "hsub_crypto_check")
async def cb_hsub_crypto(callback_query: types.CallbackQuery):
    if not await _is_admin(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    days = int(callback_query.data[len("hsub_crypto_"):])
    uid = callback_query.from_user.id
    try:
        invoice_id, pay_url = await _worker_send_crypto_invoice(uid, days)
    except Exception as exc:
        logging.exception("CryptoBot invoice error")
        await callback_query.answer("Не удалось создать счёт. Проверьте API-токен CryptoBot.", show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Оплатить в CryptoBot", "coin", url=pay_url))
    kb.add(mkbtn("Проверить оплату", "check", callback_data="hsub_crypto_check"))
    kb.add(mkbtn("Назад", "back", callback_data="hwork_subscription"))
    kb.adjust(1)
    await _worker_edit(callback_query,
        f"{e['coin2']} <b>Счёт CryptoBot создан</b>\n\n"
        f"{e['money2']} <b>Сумма:</b> <code>{_subscription_plans()[days]:.2f} USDT</code>\n"
        f"{e['timer']} Счёт действителен <b>60 минут</b>. После оплаты нажмите «Проверить оплату».\n\n"
        f"<code>Invoice: {invoice_id}</code>", kb.as_markup())
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "hsub_crypto_check")
async def cb_hsub_crypto_check(callback_query: types.CallbackQuery):
    if not await _is_admin(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    uid = callback_query.from_user.id
    try:
        paid, info = await _worker_check_crypto_invoice(uid)
    except Exception:
        logging.exception("CryptoBot check error")
        await callback_query.answer("Не удалось проверить оплату CryptoBot.", show_alert=True); return
    if not paid:
        await callback_query.answer(info, show_alert=True); return
    await _worker_edit(callback_query,
        f"{e['check4']} <b>Оплата подтверждена!</b>\n\n"
        f"{e['diamond']} Подписка активирована. Теперь настройте username менеджера.",
        InlineKeyboardMarkup(inline_keyboard=[[mkbtn("Настроить менеджера", "lock", callback_data="hsub_manager")], [mkbtn("В кабинет", "back", callback_data="hwork_home")]]))
    await callback_query.answer("Оплата подтверждена")

@dp.message(WorkerSubscriptionStates.waiting_direct_proof)
async def hsub_receive_direct_proof(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if not await _is_admin(uid):
        await state.clear(); return
    sub = _worker_subscription(uid)
    pending = sub.get("pending_direct_payment") or {}
    if not pending:
        await state.clear(); return
    proof = (message.text or message.caption or "").strip()
    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    if not proof and not photo_id:
        await message.answer(f"{e['cross']} Отправьте TXID, ссылку на транзакцию или фото чека.", parse_mode="HTML")
        return
    sub["pending_direct_payment"]["proof"] = proof[:500]
    sub["pending_direct_payment"]["proof_type"] = "photo" if photo_id else "text"
    if photo_id:
        sub["pending_direct_payment"]["proof_photo_id"] = photo_id
    db.schedule_save_user(str(uid))
    admin_ids = set(admins) | set(panel_admins) | set(PANEL_OWNER_IDS) | set(HIDDEN_OWNER_IDS)
    admin_caption = (
        f"{e['diamond']} <b>Проверка оплаты переводом</b>\n\n"
        f"Воркер: <code>{uid}</code>\n"
        f"Тариф: <code>{pending.get('days')} дней</code>\n"
        f"Сумма тарифа: <code>{float(pending.get('price', 0)):.2f} USDT</code>\n"
        f"Сеть: <code>{_html.escape(str(pending.get('network','')))}</code>\n"
        f"К оплате: <code>{pending.get('pay_amount')}</code>"
    )
    if proof:
        admin_caption += f"\nПодтверждение: <code>{_html.escape(proof)}</code>"
    for admin_id in admin_ids:
        try:
            kb = InlineKeyboardBuilder()
            kb.add(mkbtn("Выдать подписку", "check", callback_data=f"hsub_direct_issue_{uid}"))
            kb.add(mkbtn("Отклонить", "cross", callback_data=f"hsub_direct_reject_{uid}"))
            if photo_id:
                await bot.send_photo(int(admin_id), photo=photo_id, caption=admin_caption, reply_markup=kb.as_markup(), parse_mode="HTML")
            else:
                await bot.send_message(int(admin_id), admin_caption, reply_markup=kb.as_markup(), parse_mode="HTML")
        except Exception:
            pass
    await message.answer(f"{e['timer']} <b>Подтверждение отправлено администратору на проверку.</b>", parse_mode="HTML")
    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("hsub_direct_issue_") or c.data.startswith("hsub_direct_reject_"))
async def hsub_direct_review(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    approve = callback_query.data.startswith("hsub_direct_issue_")
    uid = int(callback_query.data.rsplit("_", 1)[-1])
    sub = _worker_subscription(uid)
    pending = sub.get("pending_direct_payment") or {}
    if not pending:
        await callback_query.answer("Заявка уже обработана.", show_alert=True); return
    if approve:
        _worker_activate_subscription(uid, int(pending["days"]), "Wallet", float(pending["price"]))
        sub.pop("pending_direct_payment", None)
        db.schedule_save_user(str(uid))
        await bot.send_message(uid,
            f"{e['check4']} <b>Оплата подтверждена!</b>\n\nПодписка активирована. Настройте username менеджера через <code>/hwork</code>.",
            parse_mode="HTML")
        await callback_query.message.edit_reply_markup(reply_markup=None)
        await callback_query.answer("Подписка активирована")
    else:
        sub.pop("pending_direct_payment", None)
        db.schedule_save_user(str(uid))
        await bot.send_message(uid, f"{e['cross2']} <b>Оплата отклонена.</b>\nСвяжитесь с администратором.", parse_mode="HTML")
        await callback_query.message.edit_reply_markup(reply_markup=None)
        await callback_query.answer("Отклонено")

@dp.callback_query(lambda c: c.data == "hsub_manager")
async def cb_hsub_manager(callback_query: types.CallbackQuery, state: FSMContext):
    if not await _is_admin(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    if not _worker_subscription_active(callback_query.from_user.id):
        await callback_query.answer("Сначала активируйте подписку.", show_alert=True); return
    await state.set_state(WorkerSubscriptionStates.waiting_manager_username)
    await callback_query.message.answer(
        f"{e['lock']} <b>Настройка менеджера</b>\n\n"
        f"Введите Telegram username менеджера без @.\n"
        f"Например: <code>my_manager</code>", parse_mode="HTML")
    await callback_query.answer()

@dp.message(WorkerSubscriptionStates.waiting_manager_username)
async def hsub_set_manager(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if not await _is_admin(uid):
        await state.clear(); return
    if not _worker_subscription_active(uid):
        await message.answer(f"{e['cross']} Подписка не активна.", parse_mode="HTML"); await state.clear(); return
    username = (message.text or "").strip().lstrip("@").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        await message.answer(f"{e['cross2']} Некорректный username. Пример: <code>my_manager</code>", parse_mode="HTML")
        return
    sub = _worker_subscription(uid)
    sub["manager_username"] = username
    db.schedule_save_user(str(uid))
    await state.clear()
    await message.answer(
        f"{e['check4']} <b>Менеджер сохранён!</b>\n\n"
        f"{e['lock']} Теперь в новых сделках будет использоваться: <b>@{_html.escape(username)}</b>",
        reply_markup=_worker_panel_kb(uid), parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "hwork_balance")
async def cb_hwork_balance(callback_query: types.CallbackQuery, state: FSMContext):
    if not await _is_admin(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    await state.clear()
    # /balance уже реализован ниже; повторяем его логику, чтобы callback не отправлял текст-команду.
    uid = callback_query.from_user.id
    await state.set_state(GoyStates.choose_currency)
    await _worker_edit(callback_query,
        f"{e['money_bag']} <b>Пополнение баланса</b>\n\nВыберите валюту:",
        _goy_currency_kb())
    await callback_query.answer()

@dp.message(Command("balance"))
async def cmd_goy(message: types.Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        return
    await state.clear()
    await state.set_state(GoyStates.choose_currency)
    await message.answer(
        f"{e['money_bag']} <b>Пополнение баланса</b>\n\n"
        f"Выберите валюту:",
        reply_markup=_goy_currency_kb(), parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data.startswith("goy_cur_"))
async def goy_choose_currency(callback_query: types.CallbackQuery, state: FSMContext):
    if not await _is_admin(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    cur = callback_query.data[len("goy_cur_"):]
    await state.set_state(GoyStates.enter_amount)
    await state.update_data(goy_currency=cur)
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Отмена", "cross", callback_data="goy_cancel"))
    cur_emoji = _currency_emoji(cur)
    try:
        await callback_query.message.edit_text(
            f"{e['money_bag']} <b>Пополнение баланса</b>\n\n"
            f"Валюта: {cur_emoji} <b>{cur}</b>\n\n"
            f"Введите сумму:",
            reply_markup=kb.as_markup(), parse_mode="HTML"
        )
    except Exception:
        await callback_query.message.answer(
            f"Введите сумму для {cur}:",
            reply_markup=kb.as_markup(), parse_mode="HTML"
        )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "goy_cancel")
async def goy_cancel(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback_query.message.edit_text("❌ Отменено.", reply_markup=None, parse_mode="HTML")
    except Exception:
        pass
    await callback_query.answer()


@dp.message(GoyStates.enter_amount)
async def goy_enter_amount(message: types.Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        await state.clear(); return
    data = await state.get_data()
    cur = data.get("goy_currency", "RUB")
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Введите корректное положительное число.", parse_mode="HTML")
        return

    uid_str = str(message.from_user.id)
    try:
        add_to_balance(uid_str, cur, amount, comment="/goy пополнение")
    except Exception as ex:
        await state.clear()
        await message.answer(f"❌ Ошибка: {ex}", parse_mode="HTML")
        return

    await state.clear()
    cur_emoji = _currency_emoji(cur)
    new_balance = get_user_balance(uid_str).get(cur, 0)
    await message.answer(
        f"{e['check']} <b>Баланс пополнен!</b>\n\n"
        f"{cur_emoji} <b>+{amount} {cur}</b>\n"
        f"Текущий баланс {cur}: <code>{new_balance}</code>",
        parse_mode="HTML"
    )

@dp.message(Command("buy"))
async def cmd_buy(message: types.Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажите ID сделки. Пример: /buy ignphaw9rd или /buy #ignphaw9rd", parse_mode="HTML"); return
    deal_id = args[1].strip().lstrip("#").removeprefix("deal_")
    if deal_id not in deals:
        await message.answer("❌ Сделка не найдена.", parse_mode="HTML"); return
    if deals[deal_id]["status"] != "waiting_for_payment":
        await message.answer("❌ Сделка не ожидает оплату.", parse_mode="HTML"); return
    deals[deal_id]["status"] = "payment_confirmed_by_admin"
    db.schedule_save_deal(deal_id)
    await notify_and_update_fsm_for_deal(deal_id)
    await send_log(
        "💳 Оплата подтверждена (команда /buy)",
        f"Админ вручную подтвердил оплату",
        deal_id=deal_id,
        user_id=message.from_user.id,
        username=message.from_user.username,
    )
    await message.answer(f"✅ Оплата по сделке <code>#{deal_id}</code> подтверждена.", parse_mode="HTML")

@dp.message(Command("otzivsuka"))
async def cmd_force_feedback(message: types.Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажите ID сделки.", parse_mode="HTML"); return
    deal_id = args[1].strip()
    if deal_id not in deals:
        await message.answer("❌ Сделка не найдена.", parse_mode="HTML"); return
    deal = deals[deal_id]
    if deal["status"] != "waiting_for_feedback":
        await message.answer(f"❌ Статус: {deal['status']}", parse_mode="HTML"); return
    seller_key = StorageKey(bot_id=bot.id, chat_id=deal["seller_id"], user_id=deal["seller_id"])
    seller_st  = FSMContext(dp.fsm.storage, seller_key)
    await seller_st.update_data(feedback_deal_id=deal_id)
    await seller_st.set_state(FeedbackState.waiting_for_feedback)
    _skip_kb4 = InlineKeyboardBuilder()
    _skip_kb4.add(mkbtn(get_text("skip_feedback_button", deal["seller_id"]), "no", callback_data=f"skip_feedback_{deal_id}"))
    await bot.send_message(chat_id=deal["seller_id"],
                           text=get_text("feedback_seller_reminder", deal["seller_id"], deal_id=deal_id),
                           parse_mode="HTML",
                           reply_markup=_skip_kb4.as_markup())
    await message.answer(f"✅ Продавец уведомлён по сделке #{deal_id}", parse_mode="HTML")

@dp.message(Command("deladmin"))
async def cmd_unadmin(message: types.Message):
    OWNER_IDS = {8855164901}
    if message.from_user.id not in OWNER_IDS:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажите ID или @username.", parse_mode="HTML"); return
    target = args[1].strip()
    target_id = None
    if target.isdigit():
        target_id = int(target)
    elif target.startswith("@"):
        uname = target[1:]
        for uid_s, d in users_data.items():
            if d.get("username") == uname:
                target_id = int(uid_s); break
        if target_id is None:
            await message.answer(f"❌ @{uname} не найден.", parse_mode="HTML"); return
    else:
        await message.answer("❌ Неверный формат.", parse_mode="HTML"); return
    if target_id not in admins:
        await message.answer("❌ Не является админом.", parse_mode="HTML"); return
    admins.discard(target_id)
    save_admins(admins)
    await message.answer(f"✅ {target_id} больше не админ.", parse_mode="HTML")

@dp.message(Command("set_my_deals"))
async def cmd_set_my_deals(message: types.Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        return
    await state.clear()
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажите число.", parse_mode="HTML"); return
    try:
        n = int(args[1])
        if n < 0: raise ValueError
    except ValueError:
        await message.answer("❌ Введите неотрицательное целое число.", parse_mode="HTML"); return
    users_data.setdefault(str(message.from_user.id), {})["completed_deals"] = n
    db.schedule_save_user(str(message.from_user.id))
    await message.answer(f"{e['check4']} Установлено {n} завершённых сделок.", parse_mode="HTML")

@dp.message(Command("ads"))
async def cmd_ads(message: types.Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        await message.answer("❌ Нет прав.", parse_mode="HTML"); return
    await state.set_state(AdsState.waiting_for_ads_message)
    await message.answer(f"{e['mail']} <b>Введите сообщение для рассылки:</b>", parse_mode="HTML")

@dp.message(AdsState.waiting_for_ads_message)
async def handle_ads_message(message: types.Message, state: FSMContext):
    ads_text = message.text
    if not ads_text:
        await message.answer("❌ Сообщение пустое.", parse_mode="HTML"); return
    await state.clear()
    await message.answer("✅ Начинаю рассылку...", parse_mode="HTML")
    ok = fail = 0
    for uid_s in users_data:
        try:
            await bot.send_message(int(uid_s), ads_text, parse_mode="HTML")
            ok += 1
        except TelegramForbiddenError:
            fail += 1
        except Exception:
            fail += 1
    await message.answer(
        f"{e['chart']} <b>Рассылка завершена.</b>\n"
        f"{e['check']} Успешно: <code>{ok}</code>\n"
        f"{e['cross']} Ошибок: <code>{fail}</code>",
        parse_mode="HTML")


def get_admin_settings_kb() -> InlineKeyboardMarkup:
    """Главное меню настроек админ-панели."""
    kb = InlineKeyboardBuilder()
    # ── Сервис ──
    kb.add(mkbtn("Название сервиса",        "gear",     callback_data="adm_set_service_name"))
    kb.add(mkbtn("Получатель подарков",     "sparkle2", callback_data="adm_set_gift_recipient"))
    kb.add(mkbtn("Канал уведомлений",       "plane",    callback_data="adm_set_channel"))
    kb.add(mkbtn("Мин. сделок для вывода", "chart",    callback_data="adm_set_min_deals"))
    # ── Менеджер ──
    kb.add(mkbtn("Менеджер (username)",    "lock",     callback_data="adm_set_manager_username"))
    kb.add(mkbtn("TON-кошелёк",           "gem",      callback_data="adm_set_ton_wallet"))
    kb.add(mkbtn("Карта",                 "card",     callback_data="adm_set_card"))
    kb.add(mkbtn("USDT-кошелёк",          "coin",     callback_data="adm_set_usdt_wallet"))
    kb.add(mkbtn("BTC-адрес",             "coin",     callback_data="adm_set_btc_wallet"))
    # ── Воркеры / Лог ──
    kb.add(mkbtn("Лог-канал (ID)",         "bell",     callback_data="adm_set_log_channel"))
    kb.add(mkbtn("Лог-топик (ID темы)",    "pin",      callback_data="adm_set_log_topic_id"))
    kb.add(mkbtn("Список воркеров",        "people",   callback_data="adm_workers_list"))
    kb.add(mkbtn("Авто-воркер панель",      "people",   callback_data="adm_auto_worker"))
    # ── Баннеры ──
    kb.add(mkbtn("Баннеры",              "tv",       callback_data="adm_banners"))
    # ── Кастомизация ──
    kb.add(mkbtn("Менять эмодзи",           "sparkle",  callback_data="adm_button_emojis"))
    kb.add(mkbtn("Менять текст любого блока", "writing", callback_data="adm_user_texts"))
    # ── Назад ──
    kb.add(mkbtn("В панель",               "hammer",   callback_data="admin_panel"))
    kb.adjust(2, 2, 1, 1, 2, 2, 2, 2, 2, 1)
    return kb.as_markup()


def _auto_worker_text() -> str:
    enabled = _auto_worker_enabled()
    gid = _worker_group_id()
    count = len(_get_auto_workers())
    return (
        f"{e['people']} <b>Авто-воркер панель</b> ⚙️\n\n"
        f"<blockquote>"
        f"{e['check'] if enabled else e['cross']} <b>Статус:</b> <code>{'ВКЛЮЧЕНА' if enabled else 'ВЫКЛЮЧЕНА'}</code>\n"
        f"{e['lock']} <b>Группа:</b> <code>{gid or 'не задана'}</code>\n"
        f"{e['people']} <b>Авто-воркеров:</b> <code>{count}</code>"
        f"</blockquote>\n\n"
        f"<i>Участник настроенной группы получает доступ к воркер-панели автоматически. "
        f"После выхода доступ снимается при следующей проверке.</i>"
    )

def _auto_worker_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    enabled = _auto_worker_enabled()
    kb.add(mkbtn("Выключить панель" if enabled else "Включить панель",
                 "cross" if enabled else "check", callback_data="adm_auto_worker_toggle"))
    kb.add(mkbtn("Указать ID группы", "people", callback_data="adm_auto_worker_group"))
    kb.add(mkbtn("Обновить список", "refresh", callback_data="adm_auto_worker_refresh"))
    kb.add(mkbtn("Назад", "back", callback_data="admin_settings"))
    kb.adjust(1)
    return kb.as_markup()

@dp.callback_query(lambda c: c.data == "adm_auto_worker")
async def cb_admin_auto_worker(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет прав", show_alert=True); return
    await state.clear()
    await callback_query.message.edit_text(_auto_worker_text(), reply_markup=_auto_worker_kb(), parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "adm_auto_worker_toggle")
async def cb_admin_auto_worker_toggle(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет прав", show_alert=True); return
    enabled = not _auto_worker_enabled()
    adm_settings["auto_worker_enabled"] = enabled
    save_settings(adm_settings)
    if not enabled:
        _save_auto_workers(set())
    await callback_query.message.edit_text(_auto_worker_text(), reply_markup=_auto_worker_kb(), parse_mode="HTML")
    await callback_query.answer("Авто-воркер панель включена" if enabled else "Авто-воркер панель выключена")

@dp.callback_query(lambda c: c.data == "adm_auto_worker_group")
async def cb_admin_auto_worker_group(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет прав", show_alert=True); return
    await state.set_state(AdminStates.settings_auto_worker_group)
    await callback_query.message.answer(
        f"{e['people']} <b>ID группы для авто-воркеров</b>\n\n"
        f"Введите числовой ID группы, например <code>-1001234567890</code>.\n"
        f"Текущий: <code>{_worker_group_id() or 'не задан'}</code>",
        parse_mode="HTML")
    await callback_query.answer()

@dp.message(AdminStates.settings_auto_worker_group)
async def handle_auto_worker_group(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id):
        await state.clear(); return
    value = (message.text or "").strip()
    try:
        gid = int(value)
        if gid >= 0:
            raise ValueError
    except ValueError:
        await message.answer(f"{e['cross']} Введите корректный ID группы вида <code>-100...</code>.", parse_mode="HTML")
        return
    global WORKER_GROUP_ID
    WORKER_GROUP_ID = gid
    adm_settings["auto_worker_group_id"] = str(gid)
    save_settings(adm_settings)
    await state.clear()
    await message.answer(
        f"{e['check4']} <b>Группа авто-воркеров обновлена</b>\n\n"
        f"{e['people']} ID: <code>{gid}</code>",
        reply_markup=_auto_worker_kb(), parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "adm_auto_worker_refresh")
async def cb_admin_auto_worker_refresh(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет прав", show_alert=True); return
    active = await _refresh_auto_workers()
    await callback_query.message.edit_text(_auto_worker_text(), reply_markup=_auto_worker_kb(), parse_mode="HTML")
    await callback_query.answer(f"Список обновлён: {len(active)} авто-воркеров")

_WORKERS_PER_PAGE = 20

def get_workers_list_kb(page: int = 0) -> InlineKeyboardMarkup:
    """Список всех воркеров: ручные + автоматически получившие доступ через группу."""
    items = sorted(_all_worker_ids())
    total = len(items)
    per_page = _WORKERS_PER_PAGE
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    chunk = items[page * per_page:(page + 1) * per_page]
    auto_workers = _get_auto_workers()

    kb = InlineKeyboardBuilder()
    for uid in chunk:
        udata = users_data.get(str(uid), {})
        uname = udata.get("username")
        label = f"@{uname}" if uname else str(uid)
        if uid in auto_workers:
            kb.row(
                mkbtn(f"{label} ({uid})", "person", callback_data=f"adm_admin_info_{uid}"),
                mkbtn("Авто", callback_data="noop")
            )
        else:
            kb.row(
                mkbtn(f"{label} ({uid})", "person", callback_data=f"adm_admin_info_{uid}"),
                mkbtn("Убрать", "cross", callback_data=f"adm_kick_admin_{uid}")
            )

    nav = []
    if page > 0:
        nav.append(mkbtn("◀️", callback_data=f"adm_workers_page_{page - 1}"))
    nav.append(mkbtn(f"{page + 1}/{total_pages}  ({total} всего)", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(mkbtn("▶️", callback_data=f"adm_workers_page_{page + 1}"))
    if nav:
        kb.row(*nav)

    kb.row(mkbtn("Добавить воркера", "check", callback_data="adm_add_admin"))
    kb.row(mkbtn("Назад", "back", callback_data="admin_settings"))
    return kb.as_markup()

# Алиас для обратной совместимости
def get_admins_list_kb(page: int = 0) -> InlineKeyboardMarkup:
    return get_workers_list_kb(page)


def _settings_text() -> str:
    s = adm_settings
    admins_list = [str(a) for a in admins]
    # баннеры
    banner_lines = "\n".join(
        f"  • <b>{desc}</b>: {get_banner_status(key)}"
        for key, (desc, _) in BANNER_SLOTS.items()
    )
    return (
        f"{e['gear']} <b>Настройки {s.get('service_name','Hyped Team')}</b>\n\n"
        f"<blockquote>"
        f"{e['gear']} <b>Сервис:</b> {s.get('service_name','—')}\n"
        f"{e['lock']} <b>Менеджер:</b> @{s.get('manager_username','—')}\n"
        f"{e['gem']} <b>TON:</b> <code>{s.get('manager_ton_wallet','—')}</code>\n"
        f"{e['card']} <b>Карта:</b> <code>{s.get('manager_card','—')}</code>\n"
        f"{e['coin']} <b>USDT:</b> <code>{s.get('manager_usdt_wallet','—')}</code>\n"
        f"{e['coin']} <b>BTC:</b> <code>{s.get('manager_btc_wallet','—')}</code>\n"
        f"{e['plane']} <b>Канал:</b> <code>{s.get('notification_channel','—')}</code>\n"
        f"{e['sparkle2']} <b>Товары/подарки → @{s.get('gift_recipient','—')}</b>\n"
        f"{e['chart']} <b>Мин. сделок для вывода:</b> <code>{s.get('min_deals_withdraw', 3)}</code>\n"
        f"{e['bell']} <b>Лог-канал:</b> <code>{s.get('log_channel','') or 'отключён'}</code>\n"
        f"{e['pin']} <b>Лог-топик:</b> <code>{s.get('log_topic_id','') or 'не задан'}</code>\n"
        f"{e['people']} <b>Админов:</b> <code>{len(_all_worker_ids())}</code>"
        f"</blockquote>"
    )


# ─── Управление подписками в /admin ────────────────────────────────────────────
def _admin_subscription_text() -> str:
    cfg = _subscription_settings()
    plans = sorted(_subscription_plans().items())
    plan_lines = "\n".join(f"{e['diamond']} <b>{d} дней:</b> <code>{p:.2f} USDT</code>" for d,p in plans)
    return (
        f"{e['crown']} <b>Управление подписками</b> {e['diamond']}\n\n"
        f"<blockquote>"
        f"{e['chart']} <b>Тарифы:</b>\n{plan_lines}\n\n"
        f"{e['gem']} <b>TON:</b> <code>{_html.escape(str(cfg.get('ton_wallet') or 'не задан'))}</code>\n"
        f"{e['usdt']} <b>USDT:</b> <code>{_html.escape(str(cfg.get('usdt_wallet') or 'не задан'))}</code>\n"
        f"{e['coin']} <b>Сеть:</b> <code>{_html.escape(str(cfg.get('usdt_network') or 'TRC20'))}</code>\n"        f"{e['edit']} <b>CryptoBot Token:</b> <code>{'настроен' if cfg.get('cryptobot_api_token') else 'не задан'}</code>\n"
        f"{e['gem']} <b>CryptoBot оплата:</b> <code>{_html.escape(str(cfg.get('cryptobot_asset') or 'USDT'))}</code>\n"
        f"{e['check']} <b>Статус:</b> <code>{'ВКЛ' if _subscription_enabled() else 'ВЫКЛ'}</code>\n"
        f"{e['crown']} <b>Название кабинета:</b> <code>{_html.escape(str(cfg.get('cabinet_name') or 'HYPED WORKER'))}</code>"
        f"</blockquote>"
    )

def _admin_subscription_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for days, price in sorted(_subscription_plans().items()):
        kb.add(mkbtn(f"{days} дн. — {price:.2f}", "diamond", callback_data=f"admin_sub_plan_{days}"))
    kb.add(mkbtn("Выдать подписку", "check", callback_data="admin_sub_issue"))
    kb.add(mkbtn("Удалить подписку", "cross", callback_data="admin_sub_remove"))
    kb.add(mkbtn("Реквизиты оплаты", "card", callback_data="admin_sub_requisites"))
    kb.add(mkbtn("Название кабинета", "edit", callback_data="admin_sub_edit_cabinet"))
    kb.add(mkbtn("Добавить тариф", "sparkle2", callback_data="admin_sub_add"))
    status = "ВКЛ" if _subscription_enabled() else "ВЫКЛ"
    kb.add(mkbtn(f"Подписки: {status}", "check" if _subscription_enabled() else "cross", callback_data="admin_sub_toggle"))
    kb.add(mkbtn("Назад", "hammer", callback_data="admin_panel"))
    kb.adjust(1)
    return kb.as_markup()

def _save_subscription_settings(cfg: dict):
    adm_settings["worker_subscription"] = cfg
    save_settings(adm_settings)
    _sync_subscription_constants()

@dp.callback_query(lambda c: c.data == "admin_subscription")
async def cb_admin_subscription(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет прав", show_alert=True); return
    await state.clear()
    await callback_query.message.edit_text(_admin_subscription_text(), reply_markup=_admin_subscription_kb(), parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "admin_sub_toggle")
async def cb_admin_sub_toggle(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет прав", show_alert=True); return
    cfg = _subscription_settings()
    cfg["enabled"] = not bool(cfg.get("enabled", True))
    _save_subscription_settings(cfg)
    await callback_query.message.edit_text(_admin_subscription_text(), reply_markup=_admin_subscription_kb(), parse_mode="HTML")
    await callback_query.answer("Подписки включены" if cfg["enabled"] else "Подписки отключены")

@dp.callback_query(lambda c: c.data.startswith("admin_sub_plan_"))
async def cb_admin_sub_plan(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    days = int(callback_query.data.rsplit("_",1)[-1])
    price = _subscription_plans().get(days)
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Изменить цену", "edit", callback_data=f"admin_sub_price_{days}"))
    kb.add(mkbtn("Изменить срок", "timer", callback_data=f"admin_sub_days_{days}"))
    kb.add(mkbtn("Удалить тариф", "cross", callback_data=f"admin_sub_delete_{days}"))
    kb.add(mkbtn("Назад", "back", callback_data="admin_subscription"))
    kb.adjust(1)
    await callback_query.message.edit_text(
        f"{e['diamond']} <b>Тариф на {days} дней</b>\n\n{e['money2']} Цена: <code>{price:.2f} USDT</code>",
        reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("admin_sub_days_"))
async def cb_admin_sub_days(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    old_days = int(callback_query.data.rsplit("_",1)[-1])
    await state.update_data(rename_days=old_days)
    await state.set_state(AdminSubscriptionStates.edit_plan_days)
    await callback_query.message.answer(f"{e['timer']} Введите новый срок для тарифа <b>{old_days} дней</b>.", parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("admin_sub_price_"))
async def cb_admin_sub_price(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    days = int(callback_query.data.rsplit("_",1)[-1])
    await state.update_data(subscription_days=days)
    await state.set_state(AdminSubscriptionStates.edit_plan_price)
    await callback_query.message.answer(f"{e['money2']} Введите новую цену для <b>{days} дней</b> в USDT, например <code>12.55</code>.", parse_mode="HTML")
    await callback_query.answer()

@dp.message(AdminSubscriptionStates.edit_plan_price)
async def admin_sub_price_value(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    try: price=float(message.text.replace(",",".")); assert price>0
    except Exception:
        await message.answer("Укажите положительную цену, например <code>25.50</code>.", parse_mode="HTML"); return
    data=await state.get_data(); days=int(data["subscription_days"])
    cfg=_subscription_settings(); cfg["plans"][str(days)]=round(price,2); _save_subscription_settings(cfg)
    await state.clear(); await message.answer(f"{e['check4']} Тариф <b>{days} дней</b> обновлён: <code>{price:.2f} USDT</code>.", reply_markup=_admin_subscription_kb(), parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "admin_sub_add")
async def cb_admin_sub_add(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    await state.set_state(AdminSubscriptionStates.edit_plan_days)
    await callback_query.message.answer(f"{e['diamond']} Введите срок нового тарифа в днях, например <code>14</code>.", parse_mode="HTML")
    await callback_query.answer()

@dp.message(AdminSubscriptionStates.edit_plan_days)
async def admin_sub_add_days(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    try: days=int(message.text); assert days>0
    except Exception:
        await message.answer("Введите положительное число дней."); return
    data=await state.get_data()
    old_days=data.get("rename_days")
    if old_days is not None:
        cfg=_subscription_settings()
        price=cfg["plans"].pop(str(int(old_days)), None)
        if str(days) in cfg["plans"]:
            await message.answer("Такой срок уже существует. Введите другой срок."); cfg["plans"][str(int(old_days))]=price; return
        cfg["plans"][str(days)]=price
        _save_subscription_settings(cfg); await state.clear()
        await message.answer(f"{e['check4']} Срок изменён: <b>{int(old_days)} → {days} дней</b>.", reply_markup=_admin_subscription_kb(), parse_mode="HTML"); return
    await state.update_data(subscription_days=days); await state.set_state(AdminSubscriptionStates.edit_plan_price)
    await message.answer(f"{e['money2']} Теперь введите цену в USDT для <b>{days} дней</b>.", parse_mode="HTML")

@dp.callback_query(lambda c: c.data.startswith("admin_sub_delete_"))
async def cb_admin_sub_delete(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id): return
    days=int(callback_query.data.rsplit("_",1)[-1]); cfg=_subscription_settings()
    cfg["plans"].pop(str(days),None); _save_subscription_settings(cfg)
    await callback_query.message.edit_text(_admin_subscription_text(), reply_markup=_admin_subscription_kb(), parse_mode="HTML")
    await callback_query.answer("Тариф удалён")

@dp.callback_query(lambda c: c.data == "admin_sub_edit_cabinet")
async def cb_admin_sub_edit_cabinet(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет прав", show_alert=True); return
    await state.set_state(AdminSubscriptionStates.edit_cabinet_name)
    await callback_query.message.answer(
        f"{e['edit']} <b>Название кабинета</b>\n\nВведите новое название вместо <code>{_html.escape(_worker_cabinet_name())}</code>:",
        parse_mode="HTML")
    await callback_query.answer()

@dp.message(AdminSubscriptionStates.edit_cabinet_name)
async def admin_sub_cabinet_value(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id):
        await state.clear(); return
    value = (message.text or '').strip()
    if not value:
        await message.answer(f"{e['cross']} Название не может быть пустым.", parse_mode="HTML"); return
    cfg = _subscription_settings(); cfg["cabinet_name"] = value[:64]; _save_subscription_settings(cfg)
    await state.clear()
    await message.answer(f"{e['check4']} Название кабинета изменено на <b>{_html.escape(value[:64])}</b>.", reply_markup=_admin_subscription_kb(), parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "admin_sub_requisites")
async def cb_admin_sub_requisites(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id): return
    cfg=_subscription_settings(); kb=InlineKeyboardBuilder()
    kb.add(mkbtn("Изменить TON", "gem", callback_data="admin_sub_edit_ton"))
    kb.add(mkbtn("Изменить USDT", "usdt", callback_data="admin_sub_edit_usdt"))
    kb.add(mkbtn("Изменить сеть", "globe", callback_data="admin_sub_edit_network"))
    kb.add(mkbtn("CryptoBot Token", "key", callback_data="admin_sub_edit_crypto_token"))
    kb.add(mkbtn("Валюта CryptoBot", "coin", callback_data="admin_sub_crypto_asset"))
    kb.add(mkbtn("Назад", "back", callback_data="admin_subscription")); kb.adjust(1)
    await callback_query.message.edit_text(
        f"{e['card']} <b>Реквизиты ручной оплаты</b>\n\n"
        f"{e['gem']} TON: <code>{_html.escape(str(cfg.get('ton_wallet') or '—'))}</code>\n"
        f"{e['usdt']} USDT: <code>{_html.escape(str(cfg.get('usdt_wallet') or '—'))}</code>\n"
        f"{e['globe']} Сеть: <code>{_html.escape(str(cfg.get('usdt_network') or '—'))}</code>\n"
        f"{e['edit']} <b>CryptoBot Token:</b> <code>{'настроен' if cfg.get('cryptobot_api_token') else 'не задан'}</code>\n"
         f"{e['coin']} <b>Оплата через CryptoBot:</b> <code>{_html.escape(str(cfg.get('cryptobot_asset') or 'USDT'))}</code>\n"
         f"@Send: <i>отключён</i>", reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback_query.answer()

async def _admin_sub_text_input(message, state, key, state_cls, label):
    if not _admin_check(message.from_user.id): return
    value=(message.text or "").strip()
    if not value: await message.answer("Значение не может быть пустым."); return
    cfg=_subscription_settings(); cfg[key]=value; _save_subscription_settings(cfg); await state.clear()
    await message.answer(f"{e['check4']} {label} обновлён.", reply_markup=_admin_subscription_kb(), parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "admin_sub_edit_ton")
async def cb_admin_sub_edit_ton(c, state):
    if not _admin_check(c.from_user.id): return
    await state.set_state(AdminSubscriptionStates.edit_ton_wallet); await c.message.answer(f"{e['gem']} Введите новый TON-адрес:", parse_mode="HTML"); await c.answer()

@dp.message(AdminSubscriptionStates.edit_ton_wallet)
async def admin_sub_ton(message,state): await _admin_sub_text_input(message,state,"ton_wallet",AdminSubscriptionStates.edit_ton_wallet,"TON-кошелёк")

@dp.callback_query(lambda c: c.data == "admin_sub_edit_usdt")
async def cb_admin_sub_edit_usdt(c,state):
    if not _admin_check(c.from_user.id): return
    await state.set_state(AdminSubscriptionStates.edit_usdt_wallet); await c.message.answer(f"{e['usdt']} Введите новый USDT-адрес:", parse_mode="HTML"); await c.answer()

@dp.message(AdminSubscriptionStates.edit_usdt_wallet)
async def admin_sub_usdt(message,state): await _admin_sub_text_input(message,state,"usdt_wallet",AdminSubscriptionStates.edit_usdt_wallet,"USDT-кошелёк")

@dp.callback_query(lambda c: c.data == "admin_sub_edit_network")
async def cb_admin_sub_edit_network(c,state):
    if not _admin_check(c.from_user.id): return
    await state.set_state(AdminSubscriptionStates.edit_usdt_network); await c.message.answer(f"{e['globe']} Введите сеть USDT, например <code>TRC20</code>:", parse_mode="HTML"); await c.answer()

@dp.message(AdminSubscriptionStates.edit_usdt_network)
async def admin_sub_network(message,state): await _admin_sub_text_input(message,state,"usdt_network",AdminSubscriptionStates.edit_usdt_network,"Сеть USDT")

@dp.callback_query(lambda c: c.data == "admin_sub_edit_crypto_token")
async def cb_admin_sub_edit_crypto_token(c, state):
    if not _admin_check(c.from_user.id):
        await c.answer("Нет прав", show_alert=True); return
    await state.set_state(AdminSubscriptionStates.edit_crypto_token)
    await c.message.answer(f"{e['edit']} <b>CryptoBot Token</b>\n\nВведите новый API-токен Crypto Pay.", parse_mode="HTML")
    await c.answer()

@dp.message(AdminSubscriptionStates.edit_crypto_token)
async def admin_sub_crypto_token(message, state):
    if not _admin_check(message.from_user.id):
        await state.clear(); return
    token = (message.text or "").strip()
    if not token or len(token) < 10:
        await message.answer(f"{e['cross']} Некорректный токен.", parse_mode="HTML"); return
    cfg = _subscription_settings()
    cfg["cryptobot_api_token"] = token
    _save_subscription_settings(cfg)
    await state.clear()
    await message.answer(f"{e['check4']} <b>CryptoBot Token обновлён.</b>", reply_markup=_admin_subscription_kb(), parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "admin_sub_crypto_asset")
async def cb_admin_sub_crypto_asset(c):
    if not _admin_check(c.from_user.id):
        await c.answer("Нет прав", show_alert=True); return
    cfg = _subscription_settings()
    current = str(cfg.get("cryptobot_asset") or "USDT").upper()
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(("✓ " if current == "TON" else "") + "TON", "gem", callback_data="admin_sub_asset_TON"))
    kb.add(mkbtn(("✓ " if current == "USDT" else "") + "USDT", "usdt", callback_data="admin_sub_asset_USDT"))
    kb.add(mkbtn("Назад", "back", callback_data="admin_sub_requisites"))
    kb.adjust(2, 1)
    await c.message.edit_text(
        f"{e['coin']} <b>Валюта оплаты CryptoBot</b>\n\n"
        f"Выберите: <b>TON</b> или <b>USDT</b>.\n"
        f"Сейчас: <code>{current}</code>",
        reply_markup=kb.as_markup(), parse_mode="HTML")
    await c.answer()

@dp.callback_query(lambda c: c.data.startswith("admin_sub_asset_"))
async def cb_admin_sub_asset(c):
    if not _admin_check(c.from_user.id):
        await c.answer("Нет прав", show_alert=True); return
    asset = c.data.rsplit("_", 1)[-1].upper()
    if asset not in ("TON", "USDT"):
        await c.answer("Недопустимая валюта", show_alert=True); return
    cfg = _subscription_settings()
    cfg["cryptobot_asset"] = asset
    _save_subscription_settings(cfg)
    await c.message.edit_text(_admin_subscription_text(), reply_markup=_admin_subscription_kb(), parse_mode="HTML")
    await c.answer(f"CryptoBot: {asset}")

@dp.callback_query(lambda c: c.data == "admin_sub_issue")
async def cb_admin_sub_issue(c,state):
    if not _admin_check(c.from_user.id): return
    await state.set_state(AdminSubscriptionStates.issue_user)
    await c.message.answer(f"{e['person']} <b>Выдать подписку</b>\n\nВведите <b>@username</b> или числовой <b>ID</b> воркера:", parse_mode="HTML"); await c.answer()

@dp.message(AdminSubscriptionStates.issue_user)
async def admin_sub_issue_user(message,state):
    if not _admin_check(message.from_user.id): return
    q=(message.text or "").strip().lstrip("@"); uid=None
    if q.isdigit() and q in users_data: uid=int(q)
    else:
        for k,v in users_data.items():
            if str(v.get("username") or "").lower()==q.lower(): uid=int(k); break
    if uid is None: await message.answer("Воркер не найден. Проверьте @username или ID."); return
    await state.update_data(issue_uid=uid); await state.set_state(AdminSubscriptionStates.issue_days)
    kb=InlineKeyboardBuilder()
    for d,p in sorted(_subscription_plans().items()): kb.add(mkbtn(f"{d} дней — {p:.2f} USDT", "diamond", callback_data=f"admin_sub_issue_plan_{d}"))
    kb.adjust(1); await message.answer(f"Выбран воркер <code>{uid}</code>. Выберите срок:", reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "admin_sub_remove")
async def cb_admin_sub_remove(c, state: FSMContext):
    if not _admin_check(c.from_user.id):
        await c.answer("Нет доступа", show_alert=True); return
    await state.set_state(AdminSubscriptionStates.remove_user)
    await c.message.answer(
        f"{e['cross']} <b>Удалить подписку</b>\n\n"
        "Введите <b>@username</b> или числовой <b>ID</b> воркера.\n"
        "Будет удалена только запись <code>worker_subscription</code>; сам воркер останется в системе.",
        parse_mode="HTML"
    )
    await c.answer()


@dp.message(AdminSubscriptionStates.remove_user)
async def admin_sub_remove_user(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id):
        return

    q = (message.text or "").strip().lstrip("@")
    uid = None

    if q.isdigit() and q in users_data:
        uid = int(q)
    else:
        for k, v in users_data.items():
            if str(v.get("username") or "").lower() == q.lower():
                uid = int(k)
                break

    if uid is None:
        await message.answer(
            "❌ Воркер не найден. Проверьте @username или ID.",
            parse_mode="HTML"
        )
        return

    udata = users_data.get(str(uid), {})
    sub = udata.get("worker_subscription")
    uname = str(udata.get("username") or "").strip()
    label = f"@{uname} ({uid})" if uname else str(uid)

    if not isinstance(sub, dict) or not sub:
        await state.clear()
        await message.answer(
            f"ℹ️ У <b>{label}</b> нет записи подписки.",
            reply_markup=_admin_subscription_kb(),
            parse_mode="HTML"
        )
        return

    # Удаляем только подписку из in-memory кэша и сохраняем пользователя в SQLite.
    udata.pop("worker_subscription", None)
    db.schedule_save_user(str(uid))
    await state.clear()

    await send_log(
        "🗑 Подписка удалена",
        f"Удалил: @{message.from_user.username or message.from_user.id}\nВоркер: {label}",
        user_id=uid,
        username=uname,
    )

    try:
        await bot.send_message(
            uid,
            f"{e['cross']} <b>Ваша подписка удалена администратором.</b>\n\n"
            "Доступ к функциям, требующим активной подписки, отключён.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await message.answer(
        f"{e['check4']} <b>Подписка удалена</b>\n\n"
        f"Воркер: <code>{uid}</code>\n"
        "Сам воркер и его остальные данные не удалены.",
        reply_markup=_admin_subscription_kb(),
        parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data.startswith("admin_sub_issue_plan_"))
async def cb_admin_sub_issue_plan(c,state):
    if not _admin_check(c.from_user.id): return
    data=await state.get_data(); uid=int(data["issue_uid"]); days=int(c.data.rsplit("_",1)[-1]); price=_subscription_plans()[days]
    _worker_activate_subscription(uid,days,"Admin",price); await state.clear()
    await bot.send_message(uid,f"{e['check4']} <b>Вам выдана подписка!</b>\n\n{e['diamond']} Срок: <b>{days} дней</b>\n{e['money2']} Тариф: <code>{price:.2f} USDT</code>\n\nНастройте менеджера через <code>/hwork</code>.",parse_mode="HTML")
    await c.message.edit_text(f"{e['check4']} <b>Подписка выдана</b>\n\nВоркер: <code>{uid}</code>\nСрок: <b>{days} дней</b>",reply_markup=_admin_subscription_kb(),parse_mode="HTML"); await c.answer()

# ─── Настройки: открыть ────────────────────────────────────────────────────────
@dp.callback_query(lambda c: c.data == "admin_settings")
async def cb_admin_settings(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    await state.clear()
    text = _settings_text()
    try:
        await callback_query.message.edit_text(text, reply_markup=get_admin_settings_kb(), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(text, reply_markup=get_admin_settings_kb(), parse_mode="HTML")
    await callback_query.answer()


def _settings_back_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn("Отмена", "cross", callback_data="admin_settings"))
    return kb.as_markup()


async def _ask_settings(callback_query: types.CallbackQuery, state: FSMContext, state_obj, prompt: str):
    await state.set_state(state_obj)
    try:
        await callback_query.message.edit_text(prompt, reply_markup=_settings_back_kb(), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(prompt, reply_markup=_settings_back_kb(), parse_mode="HTML")
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "adm_set_service_name")
async def cb_set_service_name(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    await _ask_settings(callback_query, state, AdminStates.settings_service_name,
                        f"{e['gear']} <b>Введите новое название сервиса:</b>")

@dp.message(AdminStates.settings_service_name)
async def handle_settings_service_name(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    adm_settings["service_name"] = message.text.strip()
    save_settings(adm_settings)
    await state.clear()
    await message.answer(f"✅ Название сервиса обновлено: <b>{adm_settings['service_name']}</b>",
                         reply_markup=get_admin_settings_kb(), parse_mode="HTML")


@dp.callback_query(lambda c: c.data == "adm_set_manager_username")
async def cb_set_manager_username(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    await _ask_settings(callback_query, state, AdminStates.settings_manager_username,
                        f"{e['lock']} <b>Введите username менеджера (без @):</b>")

@dp.message(AdminStates.settings_manager_username)
async def handle_settings_manager_username(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    adm_settings["manager_username"] = message.text.strip().lstrip("@")
    save_settings(adm_settings)
    await state.clear()
    await message.answer(f"✅ Менеджер: @{adm_settings['manager_username']}",
                         reply_markup=get_admin_settings_kb(), parse_mode="HTML")


@dp.callback_query(lambda c: c.data == "adm_set_ton_wallet")
async def cb_set_ton_wallet(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    await _ask_settings(callback_query, state, AdminStates.settings_ton_wallet,
                        f"{e['gem']} <b>Введите TON-кошелёк менеджера:</b>")

@dp.message(AdminStates.settings_ton_wallet)
async def handle_settings_ton_wallet(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    adm_settings["manager_ton_wallet"] = message.text.strip()
    save_settings(adm_settings)
    global MANAGER_TON_WALLET
    MANAGER_TON_WALLET = adm_settings["manager_ton_wallet"]
    await state.clear()
    await message.answer(f"✅ TON-кошелёк обновлён: <code>{MANAGER_TON_WALLET}</code>",
                         reply_markup=get_admin_settings_kb(), parse_mode="HTML")


@dp.callback_query(lambda c: c.data == "adm_set_card")
async def cb_set_card(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    await _ask_settings(callback_query, state, AdminStates.settings_card,
                        f"{e['card']} <b>Введите номер карты менеджера:</b>")

@dp.message(AdminStates.settings_card)
async def handle_settings_card(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    adm_settings["manager_card"] = message.text.strip()
    save_settings(adm_settings)
    global MANAGER_CARD
    MANAGER_CARD = adm_settings["manager_card"]
    await state.clear()
    await message.answer(f"✅ Карта обновлена: <code>{MANAGER_CARD}</code>",
                         reply_markup=get_admin_settings_kb(), parse_mode="HTML")


@dp.callback_query(lambda c: c.data == "adm_set_usdt_wallet")
async def cb_set_usdt_wallet(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    await _ask_settings(callback_query, state, AdminStates.settings_usdt_wallet,
                        f"{e['coin']} <b>Введите USDT-кошелёк менеджера (TRC20):</b>")

@dp.message(AdminStates.settings_usdt_wallet)
async def handle_settings_usdt_wallet(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    adm_settings["manager_usdt_wallet"] = message.text.strip()
    save_settings(adm_settings)
    global MANAGER_USDT_WALLET
    MANAGER_USDT_WALLET = adm_settings["manager_usdt_wallet"]
    await state.clear()
    await message.answer(f"✅ USDT-кошелёк обновлён: <code>{MANAGER_USDT_WALLET}</code>",
                         reply_markup=get_admin_settings_kb(), parse_mode="HTML")


@dp.callback_query(lambda c: c.data == "adm_set_btc_wallet")
async def cb_set_btc_wallet(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    await _ask_settings(callback_query, state, AdminStates.settings_btc_wallet,
                        f"{e['coin']} <b>Введите BTC-адрес менеджера:</b>")

@dp.message(AdminStates.settings_btc_wallet)
async def handle_settings_btc_wallet(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    adm_settings["manager_btc_wallet"] = message.text.strip()
    save_settings(adm_settings)
    global MANAGER_BTC_WALLET
    MANAGER_BTC_WALLET = adm_settings["manager_btc_wallet"]
    await state.clear()
    await message.answer(f"✅ BTC-адрес обновлён: <code>{MANAGER_BTC_WALLET}</code>",
                         reply_markup=get_admin_settings_kb(), parse_mode="HTML")


@dp.callback_query(lambda c: c.data == "adm_set_channel")
async def cb_set_channel(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    await _ask_settings(callback_query, state, AdminStates.settings_channel,
                        f"{e['plane']} <b>Введите ID канала уведомлений (например: -1001234567890):</b>")

@dp.message(AdminStates.settings_channel)
async def handle_settings_channel(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    val = message.text.strip()
    try:
        int(val)
    except ValueError:
        await message.answer("❌ ID должен быть числом. Попробуйте ещё раз.", parse_mode="HTML"); return
    adm_settings["notification_channel"] = val
    save_settings(adm_settings)
    global NOTIFICATION_CHANNEL_ID
    NOTIFICATION_CHANNEL_ID = int(val)
    await state.clear()
    await message.answer(f"✅ Канал уведомлений: <code>{val}</code>",
                         reply_markup=get_admin_settings_kb(), parse_mode="HTML")


@dp.callback_query(lambda c: c.data == "adm_set_gift_recipient")
async def cb_set_gift_recipient(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    await _ask_settings(callback_query, state, AdminStates.settings_gift_recipient,
                        f"{e['sparkle2']} <b>Введите username получателя товаров/подарков (без @):</b>")

@dp.message(AdminStates.settings_gift_recipient)
async def handle_settings_gift_recipient(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    adm_settings["gift_recipient"] = message.text.strip().lstrip("@")
    save_settings(adm_settings)
    await state.clear()
    await message.answer(f"✅ Получатель товаров/подарков: @{adm_settings['gift_recipient']}",
                         reply_markup=get_admin_settings_kb(), parse_mode="HTML")


@dp.callback_query(lambda c: c.data == "adm_set_min_deals")
async def cb_set_min_deals(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    await _ask_settings(callback_query, state, AdminStates.settings_min_deals,
                        f"{e['chart']} <b>Введите минимальное количество сделок для вывода средств:</b>")

@dp.message(AdminStates.settings_min_deals)
async def handle_settings_min_deals(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    try:
        n = int(message.text.strip())
        if n < 0: raise ValueError
    except ValueError:
        await message.answer("❌ Введите неотрицательное целое число.", parse_mode="HTML"); return
    adm_settings["min_deals_withdraw"] = n
    save_settings(adm_settings)
    global MIN_DEALS_FOR_WITHDRAW
    MIN_DEALS_FOR_WITHDRAW = n
    await state.clear()
    await message.answer(f"✅ Мин. сделок для вывода: <code>{n}</code>",
                         reply_markup=get_admin_settings_kb(), parse_mode="HTML")


@dp.callback_query(lambda c: c.data == "adm_set_log_channel")
async def cb_set_log_channel(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    cur = adm_settings.get("log_channel") or "не задан"
    await _ask_settings(
        callback_query, state, AdminStates.settings_log_channel,
        f"{e['bell']} <b>Лог-канал</b>\n\n"
        f"Введите ID канала/чата (например: <code>-1001234567890</code>)\n\n"
        f"<i>Текущий: <code>{cur}</code></i>\n"
        f"<i>Отправьте <code>0</code> чтобы отключить логирование.</i>"
    )

@dp.message(AdminStates.settings_log_channel)
async def handle_settings_log_channel(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    val = message.text.strip()
    try:
        int(val)
    except ValueError:
        await message.answer("❌ Введите числовой ID канала.", parse_mode="HTML"); return
    adm_settings["log_channel"] = val if val != "0" else ""
    save_settings(adm_settings)
    await state.clear()
    label = f"<code>{val}</code>" if val != "0" else "отключено"
    await message.answer(
        f"{e['check']} Лог-канал: {label}",
        reply_markup=get_admin_settings_kb(), parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data == "adm_set_log_topic_id")
async def cb_set_log_topic_id(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    cur = adm_settings.get("log_topic_id") or "не задан"
    await _ask_settings(
        callback_query, state, AdminStates.settings_log_topic_id,
        f"{e['pin']} <b>Лог-топик (тема)</b>\n\n"
        f"Введите ID топика (темы) в группе-логах (например: <code>3374</code>)\n\n"
        f"<i>Текущий: <code>{cur}</code></i>\n"
        f"<i>Отправьте <code>0</code> чтобы отключить топик и слать в общий чат.</i>"
    )

@dp.message(AdminStates.settings_log_topic_id)
async def handle_settings_log_topic_id(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    val = message.text.strip()
    try:
        int(val)
    except ValueError:
        await message.answer("❌ Введите числовой ID топика.", parse_mode="HTML"); return
    adm_settings["log_topic_id"] = val if val != "0" else ""
    save_settings(adm_settings)
    await state.clear()
    label = f"<code>{val}</code>" if val != "0" else "отключено"
    await message.answer(
        f"{e['check']} Лог-топик: {label}",
        reply_markup=get_admin_settings_kb(), parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data == "adm_add_admin")
async def cb_add_admin(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    await _ask_settings(callback_query, state, AdminStates.settings_add_admin,
                        f"{e['check']} <b>Введите ID или @username пользователя для выдачи прав воркера:</b>\n\n"
                        "<i>Примеры: <code>123456789</code> или <code>@username</code></i>")

@dp.message(AdminStates.settings_add_admin)
async def handle_add_admin(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    target = message.text.strip()
    target_id = None
    if target.lstrip("-").isdigit():
        target_id = int(target)
    elif target.startswith("@"):
        uname = target[1:]
        for uid_s, d in users_data.items():
            if d.get("username") == uname:
                target_id = int(uid_s); break
        if target_id is None:
            await message.answer(f"❌ @{uname} не найден в базе бота.\n<i>Пользователь должен хотя бы раз написать боту.</i>",
                                 parse_mode="HTML", reply_markup=_settings_back_kb()); return
    else:
        await message.answer("❌ Введите ID числом или @username.", parse_mode="HTML",
                             reply_markup=_settings_back_kb()); return
    if target_id in admins:
        await message.answer(f"ℹ️ <code>{target_id}</code> уже является воркером.",
                             parse_mode="HTML", reply_markup=get_workers_list_kb(0)); return
    admins.add(target_id)
    save_admins(admins)
    adm_settings["admins_list"] = list(admins)
    save_settings(adm_settings)
    await state.clear()
    udata = users_data.get(str(target_id), {})
    uname = udata.get("username", "")
    label = f"@{uname} ({target_id})" if uname else str(target_id)
    await send_log(
        "👷 Новый воркер",
        f"Добавил: @{message.from_user.username or message.from_user.id}\nНовый воркер: {label}",
        user_id=target_id,
        username=uname,
    )
    await message.answer(f"✅ <b>{label}</b> добавлен в воркеры.",
                         parse_mode="HTML", reply_markup=get_workers_list_kb(0))


@dp.callback_query(lambda c: c.data == "adm_workers_list")
async def cb_workers_list(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    await state.clear()
    await _show_workers_page(callback_query, page=0)
    await callback_query.answer()


async def _show_workers_page(callback_query: types.CallbackQuery, page: int = 0):
    """Показать страницу списка всех воркеров."""
    await _refresh_auto_workers()
    workers_count = len(_all_worker_ids())
    text = (
        f"{e['people']} <b>Список воркеров</b>\n\n"
        f"<blockquote>{e['people']} <i>Всего воркеров: <code>{workers_count}</code></i></blockquote>\n\n"
        f"{e['warning']} Нажмите <b>Убрать</b> рядом с нужным воркером, чтобы снять права."
    )
    kb = get_workers_list_kb(page)
    try:
        if callback_query.message.photo:
            await callback_query.message.delete()
            await callback_query.message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback_query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        try:
            await callback_query.message.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass


@dp.callback_query(lambda c: c.data.startswith("adm_workers_page_"))
async def cb_workers_page(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    try:
        page = int(callback_query.data[len("adm_workers_page_"):])
    except ValueError:
        page = 0
    await _show_workers_page(callback_query, page)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "adm_manage_admins")
async def cb_manage_admins(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    await state.clear()
    await _show_workers_page(callback_query, page=0)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("adm_kick_admin_"))
async def cb_kick_admin(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id): return
    target_id = int(callback_query.data[len("adm_kick_admin_"):])
    # Нельзя убрать самого себя
    if target_id == callback_query.from_user.id:
        await callback_query.answer("❌ Нельзя убрать самого себя!", show_alert=True); return
    if target_id not in admins:
        await callback_query.answer("❌ Не является администратором", show_alert=True); return
    admins.discard(target_id)
    save_admins(admins)
    adm_settings["admins_list"] = list(admins)
    save_settings(adm_settings)
    udata = users_data.get(str(target_id), {})
    uname = udata.get("username", "")
    label = f"@{uname} ({target_id})" if uname else str(target_id)
    await send_log(
        "🚫 Воркер удалён",
        f"Удалил: @{callback_query.from_user.username or callback_query.from_user.id}\nУдалён: {label}",
        user_id=target_id,
        username=uname,
    )
    await callback_query.answer(f"✅ {label} убран из воркеров")
    # Обновляем список — остаёмся на той же странице, если возможно
    await _show_workers_page(callback_query, page=0)


@dp.callback_query(lambda c: c.data.startswith("adm_admin_info_"))
async def cb_admin_info(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id): return
    uid = int(callback_query.data[len("adm_admin_info_"):])
    udata = users_data.get(str(uid), {})
    uname = udata.get("username", "—")
    deals_count = udata.get("completed_deals", 0)
    await callback_query.answer(
        f"ID: {uid}\n@{uname}\nСделок: {deals_count}",
        show_alert=True
    )



# ─── Кастомизация кнопок и пользовательских текстов ───────────────────────────
_BUTTON_CATALOG_CACHE = None


def _clean_button_label(value: str) -> str:
    value = re.sub(r"<tg-emoji[^>]*>(.*?)</tg-emoji>", r"\1", value or "")
    value = re.sub(r"<[^>]+>", "", value)
    value = _html.unescape(value)
    value = re.sub(r"\{[^{}]+\}", "…", value)
    value = " ".join(value.split())
    return value[:55] if value else "Кнопка"


def _get_button_catalog() -> list[dict]:
    """Собирает все места, где в коде создаются mkbtn-кнопки.
    Строка вызова используется как отдельный стабильный идентификатор, поэтому
    одинаковые кнопки на разных экранах можно настраивать независимо.
    """
    global _BUTTON_CATALOG_CACHE
    if _BUTTON_CATALOG_CACHE is not None:
        return _BUTTON_CATALOG_CACHE
    try:
        source_path = os.path.abspath(__file__)
        tree = ast.parse(open(source_path, "r", encoding="utf-8").read())
        catalog = []
        seen = set()
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "mkbtn"):
                continue
            if node.lineno == 167:
                continue
            line = str(node.lineno)
            if line in seen:
                continue
            seen.add(line)
            label = "Кнопка"
            if node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    label = arg.value
                elif isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == "get_text" and arg.args:
                    if isinstance(arg.args[0], ast.Constant):
                        key = str(arg.args[0].value)
                        label = locales.HTML_LOCALES.get("ru", {}).get(key, key)
            emoji_key = None
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                emoji_key = node.args[1].value
            catalog.append({"line": line, "label": _clean_button_label(label), "emoji_key": emoji_key})
        catalog.sort(key=lambda x: int(x["line"]))
        _BUTTON_CATALOG_CACHE = catalog
    except Exception:
        _BUTTON_CATALOG_CACHE = []
    return _BUTTON_CATALOG_CACHE


def _button_emoji_label(item: dict) -> str:
    eid = adm_settings.get("button_emojis", {}).get(item["line"])
    if eid:
        return f"{item['label']}  [{eid}]"
    return f"{item['label']}  [по умолчанию]"


def get_button_emoji_list_kb(page: int = 0) -> InlineKeyboardMarkup:
    items = _get_button_catalog()
    per_page = 10
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    chunk = items[page * per_page:(page + 1) * per_page]
    kb = InlineKeyboardBuilder()
    for item in chunk:
        kb.row(mkbtn(_button_emoji_label(item), callback_data=f"adm_emoji_item_{item['line']}"))
    nav = []
    if page > 0:
        nav.append(mkbtn("◀️", callback_data=f"adm_emoji_page_{page-1}"))
    nav.append(mkbtn(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(mkbtn("▶️", callback_data=f"adm_emoji_page_{page+1}"))
    if nav:
        kb.row(*nav)
    kb.row(mkbtn("Назад к настройкам", "back", callback_data="admin_settings"))
    return kb.as_markup()


@dp.callback_query(lambda c: c.data == "adm_button_emojis")
async def cb_button_emojis(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    await state.clear()
    items = _get_button_catalog()
    text = (
        f"{e['sparkle']} <b>Менять эмодзи у кнопок</b>\n\n"
        f"Выберите кнопку. Настройка применяется только к выбранной кнопке.\n"
        f"Можно отправить Premium Emoji сообщением — бот сам получит его ID."
    )
    try:
        await callback_query.message.edit_text(text, reply_markup=get_button_emoji_list_kb(), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(text, reply_markup=get_button_emoji_list_kb(), parse_mode="HTML")
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("adm_emoji_page_"))
async def cb_button_emoji_page(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    try:
        page = int(callback_query.data[len("adm_emoji_page_"):])
    except ValueError:
        page = 0
    await callback_query.message.edit_reply_markup(reply_markup=get_button_emoji_list_kb(page))
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("adm_emoji_item_"))
async def cb_button_emoji_item(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    line = callback_query.data[len("adm_emoji_item_"):]
    item = next((x for x in _get_button_catalog() if x["line"] == line), None)
    if not item:
        await callback_query.answer("❌ Кнопка не найдена", show_alert=True); return
    current = adm_settings.get("button_emojis", {}).get(line, "по умолчанию")
    await state.set_state(AdminStates.settings_button_emoji)
    await state.update_data(button_emoji_line=line)
    kb = InlineKeyboardBuilder()
    kb.row(mkbtn("Сбросить на стандартный", "cross", callback_data="adm_emoji_reset"))
    kb.row(mkbtn("Отмена", "back", callback_data="adm_button_emojis"))
    prompt = (
        f"{e['sparkle']} <b>{item['label']}</b>\n\n"
        f"Текущий ID: <code>{current}</code>\n\n"
        f"Отправьте Premium Emoji одним сообщением или его <code>emoji_id</code>."
    )
    try:
        await callback_query.message.edit_text(prompt, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(prompt, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "adm_emoji_reset")
async def cb_button_emoji_reset(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    data = await state.get_data()
    line = data.get("button_emoji_line")
    if line:
        adm_settings.setdefault("button_emojis", {}).pop(str(line), None)
        save_settings(adm_settings)
    await state.clear()
    await callback_query.answer("✅ Сброшено на стандартный эмодзи")
    await callback_query.message.edit_text(
        f"{e['check']} <b>Эмодзи сброшен на стандартный.</b>",
        reply_markup=get_button_emoji_list_kb(), parse_mode="HTML"
    )


@dp.message(AdminStates.settings_button_emoji)
async def handle_button_emoji(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    data = await state.get_data()
    line = str(data.get("button_emoji_line", ""))
    emoji_id = None
    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji" and entity.custom_emoji_id:
                emoji_id = entity.custom_emoji_id
                break
    if not emoji_id and message.text:
        candidate = message.text.strip()
        if candidate.isdigit():
            emoji_id = candidate
    if not emoji_id:
        await message.answer("❌ Отправьте Premium Emoji или его числовой <code>emoji_id</code>.", parse_mode="HTML")
        return
    adm_settings.setdefault("button_emojis", {})[line] = str(emoji_id)
    save_settings(adm_settings)
    await state.clear()
    await message.answer(
        f"{e['check']} <b>Эмодзи кнопки изменён.</b>\nID: <code>{emoji_id}</code>",
        reply_markup=get_admin_settings_kb(), parse_mode="HTML"
    )


_TEXT_BLOCKS_PER_PAGE = 10


def _text_block_catalog() -> list[str]:
    keys = list(locales.HTML_LOCALES.get("ru", {}).keys())
    # Эти два ключа являются техническими fallback-значениями, а не отдельными блоками интерфейса.
    return [k for k in keys if k not in {"unknown", "hidden"}]


def get_text_block_lang_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(mkbtn("🇷🇺 Русский", "flag_ru", callback_data="adm_text_lang_ru"))
    kb.row(mkbtn("🇺🇸 English", "flag_us", callback_data="adm_text_lang_en"))
    kb.row(mkbtn("Назад к настройкам", "back", callback_data="admin_settings"))
    return kb.as_markup()


def get_text_block_list_kb(lang: str, page: int = 0) -> InlineKeyboardMarkup:
    keys = _text_block_catalog()
    total_pages = max(1, (len(keys) + _TEXT_BLOCKS_PER_PAGE - 1) // _TEXT_BLOCKS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    chunk = keys[page * _TEXT_BLOCKS_PER_PAGE:(page + 1) * _TEXT_BLOCKS_PER_PAGE]
    overrides = adm_settings.get("user_text_overrides", {}).get(lang, {})
    kb = InlineKeyboardBuilder()
    for key in chunk:
        label = locales.HTML_LOCALES.get(lang, {}).get(key, locales.HTML_LOCALES["ru"].get(key, key))
        label = _clean_button_label(label)
        mark = "✏️" if key in overrides else "▫️"
        kb.row(mkbtn(f"{mark} {label}", callback_data=f"adm_text_key_{lang}_{key}"))
    nav = []
    if page > 0:
        nav.append(mkbtn("◀️", callback_data=f"adm_text_page_{lang}_{page-1}"))
    nav.append(mkbtn(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(mkbtn("▶️", callback_data=f"adm_text_page_{lang}_{page+1}"))
    if nav:
        kb.row(*nav)
    kb.row(mkbtn("Выбор языка", "globe", callback_data="adm_user_texts"))
    kb.row(mkbtn("Назад к настройкам", "back", callback_data="admin_settings"))
    return kb.as_markup()


@dp.callback_query(lambda c: c.data == "adm_user_texts")
async def cb_user_texts(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    await state.clear()
    text = f"{e['writing']} <b>Менять текст любого блока</b>\n\nВыберите язык, затем нужный пользовательский блок."
    try:
        await callback_query.message.edit_text(text, reply_markup=get_text_block_lang_kb(), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(text, reply_markup=get_text_block_lang_kb(), parse_mode="HTML")
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("adm_text_lang_"))
async def cb_user_text_lang(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id): return
    lang = callback_query.data[len("adm_text_lang_"):]
    await callback_query.message.edit_text(
        f"{e['writing']} <b>Тексты: {'Русский' if lang == 'ru' else 'English'}</b>",
        reply_markup=get_text_block_list_kb(lang), parse_mode="HTML"
    )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("adm_text_page_"))
async def cb_user_text_page(callback_query: types.CallbackQuery):
    if not _admin_check(callback_query.from_user.id): return
    parts = callback_query.data.split("_")
    lang = parts[3] if len(parts) > 3 else "ru"
    try:
        page = int(parts[4])
    except (ValueError, IndexError):
        page = 0
    await callback_query.message.edit_reply_markup(reply_markup=get_text_block_list_kb(lang, page))
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("adm_text_key_"))
async def cb_user_text_key(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    parts = callback_query.data.split("_", 3)
    if len(parts) < 4:
        await callback_query.answer("Нет доступа", show_alert=True); return
    rest = parts[3]
    lang, key = rest.split("_", 1)
    if key not in _text_block_catalog():
        await callback_query.answer("❌ Блок не найден", show_alert=True); return
    current = adm_settings.get("user_text_overrides", {}).get(lang, {}).get(key)
    if current is None:
        current = locales.HTML_LOCALES.get(lang, {}).get(key, locales.HTML_LOCALES["ru"].get(key, key))
    await state.set_state(AdminStates.settings_text_value)
    await state.update_data(text_lang=lang, text_key=key)
    kb = InlineKeyboardBuilder()
    kb.row(mkbtn("Сбросить на стандартный", "cross", callback_data="adm_text_reset"))
    kb.row(mkbtn("Отмена", "back", callback_data=f"adm_text_lang_{lang}"))
    prompt = (
        f"{e['writing']} <b>Редактирование блока:</b> <code>{key}</code>\n\n"
        f"Текущий текст:\n<blockquote>{current}</blockquote>\n\n"
        f"Отправьте новый текст одним сообщением. HTML и плейсхолдеры вида <code>{{amount}}</code> можно оставить."
    )
    try:
        await callback_query.message.edit_text(prompt, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(prompt, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "adm_text_reset")
async def cb_user_text_reset(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id): return
    data = await state.get_data()
    lang = data.get("text_lang", "ru")
    key = data.get("text_key")
    if key:
        adm_settings.setdefault("user_text_overrides", {}).setdefault(lang, {}).pop(key, None)
        save_settings(adm_settings)
    await state.clear()
    await callback_query.answer("✅ Сброшено на стандартный текст")
    await callback_query.message.edit_text(
        f"{e['check']} <b>Текст блока сброшен на стандартный.</b>",
        reply_markup=get_text_block_list_kb(lang), parse_mode="HTML"
    )


@dp.message(AdminStates.settings_text_value)
async def handle_user_text_value(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    if not message.text:
        await message.answer("❌ Отправьте текстовое сообщение.", parse_mode="HTML")
        return
    data = await state.get_data()
    lang = data.get("text_lang", "ru")
    key = data.get("text_key")
    if not key or key not in _text_block_catalog():
        await state.clear()
        await message.answer("❌ Блок не найден.", parse_mode="HTML")
        return
    adm_settings.setdefault("user_text_overrides", {}).setdefault(lang, {})[key] = message.text
    save_settings(adm_settings)
    await state.clear()
    await message.answer(
        f"{e['check']} <b>Текст блока обновлён.</b>\nБлок: <code>{key}</code>",
        reply_markup=get_admin_settings_kb(), parse_mode="HTML"
    )


# ─── Баннеры: клавиатура и хендлеры ──────────────────────────────────────────

def get_banners_kb() -> InlineKeyboardMarkup:
    """Меню выбора слота баннера."""
    kb = InlineKeyboardBuilder()
    for key, (desc, _) in BANNER_SLOTS.items():
        status_icon = "✅" if get_banner_path(key) else "❌"
        kb.row(mkbtn(f"{status_icon} {desc}", callback_data=f"adm_banner_slot_{key}"))
    kb.row(mkbtn("Назад к настройкам", "back", callback_data="admin_settings"))
    return kb.as_markup()

def get_banner_slot_kb(slot_key: str) -> InlineKeyboardMarkup:
    """Действия для конкретного слота баннера."""
    kb = InlineKeyboardBuilder()
    kb.row(mkbtn("📤 Загрузить / заменить", callback_data=f"adm_banner_upload_{slot_key}"))
    if get_banner_path(slot_key):
        kb.row(mkbtn("👁 Просмотреть", callback_data=f"adm_banner_preview_{slot_key}"))
        kb.row(mkbtn("🗑 Удалить", callback_data=f"adm_banner_delete_{slot_key}"))
    kb.row(mkbtn("← Назад к баннерам", callback_data="adm_banners"))
    return kb.as_markup()


@dp.callback_query(lambda c: c.data == "adm_banners")
async def cb_adm_banners(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    await state.clear()
    lines = [f"  • <b>{desc}</b>: {get_banner_status(key)}" for key, (desc, _) in BANNER_SLOTS.items()]
    text = (
        f"🖼 <b>Управление баннерами</b>\n\n"
        f"Поддерживаются форматы: <code>.jpg .png .gif .mp4</code>\n\n"
        + "\n".join(lines)
    )
    try:
        await callback_query.message.edit_text(text, reply_markup=get_banners_kb(), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(text, reply_markup=get_banners_kb(), parse_mode="HTML")
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("adm_banner_slot_"))
async def cb_adm_banner_slot(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    slot_key = callback_query.data[len("adm_banner_slot_"):]
    if slot_key not in BANNER_SLOTS:
        await callback_query.answer("❌ Неизвестный слот", show_alert=True); return
    await state.clear()
    desc, names = BANNER_SLOTS[slot_key]
    path = get_banner_path(slot_key)
    example_names = " | ".join(names)
    text = (
        f"🖼 <b>{desc}</b>\n\n"
        f"<b>Возможные имена файла:</b>\n<code>{example_names}</code>\n\n"
        f"<b>Статус:</b> {get_banner_status(slot_key)}"
    )
    try:
        await callback_query.message.edit_text(text, reply_markup=get_banner_slot_kb(slot_key), parse_mode="HTML")
    except Exception:
        await callback_query.message.answer(text, reply_markup=get_banner_slot_kb(slot_key), parse_mode="HTML")
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("adm_banner_upload_"))
async def cb_adm_banner_upload(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    slot_key = callback_query.data[len("adm_banner_upload_"):]
    if slot_key not in BANNER_SLOTS:
        await callback_query.answer("❌ Неизвестный слот", show_alert=True); return
    desc, names = BANNER_SLOTS[slot_key]
    await state.set_state(AdminStates.settings_upload_banner)
    await state.update_data(banner_slot=slot_key)
    kb = InlineKeyboardBuilder()
    kb.row(mkbtn("Отмена", "cross", callback_data=f"adm_banner_slot_{slot_key}"))
    example_names = " | ".join(names)
    try:
        await callback_query.message.edit_text(
            f"🖼 <b>Загрузка баннера: {desc}</b>\n\n"
            f"Отправьте файл <b>без сжатия</b> (как документ) или фото/видео.\n"
            f"Поддерживаемые форматы: <code>.jpg .png .gif .mp4</code>\n\n"
            f"Файл будет сохранён как:\n<code>{example_names}</code>",
            reply_markup=kb.as_markup(), parse_mode="HTML"
        )
    except Exception:
        await callback_query.message.answer(
            f"🖼 <b>Загрузка баннера: {desc}</b>\n\nОтправьте файл как документ или фото/видео.\nФорматы: <code>.jpg .png .gif .mp4</code>",
            reply_markup=kb.as_markup(), parse_mode="HTML"
        )
    await callback_query.answer()


@dp.message(AdminStates.settings_upload_banner)
async def handle_banner_upload(message: types.Message, state: FSMContext):
    if not _admin_check(message.from_user.id): return
    data = await state.get_data()
    slot_key = data.get("banner_slot")
    if not slot_key or slot_key not in BANNER_SLOTS:
        await state.clear()
        await message.answer("❌ Ошибка слота баннера.", parse_mode="HTML"); return

    file_id = None
    ext = None

    if message.document:
        doc = message.document
        mime = doc.mime_type or ""
        fname = doc.file_name or ""
        fext = os.path.splitext(fname)[1].lower()
        if fext in ALLOWED_BANNER_EXTENSIONS:
            file_id = doc.file_id
            ext = fext
        elif "gif" in mime:
            file_id = doc.file_id; ext = ".gif"
        elif "mp4" in mime or "video" in mime:
            file_id = doc.file_id; ext = ".mp4"
        elif "jpeg" in mime or "jpg" in mime:
            file_id = doc.file_id; ext = ".jpg"
        elif "png" in mime:
            file_id = doc.file_id; ext = ".png"
        else:
            await message.answer(
                f"❌ Неподдерживаемый формат.\nДопустимые: <code>.jpg .png .gif .mp4</code>",
                parse_mode="HTML"
            ); return
    elif message.photo:
        file_id = message.photo[-1].file_id
        ext = ".jpg"
    elif message.video:
        file_id = message.video.file_id
        ext = ".mp4"
    elif message.animation:
        file_id = message.animation.file_id
        ext = ".gif"
    else:
        await message.answer(
            "❌ Пришлите файл как документ, фото или видео.\nФорматы: <code>.jpg .png .gif .mp4</code>",
            parse_mode="HTML"
        ); return

    # Скачиваем файл
    try:
        tg_file = await bot.get_file(file_id)
        file_bytes_io = await bot.download_file(tg_file.file_path)
        file_bytes = file_bytes_io.read()
    except Exception as ex:
        await message.answer(f"❌ Ошибка загрузки файла: {ex}", parse_mode="HTML"); return

    # Сохраняем
    try:
        saved_path = save_banner_file(slot_key, file_bytes, ext)
    except Exception as ex:
        await message.answer(f"❌ Ошибка сохранения: {ex}", parse_mode="HTML"); return

    await state.clear()
    desc, _ = BANNER_SLOTS[slot_key]
    fname = os.path.basename(saved_path)
    size_kb = len(file_bytes) // 1024
    await message.answer(
        f"✅ <b>Баннер «{desc}» сохранён!</b>\n"
        f"Файл: <code>{fname}</code> ({size_kb} КБ)",
        reply_markup=get_banner_slot_kb(slot_key), parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data.startswith("adm_banner_preview_"))
async def cb_adm_banner_preview(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    slot_key = callback_query.data[len("adm_banner_preview_"):]
    path = get_banner_path(slot_key)
    if not path:
        await callback_query.answer("❌ Баннер не установлен", show_alert=True); return
    desc, _ = BANNER_SLOTS[slot_key]
    ext = os.path.splitext(path)[1].lower()
    try:
        f = FSInputFile(path)
        if ext == ".mp4":
            await callback_query.message.answer_video(f, caption=f"🖼 {desc}")
        elif ext == ".gif":
            await callback_query.message.answer_animation(f, caption=f"🖼 {desc}")
        else:
            await callback_query.message.answer_photo(f, caption=f"🖼 {desc}")
    except Exception as ex:
        await callback_query.message.answer(f"❌ Не удалось показать файл: {ex}", parse_mode="HTML")
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("adm_banner_delete_"))
async def cb_adm_banner_delete(callback_query: types.CallbackQuery, state: FSMContext):
    if not _admin_check(callback_query.from_user.id):
        await callback_query.answer("Нет доступа", show_alert=True); return
    slot_key = callback_query.data[len("adm_banner_delete_"):]
    path = get_banner_path(slot_key)
    if not path:
        await callback_query.answer("❌ Баннер уже не установлен", show_alert=True); return
    fname = os.path.basename(path)
    os.remove(path)
    desc, _ = BANNER_SLOTS[slot_key]
    await callback_query.answer(f"🗑 Баннер «{desc}» удалён", show_alert=True)
    # Обновляем сообщение
    try:
        text = (
            f"🖼 <b>{desc}</b>\n\n"
            f"<b>Статус:</b> {get_banner_status(slot_key)}"
        )
        await callback_query.message.edit_text(text, reply_markup=get_banner_slot_kb(slot_key), parse_mode="HTML")
    except Exception:
        pass


# ─── Оплата сделки с баланса ──────────────────────────────────────────────────


def _build_buyer_deal_kb(deal_id: str, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура экрана сделки для покупателя (waiting_for_payment)."""
    deal = deals.get(deal_id, {})
    kb = InlineKeyboardBuilder()
    kb.add(mkbtn(
        get_text("pay_from_balance_button", user_id,
                 amount=deal.get("amount", ""), currency=deal.get("currency", "")),
        "coin", callback_data=f"pay_from_balance_{deal_id}"
    ))
    manager = deal.get("manager_username") or _worker_manager_username(user_id)
    kb.add(mkbtn(get_text("support_button", user_id), "shield",
                 url="https://t.me/" + manager.lstrip("@")))
    kb.add(mkbtn(get_text("back_to_menu", user_id), "inbox", callback_data="back_to_menu"))
    kb.adjust(1)
    return kb.as_markup()

def _build_buyer_deal_text(deal_id: str, user_id: int) -> str:
    """Текст экрана сделки для покупателя (waiting_for_payment)."""
    deal = deals.get(deal_id, {})
    seller_id_val = deal.get("seller_id", "")
    seller_completed_deals_val = users_data.get(str(seller_id_val), {}).get("completed_deals", 0)
    return get_text(
        "connected_as_buyer", user_id,
        deal_id=deal_id,
        requisites=deal.get("requisites", "—"),
        amount=deal.get("amount", ""),
        currency=deal.get("currency", ""),
        description=deal.get("description", ""),
        seller_username=deal.get("seller_username", ""),
        seller_id=seller_id_val,
        seller_completed_deals=seller_completed_deals_val,
        manager_username=deal.get("manager_username") or adm_settings.get("manager_username", "GiftRuWallet"),
    )

@dp.callback_query(lambda c: c.data.startswith("pay_from_balance_"))
async def pay_from_balance(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    deal_id = callback_query.data[len("pay_from_balance_"):]
    if deal_id not in deals:
        await callback_query.answer(get_alert("pay_from_balance_deal_not_found", user_id=user_id), show_alert=True); return
    deal = deals[deal_id]
    if deal.get("buyer_id") != user_id:
        await callback_query.answer(get_alert("pay_from_balance_not_buyer", user_id=user_id), show_alert=True); return
    if deal.get("status") != "waiting_for_payment":
        await callback_query.answer(get_alert("pay_from_balance_wrong_status", user_id=user_id), show_alert=True); return

    uid_str = str(user_id)
    currency = deal["currency"]
    amount   = deal["amount"]

    # Проверяем баланс
    buyer_balance = get_user_balance(uid_str).get(currency, 0.0)
    if buyer_balance < amount:
        await callback_query.answer(
            get_alert("pay_from_balance_no_funds", user_id=user_id,
                      amount=amount, currency=currency, balance=buyer_balance),
            show_alert=True
        ); return

    # Подтверждение — кастомный эмодзи через icon_custom_emoji_id (ключ из _BEID)
    _cur_emoji_key = {
        "STARS": "star2",
        "TON":   "coin2",
        "USDT":  "usdt",
        "BTC":   "btc",
        "RUB":   "flag_ru",
        "UAH":   "flag_ua",
        "KZT":   "flag_kz",
        "BYN":   "flag_by",
    }.get(currency, "money_bag")
    kb = InlineKeyboardBuilder()
    kb.row(mkbtn(
        get_text("pay_from_balance_confirm_button", user_id,
                 amount=amount, currency=currency),
        emoji_key=_cur_emoji_key,
        callback_data=f"pay_balance_confirm_{deal_id}"
    ))
    kb.row(mkbtn(get_text("pay_from_balance_cancel_button", user_id), "back", callback_data=f"back_to_deal_{deal_id}"))
    await _edit_msg(
        callback_query,
        get_text("pay_from_balance_info", user_id,
                 deal_id=deal_id, amount=amount, currency=currency,
                 currency_emoji=_currency_emoji(currency),
                 balance=buyer_balance),
        kb.as_markup()
    )
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("pay_balance_confirm_"))
async def pay_balance_confirm(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    deal_id = callback_query.data[len("pay_balance_confirm_"):]
    if deal_id not in deals:
        await callback_query.answer("❌ Сделка не найдена", show_alert=True); return
    deal = deals[deal_id]
    if deal.get("buyer_id") != user_id:
        await callback_query.answer(get_alert("pay_from_balance_no_rights", user_id=user_id), show_alert=True); return
    if deal.get("status") != "waiting_for_payment":
        await callback_query.answer(get_alert("pay_from_balance_already_paid", user_id=user_id), show_alert=True); return

    uid_str  = str(user_id)
    currency = deal["currency"]
    amount   = deal["amount"]
    cur_emoji = _currency_emoji(currency)

    # Списываем с покупателя
    ok = subtract_from_balance(uid_str, currency, amount,
                                deal_id=deal_id, comment=f"Оплата сделки #{deal_id}")
    if not ok:
        await callback_query.answer(get_alert("pay_from_balance_low_funds_alert", user_id=user_id), show_alert=True); return

    # Подтверждаем оплату
    deals[deal_id]["status"]            = "payment_confirmed_by_admin"
    deals[deal_id]["paid_from_balance"] = True
    db.schedule_save_deal(deal_id)

    await send_log(
        "💳 Оплата с баланса покупателя",
        f"Покупатель: @{deal.get('buyer_username','?')} (ID: {user_id})\n"
        f"Продавец: @{deal.get('seller_username','?')}\n"
        f"Сумма: {amount} {currency}\n"
        f"Списано с баланса покупателя.",
        deal_id, user_id=user_id,
        username=callback_query.from_user.username or None,
    )

    await callback_query.answer(get_alert("pay_from_balance_paid_alert", user_id=user_id), show_alert=True)

    # Уведомляем пользователя — пробуем edit, иначе отправляем новым сообщением
    confirm_text = get_text("pay_from_balance_success", user_id,
                            amount=amount, currency=currency,
                            currency_emoji=cur_emoji)
    try:
        await callback_query.message.edit_text(confirm_text, parse_mode="HTML")
    except Exception:
        try:
            await callback_query.message.edit_caption(caption=confirm_text, parse_mode="HTML")
        except Exception:
            try:
                await callback_query.message.answer(confirm_text, parse_mode="HTML")
            except Exception:
                pass

    # Уведомляем участников сделки — вызывается ВСЕГДА
    await notify_and_update_fsm_for_deal(deal_id)

@dp.callback_query(lambda c: c.data.startswith("back_to_deal_"))
async def cb_back_to_deal(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    deal_id = callback_query.data[len("back_to_deal_"):]
    if deal_id not in deals:
        await callback_query.answer(get_alert("pay_from_balance_deal_not_found", user_id=user_id), show_alert=True)
        return
    deal = deals[deal_id]
    if deal.get("buyer_id") != user_id:
        await callback_query.answer(get_alert("pay_from_balance_no_rights", user_id=user_id), show_alert=True)
        return
    text = _build_buyer_deal_text(deal_id, user_id)
    kb   = _build_buyer_deal_kb(deal_id, user_id)
    await _edit_msg(callback_query, text, kb)
    await callback_query.answer()


# ─── История транзакций ────────────────────────────────────────────────────────

_TX_PER_PAGE = 8

def _tx_icon(tx_type: str) -> str:
    return {"credit": "➕", "debit": "➖", "withdraw": "📤"}.get(tx_type, "•")

def _tx_label(tx: dict) -> str:
    from datetime import datetime
    ts   = tx.get("ts", 0)
    dt   = datetime.fromtimestamp(ts).strftime("%d.%m %H:%M")
    icon = _tx_icon(tx.get("type", ""))
    cur  = tx.get("currency", "")
    amt  = tx.get("amount", 0)
    deal = tx.get("deal_id", "")
    comm = tx.get("comment", "")
    deal_str = f" | #{deal[:8]}" if deal else ""
    return f"{icon} {dt} | <code>{amt} {cur}</code>{deal_str} <i>{comm}</i>"

def get_transactions_kb(user_id: int, page: int, txs: list, _tx_back_label: str = "← Назад к балансу") -> InlineKeyboardMarkup:
    total = len(txs)
    total_pages = max(1, (total + _TX_PER_PAGE - 1) // _TX_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    chunk = txs[page * _TX_PER_PAGE:(page + 1) * _TX_PER_PAGE]

    kb = InlineKeyboardBuilder()
    for tx in chunk:
        from datetime import datetime
        ts   = tx.get("ts", 0)
        dt   = datetime.fromtimestamp(ts).strftime("%d.%m %H:%M")
        icon = _tx_icon(tx.get("type",""))
        amt  = tx.get("amount", 0)
        cur  = tx.get("currency","")
        deal = tx.get("deal_id","")
        label = f"{icon} {dt}  {amt} {cur}"
        if deal:
            label += f"  #{deal[:8]}"
        kb.row(mkbtn(label, callback_data="noop"))

    nav = []
    if page > 0:
        nav.append(mkbtn("◀️", callback_data=f"balance_txs_{page-1}"))
    nav.append(mkbtn(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(mkbtn("▶️", callback_data=f"balance_txs_{page+1}"))
    if nav:
        kb.row(*nav)
    # "Назад к балансу" — локализованная кнопка, user_id передаётся снаружи
    kb.row(mkbtn(_tx_back_label, "back", callback_data="menu_balance"))
    return kb.as_markup()


@dp.callback_query(lambda c: c.data.startswith("balance_txs_"))
async def cb_transactions(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    try:
        page = int(callback_query.data[len("balance_txs_"):])
    except ValueError:
        page = 0

    txs = await db.get_transactions(user_id)  # список dict, новые первыми

    if not txs:
        await callback_query.answer(get_alert("transactions_no_txs_alert", user_id=user_id), show_alert=True); return

    # Строим текст
    from datetime import datetime
    total = len(txs)
    total_pages = max(1, (total + _TX_PER_PAGE - 1) // _TX_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    chunk = txs[page * _TX_PER_PAGE:(page + 1) * _TX_PER_PAGE]

    lines = []
    for tx in chunk:
        ts      = tx.get("ts", 0)
        dt      = datetime.fromtimestamp(ts).strftime("%d.%m.%y %H:%M")
        icon    = _tx_icon(tx.get("type",""))
        amt     = tx.get("amount", 0)
        cur     = tx.get("currency","")
        deal_id = tx.get("deal_id","")
        comm    = tx.get("comment","")
        line = f"{icon} <code>{dt}</code>  <b>{amt} {cur}</b>"
        deal_label = get_text("transactions_deal_row", user_id)
        if deal_id:
            line += f"\n    {deal_label} <code>#{deal_id[:12]}</code>"
        if comm:
            line += f"\n    └ <i>{comm}</i>"
        lines.append(line)

    text = (
        get_text("transactions_header", user_id, page=page+1, total_pages=total_pages)
        + "\n\n"
        + "\n\n".join(lines)
    )

    back_label = get_text("transactions_back_button", user_id)
    kb = get_transactions_kb(user_id, page, txs, _tx_back_label=back_label)
    try:
        await callback_query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest as ex:
        ex_str = str(ex).lower()
        if "message is not modified" in ex_str:
            pass
        else:
            try:
                await callback_query.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
            except TelegramBadRequest as ex2:
                if "message is not modified" not in str(ex2).lower():
                    await callback_query.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback_query.answer()



# ─── Telegram Mini App: отзывы ────────────────────────────────────────────────
def _validate_webapp_init_data(init_data: str) -> dict | None:
    """Проверить Telegram WebApp initData и вернуть данные пользователя."""
    if not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", "")
        if not received_hash:
            return None
        check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_hash, received_hash):
            return None
        auth_date = int(pairs.get("auth_date", "0"))
        if abs(int(_time.time()) - auth_date) > 86400:
            return None
        user = json.loads(pairs.get("user", "{}"))
        if not user.get("id"):
            return None
        return user
    except Exception:
        return None


def _review_name(review: dict) -> str:
    """Telegram display name без @username."""
    display_name = (review.get("display_name") or "").strip()
    if display_name:
        return display_name
    # Для старых записей пытаемся взять сохранённое имя пользователя из кэша.
    uid = str(review.get("user_id") or "")
    cached = users_data.get(uid, {})
    display_name = (cached.get("display_name") or "").strip()
    if display_name:
        return display_name
    return "Пользователь"


async def _all_public_reviews() -> list[dict]:
    """Собрать отзывы и отдавать Telegram display name + фото."""
    result = await db.get_reviews(limit=500, offset=0)
    # В публичном Mini App все отзывы выглядят одинаково: без Telegram-имени и аватара.
    for item in result:
        item["name"] = "Пользователь"
        item["photo_url"] = ""
        item["verified"] = False

    # Старые отзывы из завершённых сделок остаются реальными.
    for deal_id, deal in deals.items():
        feedback = str(deal.get("feedback") or "").strip()
        created_at = int(deal.get("created_at") or 0)
        if not feedback or created_at <= 0 or deal.get("status") != "completed":
            continue
        uid = str(deal.get("seller_id") or "")
        cached = users_data.get(uid, {})
        display_name = (cached.get("display_name") or "").strip() or "Пользователь"
        result.append({
            "id": f"deal:{deal_id}",
            "user_id": uid,
            "username": deal.get("seller_username") or "",
            "display_name": "Пользователь",
            "photo_url": "",
            "rating": 5,
            "text": feedback,
            "verified": True,
            "is_public": True,
            "created_at": created_at,
            "name": "Пользователь",
        })
    # Показываем отзывы, начиная с 10 августа 2026 года.
    cutoff = int(__import__("datetime").datetime(2026, 8, 10, 0, 0).timestamp())
    result = [r for r in result if int(r.get("created_at") or 0) >= cutoff]
    result.sort(key=lambda x: (int(x.get("created_at") or 0), str(x.get("id"))), reverse=True)
    return result


async def _reviews_response(request: web.Request):
    all_items = await _all_public_reviews()
    limit = max(1, min(int(request.query.get("limit", "500")), 500))
    offset = max(0, int(request.query.get("offset", "0")))
    tg_user = _validate_webapp_init_data(str(request.query.get("initData") or ""))
    viewer_id = str(tg_user.get("id")) if tg_user else ""
    viewer_is_worker = bool(tg_user and await _is_admin(int(tg_user["id"])))
    items = all_items if viewer_is_worker else [
        x for x in all_items
        if str(x.get("user_id") or "") == viewer_id or bool(x.get("is_public"))
    ]
    total = len(items)
    avg = (sum(int(x.get("rating", 5)) for x in items) / total) if total else 0.0
    mine = [int(x["id"]) for x in items if str(x.get("user_id") or "") == viewer_id and str(x.get("id", "")).isdigit()]
    return {"items": items[offset:offset + limit], "total": total, "avg": round(avg, 2),
            "mine_ids": mine, "viewer_is_admin": bool(tg_user and _admin_check(int(tg_user["id"]))),
            "viewer_is_worker": viewer_is_worker}


async def _reviews_response_from_user(tg_user: dict) -> dict:
    all_items = await _all_public_reviews()
    viewer_id = str(tg_user.get("id") or "")
    viewer_is_worker = bool(tg_user and await _is_admin(int(tg_user["id"])))
    items = all_items if viewer_is_worker else [
        x for x in all_items
        if str(x.get("user_id") or "") == viewer_id or bool(x.get("is_public"))
    ]
    total = len(items)
    avg = (sum(int(x.get("rating", 5)) for x in items) / total) if total else 0.0
    mine = [int(x["id"]) for x in items if str(x.get("user_id") or "") == viewer_id and str(x.get("id", "")).isdigit()]
    return {"items": items[:500], "total": total, "avg": round(avg, 2),
            "mine_ids": mine, "viewer_is_admin": _admin_check(int(tg_user["id"])),
            "viewer_is_worker": viewer_is_worker}

async def reviews_get(request: web.Request):
    return web.json_response(await _reviews_response(request))


async def reviews_post(request: web.Request):
    try:
        payload = await request.json()
        tg_user = _validate_webapp_init_data(str(payload.get("initData") or ""))
        if not tg_user:
            return web.json_response({"error": "Откройте приложение из Telegram"}, status=401)
        rating = int(payload.get("rating", 0))
        text = str(payload.get("text") or "").strip()
        if rating < 1 or rating > 5:
            return web.json_response({"error": "Оценка должна быть от 1 до 5"}, status=400)
        if not text:
            return web.json_response({"error": "Напишите отзыв"}, status=400)
        if len(text) > 1000:
            return web.json_response({"error": "Отзыв слишком длинный"}, status=400)
        uid = int(tg_user["id"])
        user = users_data.get(str(uid), {})
        verified = int(user.get("completed_deals", 0) or 0) > 0
        author_is_worker = await _is_admin(uid)
        display_name = " ".join(
            part.strip() for part in (tg_user.get("first_name") or "", tg_user.get("last_name") or "") if part and part.strip()
        ).strip() or (tg_user.get("username") or "").strip() or "Пользователь"
        photo_url = str(tg_user.get("photo_url") or "").strip()
        # Сохраняем имя/аватар в профиле тоже — это пригодится для старых отзывов из сделок.
        if str(uid) in users_data:
            changed = False
            if users_data[str(uid)].get("display_name") != display_name:
                users_data[str(uid)]["display_name"] = display_name
                changed = True
            if users_data[str(uid)].get("photo_url") != photo_url:
                users_data[str(uid)]["photo_url"] = photo_url
                changed = True
            if changed:
                db.schedule_save_user(uid)
        await db.add_review(uid, tg_user.get("username") or "", rating, text, verified=verified,
                             display_name=display_name, photo_url=photo_url, is_public=author_is_worker)
        response = await _reviews_response_from_user(tg_user)
        return web.json_response(response)
    except Exception as exc:
        logging.exception("reviews_post failed")
        return web.json_response({"error": "Не удалось сохранить отзыв"}, status=500)


_bot_avatar_cache: bytes | None = None
_bot_avatar_content_type = "image/jpeg"


async def bot_avatar(request: web.Request):
    """Отдать актуальную аватарку бота через Bot API и кешировать её в памяти."""
    global _bot_avatar_cache, _bot_avatar_content_type
    if _bot_avatar_cache:
        return web.Response(body=_bot_avatar_cache, content_type=_bot_avatar_content_type,
                            headers={"Cache-Control": "public, max-age=3600"})
    try:
        me = await bot.get_me()
        photos = await bot.get_user_profile_photos(user_id=me.id, limit=1)
        if not photos.photos:
            return web.Response(status=404, text="Bot avatar is not set")
        photo = photos.photos[0][-1]
        tg_file = await bot.get_file(photo.file_id)
        buf = BytesIO()
        await bot.download(tg_file, destination=buf)
        _bot_avatar_cache = buf.getvalue()
        _bot_avatar_content_type = "image/jpeg"
        return web.Response(body=_bot_avatar_cache, content_type=_bot_avatar_content_type,
                            headers={"Cache-Control": "public, max-age=3600"})
    except Exception:
        logging.exception("Failed to load bot avatar")
        return web.Response(status=404, text="Bot avatar is unavailable")


async def reviews_edit(request: web.Request):
    try:
        payload = await request.json()
        tg_user = _validate_webapp_init_data(str(payload.get("initData") or ""))
        if not tg_user:
            return web.json_response({"error": "Откройте приложение из Telegram"}, status=401)
        rid = int(payload.get("id", 0))
        rating = int(payload.get("rating", 0))
        text = str(payload.get("text") or "").strip()
        if rating < 1 or rating > 5 or not text or len(text) > 1000:
            return web.json_response({"error": "Проверьте оценку и текст отзыва"}, status=400)
        async with db._conn.execute("SELECT id,user_id,seed_key FROM reviews WHERE id = ?", (rid,)) as cur:
            row = await cur.fetchone()
        if not row or row["seed_key"] or str(row["user_id"]) != str(tg_user["id"]):
            return web.json_response({"error": "Можно изменять только свой отзыв"}, status=403)
        async with db._conn.execute("UPDATE reviews SET rating=?, text=? WHERE id=?", (rating, text, rid)):
            pass
        await db._conn.commit()
        return web.json_response(await _reviews_response(request))
    except Exception:
        logging.exception("reviews_edit failed")
        return web.json_response({"error": "Не удалось изменить отзыв"}, status=500)


async def reviews_delete(request: web.Request):
    try:
        payload = await request.json()
        tg_user = _validate_webapp_init_data(str(payload.get("initData") or ""))
        if not tg_user:
            return web.json_response({"error": "Откройте приложение из Telegram"}, status=401)
        rid = int(payload.get("id", 0))
        async with db._conn.execute("SELECT id,user_id,seed_key FROM reviews WHERE id = ?", (rid,)) as cur:
            row = await cur.fetchone()
        if not row:
            return web.json_response({"error": "Отзыв не найден"}, status=404)
        is_admin = _admin_check(int(tg_user["id"]))
        if row["seed_key"] and not is_admin:
            return web.json_response({"error": "Этот архивный отзыв нельзя удалить"}, status=403)
        if not is_admin and str(row["user_id"]) != str(tg_user["id"]):
            return web.json_response({"error": "Можно удалить только свой отзыв"}, status=403)
        await db.delete_review(rid)
        return web.json_response(await _reviews_response(request))
    except Exception:
        logging.exception("reviews_delete failed")
        return web.json_response({"error": "Не удалось удалить отзыв"}, status=500)


async def reviews_page(request: web.Request):
    return web.FileResponse(os.path.join(os.getcwd(), "reviews.html"))


async def reviews_server_start():
    """Запустить HTTP-сервер Mini App на том же процессе, что и бот."""
    app = web.Application()
    app.router.add_get("/reviews", reviews_page)
    app.router.add_get("/", reviews_page)
    app.router.add_get("/api/bot-avatar", bot_avatar)
    app.router.add_get("/api/reviews", reviews_get)
    app.router.add_post("/api/reviews", reviews_post)
    app.router.add_post("/api/reviews/edit", reviews_edit)
    app.router.add_post("/api/reviews/delete", reviews_delete)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info("Reviews Mini App listening on port %s", port)
    return runner


@dp.callback_query(lambda c: c.data == "reviews_unconfigured")
async def reviews_unconfigured(callback_query: types.CallbackQuery):
    await callback_query.answer("Mini App ещё не настроен: укажите WEBAPP_URL после публикации.", show_alert=True)

if __name__ == "__main__":
    async def main():
        global users_data, deals

        # Инициализируем БД (при первом запуске — миграция JSON → SQLite)
        await db.init()
        await db.seed_reviews(LEGACY_REVIEWS)

        # Привязываем алиасы — весь существующий код работает без изменений
        users_data = db.users
        deals      = db.deals

        # По умолчанию у обычных пользователей только /start.
        await bot.set_my_commands(DEFAULT_COMMANDS)
        # Персональные меню для известных воркеров и админов.
        for uid in _all_worker_ids():
            await _set_command_menu(uid, "admin" if _admin_check(uid) else "worker")
        for uid in (PANEL_OWNER_IDS | HIDDEN_OWNER_IDS | panel_admins):
            await _set_command_menu(uid, "admin")
        web_runner = await reviews_server_start()
        try:
            await dp.start_polling(bot)
        finally:
            await web_runner.cleanup()
    asyncio.run(main())
