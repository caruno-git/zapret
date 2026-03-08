# strategy_menu/tabs.py

from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, 
                            QRadioButton, QButtonGroup, QTextBrowser, 
                            QScrollArea, QWidget, QFrame, QCheckBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from log import log
from config import (get_strategy_launch_method, set_strategy_launch_method,
                   get_game_filter_enabled, set_game_filter_enabled,
                   get_wssize_enabled, set_wssize_enabled)
from .widgets import CompactStrategyItem
from .constants import LABEL_TEXTS, LABEL_COLORS


class StrategyTabBuilder:
    """Класс для построения вкладок стратегий."""
    
    @staticmethod
    def build_youtube_tab(layout, strategies, category_selections, on_selection_changed):
        """Строит вкладку YouTube."""
        # Заголовок
        header = QLabel("Выберите стратегию для YouTube")
        header.setStyleSheet("font-weight: bold; font-size: 10pt; margin: 5px;")
        layout.addWidget(header)
        
        # Область прокрутки
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
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
        """)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        
        button_group = QButtonGroup()
        
        for idx, (strat_id, strat_data) in enumerate(strategies.items()):
            # Создаем виджет стратегии
            strategy_widget = QWidget()
            strategy_widget.setStyleSheet("""
                QWidget:hover {
                    background: #333;
                    border-radius: 5px;
                }
            """)
            strategy_layout = QVBoxLayout(strategy_widget)
            strategy_layout.setContentsMargins(10, 5, 10, 5)
            
            # Радиокнопка
            radio = QRadioButton(strat_data['name'])
            radio.setProperty('strategy_id', strat_id)
            radio.setStyleSheet("font-weight: bold; font-size: 10pt;")
            
            if strat_id == category_selections.get('youtube'):
                radio.setChecked(True)
            
            button_group.addButton(radio, idx)
            strategy_layout.addWidget(radio)
            
            # Описание
            desc_text = strat_data['description']
            if strat_data.get('label'):
                label = strat_data['label']
                if label in LABEL_TEXTS:
                    label_color = LABEL_COLORS.get(label, '#888')
                    desc_text += f" <span style='color: {label_color}; font-weight: bold;'>[{LABEL_TEXTS[label]}]</span>"
            
            desc_label = QLabel(desc_text)
            desc_label.setWordWrap(True)
            desc_label.setTextFormat(Qt.TextFormat.RichText)
            desc_label.setStyleSheet("color: #aaa; margin-left: 25px; font-size: 9pt;")
            strategy_layout.addWidget(desc_label)
            
            # Автор
            author_label = QLabel(f"Автор: {strat_data.get('author', 'Unknown')}")
            author_label.setStyleSheet("color: #888; margin-left: 25px; font-size: 8pt; font-style: italic;")
            strategy_layout.addWidget(author_label)
            
            scroll_layout.addWidget(strategy_widget)
        
        button_group.buttonClicked.connect(on_selection_changed)
        
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        return button_group
    
    @staticmethod
    def build_settings_tab(parent, on_method_changed, on_ipset_changed, on_wssize_changed):
        """Строит вкладку настроек."""
        layout = QVBoxLayout(parent)
        
        # Заголовок
        title = QLabel("Выберите метод запуска стратегий")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("margin: 10px; color: #2196F3;")
        layout.addWidget(title)
        
        # Группа методов
        method_group = QGroupBox("Метод запуска стратегий")
        method_layout = QVBoxLayout(method_group)
        
        button_group = QButtonGroup()
        
        # BAT метод
        bat_radio = QRadioButton("Классический метод (через .bat файлы)")
        bat_radio.setToolTip(
            "Использует .bat файлы для запуска стратегий.\n"
            "Загружает стратегии из интернета.\n"
            "Может показывать окна консоли при запуске."
        )
        button_group.addButton(bat_radio, 0)
        method_layout.addWidget(bat_radio)
        
        # Direct метод
        direct_radio = QRadioButton("Прямой запуск (рекомендуется)")
        direct_radio.setToolTip(
            "Запускает встроенные стратегии напрямую из Python.\n"
            "Не требует интернета, все стратегии включены в программу.\n"
            "Полностью скрытый запуск без окон консоли."
        )
        button_group.addButton(direct_radio, 1)
        method_layout.addWidget(direct_radio)
        
        # Загружаем текущий метод
        current_method = get_strategy_launch_method()
        if current_method == "direct":
            direct_radio.setChecked(True)
        else:
            bat_radio.setChecked(True)
        
        button_group.buttonClicked.connect(on_method_changed)
        layout.addWidget(method_group)
        
        # Параметры запуска
        params_group = QGroupBox("Параметры запуска")
        params_layout = QVBoxLayout(params_group)
        
        # Чекбокс ipset-all
        ipset_checkbox = QCheckBox("Включить фильтр для игр (Game Filter)")
        ipset_checkbox.setToolTip(
            "Добавляет фильтрацию для портов 443,1024-65535 с использованием ipset-all.txt."
        )
        ipset_checkbox.setChecked(get_game_filter_enabled())
        ipset_checkbox.stateChanged.connect(on_ipset_changed)
        params_layout.addWidget(ipset_checkbox)
        
        # Чекбокс wssize
        wssize_checkbox = QCheckBox("Добавить --wssize=1:6 для TCP 443")
        wssize_checkbox.setToolTip(
            "Включает параметр --wssize=1:6 для всех TCP соединений на порту 443."
        )
        wssize_checkbox.setChecked(get_wssize_enabled())
        wssize_checkbox.stateChanged.connect(on_wssize_changed)
        params_layout.addWidget(wssize_checkbox)
        
        layout.addWidget(params_group)
        layout.addStretch()
        
        return button_group, bat_radio, direct_radio, ipset_checkbox, wssize_checkbox