from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QMessageBox,
)

from .autostart_exe      import setup_autostart_for_exe
from .autostart_strategy import setup_autostart_for_strategy
from .autostart_service  import setup_service_for_strategy
from .autostart_direct   import (
    setup_direct_autostart_task,
    setup_direct_autostart_service,
    collect_direct_strategy_args
)
from .autostart_direct_service import setup_direct_service  # НОВЫЙ ИМПОРТ
from log                 import log
from strategy_menu import get_strategy_launch_method
import os

class AutoStartMenu(QDialog):
    """
    Диалог настройки автозапуска с поддержкой Direct и BAT режимов
    """

    def __init__(
        self,
        parent,
        strategy_name: str,
        bat_folder: str,
        json_folder: str,
        check_autostart_cb,
        update_ui_cb,
        status_cb,
        app_instance=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Настройка автозапуска")
        self.setMinimumWidth(450)

        # Сохраненные параметры
        self.strategy_name   = strategy_name
        self.bat_folder      = bat_folder
        self.json_folder     = json_folder
        self.check_autostart = check_autostart_cb
        self.update_ui       = update_ui_cb
        self.status          = status_cb
        self.app_instance    = app_instance
        
        # Определяем режим запуска
        self.launch_method = get_strategy_launch_method()
        self.is_direct_mode = (self.launch_method == "direct")
        
        # UI
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Информационный текст
        if self.is_direct_mode:
            info_text = (
                "Режим: ПРЯМОЙ ЗАПУСК\n\n"
                "Выберите тип автозапуска:"
            )
        else:
            info_text = (
                "Режим: КЛАССИЧЕСКИЙ (BAT)\n\n"
                "Выберите тип автозапуска:"
            )
        
        info = QLabel(info_text)
        info.setWordWrap(True)
        layout.addWidget(info)

        # Кнопка автозапуска GUI
        self.exe_btn = QPushButton("🖥️ Автозапуск программы ZapretGUI")
        self.exe_btn.setToolTip(
            "Запускает главное окно программы при входе в Windows.\n"
            "Вы сможете управлять DPI из системного трея."
        )
        layout.addWidget(self.exe_btn)
        
        # Разделитель
        separator = QLabel("─" * 40)
        separator.setStyleSheet("color: gray;")
        separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(separator)
        
        # Кнопки для стратегий
        if self.is_direct_mode:
            # Для Direct режима
            
            # НОВАЯ КНОПКА - Служба Windows (самая надежная)
            self.real_service_btn = QPushButton("⚙️ Служба Windows (рекомендуется)")
            self.real_service_btn.setToolTip(
                "Создает настоящую службу Windows для запуска winws.exe.\n"
                "Самый надежный способ автозапуска.\n"
                "Работает даже если никто не вошел в систему."
            )
            self.real_service_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2e7d32;
                    color: white;
                    font-weight: bold;
                    padding: 10px;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #388e3c;
                }
            """)
            layout.addWidget(self.real_service_btn)
            
            # Задача при входе
            self.strategy_btn = QPushButton("⚡ Задача при входе пользователя")
            self.strategy_btn.setToolTip(
                "Создает задачу планировщика для запуска winws.exe\n"
                "при входе пользователя в систему."
            )
            
            # Задача при загрузке
            self.service_btn = QPushButton("🚀 Задача при загрузке системы")
            self.service_btn.setToolTip(
                "Создает задачу планировщика для запуска winws.exe\n"
                "при загрузке Windows (до входа пользователя)."
            )
        else:
            # Для BAT режима
            self.strategy_btn = QPushButton("📋 Автозапуск стратегии (.bat файл)")
            self.strategy_btn.setToolTip(
                "Создает задачу планировщика для запуска .bat файла\n"
                "выбранной стратегии при входе в Windows."
            )
            
            self.service_btn = QPushButton("⚙️ Служба Windows (.bat файл)")
            self.service_btn.setToolTip(
                "Создает службу Windows для запуска .bat файла.\n"
                "Запускается при загрузке системы."
            )
        
        layout.addWidget(self.strategy_btn)
        layout.addWidget(self.service_btn)
    
        # Подключаем обработчики
        self.exe_btn.clicked.connect(self.enable_exe_autostart)
        self.strategy_btn.clicked.connect(self.enable_strategy_autostart)
        self.service_btn.clicked.connect(self.enable_strategy_service)
        
        # Подключаем обработчик для новой кнопки службы
        if self.is_direct_mode and hasattr(self, 'real_service_btn'):
            self.real_service_btn.clicked.connect(self.enable_real_direct_service)

    def enable_exe_autostart(self):
        """Автозапуск GUI приложения"""
        log("Включаем автозапуск GUI", "INFO")

        ok = setup_autostart_for_exe(
            selected_mode=self.strategy_name,
            status_cb=self.status,
        )

        if ok:
            self.status("Автозапуск GUI настроен")
            self.update_ui(True)
            QMessageBox.information(
                self,
                "Успешно",
                "✅ Автозапуск программы ZapretGUI настроен!\n\n"
                "Программа будет запускаться при входе в Windows\n"
                "и будет доступна в системном трее."
            )
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Ошибка",
                "❌ Не удалось настроить автозапуск.\n\n"
                "Проверьте права администратора и повторите попытку."
            )

    def enable_strategy_autostart(self):
        """Автозапуск стратегии при входе пользователя"""
        log(f"Включаем автозапуск стратегии при входе (режим: {self.launch_method})", "INFO")

        def _show_error(msg: str):
            QMessageBox.critical(self, "Ошибка автозапуска", msg)

        if self.is_direct_mode:
            # Direct режим - задача при входе
            ok = self._setup_direct_task(_show_error)
            success_msg = (
                "✅ Автозапуск DPI настроен!\n\n"
                "Создана задача планировщика Windows.\n"
                "DPI будет запускаться при входе в систему."
            )
        else:
            # BAT режим
            index_json_path = (Path(self.json_folder) / "index.json").resolve()
            ok = setup_autostart_for_strategy(
                selected_mode=self.strategy_name,
                bat_folder=self.bat_folder,
                index_path=str(index_json_path),
                ui_error_cb=_show_error,
            )
            success_msg = (
                "✅ Автозапуск стратегии настроен!\n\n"
                f"Стратегия «{self.strategy_name}» будет\n"
                "запускаться при входе в Windows."
            )

        if ok:
            self.status("Автозапуск стратегии настроен")
            self.update_ui(True)
            QMessageBox.information(self, "Успешно", success_msg)
            self.accept()

    def enable_strategy_service(self):
        """Создание автозапуска при загрузке системы"""
        log(f"Создаём автозапуск при загрузке (режим: {self.launch_method})", "INFO")

        def _show_error(msg: str):
            QMessageBox.critical(self, "Ошибка автозапуска", msg)

        if self.is_direct_mode:
            # Direct режим - задача при загрузке
            ok = self._setup_direct_service(_show_error)
            success_msg = (
                "✅ Автозапуск DPI при загрузке настроен!\n\n"
                "Создана системная задача планировщика.\n"
                "DPI будет запускаться при загрузке Windows\n"
                "(до входа пользователя в систему).\n\n"
                "Это наиболее надежный способ автозапуска."
            )
        else:
            # BAT режим - настоящая служба
            index_json_path = (Path(self.json_folder) / "index.json").resolve()
            ok = setup_service_for_strategy(
                selected_mode=self.strategy_name,
                bat_folder=self.bat_folder,
                index_path=str(index_json_path),
                ui_error_cb=_show_error,
            )
            success_msg = (
                "✅ Служба Windows создана!\n\n"
                f"Стратегия «{self.strategy_name}» будет\n"
                "запускаться как служба Windows."
            )

        if ok:
            self.status("Автозапуск настроен")
            self.update_ui(True)
            QMessageBox.information(self, "Успешно", success_msg)
            self.accept()

    def enable_real_direct_service(self):
        """НОВЫЙ МЕТОД: Создание настоящей службы Windows для Direct режима"""
        log("Создаём службу Windows для Direct режима", "INFO")
        
        # НОВОЕ: Предупреждение о необходимости остановки
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("Создание службы Windows")
        msg.setText("Для создания службы необходимо остановить Zapret")
        msg.setInformativeText(
            "Текущий процесс winws.exe будет остановлен и перезапущен как служба Windows.\n\n"
            "Это обеспечит автоматический запуск при загрузке системы.\n\n"
            "Продолжить?"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        if msg.exec() != QMessageBox.StandardButton.Yes:
            return
        
        def _show_error(msg: str):
            QMessageBox.critical(self, "Ошибка создания службы", msg)
        
        try:
            if not self.app_instance:
                _show_error("Ошибка: не передан экземпляр приложения")
                return
            
            # Собираем аргументы стратегии
            args, name, winws_exe = collect_direct_strategy_args(self.app_instance)
            
            if not args:
                _show_error("Не удалось собрать аргументы стратегии")
                return
            
            if not winws_exe or not os.path.exists(winws_exe):
                _show_error(f"winws.exe не найден: {winws_exe}")
                return
            
            # Импортируем функцию создания службы
            from .autostart_direct_service import setup_direct_service
            
            # Создаем службу
            ok = setup_direct_service(
                winws_exe=winws_exe,
                strategy_args=args,
                strategy_name=name,
                ui_error_cb=lambda msg: None  # Показываем свое сообщение
            )
            
            if ok:
                self.status("Служба Windows создана")
                self.update_ui(True)
                QMessageBox.information(
                    self,
                    "Успешно",
                    "✅ Служба Windows успешно создана!\n\n"
                    "Zapret будет автоматически запускаться\n"
                    "при загрузке системы как служба Windows.\n\n"
                    "Это самый надежный способ автозапуска:\n"
                    "• Работает до входа в систему\n"
                    "• Автоматически перезапускается при сбоях\n"
                    "• Не требует входа пользователя\n\n"
                    "Служба уже запущена и работает."
                )
                self.accept()
            else:
                _show_error(
                    "Не удалось создать службу Windows.\n\n"
                    "Убедитесь, что:\n"
                    "1. Программа запущена с правами администратора\n"
                    "2. Антивирус не блокирует создание служб\n"
                    "3. У вас есть права на создание служб"
                )
                
        except Exception as e:
            _show_error(f"Ошибка создания службы: {e}")

    def _setup_direct_task(self, error_cb) -> bool:
        """Настройка задачи планировщика для Direct режима (при входе)"""
        try:
            if not self.app_instance:
                error_cb("Ошибка: не передан экземпляр приложения")
                return False
            
            # Собираем аргументы стратегии
            args, name, winws_exe = collect_direct_strategy_args(self.app_instance)
            
            if not args:
                error_cb("Не удалось собрать аргументы стратегии")
                return False
            
            if not winws_exe or not os.path.exists(winws_exe):
                error_cb(f"winws.exe не найден: {winws_exe}")
                return False
            
            # Создаем задачу
            return setup_direct_autostart_task(
                winws_exe=winws_exe,
                strategy_args=args,
                strategy_name=name,
                ui_error_cb=error_cb
            )
            
        except Exception as e:
            error_cb(f"Ошибка настройки: {e}")
            return False

    def _setup_direct_service(self, error_cb) -> bool:
        """Настройка задачи планировщика для Direct режима (при загрузке)"""
        try:
            if not self.app_instance:
                error_cb("Ошибка: не передан экземпляр приложения")
                return False
            
            # Собираем аргументы стратегии
            args, name, winws_exe = collect_direct_strategy_args(self.app_instance)
            
            if not args:
                error_cb("Не удалось собрать аргументы стратегии")
                return False
            
            if not winws_exe or not os.path.exists(winws_exe):
                error_cb(f"winws.exe не найден: {winws_exe}")
                return False
            
            # Создаем задачу с запуском при загрузке
            return setup_direct_autostart_service(
                winws_exe=winws_exe,
                strategy_args=args,
                strategy_name=name,
                ui_error_cb=error_cb
            )
            
        except Exception as e:
            error_cb(f"Ошибка настройки: {e}")
            return False
