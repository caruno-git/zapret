import base64

# Данные из github_release.py
_GH_PARTS = [
    ("PTIqBQ8VGBUuPQ==", 0x5A, 0),
    ("aW8NWE8EbmlTWw==", 0x3D, 10),
    ("HXpbYXVDZVl9eQ==", 0x2C, 20),
    ("LAkkB08IDkwuKA==", 0x7E, 30),
]

# Данные из telegram_updater.py
_TG_PARTS = [
    ("eHp7f397eXZ+fnU=", 0x4F, 0),
    ("amptXw==", 0x2B, 11),
    ("WEooTm00dltXSihhWFFeKQ==", 0x19, 15),
    ("k4C5iIutlZeIu7qS+vqG", 0xC3, 31),
]

def decrypt_token(parts, length):
    result = [''] * length
    for encoded, xor_key, offset in parts:
        decoded = base64.b64decode(encoded)
        for i, byte in enumerate(decoded):
            if offset + i < len(result):
                result[offset + i] = chr(byte ^ xor_key)
    return ''.join(result).rstrip('\x00')

# Извлечение
github_token = decrypt_token(_GH_PARTS, 40)
telegram_token = decrypt_token(_TG_PARTS, 46)

print("--- Расшифрованные токены ---")
print(f"GitHub Token: {github_token}")
print(f"Telegram Token: {telegram_token}")
print("-----------------------------")