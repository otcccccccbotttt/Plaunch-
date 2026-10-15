#!/usr/bin/env python3
"""
🔧 Утилита настройки бота
Запуск: python3 setup.py
"""
import json, os, sys

CONFIG_FILE = "config.json"
BOT_FILE    = "bot.py"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"BOT_TOKEN": "", "ADMIN_GROUP_ID": 0}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    print("✅ config.json сохранён")

def get_owner_ids():
    with open(BOT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if "PANEL_OWNER_IDS = {" in line:
                ids_str = line.strip().split("{")[1].rstrip("}")
                return [int(x.strip()) for x in ids_str.split(",") if x.strip()]
    return []

def set_owner_ids(ids):
    ids_str = ", ".join(str(i) for i in ids)
    with open(BOT_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    import re
    new_content = re.sub(
        r"PANEL_OWNER_IDS = \{[^}]*\}",
        f"PANEL_OWNER_IDS = {{{ids_str}}}",
        content
    )
    with open(BOT_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"✅ PANEL_OWNER_IDS обновлён: {{{ids_str}}}")

def set_token_in_bot(old_token, new_token):
    with open(BOT_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    if old_token in content:
        content = content.replace(old_token, new_token)
        with open(BOT_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print("✅ Токен в bot.py обновлён")
    else:
        print("⚠️  Старый токен не найден в bot.py (config.json всё равно обновлён)")

def menu():
    while True:
        cfg = load_config()
        owners = get_owner_ids()
        print("\n" + "="*45)
        print("       🔧 Настройки бота")
        print("="*45)
        print(f"  Токен:   {cfg.get('BOT_TOKEN','—')[:20]}...")
        print(f"  Группа: {cfg.get('ADMIN_GROUP_ID','—')}")
        print(f"  Owners:  {owners}")
        print("="*45)
        print("  1. Изменить токен бота")
        print("  2. Изменить ADMIN_GROUP_ID")
        print("  3. Добавить owner ID")
        print("  4. Удалить owner ID")
        print("  5. Заменить всех owners")
        print("  0. Выход")
        print("="*45)
        choice = input("Выбор: ").strip()

        if choice == "1":
            old = cfg.get("BOT_TOKEN","")
            new = input("Новый токен: ").strip()
            if not new:
                print("❌ Пусто, отмена")
                continue
            set_token_in_bot(old, new)
            cfg["BOT_TOKEN"] = new
            save_config(cfg)

        elif choice == "2":
            val = input("Новый ADMIN_GROUP_ID (например -1001234567890): ").strip()
            try:
                cfg["ADMIN_GROUP_ID"] = int(val)
                save_config(cfg)
            except ValueError:
                print("❌ Неверный формат ID")

        elif choice == "3":
            val = input("ID для добавления: ").strip()
            try:
                uid = int(val)
                if uid not in owners:
                    owners.append(uid)
                    set_owner_ids(owners)
                else:
                    print("⚠️  Уже есть в списке")
            except ValueError:
                print("❌ Неверный формат ID")

        elif choice == "4":
            if not owners:
                print("❌ Список пуст")
                continue
            for i, uid in enumerate(owners):
                print(f"  {i+1}. {uid}")
            val = input("Номер для удаления: ").strip()
            try:
                idx = int(val) - 1
                removed = owners.pop(idx)
                set_owner_ids(owners)
                print(f"✅ Удалён {removed}")
            except (ValueError, IndexError):
                print("❌ Неверный номер")

        elif choice == "5":
            raw = input("Введи ID через пробел или запятую: ").strip()
            try:
                new_ids = [int(x.strip()) for x in raw.replace(",", " ").split() if x.strip()]
                if not new_ids:
                    print("❌ Пусто, отмена")
                    continue
                set_owner_ids(new_ids)
            except ValueError:
                print("❌ Неверный формат")

        elif choice == "0":
            print("👋 Выход")
            sys.exit(0)
        else:
            print("❌ Неверный выбор")

if __name__ == "__main__":
    if not os.path.exists(BOT_FILE):
        print(f"❌ Файл {BOT_FILE} не найден. Запусти setup.py в той же папке что и bot.py")
        sys.exit(1)
    menu()
