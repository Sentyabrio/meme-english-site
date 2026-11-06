"""Проверяет hidden.json теми же правилами, что и приложение.

Правила повторяют RemoteConfig.parse в приложении Meme English
(lib/core/remote/remote_config.dart). Файл, который приложение не примет,
здесь тоже не проходит, и коммит на GitHub получает красный крестик.
"""

import json
import re
import sys

VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def version(text):
    if not VERSION.match(text):
        raise ValueError(f"не версия: {text!r}")


def rule(text):
    if text == "*":
        return
    if ".." in text:
        parts = text.split("..")
        if len(parts) != 2:
            raise ValueError(f"не диапазон: {text!r}")
        version(parts[0])
        version(parts[1])
        return
    for op in ("<=", ">=", "<", ">"):
        if text.startswith(op):
            version(text[len(op):])
            return
    version(text)


def check(data):
    if not isinstance(data, dict):
        raise ValueError("файл должен быть объектом { ... }")
    hidden = data.get("hidden")
    if isinstance(hidden, dict):
        pass
    elif isinstance(hidden, list) and all(isinstance(i, str) for i in hidden):
        pass
    else:
        raise ValueError('"hidden" должен быть объектом {"номер": "причина"} или списком номеров')
    for key in ("analyticsOff", "adsOff"):
        value = data.get(key)
        if value is None:
            continue
        if not isinstance(value, list) or not all(isinstance(r, str) for r in value):
            raise ValueError(f'"{key}" должен быть списком версий в кавычках')
        for r in value:
            rule(r)
    every = data.get("adsEvery")
    if every is not None and (type(every) is not int or not 3 <= every <= 100):
        raise ValueError('"adsEvery" должен быть числом от 3 до 100, без кавычек')


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "hidden.json"
    try:
        with open(path, encoding="utf-8") as f:
            check(json.load(f))
    except (ValueError, json.JSONDecodeError) as e:
        print(f"hidden.json не годится: {e}")
        sys.exit(1)
    print("hidden.json в порядке")
