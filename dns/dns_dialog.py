# dns.py

import os
import subprocess
import threading
from PyQt6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                            QPushButton, QRadioButton, QLineEdit, QMessageBox,
                            QGroupBox, QButtonGroup, QApplication, QCheckBox, QProgressBar, QTabWidget)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from log import log
from functools import lru_cache
from dns import DNSManager, DNSForceManager, _normalize_alias, refresh_exclusion_cache
from typing import List, Tuple, Dict
import json
from utils import run_hidden

# Предопределенные DNS-серверы с поддержкой IPv6
PREDEFINED_DNS = {
    "Quad9": {
        "ipv4": ["9.9.9.9", "149.112.112.112"],
        "ipv6": ["2620:fe::fe", "2620:fe::9"]
    },
    "Quad9 ECS": {
        "ipv4": ["9.9.9.11", "149.112.112.11"],
        "ipv6": ["2620:fe::11", "2620:fe::fe:11"]
    },
    "Quad9 No Malware blocking": {
        "ipv4": ["9.9.9.10", "149.112.112.10"],
        "ipv6": ["2620:fe::10", "2620:fe::fe:10"]
    },
    "Xbox DNS": {
        "ipv4": ["176.99.11.77", "80.78.247.254"],
        "ipv6": []  # Xbox DNS не предоставляет IPv6
    },
    "Google": {
        "ipv4": ["8.8.8.8", "8.8.4.4"],
        "ipv6": ["2001:4860:4860::8888", "2001:4860:4860::8844"]
    },
    "Dns.SB": {
        "ipv4": ["185.222.222.222", "45.11.45.11"],
        "ipv6": ["2a09::", "2a11::"]
    },
    "OpenDNS": {
        "ipv4": ["208.67.222.222", "208.67.220.220"],
        "ipv6": ["2620:119:35::35", "2620:119:53::53"]
    },
    "AdGuard": {
        "ipv4": ["94.140.14.14", "94.140.15.15"],
        "ipv6": ["2a10:50c0::ad1:ff", "2a10:50c0::ad2:ff"]
    },
    "Cloudflare": {
        "ipv4": ["1.1.1.1", "1.0.0.1"],
        "ipv6": ["2606:4700:4700::1111", "2606:4700:4700::1001"]
    }
}

class DNSSettingsDialog(QDialog):
    # Добавляем сигналы для уведомления о завершении загрузки
    adapters_loaded = pyqtSignal(list)
    dns_info_loaded = pyqtSignal(dict)
    
    def __init__(self, parent=None, common_style=None):
        super().__init__(parent)
            # ①  Проверяем состояние принудительного DNS
        try:
            self.force_dns_active = DNSForceManager().is_force_dns_enabled()
        except Exception:
            self.force_dns_active = False

        self.setWindowTitle("Настройка DNS-серверов")
        self.setMinimumWidth(600)
        self.dns_manager = DNSManager()
        
        # Сохраняем переданный стиль или используем стандартный
        self.common_style = common_style or "color: #333;"
        
        # Проверяем IPv6 подключение СРАЗУ
        self.ipv6_available = self.check_ipv6_connectivity()
        log(f"DEBUG: IPv6 подключение: {'доступно' if self.ipv6_available else 'недоступно'}", "DEBUG")
        
        # Сначала создаем базовый интерфейс с индикатором загрузки
        self.init_loading_ui()
        
        # Запускаем загрузку данных в отдельном потоке
        self.load_data_thread = threading.Thread(target=self.load_data_in_background)
        self.load_data_thread.daemon = True
        self.load_data_thread.start()

    @staticmethod
    def check_ipv6_connectivity():
        """Быстрая проверка доступности IPv6 подключения"""
        try:
            result = run_hidden(
                ['ping', '-6', '-n', '1', '-w', '1500', '2001:4860:4860::8888'],
                capture_output=True, 
                text=True, 
                timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except:
            return False
        
    def check_ipv6_in_background(self):
        """Проверяем IPv6 подключение в фоне"""
        try:
            # Быстрая проверка IPv6
            result = run_hidden(
                ['ping', '-6', '-n', '1', '-w', '2000', '2001:4860:4860::8888'],
                capture_output=True, 
                text=True, 
                timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.ipv6_available = (result.returncode == 0)
            log(f"DEBUG: IPv6 подключение: {'доступно' if self.ipv6_available else 'недоступно'}", "DEBUG")
        except:
            self.ipv6_available = False
            log("DEBUG: IPv6 подключение: недоступно (ошибка проверки)", "DEBUG")

    def init_loading_ui(self):
        """Инициализация интерфейса с индикатором загрузки"""
        layout = QVBoxLayout()
        
        # Сообщение о загрузке
        loading_label = QLabel("Получение списка сетевых адаптеров и настроек DNS...")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(loading_label)
        
        # Индикатор прогресса
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Бесконечный прогресс
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
        
        # Подключаем сигналы
        self.adapters_loaded.connect(self.on_adapters_loaded)
        self.dns_info_loaded.connect(self.on_dns_info_loaded)
    
    def load_data_in_background(self):
        """Оптимизированная загрузка данных"""
        try:
            refresh_exclusion_cache()

            # 1. Быстро получаем все адаптеры (WMI)
            all_adapters = self.dns_manager.get_network_adapters_fast(
                include_ignored=True,
                include_disconnected=True
            )
            
            filtered_adapters = []
            for name, desc in all_adapters:
                if not self.dns_manager.should_ignore_adapter(name, desc):
                    filtered_adapters.append((name, desc))
            
            self.all_adapters = all_adapters
            self.adapters = filtered_adapters
            self.adapters_loaded.emit(filtered_adapters)
            
            # 2. Быстро получаем DNS для всех адаптеров ОДНИМ запросом
            adapter_names = [name for name, _ in all_adapters]
            dns_info = self.dns_manager.get_all_dns_info_fast(adapter_names)
            
            self.dns_info_loaded.emit(dns_info)
            
        except Exception as e:
            log(f"Ошибка при быстрой загрузке данных: {str(e)}", level="❌ ERROR")
            self._load_data_slow_fallback()

    def _load_data_slow_fallback(self):
        """Fallback к старому медленному методу"""
        try:
            all_adapters = self.dns_manager.get_network_adapters_powershell_fallback(include_ignored=True)
            filtered_adapters = [(name, desc) for name, desc in all_adapters 
                            if not self.dns_manager.should_ignore_adapter(name, desc)]
            
            self.all_adapters = all_adapters
            self.adapters = filtered_adapters
            self.adapters_loaded.emit(filtered_adapters)
            
            # DNS по одному адаптеру (медленно)
            dns_info = {}
            for name, _ in all_adapters:
                # ИСПРАВЛЕНО: убрали создание экземпляра
                dns_servers_v4 = self.dns_manager.get_current_dns(name, "IPv4")
                dns_servers_v6 = self.dns_manager.get_current_dns(name, "IPv6")
                dns_info[name] = {
                    "ipv4": dns_servers_v4,
                    "ipv6": dns_servers_v6
                }
            
            self.dns_info_loaded.emit(dns_info)
        except Exception as e:
            log(f"Критическая ошибка загрузки DNS данных: {e}", "❌ ERROR")

    def on_adapters_loaded(self, adapters):
        """Обработчик загрузки списка адаптеров"""
        self.adapters = adapters
        if hasattr(self, 'dns_info'):
            self.init_full_ui()
    
    def on_dns_info_loaded(self, dns_info):
        """Обработчик загрузки информации о DNS"""
        self.dns_info = dns_info
        if hasattr(self, 'adapters'):
            self.init_full_ui()
    
    def init_full_ui(self):
        """Инициализация полного интерфейса после загрузки данных"""
        # Удаляем текущий интерфейс загрузки
        QWidget().setLayout(self.layout())

        self.init_ui()

    def init_ui(self):
        """Инициализация интерфейса с поддержкой IPv6"""
        layout = QVBoxLayout()

        # ②  Показываем предупреждение
        if self.force_dns_active:
            warn = QLabel(
                "⚠️  Принудительный DNS включён.\n"
                "Сначала отключите его в разделе «Принудительный DNS», "
                "затем вернитесь к настройке DNS-серверов."
            )
            warn.setStyleSheet(
                "color:#721c24; background:#f8d7da; border:1px solid #f5c6cb; "
                "padding:8px; border-radius:4px;"
            )
            layout.addWidget(warn)

        # Группа для выбора адаптера
        self.adapter_group = QGroupBox("Сетевой адаптер")
        adapter_layout = QVBoxLayout()
        
        # Комбобокс для выбора адаптера с применением стиля
        self.adapter_combo = QComboBox()
        self.adapter_combo.setStyleSheet(self.common_style)
        self.refresh_adapters()
        adapter_layout.addWidget(self.adapter_combo)
        
        # Кнопка обновления списка адаптеров
        refresh_button = QPushButton("Обновить список")
        refresh_button.clicked.connect(self.refresh_adapters)
        adapter_layout.addWidget(refresh_button)
        
        self.adapter_group.setLayout(adapter_layout)
        layout.addWidget(self.adapter_group)
        
        # Флажок для применения ко всем адаптерам
        self.apply_all_check = QCheckBox("Применить настройки ко всем сетевым адаптерам")
        self.apply_all_check.setChecked(True)
        self.apply_all_check.stateChanged.connect(self.toggle_adapter_visibility)
        layout.addWidget(self.apply_all_check)
        
        # Создаем вкладки
        self.tabs = QTabWidget()
        
        # Вкладка IPv4 (всегда есть)
        self.ipv4_tab = QWidget()
        self.init_ipv4_tab()
        self.tabs.addTab(self.ipv4_tab, "IPv4")
        
        # Вкладка IPv6 (только если IPv6 доступен)
        if self.ipv6_available:
            self.ipv6_tab = QWidget()
            self.init_ipv6_tab()
            self.tabs.addTab(self.ipv6_tab, "IPv6")
            log("DEBUG: IPv6 вкладка добавлена (IPv6 доступен)", "DEBUG")
        else:
            # Создаем заглушку для IPv6 (чтобы код не ломался)
            self.ipv6_tab = None
            self.auto_dns_v6_radio = None
            self.predefined_dns_v6_radio = None
            self.custom_dns_v6_radio = None
            
            # Добавляем информационное сообщение
            ipv6_info = QLabel(
                "ℹ️ IPv6 подключение недоступно - настройки IPv6 скрыты.\n"
                "Для IPv6 DNS будет использоваться автоматический режим."
            )
            ipv6_info.setStyleSheet(
                "color: #856404; background-color: #fff3cd; padding: 10px; "
                "border: 1px solid #ffeaa7; border-radius: 5px; margin: 5px;"
            )
            layout.addWidget(ipv6_info)
            log("DEBUG: IPv6 вкладка скрыта (IPv6 недоступен)", "DEBUG")
        
        layout.addWidget(self.tabs)
        
        # Отображение текущих DNS-серверов
        current_dns_label = QLabel("Текущие DNS-серверы:")
        layout.addWidget(current_dns_label)
        
        self.current_dns_value = QLabel()
        self.current_dns_value.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.current_dns_value)
        
        # Кнопки ОК и Отмена
        buttons_layout = QHBoxLayout()
        
        self.apply_button = QPushButton("Применить")   # ← делаем атрибутом
        self.apply_button.clicked.connect(self.apply_dns_settings)
        buttons_layout.addWidget(self.apply_button)
        
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)

        # ④  Фактическое блокирование управления
        if self.force_dns_active:
            # Самый простой вариант — полностью заблокировать вкладки
            self.tabs.setEnabled(False)
            self.apply_button.setEnabled(False)

        # Подключаем обработчик изменения выбранного адаптера
        self.adapter_combo.currentIndexChanged.connect(self.update_current_dns)
        
        # Обновляем информацию о текущих DNS
        self.update_current_dns()
        
        # Применяем начальное состояние видимости адаптера
        self.toggle_adapter_visibility()

        # Применяем стиль к тексту в интерфейсе
        self.adapter_group.setStyleSheet(self.common_style)
        current_dns_label.setStyleSheet(self.common_style)
        self.apply_all_check.setStyleSheet(self.common_style)

    def init_ipv4_tab(self):
        """Инициализация вкладки IPv4"""
        layout = QVBoxLayout()
        
        # Радиокнопка для автоматических DNS
        self.auto_dns_v4_radio = QRadioButton("Получать адреса DNS-серверов автоматически")
        layout.addWidget(self.auto_dns_v4_radio)
        
        # Радиокнопка для предустановленных DNS
        self.predefined_dns_v4_radio = QRadioButton("Использовать предустановленные DNS-серверы:")
        layout.addWidget(self.predefined_dns_v4_radio)
        
        # Комбобокс для выбора предустановленных DNS
        self.predefined_dns_v4_combo = QComboBox()
        self.predefined_dns_v4_combo.setStyleSheet(self.common_style)
        for name, dns_data in PREDEFINED_DNS.items():
            if dns_data["ipv4"]:  # Добавляем только если есть IPv4 адреса
                self.predefined_dns_v4_combo.addItem(name)
        layout.addWidget(self.predefined_dns_v4_combo)
        
        # Радиокнопка для пользовательских DNS
        self.custom_dns_v4_radio = QRadioButton("Использовать следующие адреса DNS-серверов:")
        layout.addWidget(self.custom_dns_v4_radio)
        
        # Поля для ввода пользовательских DNS
        custom_dns_layout = QHBoxLayout()
        
        custom_dns_layout.addWidget(QLabel("Основной DNS:"))
        self.primary_dns_v4_edit = QLineEdit()
        self.primary_dns_v4_edit.setPlaceholderText("Например: 8.8.8.8")
        custom_dns_layout.addWidget(self.primary_dns_v4_edit)
        
        custom_dns_layout.addWidget(QLabel("Дополнительный DNS:"))
        self.secondary_dns_v4_edit = QLineEdit()
        self.secondary_dns_v4_edit.setPlaceholderText("Например: 8.8.4.4")
        custom_dns_layout.addWidget(self.secondary_dns_v4_edit)
        
        layout.addLayout(custom_dns_layout)
        
        # Группируем радиокнопки
        self.dns_v4_button_group = QButtonGroup()
        self.dns_v4_button_group.addButton(self.auto_dns_v4_radio)
        self.dns_v4_button_group.addButton(self.predefined_dns_v4_radio)
        self.dns_v4_button_group.addButton(self.custom_dns_v4_radio)
        
        # По умолчанию выбираем предустановленные DNS
        self.predefined_dns_v4_radio.setChecked(True)
        
        # Применяем стили
        self.auto_dns_v4_radio.setStyleSheet(self.common_style)
        self.predefined_dns_v4_radio.setStyleSheet(self.common_style)
        self.custom_dns_v4_radio.setStyleSheet(self.common_style)
        self.primary_dns_v4_edit.setStyleSheet(self.common_style)
        self.secondary_dns_v4_edit.setStyleSheet(self.common_style)
        
        layout.addStretch()
        self.ipv4_tab.setLayout(layout)

    def init_ipv6_tab(self):
        """Инициализация вкладки IPv6"""
        if not self.ipv6_available:
            return  # Не создаем вкладку если IPv6 недоступен
    
        layout = QVBoxLayout()

        # Информационная панель (заполняется после проверки IPv6)
        self.ipv6_info_label = QLabel("Проверка IPv6 подключения...")
        self.ipv6_info_label.setStyleSheet("padding: 5px; border-radius: 3px;")
        layout.addWidget(self.ipv6_info_label)
        
        # Обновляем информацию когда проверка завершится
        QTimer.singleShot(3000, self.update_ipv6_info)  # Через 3 сек обновляем
                
        # Радиокнопка для автоматических DNS
        self.auto_dns_v6_radio = QRadioButton("Получать адреса DNS-серверов автоматически")
        layout.addWidget(self.auto_dns_v6_radio)
        
        # Радиокнопка для предустановленных DNS
        self.predefined_dns_v6_radio = QRadioButton("Использовать предустановленные DNS-серверы:")
        layout.addWidget(self.predefined_dns_v6_radio)
        
        # Комбобокс для выбора предустановленных DNS
        self.predefined_dns_v6_combo = QComboBox()
        self.predefined_dns_v6_combo.setStyleSheet(self.common_style)
        for name, dns_data in PREDEFINED_DNS.items():
            if dns_data["ipv6"]:  # Добавляем только если есть IPv6 адреса
                self.predefined_dns_v6_combo.addItem(name)
                log(f"DEBUG: Добавлен IPv6 DNS: {name} -> {dns_data['ipv6']}", "DEBUG")
        layout.addWidget(self.predefined_dns_v6_combo)
        
        # Радиокнопка для пользовательских DNS
        self.custom_dns_v6_radio = QRadioButton("Использовать следующие адреса DNS-серверов:")
        layout.addWidget(self.custom_dns_v6_radio)
        
        # Поля для ввода пользовательских DNS
        custom_dns_layout = QHBoxLayout()
        
        custom_dns_layout.addWidget(QLabel("Основной DNS:"))
        self.primary_dns_v6_edit = QLineEdit()
        self.primary_dns_v6_edit.setPlaceholderText("Например: 2001:4860:4860::8888")
        custom_dns_layout.addWidget(self.primary_dns_v6_edit)
        
        custom_dns_layout.addWidget(QLabel("Дополнительный DNS:"))
        self.secondary_dns_v6_edit = QLineEdit()
        self.secondary_dns_v6_edit.setPlaceholderText("Например: 2001:4860:4860::8844")
        custom_dns_layout.addWidget(self.secondary_dns_v6_edit)
        
        layout.addLayout(custom_dns_layout)
        
        # Группируем радиокнопки
        self.dns_v6_button_group = QButtonGroup()
        self.dns_v6_button_group.addButton(self.auto_dns_v6_radio)
        self.dns_v6_button_group.addButton(self.predefined_dns_v6_radio)
        self.dns_v6_button_group.addButton(self.custom_dns_v6_radio)
        
        # По умолчанию выбираем автоматические DNS для IPv6
        self.auto_dns_v6_radio.setChecked(True)
        
        # Применяем стили
        self.auto_dns_v6_radio.setStyleSheet(self.common_style)
        self.predefined_dns_v6_radio.setStyleSheet(self.common_style)
        self.custom_dns_v6_radio.setStyleSheet(self.common_style)
        self.primary_dns_v6_edit.setStyleSheet(self.common_style)
        self.secondary_dns_v6_edit.setStyleSheet(self.common_style)
        
        layout.addStretch()
        self.ipv6_tab.setLayout(layout)

    def update_ipv6_info(self):
        """Обновляет информацию об IPv6 состоянии"""
        if self.ipv6_available is True:
            self.ipv6_info_label.setText("✅ IPv6 подключение доступно")
            self.ipv6_info_label.setStyleSheet("color: green; background-color: #d4edda; padding: 5px; border-radius: 3px;")
        elif self.ipv6_available is False:
            self.ipv6_info_label.setText("⚠ IPv6 подключение недоступно (IPv6 DNS могут не работать)")
            self.ipv6_info_label.setStyleSheet("color: #856404; background-color: #fff3cd; padding: 5px; border-radius: 3px;")
        else:
            self.ipv6_info_label.setText("⏳ Проверка IPv6 подключения...")
            self.ipv6_info_label.setStyleSheet("color: #6c757d; background-color: #f8f9fa; padding: 5px; border-radius: 3px;")

    def toggle_adapter_visibility(self):
        if hasattr(self, 'dns_info'):
            apply_to_all = self.apply_all_check.isChecked()
            self.adapter_group.setVisible(not apply_to_all)

            if apply_to_all:
                if hasattr(self, 'all_adapters') and hasattr(self, 'dns_info'):
                    adapters = self.adapters
                    all_adapters = self.all_adapters

                    if adapters:
                        dns_info_lines = []

                        # ── АКТИВНЫЕ ───────────────────────────────────────────
                        for name, desc in adapters[:3]:
                            clean = _normalize_alias(name)
                            dns_data = self.dns_info.get(clean, {"ipv4": [], "ipv6": []})
                            
                            ipv4_text = ", ".join(dns_data["ipv4"]) if dns_data["ipv4"] else "Автоматически (DHCP)"
                            ipv6_text = ", ".join(dns_data["ipv6"]) if dns_data["ipv6"] else "Автоматически (DHCP)"
                            
                            dns_info_lines.append(f"{name}:")
                            dns_info_lines.append(f"  IPv4: {ipv4_text}")
                            dns_info_lines.append(f"  IPv6: {ipv6_text}")

                        if len(adapters) > 3:
                            dns_info_lines.append(f"...и ещё {len(adapters) - 3} активных адаптеров")

                        # ── ИГНОРИРУЕМЫЕ ──────────────────────────────────────
                        ignored = [(n, d) for n, d in all_adapters
                                if self.dns_manager.should_ignore_adapter(n, d)]

                        if ignored:
                            dns_info_lines.append("\nИгнорируемые адаптеры (настройки не будут применены):")
                            for name, desc in ignored[:2]:
                                clean = _normalize_alias(name)
                                dns_data = self.dns_info.get(clean, {"ipv4": [], "ipv6": []})
                                
                                ipv4_text = ", ".join(dns_data["ipv4"]) if dns_data["ipv4"] else "Автоматически (DHCP)"
                                ipv6_text = ", ".join(dns_data["ipv6"]) if dns_data["ipv6"] else "Автоматически (DHCP)"
                                
                                dns_info_lines.append(f"{name}: IPv4: {ipv4_text}, IPv6: {ipv6_text}")

                            if len(ignored) > 2:
                                dns_info_lines.append(f"...и ещё {len(ignored) - 2} игнорируемых адаптеров")

                        self.current_dns_value.setText("\n".join(dns_info_lines))
                    else:
                        self.current_dns_value.setText("Не найдено подходящих сетевых адаптеров для применения настроек")
                else:
                    self.current_dns_value.setText("Загрузка информации о DNS...")
            else:
                self.update_current_dns()
    
    def refresh_adapters(self):
        """Обновляет список доступных сетевых адаптеров"""
        current_adapter = self.adapter_combo.currentText()
        
        self.adapter_combo.clear()
        
        adapters = getattr(self, 'adapters', self.dns_manager.get_network_adapters())
        
        if not adapters:
            QMessageBox.warning(self, "Предупреждение", "Не найдено активных сетевых адаптеров.")
            return
        
        adapter_names = []
        for name, description in adapters:
            adapter_text = f"{name} ({description})"
            self.adapter_combo.addItem(adapter_text, userData=name)
            adapter_names.append(adapter_text)
        
        if current_adapter in adapter_names:
            self.adapter_combo.setCurrentText(current_adapter)
            
    def update_current_dns(self, force_refresh=False):
        """Обновляет информацию о текущих DNS-серверах для выбранного адаптера"""
        if self.apply_all_check.isChecked():
            return

        if self.adapter_combo.count() == 0:
            self.current_dns_value.setText("Нет доступных адаптеров")
            return

        raw_name = self.adapter_combo.currentData()

        if not raw_name:
            self.current_dns_value.setText("Неизвестный адаптер")
            return

        clean_name = _normalize_alias(raw_name)

        need_refresh = (
            force_refresh
            or not hasattr(self, 'dns_info')
            or clean_name not in self.dns_info
        )

        if need_refresh:
            dns_v4 = self.dns_manager.get_current_dns(raw_name, "IPv4")
            if self.ipv6_available:
                dns_v6 = self.dns_manager.get_current_dns(raw_name, "IPv6")
            else:
                dns_v6 = []
            
            if not hasattr(self, 'dns_info'):
                self.dns_info = {}
            self.dns_info[clean_name] = {"ipv4": dns_v4, "ipv6": dns_v6}

        # Форматируем вывод
        dns_data = self.dns_info.get(clean_name, {"ipv4": [], "ipv6": []})
        
        lines = []
        if dns_data["ipv4"]:
            lines.append(f"IPv4: {', '.join(dns_data['ipv4'])}")
        else:
            lines.append("IPv4: Автоматически (DHCP)")
            
        if self.ipv6_available:
            if dns_data["ipv6"]:
                lines.append(f"IPv6: {', '.join(dns_data['ipv6'])}")
            else:
                lines.append("IPv6: Автоматически (DHCP)")
        else:
            lines.append("IPv6: Недоступен")
            
        self.current_dns_value.setText("\n".join(lines))

    def apply_dns_settings(self):
        """Упрощенная логика применения DNS"""
        
        # Новая первая проверка:
        if getattr(self, 'force_dns_active', False):
            QMessageBox.warning(
                self,
                "Принудительный DNS активен",
                "Отключите опцию «Принудительный DNS» перед тем, как менять DNS-серверы."
            )
            return
        
        # Получаем адаптеры
        adapters = []
        if self.apply_all_check.isChecked():
            adapters = [name for name, desc in self.adapters]
            log(f"DEBUG: Применяем ко всем адаптерам: {adapters}", "DEBUG")
        else:
            if self.adapter_combo.count() == 0:
                QMessageBox.warning(self, "Ошибка", "Нет доступных сетевых адаптеров.")
                return
            adapter_name = self.adapter_combo.currentData()
            if not adapter_name:
                QMessageBox.warning(self, "Ошибка", "Выберите сетевой адаптер.")
                return
            adapters.append(adapter_name)
            log(f"DEBUG: Применяем к адаптеру: {adapter_name}", "DEBUG")
        
        success_count = 0
        error_messages = []
        
        for adapter_name in adapters:
            log(f"DEBUG: Обрабатываем адаптер '{adapter_name}'", "DEBUG")
            
            # Логируем текущие DNS
            current_v4 = self.dns_manager.get_current_dns(adapter_name, "IPv4")
            if self.ipv6_available:
                current_v6 = self.dns_manager.get_current_dns(adapter_name, "IPv6")
                log(f"DEBUG: Текущие DNS для '{adapter_name}' - IPv4: {current_v4}, IPv6: {current_v6}", "DEBUG")
            else:
                log(f"DEBUG: Текущие DNS для '{adapter_name}' - IPv4: {current_v4}, IPv6: пропущено (недоступно)", "DEBUG")
            
            ipv4_success = True
            ipv6_success = True
            
            # ========== IPv4 ==========
            if self.auto_dns_v4_radio.isChecked():
                log(f"DEBUG: Устанавливаем автоматический IPv4 DNS для '{adapter_name}'", "DEBUG")
                success, message = self.dns_manager.set_auto_dns(adapter_name, "IPv4")
                ipv4_success = success
                log(f"DEBUG: Результат автоматического IPv4: {success}, {message}", "DEBUG")
            elif self.predefined_dns_v4_radio.isChecked():
                predefined_name = self.predefined_dns_v4_combo.currentText()
                log(f"DEBUG: Устанавливаем предустановленный IPv4 DNS '{predefined_name}' для '{adapter_name}'", "DEBUG")
                dns_servers = PREDEFINED_DNS[predefined_name]["ipv4"]
                log(f"DEBUG: IPv4 серверы: {dns_servers}", "DEBUG")
                
                primary = dns_servers[0] if len(dns_servers) > 0 else None
                secondary = dns_servers[1] if len(dns_servers) > 1 else None
                
                if primary:
                    success, message = self.dns_manager.set_custom_dns(adapter_name, primary, secondary, "IPv4")
                    ipv4_success = success
                    log(f"DEBUG: Результат предустановленного IPv4: {success}, {message}", "DEBUG")
            elif self.custom_dns_v4_radio.isChecked():
                primary = self.primary_dns_v4_edit.text().strip()
                secondary = self.secondary_dns_v4_edit.text().strip() or None
                log(f"DEBUG: Устанавливаем пользовательский IPv4 DNS для '{adapter_name}': {primary}, {secondary}", "DEBUG")
                
                if not primary:
                    error_messages.append(f"{adapter_name}: Необходимо указать основной IPv4 DNS-сервер.")
                    continue
                
                success, message = self.dns_manager.set_custom_dns(adapter_name, primary, secondary, "IPv4")
                ipv4_success = success
                log(f"DEBUG: Результат пользовательского IPv4: {success}, {message}", "DEBUG")
            
            # ========== IPv6 (только если доступен) ==========
            if self.ipv6_available:
                if self.auto_dns_v6_radio.isChecked():
                    log(f"DEBUG: Устанавливаем автоматический IPv6 DNS для '{adapter_name}'", "DEBUG")
                    success, message = self.dns_manager.set_auto_dns(adapter_name, "IPv6")
                    ipv6_success = success
                    log(f"DEBUG: Результат автоматического IPv6: {success}, {message}", "DEBUG")
                elif self.predefined_dns_v6_radio.isChecked():
                    predefined_name = self.predefined_dns_v6_combo.currentText()
                    log(f"DEBUG: Устанавливаем предустановленный IPv6 DNS '{predefined_name}' для '{adapter_name}'", "DEBUG")
                    dns_servers = PREDEFINED_DNS[predefined_name]["ipv6"]
                    log(f"DEBUG: IPv6 серверы: {dns_servers}", "DEBUG")
                    
                    primary = dns_servers[0] if len(dns_servers) > 0 else None
                    secondary = dns_servers[1] if len(dns_servers) > 1 else None
                    
                    if primary:
                        success, message = self.dns_manager.set_custom_dns(adapter_name, primary, secondary, "IPv6")
                        ipv6_success = success
                        log(f"DEBUG: Результат предустановленного IPv6: {success}, {message}", "DEBUG")
                elif self.custom_dns_v6_radio.isChecked():
                    primary = self.primary_dns_v6_edit.text().strip()
                    secondary = self.secondary_dns_v6_edit.text().strip() or None
                    log(f"DEBUG: Устанавливаем пользовательский IPv6 DNS для '{adapter_name}': {primary}, {secondary}", "DEBUG")
                    
                    if primary:
                        success, message = self.dns_manager.set_custom_dns(adapter_name, primary, secondary, "IPv6")
                        ipv6_success = success
                        log(f"DEBUG: Результат пользовательского IPv6: {success}, {message}", "DEBUG")
            else:
                log(f"DEBUG: IPv6 настройки пропущены для '{adapter_name}' (IPv6 недоступен)", "DEBUG")
            
            # Подсчет успехов
            if ipv4_success and ipv6_success:
                success_count += 1
            else:
                if not ipv4_success:
                    error_messages.append(f"{adapter_name}: Ошибка IPv4 - {message}")
                if not ipv6_success and self.ipv6_available:
                    error_messages.append(f"{adapter_name}: Ошибка IPv6 - {message}")
        
        # Обновляем интерфейс
        if success_count > 0:
            self.dns_manager.flush_dns_cache()
            QApplication.processEvents()
            
            # Обновляем кэш
            all_adapter_names = [_normalize_alias(name) for name, _ in self.all_adapters]
            self.dns_info = self.dns_manager.get_all_dns_info_fast(all_adapter_names)
            
            if self.apply_all_check.isChecked():
                self.toggle_adapter_visibility()
            else:
                self.update_current_dns(force_refresh=True)
        
        # Результат
        if success_count == len(adapters):
            message = f"Настройки DNS успешно применены для {success_count} адаптера(ов)."
            if not self.ipv6_available:
                message += "\n(IPv6 настройки пропущены - IPv6 недоступен)"
            QMessageBox.information(self, "Успех", message)
            self.accept()
        elif success_count > 0:
            QMessageBox.warning(self, "Частичный успех", 
                            f"Настройки применены для {success_count} из {len(adapters)} адаптера(ов).\n\n"
                            f"Ошибки:\n{chr(10).join(error_messages)}")
        else:
            QMessageBox.critical(self, "Ошибка", 
                            f"Не удалось применить настройки DNS ни к одному из адаптеров.\n\n"
                            f"Ошибки:\n{chr(10).join(error_messages)}")

    def _apply_dns_settings_internal(self):
        """Применяет выбранные настройки DNS для IPv4 и IPv6"""
        
        # Проверяем и отключаем принудительный DNS
        try:
            force_mgr = DNSForceManager()
            if force_mgr.is_force_dns_enabled():
                force_mgr.set_force_dns_enabled(False)
                log("⚠ Принудительный DNS отключен на время изменения настроек", "DEBUG")
        except Exception as e:
            log(f"Ошибка отключения принудительного DNS: {e}", "DEBUG")
        
        # Получаем выбранные адаптеры
        adapters = []
        if self.apply_all_check.isChecked():
            adapters = [name for name, desc in self.adapters]
            log(f"DEBUG: Применяем ко всем адаптерам: {adapters}", "DEBUG")
        else:
            if self.adapter_combo.count() == 0:
                QMessageBox.warning(self, "Ошибка", "Нет доступных сетевых адаптеров.")
                return
                
            adapter_name = self.adapter_combo.currentData()
            if not adapter_name:
                QMessageBox.warning(self, "Ошибка", "Выберите сетевой адаптер.")
                return
                
            adapters.append(adapter_name)
            log(f"DEBUG: Применяем к адаптеру: {adapter_name}", "DEBUG")
        
        success_count = 0
        error_messages = []
        
        for adapter_name in adapters:
            log(f"DEBUG: Обрабатываем адаптер '{adapter_name}'", "DEBUG")
            
            # Проверяем текущие DNS ПЕРЕД изменением
            current_v4 = self.dns_manager.get_current_dns(adapter_name, "IPv4")
            current_v6 = self.dns_manager.get_current_dns(adapter_name, "IPv6")
            log(f"DEBUG: Текущие DNS для '{adapter_name}' - IPv4: {current_v4}, IPv6: {current_v6}", "DEBUG")
            
            ipv4_success = True
            ipv6_success = True
            
            # ========== ПРИМЕНЯЕМ НАСТРОЙКИ IPv4 ==========
            if self.auto_dns_v4_radio.isChecked():
                log(f"DEBUG: Устанавливаем автоматический IPv4 DNS для '{adapter_name}'", "DEBUG")
                success, message = self.dns_manager.set_auto_dns(adapter_name, "IPv4")
                ipv4_success = success
                log(f"DEBUG: Результат автоматического IPv4: {success}, {message}", "DEBUG")
            elif self.predefined_dns_v4_radio.isChecked():
                predefined_name = self.predefined_dns_v4_combo.currentText()
                log(f"DEBUG: Устанавливаем предустановленный IPv4 DNS '{predefined_name}' для '{adapter_name}'", "DEBUG")
                if predefined_name in PREDEFINED_DNS:
                    dns_servers = PREDEFINED_DNS[predefined_name]["ipv4"]
                    log(f"DEBUG: IPv4 серверы: {dns_servers}", "DEBUG")
                    if len(dns_servers) >= 2:
                        success, message = self.dns_manager.set_custom_dns(adapter_name, dns_servers[0], dns_servers[1], "IPv4")
                    elif len(dns_servers) == 1:
                        success, message = self.dns_manager.set_custom_dns(adapter_name, dns_servers[0], None, "IPv4")
                    else:
                        success = False
                        message = "Нет IPv4 адресов для выбранного DNS сервера"
                    ipv4_success = success
                    log(f"DEBUG: Результат предустановленного IPv4: {success}, {message}", "DEBUG")
            elif self.custom_dns_v4_radio.isChecked():
                primary = self.primary_dns_v4_edit.text().strip()
                secondary = self.secondary_dns_v4_edit.text().strip()
                log(f"DEBUG: Устанавливаем пользовательский IPv4 DNS для '{adapter_name}': {primary}, {secondary}", "DEBUG")
                
                if not primary:
                    error_messages.append(f"{adapter_name}: Необходимо указать основной IPv4 DNS-сервер.")
                    continue
                
                success, message = self.dns_manager.set_custom_dns(adapter_name, primary, secondary if secondary else None, "IPv4")
                ipv4_success = success
                log(f"DEBUG: Результат пользовательского IPv4: {success}, {message}", "DEBUG")
            
            # ========== ПРИМЕНЯЕМ НАСТРОЙКИ IPv6 ==========
            log(f"DEBUG: Проверяем состояние IPv6 радиокнопок:", "DEBUG")
            log(f"DEBUG: auto_dns_v6_radio.isChecked() = {self.auto_dns_v6_radio.isChecked()}", "DEBUG")
            log(f"DEBUG: predefined_dns_v6_radio.isChecked() = {self.predefined_dns_v6_radio.isChecked()}", "DEBUG")
            log(f"DEBUG: custom_dns_v6_radio.isChecked() = {self.custom_dns_v6_radio.isChecked()}", "DEBUG")

            if self.auto_dns_v6_radio.isChecked():
                log(f"DEBUG: Устанавливаем автоматический IPv6 DNS для '{adapter_name}'", "DEBUG")
                success, message = self.dns_manager.set_auto_dns(adapter_name, "IPv6")
                ipv6_success = success
                log(f"DEBUG: Результат автоматического IPv6: {success}, {message}", "DEBUG")
            elif self.predefined_dns_v6_radio.isChecked():
                predefined_name = self.predefined_dns_v6_combo.currentText()
                log(f"DEBUG: Устанавливаем предустановленный IPv6 DNS '{predefined_name}' для '{adapter_name}'", "DEBUG")
                if predefined_name in PREDEFINED_DNS:
                    dns_servers = PREDEFINED_DNS[predefined_name]["ipv6"]
                    log(f"DEBUG: IPv6 серверы: {dns_servers}", "DEBUG")
                    if len(dns_servers) >= 2:
                        success, message = self.dns_manager.set_custom_dns(adapter_name, dns_servers[0], dns_servers[1], "IPv6")
                    elif len(dns_servers) == 1:
                        success, message = self.dns_manager.set_custom_dns(adapter_name, dns_servers[0], None, "IPv6")
                    else:
                        success = False
                        message = "Нет IPv6 адресов для выбранного DNS сервера"
                    ipv6_success = success
                    log(f"DEBUG: Результат предустановленного IPv6: {success}, {message}", "DEBUG")
            elif self.custom_dns_v6_radio.isChecked():
                primary = self.primary_dns_v6_edit.text().strip()
                secondary = self.secondary_dns_v6_edit.text().strip()
                log(f"DEBUG: Устанавливаем пользовательский IPv6 DNS для '{adapter_name}': {primary}, {secondary}", "DEBUG")
                
                if primary:  # IPv6 может быть не настроен, поэтому не требуем обязательно
                    success, message = self.dns_manager.set_custom_dns(adapter_name, primary, secondary if secondary else None, "IPv6")
                    ipv6_success = success
                    log(f"DEBUG: Результат пользовательского IPv6: {success}, {message}", "DEBUG")
            elif self.custom_dns_v6_radio.isChecked():
                primary = self.primary_dns_v6_edit.text().strip()
                secondary = self.secondary_dns_v6_edit.text().strip()
                log(f"DEBUG: Устанавливаем пользовательский IPv6 DNS для '{adapter_name}': {primary}, {secondary}", "DEBUG")
                
                if primary:  # IPv6 может быть не настроен, поэтому не требуем обязательно
                    success, message = self.dns_manager.set_custom_dns(adapter_name, primary, secondary if secondary else None, "IPv6")
                    ipv6_success = success
                    log(f"DEBUG: Результат пользовательского IPv6: {success}, {message}", "DEBUG")
            
            # ========== ПРОВЕРКА РЕЗУЛЬТАТОВ ==========
            import time
            time.sleep(1)
            
            # Проверяем IPv4
            immediate_v4 = self.dns_manager.get_current_dns(adapter_name, "IPv4")
            log(f"DEBUG: НЕМЕДЛЕННАЯ проверка IPv4 для '{adapter_name}': {immediate_v4}", "DEBUG")
            
            # Проверяем IPv6
            immediate_v6 = self.dns_manager.get_current_dns(adapter_name, "IPv6")
            log(f"DEBUG: НЕМЕДЛЕННАЯ проверка IPv6 для '{adapter_name}': {immediate_v6}", "DEBUG")
            
            time.sleep(2)
            
            delayed_v4 = self.dns_manager.get_current_dns(adapter_name, "IPv4")
            delayed_v6 = self.dns_manager.get_current_dns(adapter_name, "IPv6")
            log(f"DEBUG: ОТЛОЖЕННАЯ проверка IPv4 для '{adapter_name}': {delayed_v4}", "DEBUG")
            log(f"DEBUG: ОТЛОЖЕННАЯ проверка IPv6 для '{adapter_name}': {delayed_v6}", "DEBUG")
            
            if immediate_v4 != delayed_v4:
                log(f"⚠ WARNING: IPv4 DNS были изменены внешним процессом! Было: {immediate_v4}, стало: {delayed_v4}", "WARNING")
            
            if immediate_v6 != delayed_v6:
                log(f"⚠ WARNING: IPv6 DNS были изменены внешним процессом! Было: {immediate_v6}, стало: {delayed_v6}", "WARNING")
            
            if ipv4_success and ipv6_success:
                success_count += 1
            else:
                if not ipv4_success:
                    error_messages.append(f"{adapter_name}: Ошибка IPv4 - {message}")
                if not ipv6_success:
                    error_messages.append(f"{adapter_name}: Ошибка IPv6 - {message}")

        # ========== ОБНОВЛЯЕМ ИНТЕРФЕЙС ==========
        if success_count > 0:
            # Очищаем DNS кэш системы
            dns_flush_success, dns_flush_message = self.dns_manager.flush_dns_cache()
            if not dns_flush_success:
                log(f"Предупреждение: {dns_flush_message}", level="DNS")
            
            # Даем время системе применить настройки
            QApplication.processEvents()
            import time
            time.sleep(0.5)
            
            # Обновляем наш кэш с актуальными данными
            all_adapter_names = [_normalize_alias(name) for name, _ in self.all_adapters]
            self.dns_info = self.dns_manager.get_all_dns_info_fast(all_adapter_names)
            
            # Перерисовываем интерфейс с новыми данными
            if self.apply_all_check.isChecked():
                self.toggle_adapter_visibility()
            else:
                self.update_current_dns(force_refresh=True)
        
        # ========== ВЫВОДИМ РЕЗУЛЬТАТ ==========
        if success_count == len(adapters):
            message = f"Настройки DNS успешно применены для {success_count} адаптера(ов)."
            if success_count > 0:
                message += "\nКэш DNS очищен для ускорения применения настроек."
            QMessageBox.information(self, "Успех", message)
            self.accept()
        elif success_count > 0:
            QMessageBox.warning(self, "Частичный успех", 
                            f"Настройки DNS применены для {success_count} из {len(adapters)} адаптера(ов).\n"
                            f"Кэш DNS очищен для ускорения применения настроек.\n\n"
                            f"Ошибки:\n{chr(10).join(error_messages)}")
        else:
            QMessageBox.critical(self, "Ошибка", 
                            f"Не удалось применить настройки DNS ни к одному из адаптеров.\n\n"
                            f"Ошибки:\n{chr(10).join(error_messages)}")