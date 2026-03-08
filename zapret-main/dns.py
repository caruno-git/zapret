# dns.py
 
import os
import subprocess
import threading
from PyQt6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                            QPushButton, QRadioButton, QLineEdit, QMessageBox,
                            QGroupBox, QButtonGroup, QApplication, QCheckBox, QProgressBar)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from log import log

from typing import List, Tuple, Dict
import json

IGNORED_ADAPTERS = [
    "VMware", "VirtualBox", "Hyper-V", "WSL", "vEthernet", 
    "Bluetooth", "Loopback", "Pseudo", "Miniport", 
    "Virtual", "VPN", "TAP"
]

# Предопределенные DNS-серверы (название: [IPv4 Primary, IPv4 Secondary])
PREDEFINED_DNS = {
    "Quad9": ["9.9.9.9", "149.112.112.112"],
    "Quad9 ECS": ["9.9.9.11", "149.112.112.11"],
    "Quad9 No Malware blocking": ["9.9.9.10", "149.112.112.10"],
    "Xbox DNS": ["176.99.11.77", "80.78.247.254"],
    "Google": ["8.8.8.8", "8.8.4.4"],
    "Dns.SB": ["185.222.222.222", "45.11.45.11"],
    "OpenDNS": ["208.67.222.222", "208.67.220.220"],
    "AdGuard": ["94.140.14.14", "94.140.15.15"]
    #"Cloudflare": ["1.1.1.1", "1.0.0.1"],
    #"Яндекс.DNS": ["77.88.8.8", "77.88.8.1"],
    #"Яндекс.DNS Безопасный": ["77.88.8.88", "77.88.8.2"],
    #"Яндекс.DNS Семейный": ["77.88.8.7", "77.88.8.3"],
}

class DNSManager:
    """Класс для управления DNS настройками в Windows"""
    
    def __init__(self):
        # Кэшируем WMI соединение
        try:
            import wmi
            self.wmi_conn = wmi.WMI()
        except Exception:
            self.wmi_conn = None

    @staticmethod
    def should_ignore_adapter(name, description):
        """Проверяет, должен ли адаптер быть проигнорирован"""
        # Проверяем и имя, и описание адаптера
        for pattern in IGNORED_ADAPTERS:
            if (pattern.lower() in name.lower() or 
                pattern.lower() in description.lower()):
                return True
        return False

    @staticmethod
    def get_network_adapters_fast(include_ignored=False) -> List[Tuple[str, str]]:
        """Быстрое получение сетевых адаптеров через WMI"""
        try:
            # Используем WMI напрямую - в 5-10 раз быстрее PowerShell
            import wmi
            c = wmi.WMI()
            
            adapters = []
            # Получаем только активные адаптеры одним запросом
            for adapter in c.Win32_NetworkAdapter(NetConnectionStatus=2):  # 2 = Connected
                if adapter.NetConnectionID and adapter.Description:
                    name = adapter.NetConnectionID
                    description = adapter.Description
                    
                    # Фильтруем игнорируемые адаптеры
                    if include_ignored or not DNSManager.should_ignore_adapter(name, description):
                        adapters.append((name, description))
            
            return adapters
            
        except ImportError:
            # Fallback к PowerShell если WMI недоступен
            return DNSManager.get_network_adapters_powershell_fallback(include_ignored)
        except Exception as e:
            log(f"Ошибка WMI, используем fallback: {e}", "DEBUG")
            return DNSManager.get_network_adapters_powershell_fallback(include_ignored)
    

    @staticmethod
    def get_network_adapters_powershell_fallback(include_ignored=False):
        """Fallback через PowerShell с оптимизациями"""
        try:
            # Оптимизированная PowerShell команда - без лишних вызовов
            command = [
                'powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command',
                'Get-NetAdapter | Where-Object {$_.Status -eq "Up"} | Select-Object Name,InterfaceDescription | ConvertTo-Json'
            ]
            
            # Используем subprocess с оптимизациями
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                timeout=5,  # Добавляем таймаут
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode != 0:
                log(f"PowerShell ошибка: {result.stderr}", "❌ ERROR")
                return []
            
            adapters = []
            adapter_list = json.loads(result.stdout)
            if not isinstance(adapter_list, list):
                adapter_list = [adapter_list]
                
            for adapter in adapter_list:
                name = adapter.get('Name', '')
                description = adapter.get('InterfaceDescription', '')
                
                if include_ignored or not DNSManager.should_ignore_adapter(name, description):
                    adapters.append((name, description))
                    
            return adapters
            
        except subprocess.TimeoutExpired:
            log("Таймаут при получении адаптеров", "❌ ERROR")
            return []
        except Exception as e:
            log(f"Ошибка fallback: {e}", "❌ ERROR")
            return []

    def get_all_dns_info_fast(self, adapter_names: List[str]) -> Dict[str, List[str]]:
        """Быстрое получение DNS для всех адаптеров одним запросом"""
        try:
            if not adapter_names:
                return {}
            
            # Формируем одну PowerShell команду для всех адаптеров
            adapter_list = "','".join(adapter_names)
            command = [
                'powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command',
                f'''
                $adapters = @('{adapter_list}')
                $result = @{{}}
                foreach ($adapter in $adapters) {{
                    try {{
                        $dns = Get-DnsClientServerAddress -InterfaceAlias $adapter -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ServerAddresses
                        $result[$adapter] = if ($dns) {{ $dns }} else {{ @() }}
                    }} catch {{
                        $result[$adapter] = @()
                    }}
                }}
                $result | ConvertTo-Json -Depth 3
                '''
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10,  # Таймаут для всех адаптеров
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode != 0:
                log(f"Ошибка получения DNS: {result.stderr}", "DEBUG")
                return self._get_dns_fallback(adapter_names)
            
            dns_data = json.loads(result.stdout)
            
            # Преобразуем в нужный формат
            dns_info = {}
            for adapter_name in adapter_names:
                dns_list = dns_data.get(adapter_name, [])
                if isinstance(dns_list, str):
                    dns_list = [dns_list]
                elif not isinstance(dns_list, list):
                    dns_list = []
                dns_info[adapter_name] = [ip.strip() for ip in dns_list if ip.strip()]
            
            return dns_info
            
        except subprocess.TimeoutExpired:
            log("Таймаут при получении DNS, используем fallback", "⚠ WARNING")
            return self._get_dns_fallback(adapter_names)
        except Exception as e:
            log(f"Ошибка получения DNS: {e}", "DEBUG")
            return self._get_dns_fallback(adapter_names)

    def _get_dns_fallback(self, adapter_names: List[str]) -> Dict[str, List[str]]:
        """Fallback - получаем DNS по одному адаптеру"""
        dns_info = {}
        for name in adapter_names:
            try:
                dns_servers = self.get_current_dns(name)
                dns_info[name] = dns_servers
            except Exception:
                dns_info[name] = []
        return dns_info
    
    # Обновляем старый метод для совместимости
    @staticmethod
    def get_network_adapters(include_ignored=False):
        """Обратная совместимость"""
        return DNSManager.get_network_adapters_fast(include_ignored)
        
    @staticmethod
    def get_current_dns(adapter_name):
        """Получает текущие DNS-серверы для указанного адаптера"""
        try:
            # Используем PowerShell для получения текущих DNS-серверов
            command = f'powershell -Command "Get-DnsClientServerAddress -InterfaceAlias \'{adapter_name}\' -AddressFamily IPv4 | Select-Object -ExpandProperty ServerAddresses"'
            result = subprocess.run(command, capture_output=True, text=True, shell=True)
            
            if result.returncode != 0:
                log(f"Ошибка получения DNS-серверов: {result.stderr}", level="DNS")
                return []
            
            dns_servers = [ip.strip() for ip in result.stdout.splitlines() if ip.strip()]
            return dns_servers
        except Exception as e:
            log(f"Ошибка при получении DNS-серверов: {str(e)}", level="DNS")
            return []
    
    @staticmethod
    def set_custom_dns(adapter_name, primary_dns, secondary_dns=None):
        """Устанавливает пользовательские DNS-серверы для указанного адаптера"""
        try:
            dns_servers = f'"{primary_dns}"'
            if secondary_dns:
                dns_servers = f'"{primary_dns}","{secondary_dns}"'
            
            # Экранируем имя адаптера для безопасного использования в PowerShell
            adapter_name_escaped = adapter_name.replace("'", "''")
            
            # Используем -ExecutionPolicy Bypass для обхода возможных ограничений политик
            command = f'powershell -ExecutionPolicy Bypass -Command "$ErrorActionPreference = \'Stop\'; try {{ Set-DnsClientServerAddress -InterfaceAlias \'{adapter_name_escaped}\' -ServerAddresses {dns_servers} }} catch {{ $_.Exception.Message }}"'
            
            # Запускаем с явным указанием кодировки
            result = subprocess.run(command, capture_output=True, text=True, shell=True, encoding='utf-8')
            
            # Проверяем результат выполнения
            if result.returncode != 0 or result.stderr or (result.stdout and "Exception" in result.stdout):
                error_msg = result.stderr if result.stderr else result.stdout
                log(f"Ошибка установки DNS-серверов: {error_msg}", level="DNS")
                return False, f"Ошибка установки DNS-серверов: {error_msg}"
            
            return True, f"DNS-серверы успешно установлены для {adapter_name}"
        except Exception as e:
            error_msg = str(e)
            log(f"Исключение при установке DNS-серверов: {error_msg}", level="DNS")
            return False, f"Ошибка при установке DNS-серверов: {error_msg}"
    
    @staticmethod
    def set_auto_dns(adapter_name):
        """Устанавливает автоматическое получение DNS-серверов для указанного адаптера"""
        try:
            # Экранируем имя адаптера для безопасного использования в PowerShell
            adapter_name_escaped = adapter_name.replace("'", "''")
            
            # Используем -ExecutionPolicy Bypass и перехват ошибок
            command = f'powershell -ExecutionPolicy Bypass -Command "$ErrorActionPreference = \'Stop\'; try {{ Set-DnsClientServerAddress -InterfaceAlias \'{adapter_name_escaped}\' -ResetServerAddresses }} catch {{ $_.Exception.Message }}"'
            
            # Запускаем с явным указанием кодировки
            result = subprocess.run(command, capture_output=True, text=True, shell=True, encoding='utf-8')
            
            # Проверяем результат выполнения
            if result.returncode != 0 or result.stderr or (result.stdout and "Exception" in result.stdout):
                error_msg = result.stderr if result.stderr else result.stdout
                log(f"Ошибка сброса DNS-серверов: {error_msg}", level="DNS")
                return False, f"Ошибка сброса DNS-серверов: {error_msg}"
            
            return True, f"DNS-серверы сброшены на автоматические для {adapter_name}"
        except Exception as e:
            error_msg = str(e)
            log(f"Исключение при сбросе DNS-серверов: {error_msg}", level="DNS")
            return False, f"Ошибка при сбросе DNS-серверов: {error_msg}"
        
    @staticmethod
    def flush_dns_cache():
        """Очищает кэш DNS для быстрого применения новых настроек"""
        try:
            # Используем команду ipconfig /flushdns
            command = 'ipconfig /flushdns'
            result = subprocess.run(command, capture_output=True, text=True, shell=True)
            
            if result.returncode != 0:
                log(f"Ошибка при очистке кэша DNS: {result.stderr}", level="DNS")
                return False, f"Ошибка при очистке кэша DNS: {result.stderr}"
            
            return True, "Кэш DNS успешно очищен"
        except Exception as e:
            log(f"Ошибка при очистке кэша DNS: {str(e)}", level="DNS")
            return False, f"Ошибка при очистке кэша DNS: {str(e)}"
    
class DNSSettingsDialog(QDialog):
    # Добавляем сигналы для уведомления о завершении загрузки
    adapters_loaded = pyqtSignal(list)
    dns_info_loaded = pyqtSignal(dict)
    
    def __init__(self, parent=None, common_style=None):
        super().__init__(parent)
        self.setWindowTitle("Настройка DNS-серверов")
        self.setMinimumWidth(500)
        self.dns_manager = DNSManager()
        
        # Сохраняем переданный стиль или используем стандартный
        self.common_style = common_style or "color: #333;"
        
        # Сначала создаем базовый интерфейс с индикатором загрузки
        self.init_loading_ui()
        
        # Запускаем загрузку данных в отдельном потоке
        self.load_data_thread = threading.Thread(target=self.load_data_in_background)
        self.load_data_thread.daemon = True
        self.load_data_thread.start()
    
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
            # 1. Быстро получаем все адаптеры (WMI)
            all_adapters = self.dns_manager.get_network_adapters_fast(include_ignored=True)
            filtered_adapters = [(name, desc) for name, desc in all_adapters 
                            if not self.dns_manager.should_ignore_adapter(name, desc)]
            
            self.all_adapters = all_adapters
            self.adapters = filtered_adapters
            self.adapters_loaded.emit(filtered_adapters)
            
            # 2. Быстро получаем DNS для всех адаптеров ОДНИМ запросом
            adapter_names = [name for name, _ in all_adapters]
            dns_info = self.dns_manager.get_all_dns_info_fast(adapter_names)
            
            self.dns_info_loaded.emit(dns_info)
            
        except Exception as e:
            log(f"Ошибка при быстрой загрузке данных: {str(e)}", level="❌ ERROR")
            # Fallback к старому методу
            self._load_data_slow_fallback()

    def _load_data_slow_fallback(self):
        """Fallback к старому медленному методу"""
        try:
            all_adapters = DNSManager.get_network_adapters_powershell_fallback(include_ignored=True)
            filtered_adapters = [(name, desc) for name, desc in all_adapters 
                            if not DNSManager.should_ignore_adapter(name, desc)]
            
            self.all_adapters = all_adapters
            self.adapters = filtered_adapters
            self.adapters_loaded.emit(filtered_adapters)
            
            # DNS по одному адаптеру (медленно)
            dns_info = {}
            for name, _ in all_adapters:
                dns_servers = DNSManager().get_current_dns(name)
                dns_info[name] = dns_servers
            
            self.dns_info_loaded.emit(dns_info)
        except Exception as e:
            log(f"Критическая ошибка загрузки DNS данных: {e}", "❌ ERROR")

    def on_adapters_loaded(self, adapters):
        """Обработчик загрузки списка адаптеров"""
        self.adapters = adapters
        # Данные могут прийти в любом порядке, поэтому проверяем, 
        # загружена ли уже информация о DNS
        if hasattr(self, 'dns_info'):
            self.init_full_ui()
    
    def on_dns_info_loaded(self, dns_info):
        """Обработчик загрузки информации о DNS"""
        self.dns_info = dns_info
        # Данные могут прийти в любом порядке, поэтому проверяем, 
        # загружен ли уже список адаптеров
        if hasattr(self, 'adapters'):
            self.init_full_ui()
    
    def init_full_ui(self):
        """Инициализация полного интерфейса после загрузки данных"""
        # Удаляем текущий интерфейс загрузки
        QWidget().setLayout(self.layout())

        self.init_ui()

    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        
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
        
        # Флажок для применения ко всем адаптерам - устанавливаем True по умолчанию
        self.apply_all_check = QCheckBox("Применить настройки ко всем сетевым адаптерам")
        self.apply_all_check.setChecked(True)  # Устанавливаем галочку по умолчанию
        self.apply_all_check.stateChanged.connect(self.toggle_adapter_visibility)
        layout.addWidget(self.apply_all_check)
        
        # Группа для выбора DNS
        dns_group = QGroupBox("Настройки DNS")
        dns_layout = QVBoxLayout()
        
        # Радиокнопка для автоматических DNS
        self.auto_dns_radio = QRadioButton("Получать адреса DNS-серверов автоматически")
        dns_layout.addWidget(self.auto_dns_radio)
        
        # Радиокнопка для предустановленных DNS
        self.predefined_dns_radio = QRadioButton("Использовать предустановленные DNS-серверы:")
        dns_layout.addWidget(self.predefined_dns_radio)
        
        # Комбобокс для выбора предустановленных DNS
        self.predefined_dns_combo = QComboBox()
        self.predefined_dns_combo.setStyleSheet(self.common_style)
        self.predefined_dns_combo.addItems(PREDEFINED_DNS.keys())
        dns_layout.addWidget(self.predefined_dns_combo)
        
        # Радиокнопка для пользовательских DNS
        self.custom_dns_radio = QRadioButton("Использовать следующие адреса DNS-серверов:")
        dns_layout.addWidget(self.custom_dns_radio)
        
        # Поля для ввода пользовательских DNS
        custom_dns_layout = QHBoxLayout()
        
        custom_dns_layout.addWidget(QLabel("Основной DNS:"))
        self.primary_dns_edit = QLineEdit()
        self.primary_dns_edit.setPlaceholderText("Например: 8.8.8.8")
        custom_dns_layout.addWidget(self.primary_dns_edit)
        
        custom_dns_layout.addWidget(QLabel("Дополнительный DNS:"))
        self.secondary_dns_edit = QLineEdit()
        self.secondary_dns_edit.setPlaceholderText("Например: 8.8.4.4")
        custom_dns_layout.addWidget(self.secondary_dns_edit)
        
        dns_layout.addLayout(custom_dns_layout)
        
        # Группируем радиокнопки
        self.dns_button_group = QButtonGroup()
        self.dns_button_group.addButton(self.auto_dns_radio)
        self.dns_button_group.addButton(self.predefined_dns_radio)
        self.dns_button_group.addButton(self.custom_dns_radio)
        
        # По умолчанию выбираем предустановленные DNS
        self.predefined_dns_radio.setChecked(True)
        
        dns_group.setLayout(dns_layout)
        layout.addWidget(dns_group)
        
        # Отображение текущих DNS-серверов
        current_dns_label = QLabel("Текущие DNS-серверы:")
        layout.addWidget(current_dns_label)
        
        self.current_dns_value = QLabel()
        self.current_dns_value.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.current_dns_value)
        
        # Кнопки ОК и Отмена
        buttons_layout = QHBoxLayout()
        
        apply_button = QPushButton("Применить")
        apply_button.clicked.connect(self.apply_dns_settings)
        buttons_layout.addWidget(apply_button)
        
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        
        # Подключаем обработчик изменения выбранного адаптера
        self.adapter_combo.currentIndexChanged.connect(self.update_current_dns)
        
        # Обновляем информацию о текущих DNS
        self.update_current_dns()
        
        # Применяем начальное состояние видимости адаптера
        self.toggle_adapter_visibility()

        # Применяем стиль к тексту в интерфейсе
        self.adapter_group.setStyleSheet(self.common_style)
        dns_group.setStyleSheet(self.common_style)
        current_dns_label.setStyleSheet(self.common_style)
        self.auto_dns_radio.setStyleSheet(self.common_style)
        self.predefined_dns_radio.setStyleSheet(self.common_style)
        self.custom_dns_radio.setStyleSheet(self.common_style)
        self.apply_all_check.setStyleSheet(self.common_style)

        # Стиль для полей ввода
        self.primary_dns_edit.setStyleSheet(self.common_style)
        self.secondary_dns_edit.setStyleSheet(self.common_style)

    def toggle_adapter_visibility(self):
        """Скрывает или показывает выбор адаптера в зависимости от состояния галочки"""
        apply_to_all = self.apply_all_check.isChecked()
        self.adapter_group.setVisible(not apply_to_all)
        
        # Если галочка установлена, обновляем статус текущих DNS всех адаптеров
        if apply_to_all:
            # Используем кэшированные данные, если доступны
            if hasattr(self, 'all_adapters') and hasattr(self, 'dns_info'):
                adapters = self.adapters  # Используем только нефильтрованные адаптеры для применения
                all_adapters = self.all_adapters  # Для отображения используем все
                
                if adapters:
                    dns_info = []
                    active_count = len(adapters)
                    
                    # Показываем активные адаптеры, к которым будут применены настройки
                    for name, desc in adapters[:3]:  # Показываем только первые 3 адаптера
                        dns_servers = self.dns_info.get(name, [])
                        dns_text = ", ".join(dns_servers) if dns_servers else "Автоматически (DHCP)"
                        dns_info.append(f"{name}: {dns_text}")
                    
                    if len(adapters) > 3:
                        dns_info.append(f"...и еще {len(adapters) - 3} активных адаптеров")
                    
                    # Показываем игнорируемые адаптеры отдельно
                    ignored_adapters = [(name, desc) for name, desc in all_adapters 
                                    if self.dns_manager.should_ignore_adapter(name, desc)]
                    
                    if ignored_adapters:
                        dns_info.append("\nИгнорируемые адаптеры (настройки не будут применены):")
                        for name, desc in ignored_adapters[:2]:
                            dns_servers = self.dns_info.get(name, [])
                            dns_text = ", ".join(dns_servers) if dns_servers else "Автоматически (DHCP)"
                            dns_info.append(f"{name}: {dns_text}")
                        
                        if len(ignored_adapters) > 2:
                            dns_info.append(f"...и еще {len(ignored_adapters) - 2} игнорируемых адаптеров")
                    
                    self.current_dns_value.setText("\n".join(dns_info))
                else:
                    self.current_dns_value.setText("Не найдено подходящих сетевых адаптеров для применения настроек")
            else:
                self.current_dns_value.setText("Загрузка информации о DNS...")
        else:
            # Если галочка снята, показываем DNS только для выбранного адаптера
            self.update_current_dns()
    
    def refresh_adapters(self):
        """Обновляет список доступных сетевых адаптеров"""
        # Запоминаем текущий выбранный адаптер
        current_adapter = self.adapter_combo.currentText()
        
        # Очищаем список
        self.adapter_combo.clear()
        
        # Используем уже загруженные адаптеры
        adapters = getattr(self, 'adapters', self.dns_manager.get_network_adapters())
        
        if not adapters:
            QMessageBox.warning(self, "Предупреждение", "Не найдено активных сетевых адаптеров.")
            return
        
        # Добавляем адаптеры в комбобокс
        adapter_names = []
        for name, description in adapters:
            adapter_text = f"{name} ({description})"
            self.adapter_combo.addItem(adapter_text, userData=name)
            adapter_names.append(adapter_text)
        
        # Восстанавливаем выбранный адаптер, если он все еще существует
        if current_adapter in adapter_names:
            self.adapter_combo.setCurrentText(current_adapter)
            
    def update_current_dns(self):
        """Обновляет информацию о текущих DNS-серверах"""
        if self.apply_all_check.isChecked():
            # Если галочка установлена, эта функция вызывается из toggle_adapter_visibility
            return
        
        if self.adapter_combo.count() == 0:
            self.current_dns_value.setText("Нет доступных адаптеров")
            return
        
        adapter_name = self.adapter_combo.currentData()
        
        if not adapter_name:
            self.current_dns_value.setText("Неизвестный адаптер")
            return
        
        # Используем кэшированные данные, если доступны
        if hasattr(self, 'dns_info') and adapter_name in self.dns_info:
            dns_servers = self.dns_info[adapter_name]
        else:
            # Или запрашиваем новые
            dns_servers = self.dns_manager.get_current_dns(adapter_name)
        
        if not dns_servers:
            self.current_dns_value.setText("Автоматически (DHCP)")
        else:
            self.current_dns_value.setText(", ".join(dns_servers))
    
    def apply_dns_settings(self):
        """Применяет выбранные настройки DNS"""
        # Получаем выбранные адаптеры
        adapters = []
        if self.apply_all_check.isChecked():
            # Применяем ко всем адаптерам (кроме игнорируемых)
            adapters = [name for name, desc in self.adapters]
        else:
            # Применяем только к выбранному адаптеру
            if self.adapter_combo.count() == 0:
                QMessageBox.warning(self, "Ошибка", "Нет доступных сетевых адаптеров.")
                return
                
            adapter_name = self.adapter_combo.currentData()
            if not adapter_name:
                QMessageBox.warning(self, "Ошибка", "Выберите сетевой адаптер.")
                return
                
            adapters.append(adapter_name)
        
        success_count = 0
        error_messages = []
        
        for adapter_name in adapters:
            # Проверяем, какой тип DNS выбран
            if self.auto_dns_radio.isChecked():
                # Автоматические DNS
                success, message = self.dns_manager.set_auto_dns(adapter_name)
            elif self.predefined_dns_radio.isChecked():
                # Предустановленные DNS
                predefined_name = self.predefined_dns_combo.currentText()
                primary, secondary = PREDEFINED_DNS[predefined_name]
                success, message = self.dns_manager.set_custom_dns(adapter_name, primary, secondary)
            elif self.custom_dns_radio.isChecked():
                # Пользовательские DNS
                primary = self.primary_dns_edit.text().strip()
                secondary = self.secondary_dns_edit.text().strip()
                
                if not primary:
                    QMessageBox.warning(self, "Ошибка", "Необходимо указать основной DNS-сервер.")
                    return
                
                success, message = self.dns_manager.set_custom_dns(adapter_name, primary, secondary if secondary else None)
            else:
                # Не выбран тип DNS (не должно произойти)
                QMessageBox.warning(self, "Ошибка", "Не выбран тип DNS-сервера.")
                return
            
            if success:
                success_count += 1
            else:
                error_messages.append(message)
        
        # Обновляем информацию о текущих DNS
        self.toggle_adapter_visibility()
        
        # Сбрасываем кэш DNS для быстрого применения настроек
        if success_count > 0:
            dns_flush_success, dns_flush_message = self.dns_manager.flush_dns_cache()
            if not dns_flush_success:
                log(f"Предупреждение: {dns_flush_message}", level="DNS")
        
        # Выводим результат
        if success_count == len(adapters):
            message = f"Настройки DNS успешно применены для {success_count} адаптера(ов)."
            if success_count > 0:
                message += "\nКэш DNS очищен для ускорения применения настроек."
            QMessageBox.information(self, "Успех", message)
            self.accept()  # Закрываем диалог
        elif success_count > 0:
            QMessageBox.warning(self, "Частичный успех", 
                            f"Настройки DNS применены для {success_count} из {len(adapters)} адаптера(ов).\n"
                            f"Кэш DNS очищен для ускорения применения настроек.\n\n"
                            f"Ошибки:\n{chr(10).join(error_messages)}")
        else:
            QMessageBox.critical(self, "Ошибка", 
                            f"Не удалось применить настройки DNS ни к одному из адаптеров.\n\n"
                            f"Ошибки:\n{chr(10).join(error_messages)}")
