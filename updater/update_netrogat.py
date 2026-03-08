# update_netrogat.py

import os
import sys
import shutil
import subprocess
from PyQt6.QtWidgets import QMessageBox

# Импортируем константы из urls и config
from config.urls import NETROGAT_LIST_URL

def update_netrogat_list(parent=None, status_callback=None):
    """
    Args:
        parent: Родительское окно для диалогов
        status_callback: Функция для отображения статуса
    """
    try:
        if status_callback:
            status_callback("Обновление списка доменов...")
        
        # Проверка наличия модуля requests
        try:
            import requests
        except ImportError:
            if status_callback:
                status_callback("Установка зависимостей...")
            subprocess.run([sys.executable, "-m", "pip", "install", "requests"], 
                        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            import requests
        
        # Путь к локальному файлу
        from config import NETROGAT_PATH
        
        # Создаем директорию, если она не существует
        os.makedirs(os.path.dirname(NETROGAT_PATH), exist_ok=True)
        
        # Скачиваем файл с сервера
        if status_callback:
            status_callback("Загрузка списка доменов...")
        response = requests.get(NETROGAT_LIST_URL, timeout=10)
        
        if response.status_code == 200:
            # Обрабатываем полученное содержимое
            domains = []
            for line in response.text.splitlines():
                line = line.strip()  # Удаляем пробелы в начале и конце строки
                if line:  # Пропускаем пустые строки
                    domains.append(line)
            
            # Собираем все домены в один текст, каждый на новой строке БЕЗ пустых строк
            downloaded_content = "\n".join(domains)
            
            # Читаем текущий файл, если он существует
            current_content = ""
            if os.path.exists(NETROGAT_PATH):
                with open(NETROGAT_PATH, 'r', encoding='utf-8') as f:
                    # Также обрабатываем существующее содержимое
                    current_domains = []
                    for line in f:
                        line = line.strip()
                        if line:
                            current_domains.append(line)
                    current_content = "\n".join(current_domains)
            
            # Если файла нет или содержимое отличается
            if not os.path.exists(NETROGAT_PATH) or current_content != downloaded_content:
                # Делаем резервную копию текущего файла
                if os.path.exists(NETROGAT_PATH):
                    backup_path = NETROGAT_PATH + '.bak'
                    shutil.copy2(NETROGAT_PATH, backup_path)
                
                # Сохраняем новый файл (без пустых строк)
                with open(NETROGAT_PATH, 'w', encoding='utf-8') as f:
                    f.write(downloaded_content)
                    
                if status_callback:
                    status_callback("Список успешно обновлен")
                if parent:
                    QMessageBox.information(parent, "Успешно", "Список доменов успешно обновлен")
                return True, "Список успешно обновлен"
            else:
                if status_callback:
                    status_callback("Список уже актуален")
                if parent:
                    QMessageBox.information(parent, "Информация", "Список доменов уже актуален")
                return True, "Список уже актуален"
        else:
            error_msg = f"Ошибка при загрузке списка доменов: {response.status_code}"
            if status_callback:
                status_callback(error_msg)
            if parent:
                QMessageBox.warning(parent, "Ошибка", f"Не удалось получить список доменов с сервера. Код ответа: {response.status_code}")
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Ошибка при обновлении списка доменов: {str(e)}"
        print(error_msg)
        if status_callback:
            status_callback(error_msg)
        if parent:
            QMessageBox.critical(parent, "Ошибка", error_msg)
        return False, error_msg
