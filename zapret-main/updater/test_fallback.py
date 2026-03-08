# updater/test_fallback.py
"""
test_fallback.py
────────────────────────────────────────────────────────────────
Утилита для тестирования fallback механизма
"""

import sys
import os
from pathlib import Path

# Добавляем родительскую директорию в PYTHONPATH
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from updater.release_manager import get_release_manager, get_latest_release

def main():
    manager = get_release_manager()
    
    print("🔍 Тестирование получения релизов...\n")
    
    # Показываем текущую конфигурацию
    print("⚙️  Конфигурация:")
    print("-" * 50)
    print(f"📍 Серверы:")
    for server in manager.fallback_servers:
        print(f"   {server['priority']}. {server['name']} - {server['url']}")
    
    api_key = os.getenv("ZAPRET_SERVER_API_KEY")
    if api_key:
        print(f"🔐 API ключ: установлен")
    else:
        print(f"🔓 API ключ: не установлен")
    print()
    
    # Тестируем каналы
    for channel in ["stable", "dev"]:
        print(f"📦 Канал: {channel}")
        print("-" * 50)
        
        release = get_latest_release(channel)
        
        if release:
            print(f"✅ Источник: {release.get('source', manager.last_source)}")
            print(f"📌 Версия: {release['version']}")
            print(f"🏷️  Тег: {release['tag_name']}")
            print(f"🔗 URL загрузки: {release['update_url']}")
            print(f"📅 Дата: {release.get('published_at', 'н/д')}")
            print(f"🔄 Prerelease: {'Да' if release.get('prerelease') else 'Нет'}")
            
            # Показываем первые 200 символов описания
            notes = release.get('release_notes', '')
            if notes:
                if len(notes) > 200:
                    print(f"📝 Описание: {notes[:200]}...")
                else:
                    print(f"📝 Описание: {notes}")
            else:
                print("📝 Описание: нет")
        else:
            print(f"❌ Не удалось получить релиз")
            print(f"❌ Последняя ошибка: {manager.last_error}")
        
        print("\n")
    
    # Проверяем состояние серверов
    print("🏥 Проверка состояния серверов:")
    print("-" * 50)
    
    # Проверяем GitHub
    print("📍 GitHub API:")
    try:
        import requests
        resp = requests.get("https://api.github.com/rate_limit", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            rate = data.get('rate', {})
            remaining = rate.get('remaining', 0)
            limit = rate.get('limit', 0)
            print(f"   ✅ Доступен (лимит: {remaining}/{limit})")
        else:
            print(f"   ⚠️  HTTP {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Недоступен: {str(e)}")
    
    print()
    
    # Проверяем fallback серверы
    for server in manager.fallback_servers:
        print(f"📍 {server['name']} ({server['url']}):")
        health = manager.check_server_health(server["url"], server["verify_ssl"])
        
        if health.get("status") == "ok":
            print(f"   ✅ Онлайн")
            if health.get("files"):
                files = health["files"]
                print(f"   📄 Файлы: stable={files.get('stable', False)}, "
                      f"test={files.get('test', False)}, "
                      f"version.json={files.get('version_json', False)}")
            if health.get("versions"):
                versions = health["versions"]
                print(f"   📌 Версии: stable={versions.get('stable', 'н/д')}, "
                      f"test={versions.get('test', 'н/д')}")
        else:
            error = health.get("error", "Unknown error")
            print(f"   ❌ Оффлайн: {error}")
    
    print("\n" + "=" * 50)
    print("💡 Подсказки:")
    print("   - Используйте переменные окружения для настройки серверов:")
    print("     set ZAPRET_FALLBACK_SERVER_1=https://example.com")
    print("     set ZAPRET_SERVER_API_KEY=your-key")
    print("   - Или укажите локальные серверы:")
    print("     set ZAPRET_HTTPS_SERVER=https://192.168.1.100:8443")
    print("     set ZAPRET_HTTP_SERVER=http://192.168.1.100:8080")

if __name__ == "__main__":
    main()