# strategy_menu/ipsets_tab.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                            QGroupBox, QTextEdit, QLabel, QCheckBox,
                            QScrollArea, QMessageBox, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor

from log import log
from utils.ipsets_manager import (
    PREDEFINED_IP_RANGES, save_ipsets_settings, load_ipsets_settings,
    rebuild_ipsets_from_registry, ensure_ipsets_exist, get_base_ips
)


class IpsetsTab(QWidget):
    """Вкладка для управления списками IP-адресов"""
    
    ipsets_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_services = set()
        self.custom_ips = []
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Заголовок
        title = QLabel("Управление списками IP-адресов (IPsets)")
        title.setStyleSheet("font-weight: bold; font-size: 11pt; color: #2196F3;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Описание
        desc = QLabel(
            "Здесь вы можете добавить IP-адреса и диапазоны для фильтрации.\n"
            "Базовые IP и выбранные сервисы сохраняются в ipset-base.txt\n"
            "Пользовательские IP сохраняются в ipset-all2.txt"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaa; padding: 5px;")
        layout.addWidget(desc)
        
        # Разделитель для групп
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Группа предустановленных IP диапазонов
        services_group = QGroupBox("📦 Предустановленные IP диапазоны")
        services_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        services_layout = QVBoxLayout(services_group)
        
        # Создаем чекбоксы для предустановленных сервисов
        self.service_checkboxes = {}
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        for service_id, service_info in PREDEFINED_IP_RANGES.items():
            checkbox = QCheckBox(f"{service_info['name']} ({len(service_info['ranges'])} диапазонов)")
            checkbox.setToolTip(f"IP диапазоны: {', '.join(service_info['ranges'][:3])}...")
            checkbox.setProperty('service_id', service_id)
            checkbox.stateChanged.connect(self.on_service_toggled)
            self.service_checkboxes[service_id] = checkbox
            scroll_layout.addWidget(checkbox)
        
        scroll_area.setWidget(scroll_widget)
        services_layout.addWidget(scroll_area)
        
        splitter.addWidget(services_group)
        
        # Группа пользовательских IP
        custom_group = QGroupBox("✏️ Пользовательские IP-адреса и диапазоны")
        custom_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        custom_layout = QVBoxLayout(custom_group)
        
        # Подсказка
        hint = QLabel(
            "Введите IP-адреса или диапазоны (по одному на строку).\n"
            "Примеры: 192.168.1.1 или 10.0.0.0/8 или 172.16.0.0-172.31.255.255"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 9pt; padding: 5px;")
        custom_layout.addWidget(hint)
        
        # Текстовое поле для ввода IP
        self.custom_text = QTextEdit()
        self.custom_text.setPlaceholderText(
            "192.168.1.1\n"
            "10.0.0.0/8\n"
            "172.16.0.0-172.31.255.255\n"
            "# Комментарии начинаются с #"
        )
        self.custom_text.setStyleSheet("""
            QTextEdit {
                background: #2a2a2a;
                border: 1px solid #444;
                border-radius: 3px;
                color: #fff;
                font-family: Consolas, monospace;
                font-size: 10pt;
                padding: 5px;
            }
        """)
        custom_layout.addWidget(self.custom_text)
        
        # Кнопка валидации
        validate_btn = QPushButton("🔍 Проверить IP-адреса")
        validate_btn.clicked.connect(self.validate_custom_ips)
        custom_layout.addWidget(validate_btn)
        
        splitter.addWidget(custom_group)
        
        layout.addWidget(splitter)
        # Установите соотношение ширины колонок (например, 40% и 60%)
        splitter.setSizes([400, 600])     
           
        # Информация о базовых IP
        base_info = QLabel(f"📌 Базовые IP диапазоны (всегда включены): {len(get_base_ips())} записей")
        base_info.setStyleSheet("color: #888; font-size: 9pt; padding: 5px;")
        layout.addWidget(base_info)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Сохранить изменения")
        save_btn.setStyleSheet("""
            QPushButton {
                background: #2196F3;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #1976D2;
            }
        """)
        save_btn.clicked.connect(self.save_changes)
        buttons_layout.addWidget(save_btn)
        
        reset_btn = QPushButton("🔄 Сбросить")
        reset_btn.clicked.connect(self.reset_settings)
        buttons_layout.addWidget(reset_btn)
        
        layout.addLayout(buttons_layout)
    
    def on_service_toggled(self, state):
        """Обработчик изменения состояния чекбокса сервиса"""
        checkbox = self.sender()
        service_id = checkbox.property('service_id')
        
        if state == Qt.CheckState.Checked.value:
            self.selected_services.add(service_id)
            log(f"Добавлен IP диапазон: {service_id}", "DEBUG")
        else:
            self.selected_services.discard(service_id)
            log(f"Удален IP диапазон: {service_id}", "DEBUG")
    
    def validate_custom_ips(self):
        """Проверяет корректность введенных IP-адресов"""
        import re
        
        text = self.custom_text.toPlainText()
        lines = text.split('\n')
        
        valid_count = 0
        invalid_lines = []
        
        # Паттерны для проверки
        ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
        cidr_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$')
        range_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}-(\d{1,3}\.){3}\d{1,3}$')
        
        cursor = self.custom_text.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(QTextCharFormat())  # Сброс форматирования
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Пропускаем пустые строки и комментарии
            if not line or line.startswith('#'):
                continue
            
            # Проверяем формат
            if ip_pattern.match(line):
                # Проверяем корректность IP
                parts = line.split('.')
                if all(0 <= int(part) <= 255 for part in parts):
                    valid_count += 1
                    self._highlight_line(i, QColor(100, 255, 100))  # Зеленый
                else:
                    invalid_lines.append(f"Строка {i+1}: {line} - неверный IP")
                    self._highlight_line(i, QColor(255, 100, 100))  # Красный
            elif cidr_pattern.match(line):
                # Проверяем CIDR
                ip_part, mask = line.split('/')
                parts = ip_part.split('.')
                if all(0 <= int(part) <= 255 for part in parts) and 0 <= int(mask) <= 32:
                    valid_count += 1
                    self._highlight_line(i, QColor(100, 255, 100))
                else:
                    invalid_lines.append(f"Строка {i+1}: {line} - неверный CIDR")
                    self._highlight_line(i, QColor(255, 100, 100))
            elif range_pattern.match(line):
                # Проверяем диапазон
                start_ip, end_ip = line.split('-')
                start_parts = start_ip.split('.')
                end_parts = end_ip.split('.')
                
                if (all(0 <= int(part) <= 255 for part in start_parts) and
                    all(0 <= int(part) <= 255 for part in end_parts)):
                    valid_count += 1
                    self._highlight_line(i, QColor(100, 255, 100))
                else:
                    invalid_lines.append(f"Строка {i+1}: {line} - неверный диапазон")
                    self._highlight_line(i, QColor(255, 100, 100))
            else:
                invalid_lines.append(f"Строка {i+1}: {line} - неверный формат")
                self._highlight_line(i, QColor(255, 100, 100))
        
        # Показываем результат
        if invalid_lines:
            msg = f"✅ Корректных записей: {valid_count}\n"
            msg += f"❌ Некорректных записей: {len(invalid_lines)}\n\n"
            msg += "Ошибки:\n" + '\n'.join(invalid_lines[:10])
            if len(invalid_lines) > 10:
                msg += f"\n... и еще {len(invalid_lines) - 10} ошибок"
            
            QMessageBox.warning(self, "Проверка IP-адресов", msg)
        else:
            QMessageBox.information(
                self, 
                "Проверка IP-адресов", 
                f"✅ Все записи корректны!\nНайдено {valid_count} валидных IP/диапазонов"
            )
    
    def _highlight_line(self, line_number, color):
        """Подсвечивает строку указанным цветом"""
        cursor = self.custom_text.textCursor()
        
        # Переходим к нужной строке
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(line_number):
            cursor.movePosition(QTextCursor.MoveOperation.Down)
        
        # Выделяем всю строку
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        
        # Применяем форматирование
        format = QTextCharFormat()
        format.setBackground(color)
        format.setForeground(QColor(0, 0, 0))
        cursor.setCharFormat(format)
    
    def save_changes(self):
        """Сохраняет изменения в файлы и реестр"""
        try:
            # Собираем пользовательские IP
            text = self.custom_text.toPlainText()
            custom_ips = []
            
            for line in text.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    custom_ips.append(line)
            
            # Сохраняем в реестр
            if save_ipsets_settings(self.selected_services, custom_ips):
                # Перестраиваем файлы
                if rebuild_ipsets_from_registry():
                    QMessageBox.information(
                        self,
                        "Успех",
                        f"✅ Настройки сохранены!\n\n"
                        f"Выбрано сервисов: {len(self.selected_services)}\n"
                        f"Пользовательских IP: {len(custom_ips)}"
                    )
                    self.ipsets_changed.emit()
                    log(f"IPsets сохранены: {len(self.selected_services)} сервисов, {len(custom_ips)} IP", "✅ SUCCESS")
                else:
                    QMessageBox.warning(self, "Ошибка", "Не удалось создать файлы IPsets")
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось сохранить настройки в реестр")
                
        except Exception as e:
            log(f"Ошибка сохранения IPsets: {e}", "❌ ERROR")
            QMessageBox.critical(self, "Ошибка", f"Ошибка сохранения: {e}")
    
    def load_settings(self):
        """Загружает настройки из реестра"""
        try:
            self.selected_services, custom_ips = load_ipsets_settings()
            
            # Устанавливаем чекбоксы
            for service_id, checkbox in self.service_checkboxes.items():
                checkbox.setChecked(service_id in self.selected_services)
            
            # Заполняем текстовое поле
            self.custom_text.setPlainText('\n'.join(custom_ips))
            
            log(f"Загружены настройки IPsets: {len(self.selected_services)} сервисов, {len(custom_ips)} IP", "INFO")
            
        except Exception as e:
            log(f"Ошибка загрузки настроек IPsets: {e}", "⚠ WARNING")
    
    def reset_settings(self):
        """Сбрасывает настройки к исходным"""
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Вы уверены, что хотите сбросить все настройки IPsets?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Очищаем выборы
            self.selected_services.clear()
            for checkbox in self.service_checkboxes.values():
                checkbox.setChecked(False)
            
            # Очищаем текст
            self.custom_text.clear()
            
            log("Настройки IPsets сброшены", "INFO")