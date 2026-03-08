import requests
import os
import sys
from datetime import datetime

# ─── НАСТРОЙКА ────────────────────────────────────────────────
TOKEN = os.environ.get("GITHUB_TOKEN") or input("Введи GitHub токен: ").strip()
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
BASE = "https://api.github.com"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✔{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}~{RESET} {msg}")
def section(title): print(f"\n{CYAN}{'─'*50}\n  {title}\n{'─'*50}{RESET}")

# ─── 1. БАЗОВАЯ ПРОВЕРКА + RATE LIMIT ─────────────────────────
section("🔑 Базовая информация о токене")

r = requests.get(f"{BASE}/user", headers=HEADERS)
if r.status_code == 401:
    fail("Токен невалидный или истёк!")
    sys.exit(1)
elif r.status_code == 200:
    u = r.json()
    ok(f"Авторизован как: {u['login']} ({u.get('name', 'без имени')})")
    ok(f"Тип аккаунта:    {u.get('type', '?')}")
else:
    warn(f"Неожиданный статус /user: {r.status_code}")

# Scopes из заголовков (только для classic PAT)
scopes = r.headers.get("X-OAuth-Scopes", "")
if scopes:
    ok(f"OAuth scopes:    {scopes if scopes else '(пусто — только публичный доступ)'}")
else:
    warn("X-OAuth-Scopes отсутствует — возможно fine-grained токен")

# Rate limit
rl = r.headers
print(f"\n  Rate limit: {rl.get('X-RateLimit-Remaining','?')} / "
      f"{rl.get('X-RateLimit-Limit','?')} запросов")
reset_ts = rl.get("X-RateLimit-Reset")
if reset_ts:
    reset_time = datetime.fromtimestamp(int(reset_ts)).strftime("%H:%M:%S")
    print(f"  Сброс лимита: {reset_time}")

# ─── 2. ТЕСТ ДОСТУПОВ ─────────────────────────────────────────
section("🧪 Тест прав доступа")

def test(label, url, method="GET", json_body=None, expected=200):
    """Проверяет endpoint и выводит результат."""
    try:
        fn = getattr(requests, method.lower())
        resp = fn(url, headers=HEADERS, json=json_body, timeout=8)
        if resp.status_code == expected:
            ok(label)
        elif resp.status_code == 403:
            fail(f"{label}  →  403 Forbidden")
        elif resp.status_code == 404:
            warn(f"{label}  →  404 (нет ресурса или нет доступа)")
        elif resp.status_code == 422:
            ok(f"{label}  →  422 (endpoint доступен, запрос невалиден — OK)")
        else:
            warn(f"{label}  →  HTTP {resp.status_code}")
    except requests.RequestException as e:
        fail(f"{label}  →  Ошибка: {e}")

# Публичные данные
test("Читать профиль пользователя (user)",         f"{BASE}/user")
test("Читать свои репозитории (repo)",              f"{BASE}/user/repos?per_page=1")
test("Читать organizations",                       f"{BASE}/user/orgs")
test("Читать gists",                               f"{BASE}/gists")
test("Читать уведомления (notifications)",         f"{BASE}/notifications")
test("Читать SSH ключи",                           f"{BASE}/user/keys")
test("Читать GPG ключи",                           f"{BASE}/user/gpg_keys")
test("Читать emails пользователя",                 f"{BASE}/user/emails")
test("Читать starred репозитории",                 f"{BASE}/user/starred?per_page=1")
test("Читать subscriptions",                       f"{BASE}/user/subscriptions?per_page=1")

# ─── 3. ТЕСТ ЗАПИСИ В РЕПОЗИТОРИЙ (опционально) ───────────────
section("📂 Тест прав на репозиторий (write-тест)")

user_login = r.json().get("login") if r.status_code == 200 else None
REPO = input(f"\n  Введи 'owner/repo' для тестирования прав записи\n"
             f"  (Enter — пропустить): ").strip()

if REPO and "/" in REPO:
    owner, repo = REPO.split("/", 1)
    test("Читать репозиторий",        f"{BASE}/repos/{REPO}")
    test("Читать issues",             f"{BASE}/repos/{REPO}/issues?per_page=1")
    test("Читать pull requests",      f"{BASE}/repos/{REPO}/pulls?per_page=1")
    test("Читать actions/workflows",  f"{BASE}/repos/{REPO}/actions/workflows")
    test("Читать секреты (secrets)",  f"{BASE}/repos/{REPO}/actions/secrets")
    test("Читать deployments",        f"{BASE}/repos/{REPO}/deployments")
    test("Читать collaborators",      f"{BASE}/repos/{REPO}/collaborators")
    # Попытка записи: создать issue (потребует issues:write)
    test(
        "Создать issue (write-test — закрой вручную!)",
        f"{BASE}/repos/{REPO}/issues",
        method="POST",
        json_body={"title": "[TOKEN PERM TEST] Удали это issue", "body": "Автоматический тест прав токена."},
        expected=201,
    )
else:
    warn("Тест репозитория пропущен.")

# ─── 4. ПРОВЕРКА FINE-GRAINED TOKEN ───────────────────────────
section("🔍 Метаданные (fine-grained токен)")

meta = requests.get(
    "https://api.github.com/meta",
    headers={**HEADERS, "Accept": "application/vnd.github.v3+json"},
)
# Fine-grained токены возвращают X-Accepted-GitHub-Permissions
accepted = r.headers.get("X-Accepted-GitHub-Permissions", "")
if accepted:
    ok(f"Принятые разрешения: {accepted}")
else:
    warn("X-Accepted-GitHub-Permissions не найден (classic PAT или нет данных)")

print(f"\n{CYAN}Готово! ✅{RESET}\n")
