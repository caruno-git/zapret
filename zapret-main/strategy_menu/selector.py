# strategy_menu/selector.py

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QWidget, QTabWidget, QLabel, QMessageBox, QGroupBox,
                            QTextBrowser, QSizePolicy, QFrame, QScrollArea, 
                            QRadioButton, QButtonGroup, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QFont

from log import log
from config import (get_strategy_launch_method, set_strategy_launch_method,
                   get_direct_strategy_selections, set_direct_strategy_youtube,
                   set_direct_strategy_discord, set_direct_strategy_discord_voice, set_direct_strategy_other,
                   get_game_filter_enabled, set_game_filter_enabled,
                   get_wssize_enabled, set_wssize_enabled)

from .constants import MINIMUM_WIDTH, MINIMIM_HEIGHT
from .widgets import CompactStrategyItem
from .strategy_table_widget import StrategyTableWidget
from .workers import InternetStrategyLoader


class StrategySelector(QDialog):
    """Диалог для выбора стратегии обхода блокировок"""
    
    strategySelected = pyqtSignal(str, str)  # (strategy_id, strategy_name)
    
    def __init__(self, parent=None, strategy_manager=None, current_strategy_name=None):
        super().__init__(parent)
        self.strategy_manager = strategy_manager
        self.current_strategy_name = current_strategy_name
        self.selected_strategy_id = None
        self.selected_strategy_name = None
        
        # Инициализируем атрибуты для комбинированных стратегий
        self._combined_args = None
        self._combined_strategy_data = None
        self.category_selections = {}
        
        self.is_loading_strategies = False
        self.loader_thread = None
        self.loader_worker = None
        
        self.launch_method = get_strategy_launch_method()
        self.is_direct_mode = (self.launch_method == "direct")
        
        self.setWindowTitle("Выбор стратегии")
        self.resize(MINIMUM_WIDTH, MINIMIM_HEIGHT)
        self.setMinimumSize(400, 350)  # Еще меньший минимальный размер
        self.setModal(False)
        
        self.init_ui()
        
        # Инициализация данных
        if self.is_direct_mode:
            self.load_builtin_strategies()
        else:
            self.load_local_strategies()

    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Создаем кнопки управления
        self._create_control_buttons()
        
        # Создаем вкладки
        self._create_tabs()
        
        layout.addWidget(self.tab_widget)
        layout.addWidget(self.buttons_widget)

    def _create_control_buttons(self):
        """Создает кнопки управления"""
        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.setSpacing(10)
        
        self.select_button = QPushButton("✅ Выбрать")
        self.select_button.clicked.connect(self.accept)
        self.select_button.setEnabled(False)
        self.select_button.setMinimumHeight(30)
        self.buttons_layout.addWidget(self.select_button)
        
        self.cancel_button = QPushButton("❌ Отмена")
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setMinimumHeight(30)
        self.buttons_layout.addWidget(self.cancel_button)
        
        self.buttons_widget = QWidget()
        self.buttons_widget.setLayout(self.buttons_layout)

    def _create_tabs(self):
        """Создает вкладки интерфейса"""
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #444;
                background: #2a2a2a;
            }
            QTabBar::tab {
                padding: 5px 10px;
                min-width: 80px;
            }
            QTabBar::tab:selected {
                background: #3a3a3a;
                border-bottom: 2px solid #2196F3;
            }
        """)
        
        # Вкладка стратегий
        self.strategies_tab = QWidget()
        self._init_strategies_tab()
        self.tab_widget.addTab(self.strategies_tab, "📋 Стратегии")
        
        # Хостлисты
        from .hostlists_tab import HostlistsTab
        self.hostlists_tab = HostlistsTab()
        self.hostlists_tab.hostlists_changed.connect(self._on_hostlists_changed)
        self.tab_widget.addTab(self.hostlists_tab, "🌐 Хостлисты")

        # IPsets
        from .ipsets_tab import IpsetsTab
        self.ipsets_tab = IpsetsTab()
        self.ipsets_tab.ipsets_changed.connect(self._on_ipsets_changed)
        self.tab_widget.addTab(self.ipsets_tab, "🔢 Айпсеты")

        # Вкладка настроек
        self.settings_tab = QWidget()
        self._init_settings_tab()
        self.tab_widget.addTab(self.settings_tab, "⚙️ Настройки")
        
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _on_hostlists_changed(self):
        """Обработчик изменения хостлистов"""
        log("Хостлисты изменены, может потребоваться перезапуск DPI", "INFO")

    def _on_ipsets_changed(self):
        """Обработчик изменения IPsets"""
        log("IPsets изменены, может потребоваться перезапуск DPI", "INFO")
        
    def _init_strategies_tab(self):
        """Инициализирует вкладку стратегий"""
        layout = QVBoxLayout(self.strategies_tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        if self.is_direct_mode:
            self._init_direct_mode_ui(layout)
        else:
            self._init_bat_mode_ui(layout)

    def _init_bat_mode_ui(self, layout):
        """Инициализирует интерфейс для BAT режима"""
        # Создаем виджет таблицы стратегий
        self.strategy_table = StrategyTableWidget(self.strategy_manager, self)
        
        # Подключаем сигналы
        self.strategy_table.strategy_selected.connect(self._on_table_strategy_selected)
        self.strategy_table.strategy_double_clicked.connect(self._on_table_strategy_double_clicked)
        self.strategy_table.refresh_button.clicked.connect(self.refresh_strategies)
        self.strategy_table.download_all_button.clicked.connect(self.strategy_table.download_all_strategies_async)
        
        layout.addWidget(self.strategy_table)

    def _init_direct_mode_ui(self, layout):
        """Инициализирует интерфейс для прямого режима"""
        from .strategy_lists_separated import (
            YOUTUBE_STRATEGIES, DISCORD_STRATEGIES, OTHER_STRATEGIES, DISCORD_VOICE_STRATEGIES,
            get_default_selections
        )
        
        # Загружаем сохраненные выборы
        try:
            self.category_selections = get_direct_strategy_selections()
        except Exception as e:
            log(f"Ошибка загрузки выборов: {e}", "⚠ WARNING")
            self.category_selections = get_default_selections()
        
        # Заголовок
        title = QLabel("Выберите стратегию для каждой категории")
        title.setStyleSheet("font-weight: bold; font-size: 10pt; color: #2196F3; margin: 5px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Вкладки категорий
        self.category_tabs = QTabWidget()
        self.category_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.category_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #444;
                background: #2a2a2a;
            }
            QTabBar::tab {
                padding: 4px 8px;
                font-size: 9pt;
            }
        """)
        
        self._add_category_tab("🎬 YouTube", YOUTUBE_STRATEGIES, 'youtube')
        self._add_category_tab("💬 Discord", DISCORD_STRATEGIES, 'discord')
        self._add_category_tab("🔊 Discord Voice", DISCORD_VOICE_STRATEGIES, 'discord_voice')
        self._add_category_tab("🌐 Остальные", OTHER_STRATEGIES, 'other')
        
        layout.addWidget(self.category_tabs, 1)
        
        # Предпросмотр
        self._create_preview_widget(layout)
        
        # Статус
        self.status_label = QLabel("✅ Готово к выбору")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold; color: #4CAF50; font-size: 9pt; padding: 3px;")
        self.status_label.setFixedHeight(25)
        layout.addWidget(self.status_label)
        
        self.update_combined_preview()
        self.select_button.setEnabled(True)

    def _add_category_tab(self, tab_name, strategies, category_key):
        """Добавляет вкладку категории"""
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(5, 5, 5, 5)
        tab_layout.setSpacing(3)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                width: 10px;
                background: #2a2a2a;
            }
            QScrollBar::handle:vertical {
                background: #555;
                border-radius: 5px;
                min-height: 20px;
            }
        """)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        scroll_layout.setSpacing(3)
        
        button_group = QButtonGroup()
        
        for idx, (strat_id, strat_data) in enumerate(strategies.items()):
            strategy_item = CompactStrategyItem(strat_id, strat_data)
            
            if strat_id == self.category_selections.get(category_key):
                strategy_item.set_checked(True)
            
            strategy_item.clicked.connect(
                lambda sid, cat=category_key: self.on_category_selection_changed(cat, sid)
            )
            
            button_group.addButton(strategy_item.radio, idx)
            scroll_layout.addWidget(strategy_item)
        
        setattr(self, f"{category_key}_button_group", button_group)
        
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        tab_layout.addWidget(scroll_area)
        
        self.category_tabs.addTab(tab_widget, tab_name)

    def _create_preview_widget(self, layout):
        """Создает виджет предпросмотра"""
        preview_widget = QFrame()
        preview_widget.setFrameStyle(QFrame.Shape.Box)
        preview_widget.setMaximumHeight(100)
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(5, 5, 5, 5)
        preview_layout.setSpacing(2)
        
        preview_label = QLabel("📋 Итоговая конфигурация:")
        preview_label.setStyleSheet("font-weight: bold; font-size: 9pt;")
        preview_layout.addWidget(preview_label)
        
        self.preview_text = QTextBrowser()
        self.preview_text.setMaximumHeight(60)
        self.preview_text.setStyleSheet("""
            QTextBrowser {
                background: #222;
                border: 1px solid #444;
                font-family: Arial;
                font-size: 8pt;
                color: #aaa;
            }
        """)
        preview_layout.addWidget(self.preview_text)
        
        layout.addWidget(preview_widget, 0)

    def _init_settings_tab(self):
        """Инициализирует вкладку настроек с прокруткой"""
        # Основной layout для вкладки
        tab_layout = QVBoxLayout(self.settings_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # Создаем область прокрутки
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameStyle(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                width: 12px;
                background: #2a2a2a;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #555;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #666;
            }
        """)
        
        # Виджет содержимого для прокрутки
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Заголовок
        title_label = QLabel("Выберите метод запуска стратегий")
        title_font = title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("margin: 5px; color: #2196F3;")
        layout.addWidget(title_label)
        
        # Группа методов запуска
        method_group = QGroupBox("Метод запуска стратегий")
        method_group.setStyleSheet("""
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
        method_layout = QVBoxLayout(method_group)
        
        self.method_button_group = QButtonGroup()
        
        self.bat_method_radio = QRadioButton("Классический метод (через .bat файлы)")
        self.bat_method_radio.setToolTip(
            "Использует .bat файлы для запуска стратегий.\n"
            "Загружает стратегии из интернета.\n"
            "Может показывать окна консоли при запуске."
        )
        self.method_button_group.addButton(self.bat_method_radio, 0)
        method_layout.addWidget(self.bat_method_radio)
        
        self.direct_method_radio = QRadioButton("Прямой запуск (рекомендуется)")
        self.direct_method_radio.setToolTip(
            "Запускает встроенные стратегии напрямую из Python.\n"
            "Не требует интернета, все стратегии включены в программу.\n"
            "Полностью скрытый запуск без окон консоли."
        )
        self.method_button_group.addButton(self.direct_method_radio, 1)
        method_layout.addWidget(self.direct_method_radio)
        
        current_method = get_strategy_launch_method()
        if current_method == "direct":
            self.direct_method_radio.setChecked(True)
        else:
            self.bat_method_radio.setChecked(True)
        
        self.method_button_group.buttonClicked.connect(self._on_method_changed)
        layout.addWidget(method_group)
        
        # Параметры запуска
        self._create_launch_params(layout)
        
        # Информация о методах
        info_group = QGroupBox("Информация")
        info_group.setStyleSheet("""
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
        info_layout = QVBoxLayout(info_group)
        
        info_text = QLabel(
            "• Прямой запуск: использует встроенные стратегии, не требует интернета\n"
            "• Классический метод: загружает стратегии из интернета в виде .bat файлов\n"
            "• При смене метода список стратегий обновится автоматически"
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("padding: 10px; font-weight: normal;")
        info_layout.addWidget(info_text)
        layout.addWidget(info_group)
        
        # Уведомление об автоматическом обновлении
        auto_update_note = QLabel(
            "💡 После любых изменений в этом окне следует ЗАНОВО перезапустить стратегию через кнопку ✅ Выбрать"
        )
        auto_update_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        auto_update_note.setWordWrap(True)
        auto_update_note.setStyleSheet(
            "padding: 8px; background: #2196F3; color: white; "
            "border-radius: 5px; font-weight: bold; margin: 5px;"
        )
        layout.addWidget(auto_update_note)
        
        # Добавляем растяжку в конец
        layout.addStretch()
        
        # Устанавливаем виджет в область прокрутки
        scroll_area.setWidget(scroll_widget)
        
        # Добавляем область прокрутки на вкладку
        tab_layout.addWidget(scroll_area)

    def _create_launch_params(self, layout):
        """Создает параметры запуска"""
        params_group = QGroupBox("Параметры запуска")
        params_group.setStyleSheet("""
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
                color: #ffa500;
            }
        """)
        params_layout = QVBoxLayout(params_group)
        params_layout.setSpacing(8)
        
        # Заголовок с предупреждением
        warning_label = QLabel("⚠️ Перезапустите стратегию после изменения параметров")
        warning_label.setStyleSheet("color: #ffa500; font-weight: bold; font-size: 9pt; margin-bottom: 5px;")
        params_layout.addWidget(warning_label)
        
        # НОВЫЙ ЧЕКБОКС ALLZONE - В САМОМ ВЕРХУ
        allzone_widget = QWidget()
        allzone_layout = QVBoxLayout(allzone_widget)
        allzone_layout.setContentsMargins(0, 0, 0, 0)
        allzone_layout.setSpacing(3)
        
        self.allzone_checkbox = QCheckBox("Применять Zapret ко ВСЕМ сайтам")
        self.allzone_checkbox.setToolTip(
            "Заменяет хостлист other.txt на allzone.txt во всех стратегиях.\n"
            "allzone.txt содержит более полный список доменов.\n"
            "Может увеличить нагрузку на систему."
        )
        self.allzone_checkbox.setStyleSheet("font-weight: bold; color: #2196F3;")
        from config import get_allzone_hostlist_enabled
        self.allzone_checkbox.setChecked(get_allzone_hostlist_enabled())
        self.allzone_checkbox.stateChanged.connect(self._on_allzone_changed)
        allzone_layout.addWidget(self.allzone_checkbox)
        
        allzone_info = QLabel("Использует расширенный список доменов allzone.txt вместо other.txt")
        allzone_info.setWordWrap(True)
        allzone_info.setStyleSheet("padding-left: 20px; color: #aaa; font-size: 8pt;")
        allzone_layout.addWidget(allzone_info)
        
        params_layout.addWidget(allzone_widget)
        params_layout.addWidget(self._create_separator())
        
        game_widget = QWidget()
        game_layout = QVBoxLayout(game_widget)
        game_layout.setContentsMargins(0, 0, 0, 0)
        game_layout.setSpacing(3)
        
        self.ipset_all_checkbox = QCheckBox("Включить фильтр для игр (Game Filter)")
        self.ipset_all_checkbox.setToolTip(
            "Расширяет диапазон портов с 80,443 на 80,443,1024-65535\n"
            "для стратегий с хостлистами other.txt.\n"
            "Полезно для игр и приложений на нестандартных портах."
        )
        self.ipset_all_checkbox.setStyleSheet("font-weight: bold;")
        self.ipset_all_checkbox.setChecked(get_game_filter_enabled())
        self.ipset_all_checkbox.stateChanged.connect(self._on_game_filter_changed)
        game_layout.addWidget(self.ipset_all_checkbox)
        
        ipset_info = QLabel("Расширяет фильтрацию на порты 1024-65535 для игрового трафика")
        ipset_info.setWordWrap(True)
        ipset_info.setStyleSheet("padding-left: 20px; color: #aaa; font-size: 8pt;")
        game_layout.addWidget(ipset_info)
        
        params_layout.addWidget(game_widget)
        params_layout.addWidget(self._create_separator())
        
        # Чекбокс ipset lists
        ipset_widget = QWidget()
        ipset_layout = QVBoxLayout(ipset_widget)
        ipset_layout.setContentsMargins(0, 0, 0, 0)
        ipset_layout.setSpacing(3)
        
        self.ipset_lists_checkbox = QCheckBox("Добавить ipset-all.txt к хостлистам")
        self.ipset_lists_checkbox.setToolTip(
            "Добавляет --ipset=ipset-all.txt после хостлистов\n"
            "other.txt, other2.txt и russia-blacklist.txt.\n"
            "Расширяет список блокируемых IP-адресов."
        )
        self.ipset_lists_checkbox.setStyleSheet("font-weight: bold;")
        from config import get_ipset_lists_enabled
        self.ipset_lists_checkbox.setChecked(get_ipset_lists_enabled())
        self.ipset_lists_checkbox.stateChanged.connect(self._on_ipset_lists_changed)
        ipset_layout.addWidget(self.ipset_lists_checkbox)
        
        ipset_lists_info = QLabel("Добавляет дополнительный список IP-адресов к стратегиям для остальных сайтов")
        ipset_lists_info.setWordWrap(True)
        ipset_lists_info.setStyleSheet("padding-left: 20px; color: #aaa; font-size: 8pt;")
        ipset_layout.addWidget(ipset_lists_info)
        
        params_layout.addWidget(ipset_widget)
        params_layout.addWidget(self._create_separator())
        
        # Чекбокс wssize
        wssize_widget = QWidget()
        wssize_layout = QVBoxLayout(wssize_widget)
        wssize_layout.setContentsMargins(0, 0, 0, 0)
        wssize_layout.setSpacing(3)
        
        self.wssize_checkbox = QCheckBox("Добавить --wssize=1:6 для TCP 443")
        self.wssize_checkbox.setToolTip(
            "Включает параметр --wssize=1:6 для всех TCP соединений на порту 443.\n"
            "Может улучшить обход блокировок на некоторых провайдерах.\n"
            "Влияет на размер окна TCP сегментов."
        )
        self.wssize_checkbox.setStyleSheet("font-weight: bold;")
        self.wssize_checkbox.setChecked(get_wssize_enabled())
        self.wssize_checkbox.stateChanged.connect(self._on_wssize_changed)
        wssize_layout.addWidget(self.wssize_checkbox)
        
        wssize_info = QLabel("Изменяет размер TCP окна для порта 443, может помочь обойти DPI фильтрацию")
        wssize_info.setWordWrap(True)
        wssize_info.setStyleSheet("padding-left: 20px; color: #aaa; font-size: 8pt;")
        wssize_layout.addWidget(wssize_info)
        
        params_layout.addWidget(wssize_widget)
        
        # Место для будущих параметров
        params_layout.addSpacing(10)
        future_params_label = QLabel("Другие параметры будут добавлены в следующих версиях")
        future_params_label.setStyleSheet("color: #666; font-style: italic; padding: 5px; font-size: 8pt;")
        future_params_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        params_layout.addWidget(future_params_label)
        
        layout.addWidget(params_group)

    def _create_separator(self):
        """Создает визуальный разделитель"""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("QFrame { background-color: #444; max-height: 1px; margin: 5px 0; }")
        return separator

    def _on_allzone_changed(self, state):
        """Обработчик изменения allzone.txt"""
        from config import set_allzone_hostlist_enabled
        enabled = (state == Qt.CheckState.Checked.value)
        set_allzone_hostlist_enabled(enabled)
        log(f"Замена other.txt на allzone.txt {'включена' if enabled else 'выключена'}", "INFO")

    def _on_tab_changed(self, index):
        """Обработчик смены вкладок"""
        try:
            if index == 0:  # Стратегии
                self.buttons_widget.setVisible(True)
                if self.is_direct_mode:
                    self.select_button.setEnabled(True)
            elif index == 1:  # Хостлисты
                self.buttons_widget.setVisible(False)
            elif index == 2:  # Настройки
                self.buttons_widget.setVisible(False)
        except Exception as e:
            log(f"Ошибка в _on_tab_changed: {e}", "❌ ERROR")

    def _on_method_changed(self, button):
        """Обработчик изменения метода запуска"""
        old_method = self.launch_method
        
        if button == self.direct_method_radio:
            set_strategy_launch_method("direct")
            new_method = "direct"
        else:
            set_strategy_launch_method("bat")
            new_method = "bat"
        
        if old_method != new_method:
            log(f"Переключение с {old_method} на {new_method}...", "INFO")
            
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setWindowTitle("Смена метода запуска")
            msg.setText("Метод запуска изменен!")
            msg.setInformativeText("Диалог будет перезапущен для применения изменений.")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            
            self._schedule_dialog_restart()

    def _schedule_dialog_restart(self):
        """Планирует перезапуск диалога"""
        parent_window = self.parent()
        self.close()
        
        def restart_dialog():
            if parent_window and hasattr(parent_window, '_show_strategy_dialog'):
                parent_window._show_strategy_dialog()
        
        QTimer.singleShot(100, restart_dialog)

    def _on_game_filter_changed(self, state):
        """Обработчик изменения ipset-all"""
        enabled = (state == Qt.CheckState.Checked.value)
        set_game_filter_enabled(enabled)
        log(f"Параметр ipset-all {'включен' if enabled else 'выключен'}", "INFO")

    def _on_wssize_changed(self, state):
        """Обработчик изменения wssize"""
        enabled = (state == Qt.CheckState.Checked.value)
        set_wssize_enabled(enabled)
        log(f"Параметр --wssize=1:6 {'включен' if enabled else 'выключен'}", "INFO")

    def _on_ipset_lists_changed(self, state):
        """Обработчик изменения ipset lists"""
        from config import set_ipset_lists_enabled
        enabled = (state == Qt.CheckState.Checked.value)
        set_ipset_lists_enabled(enabled)
        log(f"Параметр ipset-all.txt для хостлистов {'включен' if enabled else 'выключен'}", "INFO")

    def _on_table_strategy_selected(self, strategy_id, strategy_name):
        """Обработчик выбора стратегии в таблице"""
        self.selected_strategy_id = strategy_id
        self.selected_strategy_name = strategy_name
        self.select_button.setEnabled(True)
        log(f"Выбрана стратегия: {strategy_name}", "DEBUG")

    def _on_table_strategy_double_clicked(self, strategy_id, strategy_name):
        """Обработчик двойного клика на стратегии"""
        self.selected_strategy_id = strategy_id
        self.selected_strategy_name = strategy_name
        self.accept()

    def on_category_selection_changed(self, category, strategy_id):
        """Обработчик изменения выбора в категории"""
        self.category_selections[category] = strategy_id
        self.update_combined_preview()
        
        # Сохраняем выбор
        try:
            if category == 'youtube':
                set_direct_strategy_youtube(strategy_id)
            elif category == 'discord':
                set_direct_strategy_discord(strategy_id)
            elif category == 'discord_voice':
                set_direct_strategy_discord_voice(strategy_id)
            elif category == 'other':
                set_direct_strategy_other(strategy_id)
            
            log(f"Сохранена {category} стратегия: {strategy_id}", "DEBUG")
        except Exception as e:
            log(f"Ошибка сохранения {category} стратегии: {e}", "⚠ WARNING")
        
        self.select_button.setEnabled(True)

    def update_combined_preview(self):
        """Обновляет предпросмотр комбинированной стратегии"""
        if not hasattr(self, 'preview_text'):
            return
        
        from .strategy_lists_separated import combine_strategies
        
        combined = combine_strategies(
            self.category_selections.get('youtube'),
            self.category_selections.get('discord'),
            self.category_selections.get('discord_voice'),  # НОВЫЙ ПАРАМЕТР
            self.category_selections.get('other')
        )
        
        active = []
        if self.category_selections.get('youtube') != 'youtube_none':
            active.append("<span style='color: #ff6666;'>YouTube</span>")
        if self.category_selections.get('discord') != 'discord_none':
            active.append("<span style='color: #7289da;'>Discord</span>")
        if self.category_selections.get('discord_voice') != 'discord_voice_none':
            active.append("<span style='color: #9b59b6;'>Discord Voice</span>")
        if self.category_selections.get('other') != 'other_none':
            active.append("<span style='color: #66ff66;'>Остальные</span>")
        
        if active:
            preview_html = f"<b>Активные:</b> {', '.join(active)}"
            args_count = len(combined['args'].split())
            preview_html += f"<br><span style='color: #888; font-size: 7pt;'>Аргументов: {args_count}</span>"
        else:
            preview_html = "<span style='color: #888;'>Нет активных стратегий</span>"
        
        self.preview_text.setHtml(f"""
            <style>
                body {{ 
                    margin: 2px; 
                    font-family: Arial; 
                    font-size: 8pt;
                    color: #ccc;
                }}
            </style>
            <body>{preview_html}</body>
        """)

    def load_builtin_strategies(self):
        """Загружает встроенные стратегии"""
        try:
            if hasattr(self, 'status_label'):
                self.status_label.setText("✅ Готово к выбору стратегий")
                self.status_label.setStyleSheet("font-weight: bold; color: #4CAF50; padding: 5px;")
            
            if self.is_direct_mode:
                self.select_button.setEnabled(True)
            
            log("Встроенные стратегии готовы", "INFO")
            
        except Exception as e:
            log(f"Ошибка загрузки встроенных стратегий: {e}", "❌ ERROR")

    def load_local_strategies(self):
        """Загружает локальные BAT стратегии"""
        try:
            # Показываем прогресс только во время загрузки
            if hasattr(self, 'strategy_table'):
                self.strategy_table.set_progress_visible(True)
                self.strategy_table.set_status("📂 Загрузка локальных стратегий...", "info")
            
            strategies = self.strategy_manager.get_local_strategies_only()
            
            if strategies and hasattr(self, 'strategy_table'):
                self.strategy_table.populate_strategies(strategies)
                
                # Скрываем прогресс после загрузки
                self.strategy_table.set_progress_visible(False)
                
                # Выбираем текущую стратегию
                if self.current_strategy_name:
                    self.strategy_table.select_strategy_by_name(self.current_strategy_name)
                
                log(f"Загружено {len(strategies)} локальных стратегий", "INFO")
            else:
                self.strategy_table.set_status(
                    "⚠️ Локальные стратегии не найдены. Нажмите 'Обновить'", 
                    "warning"
                )
                # Скрываем прогресс даже если нет стратегий
                self.strategy_table.set_progress_visible(False)
                
        except Exception as e:
            log(f"Ошибка загрузки локальных стратегий: {e}", "❌ ERROR")
            if hasattr(self, 'strategy_table'):
                self.strategy_table.set_status(f"❌ Ошибка: {e}", "error")
                # Скрываем прогресс при ошибке
                self.strategy_table.set_progress_visible(False)

    def refresh_strategies(self):
        """Обновляет список стратегий из интернета"""
        if self.is_loading_strategies:
            QMessageBox.information(self, "Обновление в процессе", 
                                "Обновление уже выполняется")
            return
        
        if self.is_direct_mode:
            self.load_builtin_strategies()
            return
        
        self.is_loading_strategies = True
        
        # Обновляем UI
        self.strategy_table.set_status("🌐 Загрузка стратегий из интернета...", "info")
        self.strategy_table.set_progress_visible(True)
        self.strategy_table.refresh_button.setEnabled(False)
        self.strategy_table.download_all_button.setEnabled(False)
        
        # Создаем поток для загрузки
        self.loader_thread = QThread()
        self.loader_worker = InternetStrategyLoader(self.strategy_manager)
        self.loader_worker.moveToThread(self.loader_thread)
        
        self.loader_thread.started.connect(self.loader_worker.run)
        self.loader_worker.progress.connect(
            lambda msg: self.strategy_table.set_status(f"🔄 {msg}", "info")
        )
        self.loader_worker.finished.connect(self._on_strategies_loaded)
        self.loader_worker.finished.connect(self.loader_thread.quit)
        self.loader_worker.finished.connect(self.loader_worker.deleteLater)
        self.loader_thread.finished.connect(self.loader_thread.deleteLater)
        
        self.loader_thread.start()
        log("Запуск загрузки стратегий из интернета", "INFO")

    def _on_strategies_loaded(self, strategies, error_message):
        """Обработчик завершения загрузки стратегий"""
        self.is_loading_strategies = False
        
        # Восстанавливаем UI
        self.strategy_table.set_progress_visible(False)
        self.strategy_table.refresh_button.setEnabled(True)
        self.strategy_table.download_all_button.setEnabled(True)
        
        if error_message:
            self.strategy_table.set_status(f"❌ {error_message}", "error")
            return
        
        if not strategies:
            self.strategy_table.set_status("⚠️ Список стратегий пуст", "warning")
            return
        
        # Заполняем таблицу
        self.strategy_table.populate_strategies(strategies)
        
        # Выбираем текущую стратегию
        if self.current_strategy_name:
            self.strategy_table.select_strategy_by_name(self.current_strategy_name)
        
        log(f"Загружено {len(strategies)} стратегий", "INFO")

    def accept(self):
        """Обрабатывает выбор стратегии"""
        if self.is_direct_mode:
            # Режим прямого запуска
            from .strategy_lists_separated import combine_strategies, get_default_selections
            
            if not self.category_selections:
                self.category_selections = get_default_selections()
            
            combined = combine_strategies(
                self.category_selections.get('youtube'),
                self.category_selections.get('discord'),
                self.category_selections.get('discord_voice'),
                self.category_selections.get('other')
            )
            
            # ВАЖНО: Сохраняем данные в атрибуты диалога для доступа из main.py
            self._combined_args = combined['args']
            self._combined_strategy_data = {
                'is_combined': True,
                'name': combined['description'],
                'args': combined['args'],
                'selections': self.category_selections
            }
            # Устанавливаем ID и имя для сигнала
            self.selected_strategy_id = "COMBINED_DIRECT"
            self.selected_strategy_name = combined['description']
            
            log(f"Выбрана комбинированная стратегия: {self.selected_strategy_name}", "INFO")
            log(f"Сохранены аргументы: {len(self._combined_args)} символов", "DEBUG")
            log(f"Выборы категорий: {self.category_selections}", "DEBUG")
            
        else:
            # BAT режим
            if not self.selected_strategy_id or not self.selected_strategy_name:
                QMessageBox.warning(self, "Выбор стратегии", 
                                "Пожалуйста, выберите стратегию из списка")
                return
            
            # Для совместимости создаем пустые атрибуты
            self._combined_args = None
            self._combined_strategy_data = None
            
            log(f"Выбрана стратегия: {self.selected_strategy_name}", "INFO")
        
        # Эмитим сигнал
        self.strategySelected.emit(self.selected_strategy_id, self.selected_strategy_name)
        
        # НЕ закрываем диалог здесь, так как main.py может еще обращаться к атрибутам
        # Диалог закроется автоматически после обработки сигнала

    def reject(self):
        """Обрабатывает отмену выбора"""
        self.close()
        log("Диалог выбора стратегии отменен", "INFO")

    def closeEvent(self, event):
        """Безопасное закрытие диалога"""
        # Останавливаем потоки если они запущены
        try:
            if hasattr(self, 'loader_thread') and self.loader_thread:
                if self.loader_thread.isRunning():
                    self.loader_thread.quit()  # Используем quit() вместо terminate()
                    if not self.loader_thread.wait(2000):
                        self.loader_thread.terminate()
                        self.loader_thread.wait(1000)
        except RuntimeError:
            # Объект QThread уже удален
            pass
        
        event.accept()