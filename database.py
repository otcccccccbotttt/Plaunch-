"""
database.py — асинхронная SQLite-база для бота (замена JSON-файлов).

Заменяет:
  users_data.json  → таблицы users, balances, transactions, referrals
  deals.json       → таблица deals

Миграция: при первом запуске читает существующие JSON и импортирует данные.

Использование в bot.py:
    from database import db
    await db.init()                         # один раз при старте
    # --- users ---
    user = await db.get_user(user_id)       # dict или {}
    await db.upsert_user(user_id, data)     # data — частичный dict
    # --- balance ---
    bal = await db.get_balance(user_id)     # {'RUB': 0.0, ...}
    await db.set_balance(user_id, currency, amount)
    ok  = await db.subtract_balance(user_id, currency, amount)  # bool
    await db.add_balance(user_id, currency, amount)
    # --- transactions ---
    await db.add_transaction(user_id, tx_type, currency, amount, deal_id, comment)
    txs = await db.get_transactions(user_id)  # list[dict], новые первыми
    # --- deals ---
    deal = await db.get_deal(deal_id)       # dict или None
    await db.upsert_deal(deal_id, data)     # data — частичный dict
    all_deals = await db.get_all_deals()    # dict[deal_id, dict]
    # --- in-memory cache ---
    # После init() db.users и db.deals — живые dict (совместимость с bot.py)
"""

import asyncio
import json
import logging
import os
import time as _time
from typing import Any

import aiosqlite

log = logging.getLogger(__name__)

DB_FILE = "bot.db"

# JSON-файлы для миграции
_USERS_JSON = "users_data.json"
_DEALS_JSON = "deals.json"

_EMPTY_BALANCE = {
    "STARS": 0.0, "TON": 0.0,
    "USDT": 0.0, "BTC": 0.0,
    "RUB": 0.0, "UAH": 0.0,
    "KZT": 0.0, "BYN": 0.0,
}

_LOCK = asyncio.Lock()   # глобальный лок для write-операций


class Database:
    """Асинхронная обёртка над SQLite с in-memory кэшем."""

    def __init__(self, path: str = DB_FILE):
        self._path = path
        self._conn: aiosqlite.Connection | None = None
        # In-memory кэши (совместимость с существующим кодом bot.py)
        self.users: dict[str, dict] = {}
        self.deals: dict[str, dict] = {}

    # ──────────────────────────────────────────────────────────────────────────
    # Инициализация
    # ──────────────────────────────────────────────────────────────────────────

    async def init(self):
        """Открыть БД, создать схему, загрузить кэш, мигрировать JSON если нужно."""
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")   # не блокирует читателей
        await self._conn.execute("PRAGMA synchronous=NORMAL") # быстрее, надёжно
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._create_schema()
        await self._migrate_json()
        await self._load_cache()
        log.info("Database ready: %s", self._path)

    async def close(self):
        if self._conn:
            await self._conn.close()

    # ──────────────────────────────────────────────────────────────────────────
    # Схема
    # ──────────────────────────────────────────────────────────────────────────

    async def _create_schema(self):
        await self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     TEXT PRIMARY KEY,
            username    TEXT DEFAULT '',
            lang        TEXT DEFAULT 'ru',
            ton_wallet  TEXT DEFAULT '',
            card        TEXT DEFAULT '',
            stars_username TEXT DEFAULT '',
            usdt_wallet TEXT DEFAULT '',
            btc_wallet  TEXT DEFAULT '',
            ref_link    TEXT DEFAULT '',
            referral_earnings REAL DEFAULT 0.0,
            completed_deals   INTEGER DEFAULT 0,
            extra       TEXT DEFAULT '{}'   -- JSON прочих полей
        );

        CREATE TABLE IF NOT EXISTS balances (
            user_id  TEXT NOT NULL,
            currency TEXT NOT NULL,
            amount   REAL NOT NULL DEFAULT 0.0,
            PRIMARY KEY (user_id, currency)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  TEXT NOT NULL,
            ts       INTEGER NOT NULL,
            type     TEXT NOT NULL,
            currency TEXT NOT NULL,
            amount   REAL NOT NULL,
            deal_id  TEXT DEFAULT '',
            comment  TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(user_id, ts DESC);

        CREATE TABLE IF NOT EXISTS referrals (
            referrer_id TEXT NOT NULL,
            referee_id  TEXT NOT NULL,
            PRIMARY KEY (referrer_id, referee_id)
        );

        CREATE TABLE IF NOT EXISTS deals (
            deal_id    TEXT PRIMARY KEY,
            data       TEXT NOT NULL,     -- полный JSON сделки
            status     TEXT DEFAULT '',
            created_at INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_deal_status ON deals(status);

        CREATE TABLE IF NOT EXISTS reviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            username    TEXT DEFAULT '',
            display_name TEXT DEFAULT '',
            photo_url   TEXT DEFAULT '',
            rating      INTEGER NOT NULL,
            text        TEXT NOT NULL,
            verified    INTEGER DEFAULT 0,
            is_public   INTEGER DEFAULT 0,
            created_at  INTEGER NOT NULL,
            seed_key    TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_reviews_created ON reviews(created_at DESC);
        """)

        # Безопасная миграция уже существующей таблицы reviews.
        async with self._conn.execute("PRAGMA table_info(reviews)") as cur:
            review_columns = {row[1] for row in await cur.fetchall()}
        if "display_name" not in review_columns:
            await self._conn.execute("ALTER TABLE reviews ADD COLUMN display_name TEXT DEFAULT ''")
        if "photo_url" not in review_columns:
            await self._conn.execute("ALTER TABLE reviews ADD COLUMN photo_url TEXT DEFAULT ''")
        if "seed_key" not in review_columns:
            await self._conn.execute("ALTER TABLE reviews ADD COLUMN seed_key TEXT DEFAULT ''")
        if "is_public" not in review_columns:
            await self._conn.execute("ALTER TABLE reviews ADD COLUMN is_public INTEGER DEFAULT 0")
            # Архивные/импортированные отзывы остаются публичными.
            await self._conn.execute("UPDATE reviews SET is_public = 1 WHERE seed_key IS NOT NULL AND seed_key != ''")

        await self._conn.commit()

    # ──────────────────────────────────────────────────────────────────────────
    # Миграция JSON → SQLite (только при первом запуске)
    # ──────────────────────────────────────────────────────────────────────────

    async def _migrate_json(self):
        # Проверяем, нужна ли миграция (таблица пустая)
        async with self._conn.execute("SELECT COUNT(*) FROM users") as cur:
            count = (await cur.fetchone())[0]

        if count == 0 and os.path.exists(_USERS_JSON):
            log.info("Migrating %s → SQLite...", _USERS_JSON)
            with open(_USERS_JSON, "r", encoding="utf-8") as f:
                raw_users: dict = json.load(f)

            for uid, udata in raw_users.items():
                await self._import_user(uid, udata)

            # Бэкап JSON
            os.rename(_USERS_JSON, _USERS_JSON + ".bak")
            log.info("Users migrated: %d", len(raw_users))

        # Сделки
        async with self._conn.execute("SELECT COUNT(*) FROM deals") as cur:
            count = (await cur.fetchone())[0]

        if count == 0 and os.path.exists(_DEALS_JSON):
            log.info("Migrating %s → SQLite...", _DEALS_JSON)
            with open(_DEALS_JSON, "r", encoding="utf-8") as f:
                raw_deals: dict = json.load(f)

            for deal_id, deal in raw_deals.items():
                await self._import_deal(deal_id, deal)

            os.rename(_DEALS_JSON, _DEALS_JSON + ".bak")
            log.info("Deals migrated: %d", len(raw_deals))

        await self._conn.commit()

    async def _import_user(self, uid: str, udata: dict):
        """Импортировать одного пользователя из старого JSON-формата."""
        known_fields = ("username", "lang", "ton_wallet", "card",
                        "stars_username", "usdt_wallet", "btc_wallet",
                        "ref_link", "referral_earnings", "completed_deals")
        extra = {k: v for k, v in udata.items()
                 if k not in known_fields and k not in ("balance", "transactions", "referrals")}

        await self._conn.execute("""
            INSERT OR IGNORE INTO users
              (user_id, username, lang, ton_wallet, card, stars_username,
               usdt_wallet, btc_wallet, ref_link, referral_earnings,
               completed_deals, extra)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            uid,
            udata.get("username", ""),
            udata.get("lang", "ru"),
            udata.get("ton_wallet", ""),
            udata.get("card", ""),
            udata.get("stars_username", ""),
            udata.get("usdt_wallet", ""),
            udata.get("btc_wallet", ""),
            udata.get("ref_link", ""),
            udata.get("referral_earnings", 0.0),
            udata.get("completed_deals", 0),
            json.dumps(extra, ensure_ascii=False),
        ))

        # Балансы
        balance = udata.get("balance", {})
        for cur, amt in {**_EMPTY_BALANCE, **balance}.items():
            await self._conn.execute("""
                INSERT OR IGNORE INTO balances (user_id, currency, amount)
                VALUES (?,?,?)
            """, (uid, cur, float(amt or 0)))

        # Транзакции
        for tx in udata.get("transactions", []):
            await self._conn.execute("""
                INSERT INTO transactions (user_id, ts, type, currency, amount, deal_id, comment)
                VALUES (?,?,?,?,?,?,?)
            """, (
                uid,
                tx.get("ts", 0),
                tx.get("type", ""),
                tx.get("currency", ""),
                float(tx.get("amount", 0)),
                tx.get("deal_id", ""),
                tx.get("comment", ""),
            ))

        # Рефералы
        for ref in udata.get("referrals", []):
            await self._conn.execute("""
                INSERT OR IGNORE INTO referrals (referrer_id, referee_id) VALUES (?,?)
            """, (uid, str(ref)))

    async def _import_deal(self, deal_id: str, deal: dict):
        await self._conn.execute("""
            INSERT OR IGNORE INTO deals (deal_id, data, status, created_at)
            VALUES (?,?,?,?)
        """, (
            deal_id,
            json.dumps(deal, ensure_ascii=False),
            deal.get("status", ""),
            int(deal.get("created_at", 0)),
        ))

    # ──────────────────────────────────────────────────────────────────────────
    # Загрузка кэша
    # ──────────────────────────────────────────────────────────────────────────

    async def add_review(self, user_id: int, username: str, rating: int, text: str, verified: bool = False,
                         display_name: str = "", photo_url: str = "", is_public: bool = False) -> dict:
        """Добавить отзыв пользователя и сохранить Telegram-имя/аватар для карточки."""
        import time as _time
        created_at = int(_time.time())
        async with _LOCK:
            cur = await self._conn.execute(
                "INSERT INTO reviews (user_id, username, display_name, photo_url, rating, text, verified, is_public, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (str(user_id), username or "", display_name or "", photo_url or "", int(rating), text,
                 1 if verified else 0, 1 if is_public else 0, created_at),
            )
            await self._conn.commit()
            rid = cur.lastrowid
        return {"id": rid, "user_id": str(user_id), "username": username or "",
                "display_name": display_name or "", "photo_url": photo_url or "",
                "rating": int(rating), "text": text, "verified": bool(verified), "is_public": bool(is_public), "created_at": created_at}

    async def get_reviews(self, limit: int = 50, offset: int = 0) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        async with self._conn.execute(
            "SELECT id,user_id,username,display_name,photo_url,rating,text,verified,is_public,created_at,seed_key FROM reviews ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) | {"verified": bool(r["verified"])} for r in rows]

    async def seed_reviews(self, reviews: list[dict]) -> None:
        """Импортировать архивные отзывы один раз; существующие записи не дублировать."""
        if not reviews:
            return
        async with _LOCK:
            # Заменяем предыдущие импортированные архивы, которые создавались этой интеграцией.
            # Пользовательские отзывы (seed_key='') не затрагиваются.
            await self._conn.execute(
                "DELETE FROM reviews WHERE seed_key LIKE 'legacy:%' OR seed_key LIKE 'txt20260928:%' OR seed_key LIKE 'archive_20260928_v2:%' OR seed_key LIKE 'archive_20260928_v3:%'"
            )
            for r in reviews:
                await self._conn.execute(
                    "INSERT INTO reviews (user_id,username,display_name,photo_url,rating,text,verified,is_public,created_at,seed_key) "
                    "SELECT ?,?,?,?,?,?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM reviews WHERE seed_key = ?)",
                    (str(r.get("user_id", "")), str(r.get("username", "")), "Пользователь", "", int(r.get("rating", 5)),
                     str(r.get("text", "")), 0, 1, int(r.get("created_at", 0)), str(r.get("seed_key", "")), str(r.get("seed_key", ""))),
                )
            await self._conn.commit()

    async def delete_review(self, review_id: int) -> bool:
        async with _LOCK:
            cur = await self._conn.execute("DELETE FROM reviews WHERE id = ?", (int(review_id),))
            await self._conn.commit()
            return cur.rowcount > 0

    async def get_reviews_stats(self) -> tuple[int, float]:
        async with self._conn.execute("SELECT COUNT(*), COALESCE(AVG(rating),0) FROM reviews") as cur:
            row = await cur.fetchone()
        return int(row[0]), float(row[1] or 0)

    async def _load_cache(self):
        """Загрузить всё в память для быстрого чтения."""
        # Users
        async with self._conn.execute("SELECT * FROM users") as cur:
            rows = await cur.fetchall()

        for row in rows:
            uid = row["user_id"]
            extra = json.loads(row["extra"] or "{}")
            self.users[uid] = {
                "username": row["username"],
                "lang": row["lang"],
                "ton_wallet": row["ton_wallet"],
                "card": row["card"],
                "stars_username": row["stars_username"],
                "usdt_wallet": row["usdt_wallet"],
                "btc_wallet": row["btc_wallet"],
                "ref_link": row["ref_link"],
                "referral_earnings": row["referral_earnings"],
                "completed_deals": row["completed_deals"],
                **extra,
            }

        # Балансы
        async with self._conn.execute("SELECT * FROM balances") as cur:
            rows = await cur.fetchall()
        for row in rows:
            uid = row["user_id"]
            if uid in self.users:
                self.users[uid].setdefault("balance", dict(_EMPTY_BALANCE))
                self.users[uid]["balance"][row["currency"]] = row["amount"]

        # Рефералы
        async with self._conn.execute("SELECT * FROM referrals") as cur:
            rows = await cur.fetchall()
        for row in rows:
            uid = row["referrer_id"]
            if uid in self.users:
                self.users[uid].setdefault("referrals", [])
                self.users[uid]["referrals"].append(row["referee_id"])

        # Deals
        async with self._conn.execute("SELECT deal_id, data FROM deals") as cur:
            rows = await cur.fetchall()
        for row in rows:
            self.deals[row["deal_id"]] = json.loads(row["data"])

        log.info("Cache loaded: %d users, %d deals", len(self.users), len(self.deals))

    # ──────────────────────────────────────────────────────────────────────────
    # API: пользователи
    # ──────────────────────────────────────────────────────────────────────────

    def get_user_sync(self, user_id) -> dict:
        """Синхронный доступ к кэшу (для совместимости с существующим кодом)."""
        return self.users.get(str(user_id), {})

    async def upsert_user(self, user_id, data: dict):
        """Обновить/создать пользователя. data — частичный или полный dict."""
        uid = str(user_id)
        async with _LOCK:
            # Обновляем кэш
            if uid not in self.users:
                self.users[uid] = {}
            self.users[uid].update(data)

            u = self.users[uid]
            known = ("username", "lang", "ton_wallet", "card", "stars_username",
                     "usdt_wallet", "btc_wallet", "ref_link",
                     "referral_earnings", "completed_deals")
            extra = {k: v for k, v in u.items()
                     if k not in known and k not in ("balance", "transactions", "referrals")}

            await self._conn.execute("""
                INSERT INTO users
                  (user_id, username, lang, ton_wallet, card, stars_username,
                   usdt_wallet, btc_wallet, ref_link, referral_earnings,
                   completed_deals, extra)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                  username=excluded.username,
                  lang=excluded.lang,
                  ton_wallet=excluded.ton_wallet,
                  card=excluded.card,
                  stars_username=excluded.stars_username,
                  usdt_wallet=excluded.usdt_wallet,
                  btc_wallet=excluded.btc_wallet,
                  ref_link=excluded.ref_link,
                  referral_earnings=excluded.referral_earnings,
                  completed_deals=excluded.completed_deals,
                  extra=excluded.extra
            """, (
                uid,
                u.get("username", ""),
                u.get("lang", "ru"),
                u.get("ton_wallet", ""),
                u.get("card", ""),
                u.get("stars_username", ""),
                u.get("usdt_wallet", ""),
                u.get("btc_wallet", ""),
                u.get("ref_link", ""),
                float(u.get("referral_earnings", 0)),
                int(u.get("completed_deals", 0)),
                json.dumps(extra, ensure_ascii=False),
            ))
            await self._conn.commit()

    async def add_referral(self, referrer_id, referee_id):
        rid = str(referrer_id)
        ref = str(referee_id)
        async with _LOCK:
            self.users.setdefault(rid, {}).setdefault("referrals", [])
            if ref not in self.users[rid]["referrals"]:
                self.users[rid]["referrals"].append(ref)
            await self._conn.execute(
                "INSERT OR IGNORE INTO referrals (referrer_id, referee_id) VALUES (?,?)",
                (rid, ref)
            )
            await self._conn.commit()

    # ──────────────────────────────────────────────────────────────────────────
    # API: баланс
    # ──────────────────────────────────────────────────────────────────────────

    def get_balance_sync(self, user_id) -> dict:
        uid = str(user_id)
        return dict({**_EMPTY_BALANCE, **self.users.get(uid, {}).get("balance", {})})

    async def set_balance(self, user_id, currency: str, amount: float):
        uid = str(user_id)
        async with _LOCK:
            self.users.setdefault(uid, {}).setdefault("balance", dict(_EMPTY_BALANCE))
            self.users[uid]["balance"][currency] = round(amount, 8)
            await self._conn.execute("""
                INSERT INTO balances (user_id, currency, amount) VALUES (?,?,?)
                ON CONFLICT(user_id, currency) DO UPDATE SET amount=excluded.amount
            """, (uid, currency, round(amount, 8)))
            await self._conn.commit()

    async def add_balance(self, user_id, currency: str, amount: float,
                          deal_id: str = "", comment: str = ""):
        uid = str(user_id)
        async with _LOCK:
            self.users.setdefault(uid, {}).setdefault("balance", dict(_EMPTY_BALANCE))
            cur_amt = self.users[uid]["balance"].get(currency, 0.0)
            new_amt = round(cur_amt + amount, 8)
            self.users[uid]["balance"][currency] = new_amt
            await self._conn.execute("""
                INSERT INTO balances (user_id, currency, amount) VALUES (?,?,?)
                ON CONFLICT(user_id, currency) DO UPDATE SET amount=excluded.amount
            """, (uid, currency, new_amt))
            await self._add_transaction_locked(uid, "credit", currency, amount, deal_id, comment)
            await self._conn.commit()

    async def subtract_balance(self, user_id, currency: str, amount: float,
                               deal_id: str = "", comment: str = "") -> bool:
        uid = str(user_id)
        async with _LOCK:
            self.users.setdefault(uid, {}).setdefault("balance", dict(_EMPTY_BALANCE))
            cur_amt = self.users[uid]["balance"].get(currency, 0.0)
            if cur_amt < amount:
                return False
            new_amt = round(cur_amt - amount, 8)
            self.users[uid]["balance"][currency] = new_amt
            await self._conn.execute("""
                INSERT INTO balances (user_id, currency, amount) VALUES (?,?,?)
                ON CONFLICT(user_id, currency) DO UPDATE SET amount=excluded.amount
            """, (uid, currency, new_amt))
            await self._add_transaction_locked(uid, "debit", currency, amount, deal_id, comment)
            await self._conn.commit()
        return True

    # ──────────────────────────────────────────────────────────────────────────
    # API: транзакции
    # ──────────────────────────────────────────────────────────────────────────

    async def _add_transaction_locked(self, uid: str, tx_type: str, currency: str,
                                      amount: float, deal_id: str, comment: str):
        """Вставить транзакцию (вызывать внутри _LOCK)."""
        ts = int(_time.time())
        await self._conn.execute("""
            INSERT INTO transactions (user_id, ts, type, currency, amount, deal_id, comment)
            VALUES (?,?,?,?,?,?,?)
        """, (uid, ts, tx_type, currency, amount, deal_id, comment))
        # Обновляем кэш транзакций (только если он уже загружен для этого юзера)
        # Транзакции НЕ держим в памяти (могут быть тысячи) — грузим по запросу

    async def add_transaction(self, user_id, tx_type: str, currency: str,
                              amount: float, deal_id: str = "", comment: str = ""):
        uid = str(user_id)
        async with _LOCK:
            await self._add_transaction_locked(uid, tx_type, currency, amount, deal_id, comment)
            await self._conn.commit()

    async def get_transactions(self, user_id) -> list[dict]:
        uid = str(user_id)
        async with self._conn.execute("""
            SELECT ts, type, currency, amount, deal_id, comment
            FROM transactions WHERE user_id=? ORDER BY ts DESC, id DESC
        """, (uid,)) as cur:
            rows = await cur.fetchall()
        return [dict(row) for row in rows]

    # ──────────────────────────────────────────────────────────────────────────
    # API: сделки
    # ──────────────────────────────────────────────────────────────────────────

    def get_deal_sync(self, deal_id: str) -> dict | None:
        return self.deals.get(deal_id)

    async def upsert_deal(self, deal_id: str, data: dict):
        """Сохранить/обновить сделку."""
        async with _LOCK:
            # Обновляем кэш
            if deal_id in self.deals:
                self.deals[deal_id].update(data)
            else:
                self.deals[deal_id] = data

            d = self.deals[deal_id]
            await self._conn.execute("""
                INSERT INTO deals (deal_id, data, status, created_at) VALUES (?,?,?,?)
                ON CONFLICT(deal_id) DO UPDATE SET
                  data=excluded.data,
                  status=excluded.status,
                  created_at=excluded.created_at
            """, (
                deal_id,
                json.dumps(d, ensure_ascii=False),
                d.get("status", ""),
                int(d.get("created_at", 0)),
            ))
            await self._conn.commit()

    async def save_deal(self, deal_id: str):
        """Сохранить текущее состояние сделки из кэша в БД."""
        if deal_id not in self.deals:
            return
        await self.upsert_deal(deal_id, self.deals[deal_id])

    def get_all_deals(self) -> dict:
        return self.deals

    # ──────────────────────────────────────────────────────────────────────────
    # Совместимость: замена старых синхронных save_* функций
    # ──────────────────────────────────────────────────────────────────────────

    def schedule_save_user(self, user_id):
        """Запланировать async сохранение пользователя (fire-and-forget)."""
        asyncio.create_task(self.upsert_user(user_id, self.users.get(str(user_id), {})))

    def schedule_save_deal(self, deal_id: str):
        """Запланировать async сохранение сделки (fire-and-forget)."""
        asyncio.create_task(self.save_deal(deal_id))


# Глобальный синглтон
db = Database()
