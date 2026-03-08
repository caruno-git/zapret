# zapretbuild.py
"""
Создаёт version_info.txt для PyInstaller.
Числовая версия = major.minor.micro.<build>, где <build> =
    • dev-номер   (для .devN)
    • pre-номер   (alpha/beta/rc → их номер)
    • post-номер  (для .postN)
    • 0           (если ничего из выше-перечисленного нет)
Строковые поля содержат оригинальную версию без изменений.
"""

from __future__ import annotations

import re
from pathlib import Path

# ────────────────────────────────────────────────────────────────
# 1.  Берём APP_VERSION из config/build_info.py,
# 
# ────────────────────────────────────────────────────────────────
from config import APP_VERSION           # из config/__init__.py

# -----------------------------------------------------------------
# numeric_tuple
# -----------------------------------------------------------------
try:
    from packaging.version import Version, InvalidVersion  # pip install packaging
except ModuleNotFoundError:
    Version = None
    InvalidVersion = Exception


def numeric_tuple(ver: str) -> tuple[int, int, int, int]:
    """
    Возвращает (major, minor, micro, build).
    build:
        devN  -> N
        preN  -> N
        postN -> N
        else  -> 0
    """
    # Попытка через packaging
    if Version is not None:
        try:
            v = Version(ver)
            nums = list(v.release)                  # [16, 1, 0] и т.-д.
            # добираем четвёртое число
            if len(nums) < 4:
                if v.dev is not None:               # .devN
                    nums.append(v.dev)
                elif v.pre is not None:             # a/b/rcN
                    nums.append(v.pre[1] or 0)
                elif v.post is not None:            # .postN
                    nums.append(v.post)
                else:
                    nums.append(0)
            nums += [0] * (4 - len(nums))
            return tuple(nums[:4])
        except InvalidVersion:
            pass

    # Фолбек – просто берём все числа подряд
    nums = [int(m.group()) for m in re.finditer(r"\d+", ver)]
    nums += [0] * (4 - len(nums))
    return tuple(nums[:4])


VERSION_TUPLE = numeric_tuple(APP_VERSION)

# -----------------------------------------------------------------
# Формируем текст ресурса
# -----------------------------------------------------------------
VERSION_INFO_TEXT = f"""# UTF-8
#
# Автоматически сгенерировано zapretbuild.py
#
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={VERSION_TUPLE},
    prodvers={VERSION_TUPLE},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [
        StringStruct(u'CompanyName',     u't.me/bypassblock'),
        StringStruct(u'FileDescription', u'Zapret GUI'),
        StringStruct(u'FileVersion',     u'{APP_VERSION}'),
        StringStruct(u'InternalName',    u'zapret'),
        StringStruct(u'LegalCopyright',  u'Copyright © 2025 t.me/bypassblock'),
        StringStruct(u'OriginalFilename',u'zapret.exe'),
        StringStruct(u'ProductName',     u'Zapret'),
        StringStruct(u'ProductVersion',  u'{APP_VERSION}')
        ]
      )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""

# -----------------------------------------------------------------
# Записываем файл
# -----------------------------------------------------------------
def main() -> None:
    out_file = Path(__file__).with_name("version_info.txt")
    out_file.write_text(VERSION_INFO_TEXT, encoding="utf-8-sig")

    print(
        f"version_info.txt создан.\n"
        f"  filevers/prodvers : {'.'.join(map(str, VERSION_TUPLE))}\n"
        f"  Строковая версия  : {APP_VERSION}"
    )


if __name__ == "__main__":
    main()
