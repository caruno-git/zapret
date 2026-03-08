import os
import requests
import shutil

from config import LISTS_FOLDER
# БОЛЬШЕ НЕ РАБОТАЕТ!
DOWNLOAD_URLS = {
    "winws.exe": "https://github.com/bol-van/zapret-win-bundle/raw/refs/heads/master/zapret-winws/winws.exe",
    "WinDivert.dll": "https://github.com/bol-van/zapret-win-bundle/raw/refs/heads/master/zapret-winws/WinDivert.dll",
    #"WinDivert64.sys": "https://github.com/bol-van/zapret-win-bundle/raw/refs/heads/master/zapret-winws/WinDivert64.sys",
    "cygwin1.dll": "https://github.com/bol-van/zapret-win-bundle/raw/refs/heads/master/zapret-winws/cygwin1.dll",
    "stop.bat": "https://zapretdpi.ru/stop.bat",
}

def download_files(exe_folder, download_urls, status_callback=None):
    """
    Скачивает необходимые файлы с GitHub
    
    Args:
        exe_folder (str): Путь к папке bin
        download_urls (dict): Словарь с именами файлов и URL для скачивания
        status_callback (function): Функция для отображения статуса скачивания
        
    Returns:
        bool: True если все файлы скачаны успешно, иначе False
    """
    try:
        # Создаем папки если они не существуют
        os.makedirs(exe_folder, exist_ok=True)
        
        from log import log
        # Функция для вывода статуса, если передана
        def set_status(message):
            if status_callback:
                status_callback(message)
            else:
                log(message, level="DOWNLOAD")
        
        # Проверяем, существуют ли все файлы
        all_files_exist = True
        for filename in download_urls.keys():
            filepath = os.path.join(exe_folder, filename)
            if not os.path.exists(filepath):
                all_files_exist = False
                break
                
        # Если все файлы уже существуют, сообщаем об этом
        if all_files_exist:
            log(f"Все файлы уже загружены и готовы к использованию", level="DOWNLOAD")
            set_status("Все файлы готовы к использованию")
            return True
        
        # Скачиваем файлы
        for filename, url in download_urls.items():
            filepath = os.path.join(exe_folder, filename)
            
            # Проверяем, существует ли файл уже
            if os.path.exists(filepath):
                log(f"Файл {filename} уже существует", level="DOWNLOAD")
                continue

            log(f"Файл {filename} не найден, скачиваем...", level="DOWNLOAD")
            response = requests.get(url, stream=True)
            
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    response.raw.decode_content = True
                    shutil.copyfileobj(response.raw, f)
                log(f"Файл {filename} скачан успешно", level="DOWNLOAD")
            else:
                log(f"Ошибка при скачивании {filename}, код: {response.status_code}", level="❌ ERROR")
                raise Exception(f"Не удалось скачать {filename}, код: {response.status_code}")
                
        # Создаем пустые txt файлы в lists, если их нет
        default_lists = [
            "list-general.txt", 
            "youtubeQ.txt", 
            "youtube.txt",
            "youtube_v2.txt",
            "youtubeGV.txt", 
            "discord.txt",
            "faceinsta.txt",
            "russia-youtube-rtmps.txt",
            "ipset-discord.txt",
            "ipset-cloudflare.txt"
        ]
        
        for listfile in default_lists:
            filepath = os.path.join(LISTS_FOLDER, listfile)
            if not os.path.exists(filepath):
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write("# Добавьте адреса сайтов по одному на строку\n")

        log("Все файлы успешно загружены и готовы к использованию", level="DOWNLOAD")
        log(f"======================== ВСЕ ФАЙЛЫ ГОТОВЫ ========================", level="DOWNLOAD")
        return True
                
    except Exception as e:
        error_msg = f"Ошибка при скачивании файлов: {str(e)}"
        log(f"Ошибка при скачивании файлов: {error_msg}", level="❌ ERROR")
        if status_callback:
            status_callback(error_msg)
        return False
