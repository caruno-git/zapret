"""
Утилиты для управления файлами приложения
"""
import os
from log import log
from config import LISTS_FOLDER

def ensure_required_files():
    """
    Проверяет наличие обязательных файлов и создает их при необходимости
    """
    
    # Список файлов, которые должны существовать
    required_files = [
        {
            'path': os.path.join(LISTS_FOLDER, "other2.txt"),
            'description': 'Дополнительный список доменов',
            'content': _get_other2_default_content()
        },
        # Можно добавить другие файлы при необходимости
        {
            'path': os.path.join(LISTS_FOLDER, "other.txt"),
            'description': 'Основной список доменов',
            'content': _get_other_default_content()
        }
    ]
    
    # Создаем папку lists, если её нет
    os.makedirs(LISTS_FOLDER, exist_ok=True)
    
    created_files = []
    
    for file_info in required_files:
        file_path = file_info['path']
        description = file_info['description']
        content = file_info['content']
        
        if not os.path.exists(file_path):
            try:
                # Создаем файл с содержимым по умолчанию
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                filename = os.path.basename(file_path)
                log(f"Создан файл: {filename} ({description})", "INFO")
                created_files.append(filename)
                
            except Exception as e:
                filename = os.path.basename(file_path)
                log(f"Ошибка создания файла {filename}: {e}", "❌ ERROR")
    
    if created_files:
        log(f"Созданы отсутствующие файлы: {', '.join(created_files)}", "INFO")
    else:
        log("Все обязательные файлы найдены", "DEBUG")
    
    return len(created_files) > 0

def _get_other2_default_content():
    """
    Возвращает содержимое по умолчанию для файла other2.txt
    """
    return """# Дополнительный список доменов для обхода блокировок
# Этот файл создан автоматически
# Добавьте сюда домены, которые нужно обрабатывать

# Примеры доменов (раскомментируйте при необходимости):
# example.com
# test.domain.com
# another-site.org

# Комментарии начинаются с символа #
# Пустые строки игнорируются
"""

def _get_other_default_content():
    """
    Возвращает содержимое по умолчанию для файла other.txt
    """
    return """# Основной список доменов для обхода блокировок
# Этот файл создан автоматически
# Добавьте сюда домены, которые нужно обрабатывать

# Примеры доменов (раскомментируйте при необходимости):
# blocked-site.com
# restricted.domain.org
# censored-content.net

# Комментарии начинаются с символа #
# Пустые строки игнорируются
"""

def create_file_if_missing(file_path, content="", description="файл"):
    """
    Создает конкретный файл, если он отсутствует
    
    Args:
        file_path (str): Путь к файлу
        content (str): Содержимое файла по умолчанию
        description (str): Описание файла для логов
        
    Returns:
        bool: True если файл был создан, False если уже существовал
    """
    if not os.path.exists(file_path):
        try:
            # Создаем директорию если нужно
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Создаем файл
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            filename = os.path.basename(file_path)
            log(f"Создан {description}: {filename}", "INFO")
            return True
            
        except Exception as e:
            filename = os.path.basename(file_path)
            log(f"Ошибка создания файла {filename}: {e}", "❌ ERROR")
            return False
    
    return False

def ensure_other2_file():
    """
    Специальная функция для создания файла other2.txt
    """
    other2_path = os.path.join(LISTS_FOLDER, "other2.txt")
    return create_file_if_missing(
        other2_path, 
        _get_other2_default_content(),
        "дополнительный список доменов"
    )

# Для обратной совместимости
def ensure_file_exists(file_path, default_content=""):
    """
    Устаревшая функция - используйте create_file_if_missing
    """
    return create_file_if_missing(file_path, default_content)