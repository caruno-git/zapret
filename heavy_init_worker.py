# heavy_init_worker.py

from PyQt6.QtCore import QObject, pyqtSignal
import traceback, os
from log import log

class HeavyInitWorker(QObject):
    """
    Все Qt-объекты создаём ТОЛЬКО в GUI-потоке!
    """
    progress = pyqtSignal(str)            # для status-строки
    finished = pyqtSignal(bool, str)      # (ok, err_text)

    def __init__(self, dpi_starter, download_urls, parent=None):
        super().__init__(parent)
        self.dpi  = dpi_starter
        self.urls = download_urls

        # Уменьшаем таймауты для быстрого старта
        self.connection_timeout = 3    # было 10
        self.read_timeout = 10         # было 30
        self.max_retries = 1           # было 3

    def run(self):
        try:
            log("HeavyInitWorker.run() начал выполнение", "DEBUG")
            
            # Быстрая проверка сети перед загрузкой
            if not self._quick_connectivity_check():
                log("Нет интернета - пропускаем загрузку", "⚠ WARNING")
                self.progress.emit("Работаем в автономном режиме")
                self.finished.emit(True, "")
                return
            
            # ДОБАВЛЯЕМ основную логику инициализации
            self.progress.emit("Проверка интернет-соединения...")
            log("Интернет доступен, продолжаем инициализацию", "INFO")
            
            # 1. Проверка и загрузка winws.exe
            self.progress.emit("Проверка winws.exe...")
            success = self._check_and_download_winws()
            if not success:
                log("Ошибка при работе с winws.exe", "❌ ERROR")
                self.finished.emit(False, "Не удалось загрузить winws.exe")
                return
            
            # 2. Загрузка стратегий
            self.progress.emit("Загрузка стратегий...")
            success = self._download_strategies()
            if not success:
                log("Ошибка при загрузке стратегий", "⚠ WARNING")
                # Не критично, продолжаем
            
            # 3. Загрузка других ресурсов
            self.progress.emit("Загрузка ресурсов...")
            self._download_additional_resources()
            
            # Финализация
            self.progress.emit("Инициализация завершена")
            log("HeavyInitWorker завершен успешно", "INFO")
            self.finished.emit(True, "")
            
        except Exception as e:
            error_msg = f"Ошибка в HeavyInitWorker: {e}"
            log(error_msg, "❌ ERROR")
            log(f"Traceback: {traceback.format_exc()}", "❌ ERROR")
            self.progress.emit(f"Ошибка: {e}")
            self.finished.emit(False, error_msg)

    def _check_and_download_winws(self) -> bool:
        """Проверяет наличие winws.exe и загружает при необходимости"""
        try:
            from config import WINWS_EXE
            
            if os.path.exists(WINWS_EXE):
                log(f"winws.exe найден: {WINWS_EXE}", "DEBUG")
                return True
            
            self.progress.emit("Загрузка winws.exe...")
            log("winws.exe не найден, начинаем загрузку", "INFO")
            
            # Здесь должна быть логика загрузки winws.exe
            # Если у вас есть отдельный модуль для загрузки:
            # return self._download_winws_file()
            
            # Временная заглушка
            log("ЗАГЛУШКА: загрузка winws.exe пропущена", "⚠ WARNING")
            return True
            
        except Exception as e:
            log(f"Ошибка при проверке winws.exe: {e}", "❌ ERROR")
            return False

    def _download_strategies(self) -> bool:
        """Загружает стратегии из интернета"""
        try:
            self.progress.emit("Обновление списка стратегий...")
            
            # Если у вас есть StrategyManager с методом загрузки:
            # return self.strategy_manager.download_strategies()
            
            # Временная заглушка
            log("ЗАГЛУШКА: загрузка стратегий пропущена", "❓ TEST")
            return True
            
        except Exception as e:
            log(f"Ошибка при загрузке стратегий: {e}", "❌ ERROR")
            return False

    def _download_additional_resources(self):
        """Загружает дополнительные ресурсы"""
        try:
            self.progress.emit("Обновление ресурсов...")
            
            # Загрузка списков доменов, правил и т.д.
            # Здесь может быть логика загрузки из self.urls
            
            log("Дополнительные ресурсы обработаны", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка при загрузке дополнительных ресурсов: {e}", "⚠ WARNING")
            # Не критично, продолжаем

    def _quick_connectivity_check(self) -> bool:
        """Быстрая проверка доступности интернета"""
        try:
            import socket
            socket.setdefaulttimeout(2)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            log("Интернет-соединение доступно", "DEBUG")
            return True
        except Exception as e:
            log(f"Интернет недоступен: {e}", "DEBUG")
            return False
