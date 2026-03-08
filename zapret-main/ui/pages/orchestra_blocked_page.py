# ui/pages/orchestra_blocked_page.py
"""
Страница управления заблокированными стратегиями оркестратора (чёрный список)
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget,
    QPushButton, QComboBox, QMenu,
    QLineEdit, QSpinBox, QFrame, QMessageBox
)
import qtawesome as qta

from .base_page import BasePage
from ui.sidebar import SettingsCard
from log import log


class BlockedDomainRow(QWidget):
    """Кликабельная строка заблокированной стратегии с контекстным меню"""

    unblock_requested = pyqtSignal(object)  # Сигнал для разблокировки по ПКМ

    def __init__(self, hostname: str, strategy: int, is_default: bool = False, parent=None):
        super().__init__(parent)
        self.data = (hostname, strategy)
        self.is_default = is_default

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Иконка замка для дефолтных
        if is_default:
            lock_icon = QLabel()
            lock_icon.setPixmap(qta.icon("mdi.lock", color="rgba(255,255,255,0.4)").pixmap(14, 14))
            lock_icon.setToolTip("Системная блокировка (нельзя изменить)")
            layout.addWidget(lock_icon)

        # Текст
        text = f"{hostname}  →  стратегия #{strategy}"
        self.label = QLabel(text)
        if is_default:
            self.label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 13px;")
        else:
            self.label.setStyleSheet("color: white; font-size: 13px;")
        layout.addWidget(self.label, 1)

        # Контекстное меню только для пользовательских
        if not is_default:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self._show_context_menu)
            self.setStyleSheet("""
                BlockedDomainRow {
                    background-color: rgba(255, 255, 255, 0.03);
                    border: 1px solid rgba(255, 255, 255, 0.06);
                    border-radius: 6px;
                }
                BlockedDomainRow:hover {
                    background-color: rgba(255, 255, 255, 0.06);
                }
            """)
        else:
            # Дефолтные - более тёмный стиль, без hover эффекта
            self.setStyleSheet("""
                BlockedDomainRow {
                    background-color: rgba(255, 255, 255, 0.02);
                    border: 1px solid rgba(255, 255, 255, 0.04);
                    border-radius: 6px;
                }
            """)

    def _show_context_menu(self, pos):
        """Показывает контекстное меню"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                color: white;
            }
            QMenu::item:selected {
                background-color: rgba(76, 175, 80, 0.3);
            }
        """)
        unblock_action = menu.addAction(qta.icon("mdi.check", color="#4CAF50"), "Разблокировать")
        action = menu.exec(self.mapToGlobal(pos))
        if action == unblock_action:
            self.unblock_requested.emit(self.data)


class OrchestraBlockedPage(BasePage):
    """Страница управления заблокированными стратегиями (чёрный список)"""

    def __init__(self, parent=None):
        super().__init__(
            "Заблокированные стратегии",
            "Системные блокировки (strategy=1 для заблокированных РКН сайтов) + пользовательский чёрный список. Оркестратор не будет их использовать.",
            parent
        )
        self.setObjectName("orchestraBlockedPage")
        self._setup_ui()

    def _setup_ui(self):
        # === Карточка добавления ===
        add_card = SettingsCard("Заблокировать стратегию")
        add_layout = QVBoxLayout()
        add_layout.setSpacing(12)

        # Секция: Из обученных доменов
        learned_label = QLabel("Выбрать из обученных")
        learned_label.setStyleSheet("color: #60cdff; font-size: 12px; font-weight: 600;")
        add_layout.addWidget(learned_label)

        # Комбобокс для обученных доменов
        self.domain_combo = QComboBox()
        self.domain_combo.setMaxVisibleItems(15)
        self.domain_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(255, 255, 255, 0.06);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 8px 12px;
                min-height: 24px;
            }
            QComboBox:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(96, 205, 255, 0.3);
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: white;
                selection-background-color: #0078d4;
            }
        """)
        add_layout.addWidget(self.domain_combo)

        # Разделитель
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.08); margin: 8px 0;")
        separator.setFixedHeight(1)
        add_layout.addWidget(separator)

        # Секция: Ручной ввод
        custom_label = QLabel("Или ввести вручную")
        custom_label.setStyleSheet("color: #60cdff; font-size: 12px; font-weight: 600;")
        add_layout.addWidget(custom_label)

        # Ручной ввод
        custom_row = QHBoxLayout()
        custom_row.setSpacing(8)
        self.custom_domain_input = QLineEdit()
        self.custom_domain_input.setPlaceholderText("example.com")
        self.custom_domain_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.06);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 8px 12px;
            }
            QLineEdit:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(96, 205, 255, 0.3);
            }
            QLineEdit:focus {
                border: 1px solid #60cdff;
            }
        """)
        custom_row.addWidget(self.custom_domain_input, 2)

        self.custom_proto_combo = QComboBox()
        self.custom_proto_combo.addItems(["TLS (443)", "HTTP (80)", "UDP"])
        self.custom_proto_combo.setStyleSheet(self.domain_combo.styleSheet())
        custom_row.addWidget(self.custom_proto_combo)
        add_layout.addLayout(custom_row)

        # Разделитель
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setStyleSheet("background-color: rgba(255, 255, 255, 0.08); margin: 8px 0;")
        separator2.setFixedHeight(1)
        add_layout.addWidget(separator2)

        # Номер стратегии и кнопка
        strat_row = QHBoxLayout()
        strat_row.setSpacing(12)

        strat_label = QLabel("Стратегия #")
        strat_label.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 13px;")
        strat_row.addWidget(strat_label)

        self.strat_spin = QSpinBox()
        self.strat_spin.setRange(1, 999)
        self.strat_spin.setValue(1)
        self.strat_spin.setStyleSheet("""
            QSpinBox {
                background-color: rgba(255, 255, 255, 0.06);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 6px 12px;
                min-width: 70px;
            }
            QSpinBox:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(96, 205, 255, 0.3);
            }
            QSpinBox:focus {
                border: 1px solid #60cdff;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
                border: none;
            }
        """)
        strat_row.addWidget(self.strat_spin)
        strat_row.addStretch()

        self.block_btn = QPushButton("Заблокировать")
        self.block_btn.setIcon(qta.icon("mdi.block-helper", color="#e91e63"))
        self.block_btn.clicked.connect(self._block_strategy)
        self.block_btn.setStyleSheet("""
            QPushButton {
                background: rgba(233, 30, 99, 0.2);
                border: 1px solid rgba(233, 30, 99, 0.3);
                border-radius: 6px;
                color: #e91e63;
                padding: 8px 24px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(233, 30, 99, 0.3);
            }
        """)
        strat_row.addWidget(self.block_btn)
        add_layout.addLayout(strat_row)

        add_card.add_layout(add_layout)
        self.layout.addWidget(add_card)

        # === Карточка списка ===
        list_card = SettingsCard("Чёрный список")
        list_layout = QVBoxLayout()
        list_layout.setSpacing(8)

        # Кнопка и счётчик сверху
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # Поиск
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по доменам...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_list)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.06);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 6px 12px;
                min-width: 200px;
            }
            QLineEdit:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(96, 205, 255, 0.3);
            }
            QLineEdit:focus {
                border: 1px solid #60cdff;
            }
        """)
        top_row.addWidget(self.search_input)

        self.unblock_all_btn = QPushButton("Очистить пользовательские")
        self.unblock_all_btn.setIcon(qta.icon("mdi.delete-sweep", color="#ff9800"))
        self.unblock_all_btn.setToolTip("Удалить все пользовательские блокировки (системные останутся)")
        self.unblock_all_btn.clicked.connect(self._unblock_all)
        self.unblock_all_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 152, 0, 0.15);
                border: 1px solid rgba(255, 152, 0, 0.3);
                border-radius: 6px;
                color: #ff9800;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(255, 152, 0, 0.25);
            }
        """)
        top_row.addWidget(self.unblock_all_btn)
        top_row.addStretch()

        list_layout.addLayout(top_row)

        # Счётчик на отдельной строке (чтобы влезал в таб)
        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 11px;")
        list_layout.addWidget(self.count_label)

        # Подсказка
        hint_label = QLabel("ПКМ по пользовательской строке для разблокировки • Системные блокировки неизменяемы")
        hint_label.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 10px; font-style: italic;")
        list_layout.addWidget(hint_label)

        # Контейнер для строк (без скроллбара - страница сама прокручивается)
        self.blocked_container = QWidget()
        self.blocked_rows_layout = QVBoxLayout(self.blocked_container)
        self.blocked_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.blocked_rows_layout.setSpacing(4)
        list_layout.addWidget(self.blocked_container)

        # Список строк для управления
        self._blocked_rows: list[BlockedDomainRow] = []

        list_card.add_layout(list_layout)
        self.layout.addWidget(list_card)

        # Подключаем сигналы
        self.domain_combo.currentIndexChanged.connect(self._on_domain_changed)

    def showEvent(self, event):
        """При показе страницы обновляем данные"""
        super().showEvent(event)
        self._refresh_data()

    def _get_runner(self):
        """Получает orchestra_runner из главного окна"""
        app = self.window()
        if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
            return app.orchestra_runner
        return None

    def _refresh_data(self):
        """Обновляет все данные на странице"""
        self._refresh_domain_combo()
        self._refresh_blocked_list()

    def _refresh_domain_combo(self):
        """Обновляет комбобокс с обученными доменами"""
        self.domain_combo.clear()
        runner = self._get_runner()
        if not runner:
            self.domain_combo.addItem("Оркестратор не запущен", None)
            self.domain_combo.setEnabled(False)
            return

        self.domain_combo.setEnabled(True)
        learned = runner.get_learned_data()

        all_domains = []
        for domain, strats in learned.get('tls', {}).items():
            if strats:
                blocked_list = runner.blocked_manager.get_blocked(domain)
                all_domains.append((domain, strats[0], 'tls', blocked_list))
        for domain, strats in learned.get('http', {}).items():
            if strats:
                blocked_list = runner.blocked_manager.get_blocked(domain)
                all_domains.append((domain, strats[0], 'http', blocked_list))
        for ip, strats in learned.get('udp', {}).items():
            if strats:
                blocked_list = runner.blocked_manager.get_blocked(ip)
                all_domains.append((ip, strats[0], 'udp', blocked_list))

        all_domains.sort(key=lambda x: x[0].lower())

        if all_domains:
            for domain, strat, proto, blocked_list in all_domains:
                blocked_str = f" [blocked: {blocked_list}]" if blocked_list else ""
                self.domain_combo.addItem(f"{domain} (#{strat}, {proto.upper()}){blocked_str}", (domain, strat, proto))
        else:
            self.domain_combo.addItem("Нет обученных доменов", None)

    def _refresh_blocked_list(self):
        """Обновляет список заблокированных стратегий"""
        # Очищаем старые строки
        for row in self._blocked_rows:
            row.deleteLater()
        self._blocked_rows.clear()

        runner = self._get_runner()
        if not runner:
            self._update_count()
            return

        # Собираем все блокировки с флагом is_default
        all_blocked = []
        for hostname, strategies in runner.blocked_strategies.items():
            for strategy in strategies:
                is_default = runner.blocked_manager.is_default_blocked(hostname, strategy)
                all_blocked.append((hostname, strategy, is_default))

        # Сортируем: сначала пользовательские, потом дефолтные, внутри групп по алфавиту
        all_blocked.sort(key=lambda x: (x[2], x[0].lower(), x[1]))

        # Добавляем разделитель если есть оба типа
        user_items = [x for x in all_blocked if not x[2]]
        default_items = [x for x in all_blocked if x[2]]

        if user_items:
            user_header = QLabel(f"Пользовательские ({len(user_items)})")
            user_header.setStyleSheet("color: #60cdff; font-size: 11px; font-weight: 600; padding: 4px 0;")
            self.blocked_rows_layout.addWidget(user_header)

            for hostname, strategy, is_default in user_items:
                row = BlockedDomainRow(hostname, strategy, is_default=False)
                row.unblock_requested.connect(self._unblock_by_data)
                self.blocked_rows_layout.addWidget(row)
                self._blocked_rows.append(row)

        if default_items:
            if user_items:
                # Разделитель
                spacer = QWidget()
                spacer.setFixedHeight(12)
                self.blocked_rows_layout.addWidget(spacer)

            default_header = QLabel(f"🔒 Системные ({len(default_items)}) — заблокированные РКН сайты")
            default_header.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 11px; font-weight: 600; padding: 4px 0;")
            self.blocked_rows_layout.addWidget(default_header)

            for hostname, strategy, is_default in default_items:
                row = BlockedDomainRow(hostname, strategy, is_default=True)
                self.blocked_rows_layout.addWidget(row)
                self._blocked_rows.append(row)

        self._update_count()

    def _filter_list(self, text: str):
        """Фильтрует список по введённому тексту"""
        search = text.lower().strip()
        for row in self._blocked_rows:
            hostname = row.data[0].lower()
            row.setVisible(search in hostname if search else True)

    def _unblock_by_data(self, data):
        """Разблокирует стратегию по данным из контекстного меню"""
        runner = self._get_runner()
        if not runner:
            return

        hostname, strategy = data
        success = runner.blocked_manager.unblock(hostname, strategy)
        if success:
            log(f"Разблокирована стратегия #{strategy} для {hostname}", "INFO")
        self._refresh_data()

    def _update_count(self):
        """Обновляет счётчик"""
        runner = self._get_runner()
        if runner:
            user_count = 0
            default_count = 0
            for hostname, strategies in runner.blocked_strategies.items():
                for strategy in strategies:
                    if runner.blocked_manager.is_default_blocked(hostname, strategy):
                        default_count += 1
                    else:
                        user_count += 1
            total = user_count + default_count
            self.count_label.setText(f"Всего: {total} ({user_count} пользовательских + {default_count} системных)")
        else:
            self.count_label.setText("Оркестратор не инициализирован")

    def _on_domain_changed(self, index):
        """При смене домена обновляем номер стратегии"""
        data = self.domain_combo.itemData(index)
        if data:
            self.strat_spin.setValue(data[1])

    def _block_strategy(self):
        """Блокирует стратегию"""
        runner = self._get_runner()
        if not runner:
            return

        strategy = self.strat_spin.value()

        # Приоритет: если в поле ввода есть текст - используем его
        custom_domain = self.custom_domain_input.text().strip().lower()
        if custom_domain:
            domain = custom_domain
            proto_text = self.custom_proto_combo.currentText()
            if "TLS" in proto_text:
                proto = "tls"
            elif "HTTP" in proto_text:
                proto = "http"
            else:
                proto = "udp"
            # Очищаем поле после добавления
            self.custom_domain_input.clear()
        else:
            # Используем выбор из комбобокса
            data = self.domain_combo.currentData()
            if not data:
                return
            domain, _, proto = data

        runner.blocked_manager.block(domain, strategy, proto)
        log(f"Заблокирована стратегия #{strategy} для {domain} [{proto.upper()}]", "INFO")
        self._refresh_data()

    def _unblock_all(self):
        """Очищает пользовательский чёрный список (системные блокировки остаются)"""
        runner = self._get_runner()
        if not runner:
            return

        # Считаем только пользовательские блокировки
        user_count = 0
        for hostname, strategies in runner.blocked_strategies.items():
            for strategy in strategies:
                if not runner.blocked_manager.is_default_blocked(hostname, strategy):
                    user_count += 1

        if user_count == 0:
            QMessageBox.information(
                self,
                "Информация",
                "Нет пользовательских блокировок для удаления.\n\nСистемные блокировки (для заблокированных РКН сайтов) не удаляются.",
                QMessageBox.StandardButton.Ok
            )
            return

        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Очистить пользовательский чёрный список ({user_count} записей)?\n\nСистемные блокировки останутся.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            runner.blocked_manager.clear()
            runner.blocked_strategies = runner.blocked_manager.blocked_strategies
            log(f"Очищен пользовательский чёрный список ({user_count} записей)", "INFO")
            self._refresh_data()
