"""Проверяет hidden.json теми же правилами, что и приложение, и строже.

Правила повторяют RemoteConfig.parse в приложении Meme English
(lib/core/remote/remote_config.dart). Файл, который приложение не примет,
здесь тоже не проходит, и коммит на GitHub получает красный крестик.

Строже приложения в одном: незнакомый ключ здесь — ошибка. Приложение такие
ключи пропускает (их может добавить более новая версия), а значит, ключ
с опечаткой («adsEvey») оно тоже молча пропустит. Ловить опечатки — дело
этой проверки. Новый ключ в приложении — новый ключ здесь.
"""

import json
import re
import sys

VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
AD_UNIT = re.compile(r"R-M-[0-9]+-[0-9]+")
ANDROID_STORES = (
    "market://details?id=",
    "https://play.google.com/",
    "https://www.rustore.ru/",
    "https://apps.rustore.ru/",
)
IOS_STORES = ("https://apps.apple.com/", "itms-apps://apps.apple.com/")

TOP = {"hidden", "analyticsOff", "adsOff", "adsEvery", "adUnits", "update", "fixes"}
AD_UNITS = {"android", "ios"}
UPDATE = {"suggest", "require", "message", "android", "ios"}
FIXES = {"memes", "words"}
MEME_FIX = {"titleRu", "translation", "literal", "why", "origin", "glossary"}
MEME_REQUIRED = {"titleRu", "translation", "why"}
ENTRY_FIX = {"ru", "pos", "note", "example", "exampleRu", "distractors"}


class Broken(Exception):
    pass


def utf16_len(text):
    # Длину текста приложение считает в UTF-16, как Dart.
    return len(text.encode("utf-16-le")) // 2


def known(obj, keys, at):
    extra = sorted(set(obj) - keys)
    if extra:
        raise Broken(f"в {at} незнакомый ключ {extra[0]!r} — опечатка? Можно: {', '.join(sorted(keys))}")


def obj(value, at):
    if not isinstance(value, dict):
        raise Broken(f"{at} должен быть объектом {{ ... }}")
    return value


def version(text, at):
    if not VERSION.fullmatch(text):
        raise Broken(f"{at}: {text!r} — не версия, нужно три числа через точку, например 1.0.2")


def rule(text, at):
    if text == "*":
        return
    parts = text.split("..")
    if len(parts) == 2:
        version(parts[0], at)
        version(parts[1], at)
        return
    for op in ("<=", ">=", "<", ">"):
        if text.startswith(op):
            version(text[len(op):], at)
            return
    version(text, at)


def rules(parent, key, at):
    if key not in parent:
        return
    value = parent[key]
    if not isinstance(value, list) or not all(isinstance(r, str) for r in value):
        raise Broken(f'{at} должен быть списком версий в кавычках, например ["<1.0.2"]')
    for r in value:
        rule(r, at)


def field(parent, key, at, required):
    if key not in parent:
        return
    value = parent[key]
    if not isinstance(value, str):
        raise Broken(f"{at}.{key} должен быть текстом в кавычках")
    if required and not value:
        raise Broken(f"{at}.{key} не может быть пустым")


def entry_fix(value, at):
    e = obj(value, at)
    known(e, ENTRY_FIX, at)
    for key in ENTRY_FIX - {"distractors"}:
        field(e, key, at, required=key == "ru")
    if "distractors" in e:
        d = e["distractors"]
        if not isinstance(d, list) or len(d) != 3 or not all(isinstance(x, str) and x for x in d):
            raise Broken(f"{at}.distractors — ровно три неправильных ответа в кавычках")


def by_key(parent, key, at, check):
    if key not in parent:
        return
    for name, value in obj(parent[key], at).items():
        if not name:
            raise Broken(f"в {at} пустой ключ")
        check(value, f"{at}.{name}")


def meme_fix(value, at):
    m = obj(value, at)
    known(m, MEME_FIX, at)
    for key in MEME_FIX - {"glossary"}:
        field(m, key, at, required=key in MEME_REQUIRED)
    by_key(m, "glossary", f"{at}.glossary", entry_fix)


def check(data):
    root = obj(data, "файл")
    known(root, TOP, "файле")

    hidden = root.get("hidden")
    if isinstance(hidden, dict):
        pass
    elif isinstance(hidden, list) and all(isinstance(i, str) for i in hidden):
        pass
    else:
        raise Broken('"hidden" должен быть объектом {"номер": "причина"} или списком номеров')

    rules(root, "analyticsOff", "analyticsOff")
    rules(root, "adsOff", "adsOff")

    if "adsEvery" in root:
        every = root["adsEvery"]
        if type(every) is not int or not 3 <= every <= 100:
            raise Broken('"adsEvery" должен быть числом от 3 до 100, без кавычек')

    if "adUnits" in root:
        units = obj(root["adUnits"], "adUnits")
        known(units, AD_UNITS, "adUnits")
        for key, unit in units.items():
            if not isinstance(unit, str) or not AD_UNIT.fullmatch(unit):
                raise Broken(f"adUnits.{key} должен быть номером блока вида R-M-20184317-1")

    if "update" in root:
        update = obj(root["update"], "update")
        known(update, UPDATE, "update")
        rules(update, "suggest", "update.suggest")
        rules(update, "require", "update.require")
        if "message" in update:
            m = update["message"]
            if not isinstance(m, str) or not m or utf16_len(m) > 500:
                raise Broken("update.message должен быть текстом до 500 знаков")
        for key, stores in (("android", ANDROID_STORES), ("ios", IOS_STORES)):
            if key in update:
                url = update[key]
                if not isinstance(url, str) or not url.startswith(stores):
                    raise Broken(f"update.{key} должен быть ссылкой на магазин: {', '.join(stores)}")

    if "fixes" in root:
        fixes = obj(root["fixes"], "fixes")
        known(fixes, FIXES, "fixes")
        by_key(fixes, "memes", "fixes.memes", meme_fix)
        by_key(fixes, "words", "fixes.words", entry_fix)


def no_constants(name):
    # NaN и Infinity Dart не читает, значит, и здесь нельзя.
    raise Broken(f"{name} — не число JSON")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "hidden.json"
    try:
        with open(path, encoding="utf-8") as f:
            check(json.loads(f.read(), parse_constant=no_constants))
    except json.JSONDecodeError as e:
        print(f"hidden.json не годится: не JSON — {e.msg}, строка {e.lineno}, позиция {e.colno}")
        sys.exit(1)
    except Broken as e:
        print(f"hidden.json не годится: {e}")
        sys.exit(1)
    print("hidden.json в порядке")
