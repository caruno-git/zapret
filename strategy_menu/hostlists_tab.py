# strategy_menu/hostlists_tab.py

import os
import re
from typing import List, Dict, Set
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QCheckBox, QGroupBox, QPushButton,
                            QFrame, QMessageBox, QLineEdit,
                            QListWidget, QListWidgetItem, QSplitter,
                            QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from log import log
from config import OTHER_PATH, OTHER2_PATH, LISTS_FOLDER
# Импортируем всё из hostlists_manager
from utils.hostlists_manager import (
    PREDEFINED_DOMAINS, 
    get_base_domains,
    save_hostlists_settings,
    load_hostlists_settings
)


class HostlistsTab(QWidget):
    """Компактная вкладка управления хостлистами"""
    
    hostlists_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_services = set()
        self.custom_domains = []
        self.init_ui()
        self.load_existing_domains()
    
    def init_ui(self):
        """Инициализация компактного интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Компактный заголовок
        title = QLabel("Управление списками доменов")
        title.setStyleSheet("font-weight: bold; font-size: 10pt; color: #2196F3;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Создаем разделитель для двух панелей
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Левая панель - предустановленные сервисы
        predefined_widget = self._create_predefined_panel()
        splitter.addWidget(predefined_widget)
        
        # Правая панель - пользовательские домены
        custom_widget = self._create_custom_panel()
        splitter.addWidget(custom_widget)
        
        # Устанавливаем пропорции 40/60
        splitter.setSizes([300, 400])
        
        layout.addWidget(splitter, 1)
        
        # Компактные кнопки управления
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(5)
        
        self.apply_button = QPushButton("✅ Применить")
        self.apply_button.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px;
                border-radius: 3px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background: #45a049;
            }
        """)
        self.apply_button.setFixedHeight(28)
        self.apply_button.clicked.connect(self.apply_changes)
        buttons_layout.addWidget(self.apply_button)
        
        self.reload_button = QPushButton("🔄 Обновить")
        self.reload_button.setFixedHeight(28)
        self.reload_button.setStyleSheet("font-size: 9pt;")
        self.reload_button.clicked.connect(self.reload_domains)
        buttons_layout.addWidget(self.reload_button)
        
        layout.addLayout(buttons_layout)
        
        # Компактный статус
        self.status_label = QLabel("Готово")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #888; font-size: 8pt;")
        self.status_label.setFixedHeight(20)
        layout.addWidget(self.status_label)
    
    def _create_predefined_panel(self) -> QWidget:
        """Создает компактную панель с предустановленными сервисами"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Компактная группа
        group = QGroupBox("Сервисы для other.txt")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 9pt;
                border: 1px solid #444;
                border-radius: 3px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(3)
        
        # Компактная сетка чекбоксов
        grid_layout = QGridLayout()
        grid_layout.setSpacing(5)
        
        self.service_checkboxes = {}
        
        # Используем PREDEFINED_DOMAINS из hostlists_manager
        for idx, (service_id, service_data) in enumerate(PREDEFINED_DOMAINS.items()):
            # Компактный чекбокс
            checkbox = QCheckBox(service_data['name'])
            checkbox.setStyleSheet("font-size: 9pt;")
            checkbox.setToolTip(f"{len(service_data['domains'])} доменов\nПримеры: {', '.join(service_data['domains'][:3])}...")
            self.service_checkboxes[service_id] = checkbox
            
            # Размещаем в сетке 2x2
            row = idx // 2
            col = idx % 2
            grid_layout.addWidget(checkbox, row, col)
        
        group_layout.addLayout(grid_layout)
        
        # Компактная информация
        info_label = QLabel("Выберите сервисы для фильтрации")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888; font-size: 8pt; margin-top: 5px;")
        group_layout.addWidget(info_label)
        
        group_layout.addStretch()
        layout.addWidget(group)
        
        return widget
    
    def _create_custom_panel(self) -> QWidget:
        """Создает компактную панель для пользовательских доменов"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Компактная группа
        group = QGroupBox("Свои домены для other2.txt")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 9pt;
                border: 1px solid #444;
                border-radius: 3px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(3)
        
        # Компактное поле ввода
        input_layout = QHBoxLayout()
        input_layout.setSpacing(3)
        
        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("example.com")
        self.domain_input.setStyleSheet("""
            QLineEdit {
                padding: 3px;
                border: 1px solid #555;
                border-radius: 2px;
                background: #2a2a2a;
                font-size: 9pt;
            }
            QLineEdit:focus {
                border: 1px solid #2196F3;
            }
        """)
        self.domain_input.setFixedHeight(24)
        self.domain_input.returnPressed.connect(self.add_custom_domain)
        input_layout.addWidget(self.domain_input)
        
        self.add_button = QPushButton("➕")
        self.add_button.clicked.connect(self.add_custom_domain)
        self.add_button.setFixedSize(24, 24)
        self.add_button.setToolTip("Добавить домен")
        input_layout.addWidget(self.add_button)
        
        group_layout.addLayout(input_layout)
        
        # Компактный список доменов
        self.custom_list = QListWidget()
        self.custom_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #333;
                background: #2a2a2a;
                padding: 2px;
                font-size: 9pt;
            }
            QListWidget::item {
                padding: 2px;
                border-bottom: 1px solid #333;
            }
            QListWidget::item:selected {
                background: #3a3a3a;
            }
            QListWidget::item:hover {
                background: #353535;
            }
        """)
        self.custom_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        group_layout.addWidget(self.custom_list, 1)
        
        # Компактные кнопки управления
        list_buttons = QHBoxLayout()
        list_buttons.setSpacing(3)
        
        self.remove_button = QPushButton("🗑️ Удалить")
        self.remove_button.clicked.connect(self.remove_selected_domains)
        self.remove_button.setFixedHeight(22)
        self.remove_button.setStyleSheet("font-size: 8pt;")
        list_buttons.addWidget(self.remove_button)
        
        self.clear_button = QPushButton("🧹 Очистить")
        self.clear_button.clicked.connect(self.clear_custom_domains)
        self.clear_button.setFixedHeight(22)
        self.clear_button.setStyleSheet("font-size: 8pt;")
        list_buttons.addWidget(self.clear_button)
        
        group_layout.addLayout(list_buttons)
        
        layout.addWidget(group)
        return widget
    
    def normalize_domain(self, domain: str) -> str:
        """Нормализует домен, убирая протокол и www"""
        domain = domain.strip()
        domain = re.sub(r'^https?://', '', domain, flags=re.IGNORECASE)
        domain = re.sub(r'^www\.', '', domain, flags=re.IGNORECASE)
        domain = domain.split('/')[0]
        domain = domain.split(':')[0]
        return domain.lower()
    
    def validate_domain(self, domain: str) -> bool:
        """Проверяет валидность домена"""
        pattern = r'^[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,}$'
        return bool(re.match(pattern, domain))
    
    def add_custom_domain(self):
        """Добавляет пользовательский домен в список"""
        domain = self.domain_input.text().strip()
        if not domain:
            return
        
        normalized = self.normalize_domain(domain)
        
        if not self.validate_domain(normalized):
            QMessageBox.warning(self, "Ошибка", 
                              f"Неверный формат: {normalized}")
            return
        
        if normalized in self.custom_domains:
            self.status_label.setText(f"Уже есть: {normalized}")
            return
        
        self.custom_domains.append(normalized)
        self.custom_list.addItem(normalized)
        self.domain_input.clear()
        
        self.status_label.setText(f"Добавлен: {normalized}")
        log(f"Добавлен домен: {normalized}", "INFO")
    
    def remove_selected_domains(self):
        """Удаляет выбранные домены"""
        items = self.custom_list.selectedItems()
        if not items:
            return
        
        for item in items:
            domain = item.text()
            self.custom_domains.remove(domain)
            self.custom_list.takeItem(self.custom_list.row(item))
        
        self.status_label.setText(f"Удалено: {len(items)}")
    
    def clear_custom_domains(self):
        """Очищает список пользовательских доменов"""
        if not self.custom_domains:
            return
        
        reply = QMessageBox.question(self, "Подтверждение", 
                                    "Удалить все?",
                                    QMessageBox.StandardButton.Yes | 
                                    QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.custom_domains.clear()
            self.custom_list.clear()
            self.status_label.setText("Очищено")
    
    def load_existing_domains(self):
        """Загружает существующие домены из реестра и файлов"""
        try:
            # Загружаем из реестра
            selected_services, custom_domains = load_hostlists_settings()
            
            if selected_services:
                # Устанавливаем чекбоксы согласно настройкам из реестра
                for service_id in selected_services:
                    if service_id in self.service_checkboxes:
                        self.service_checkboxes[service_id].setChecked(True)
                        self.selected_services.add(service_id)
                log(f"Загружены настройки сервисов из реестра: {selected_services}", "INFO")
            
            if custom_domains:
                # Загружаем пользовательские домены из реестра
                self.custom_domains = custom_domains
                for domain in custom_domains:
                    self.custom_list.addItem(domain)
                log(f"Загружено {len(custom_domains)} пользовательских доменов из реестра", "INFO")
            
            # Если в реестре пусто - загружаем из файлов (обратная совместимость)
            if not selected_services and not custom_domains:
                self._load_from_files()
                
        except Exception as e:
            log(f"Ошибка загрузки настроек хостлистов: {e}", "⚠ WARNING")
            self._load_from_files()
    
    def _load_from_files(self):
        """Загружает настройки из файлов (fallback метод)"""
        # Загружаем other2.txt
        try:
            if os.path.exists(OTHER2_PATH):
                with open(OTHER2_PATH, 'r', encoding='utf-8') as f:
                    domains = [line.strip() for line in f if line.strip()]
                    self.custom_domains = domains
                    for domain in domains:
                        self.custom_list.addItem(domain)
                    log(f"Загружено {len(domains)} доменов из other2.txt", "INFO")
        except Exception as e:
            log(f"Ошибка загрузки other2.txt: {e}", "⚠ WARNING")
        
        # Анализируем other.txt
        try:
            if os.path.exists(OTHER_PATH):
                with open(OTHER_PATH, 'r', encoding='utf-8') as f:
                    existing_domains = set(line.strip() for line in f if line.strip())
                
                for service_id, service_data in PREDEFINED_DOMAINS.items():
                    service_domains = set(service_data['domains'])
                    if len(service_domains & existing_domains) >= len(service_domains) * 0.5:
                        self.service_checkboxes[service_id].setChecked(True)
                        self.selected_services.add(service_id)
        except Exception as e:
            log(f"Ошибка анализа other.txt: {e}", "⚠ WARNING")
    
    def apply_changes(self):
        """Применяет изменения к файлам и сохраняет в реестр"""
        try:
            # Собираем выбранные сервисы
            selected_services = set()
            for service_id, checkbox in self.service_checkboxes.items():
                if checkbox.isChecked():
                    selected_services.add(service_id)
            
            # Сохраняем в реестр
            if not save_hostlists_settings(selected_services, self.custom_domains):
                QMessageBox.warning(self, "Предупреждение", 
                                  "Не удалось сохранить настройки в реестр")
            
            # Сохраняем other.txt
            selected_domains = set(get_base_domains())  # Используем из менеджера
            
            # Добавляем домены выбранных сервисов
            for service_id in selected_services:
                if service_id in PREDEFINED_DOMAINS:
                    selected_domains.update(PREDEFINED_DOMAINS[service_id]['domains'])
            
            # Сохраняем файлы
            with open(OTHER_PATH, 'w', encoding='utf-8') as f:
                for domain in sorted(selected_domains):
                    f.write(f"{domain}\n")
            
            with open(OTHER2_PATH, 'w', encoding='utf-8') as f:
                for domain in sorted(self.custom_domains):
                    f.write(f"{domain}\n")
            
            self.status_label.setText("✅ Сохранено")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 8pt;")
            
            self.hostlists_changed.emit()
            
            QMessageBox.information(self, "Успешно", 
                                  f"Настройки сохранены!\nother.txt: {len(selected_domains)} доменов\n"
                                  f"other2.txt: {len(self.custom_domains)} доменов")
            
            log(f"Настройки хостлистов сохранены в реестр и файлы", "✅ SUCCESS")
            
        except Exception as e:
            self.status_label.setText(f"❌ Ошибка")
            QMessageBox.critical(self, "Ошибка", str(e))
            log(f"Ошибка применения настроек хостлистов: {e}", "❌ ERROR")
    
    def reload_domains(self):
        """Перезагружает домены из файлов"""
        self.custom_domains.clear()
        self.custom_list.clear()
        self.selected_services.clear()
        
        for checkbox in self.service_checkboxes.values():
            checkbox.setChecked(False)
        
        self.load_existing_domains()
        self.status_label.setText("🔄 Обновлено")