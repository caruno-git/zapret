# ui/pages/orchestra_page.py
"""Страница оркестратора автоматического обучения (circular)"""

import os
from queue import Queue, Empty
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFrame, QCheckBox,
    QLineEdit, QListWidget, QListWidgetItem, QComboBox
)
from PyQt6.QtGui import QFont, QTextCursor, QAction, QPainter, QColor
import qtawesome as qta

from .base_page import BasePage


class StyledCheckBox(QCheckBox):
    """Кастомный чекбокс с красивой галочкой"""

    def __init__(self, text: str, color: str = "#4CAF50", parent=None):
        super().__init__(text, parent)
        self._check_color = QColor(color)
        self.setStyleSheet(f"""
            QCheckBox {{
                color: rgba(255,255,255,0.7);
                font-size: 12px;
                spacing: 8px;
                padding-left: 4px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid rgba(255,255,255,0.3);
                background: rgba(0,0,0,0.2);
            }}
            QCheckBox::indicator:checked {{
                background: {color};
                border-color: {color};
            }}
            QCheckBox::indicator:hover {{
                border-color: rgba(255,255,255,0.5);
            }}
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isChecked():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Рисуем галочку белым цветом поверх индикатора
            painter.setPen(QColor(255, 255, 255))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            # Позиция индикатора (примерно 4px от левого края)
            x = 6
            y = (self.height() - 18) // 2 + 2

            # Рисуем галочку (✓) - две линии
            from PyQt6.QtGui import QPen
            pen = QPen(QColor(255, 255, 255))
            pen.setWidth(2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)

            # Короткая часть галочки
            painter.drawLine(x + 4, y + 9, x + 7, y + 12)
            # Длинная часть галочки
            painter.drawLine(x + 7, y + 12, x + 14, y + 5)

            painter.end()


from ui.sidebar import SettingsCard, ActionButton
from log import log
from orchestra import MAX_ORCHESTRA_LOGS


class OrchestraPage(BasePage):
    """Страница оркестратора с логами обучения"""

    clear_learned_requested = pyqtSignal()  # Сигнал очистки данных обучения
    log_received = pyqtSignal(str)  # Сигнал для получения логов из потока runner'а

    # Состояния оркестратора
    STATE_IDLE = "idle"          # Нет активности (серый)
    STATE_RUNNING = "running"    # Работает на залоченной стратегии (зелёный)
    STATE_LEARNING = "learning"  # Перебирает стратегии (оранжевый)
    STATE_UNLOCKED = "unlocked"  # RST блокировка, переобучение (красный)

    def __init__(self, parent=None):
        super().__init__(
            "Оркестратор v0.9.2 (Alpha)",
            "Автоматическое обучение стратегий DPI bypass. Система находит лучшую стратегию для каждого домена (TCP: TLS/HTTP, UDP: QUIC/Discord Voice/STUN).\nЧтобы начать обучение зайдите на сайт и через несколько секунд обновите вкладку. Продолжайте это пока стратегия не будет помечена как LOCKED",
            parent
        )
        self._build_ui()

        # Путь к лог-файлу (берём из runner динамически)
        self._log_file_path = None  # Устанавливается в _update_log_file_path()
        self._last_log_position = 0  # Позиция в файле для инкрементального чтения
        self._current_state = self.STATE_IDLE  # Текущее состояние

        # Хранилище всех строк лога для фильтрации
        self._full_log_lines = []
        self._max_log_lines = 1000  # Максимум строк в памяти

        # Таймер для обновления статуса и логов
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_all)

        # Thread-safe очередь для логов из runner потока
        self._log_queue = Queue()

        # Таймер для обработки очереди логов (50ms - быстро, но не блокирует UI)
        self._log_queue_timer = QTimer(self)
        self._log_queue_timer.timeout.connect(self._process_log_queue)
        self._log_queue_timer.start(50)

        # Подключаем сигнал для обновления логов (теперь только из main thread)
        self.log_received.connect(self._on_log_received)

    def _build_ui(self):
        """Строит UI страницы"""

        # === Статус карточка ===
        status_card = SettingsCard("Статус обучения")
        status_layout = QVBoxLayout()

        # Статус
        status_row = QHBoxLayout()
        self.status_icon = QLabel()
        self.status_icon.setFixedSize(24, 24)
        self.status_label = QLabel("Не запущен")
        self.status_label.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 14px;")
        status_row.addWidget(self.status_icon)
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        status_layout.addLayout(status_row)

        # Информация о режимах
        info_label = QLabel(
            "• IDLE - ожидание соединений\n"
            "• LEARNING - перебирает стратегии\n"
            "• RUNNING - работает на лучших стратегиях\n"
            "• UNLOCKED - переобучение (RST блокировка)"
        )
        info_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 12px; margin-top: 8px;")
        status_layout.addWidget(info_label)

        status_card.add_layout(status_layout)
        self.layout.addWidget(status_card)

        # === Лог карточка ===
        log_card = SettingsCard("Лог обучения")
        log_layout = QVBoxLayout()

        # Текстовое поле для логов
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(300)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: #00ff00;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                padding: 8px;
            }
        """)
        self.log_text.setPlaceholderText("Логи обучения будут отображаться здесь...")
        # Контекстное меню для блокировки стратегий
        self.log_text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_text.customContextMenuRequested.connect(self._show_log_context_menu)
        log_layout.addWidget(self.log_text)

        # === Фильтры лога ===
        filter_row = QHBoxLayout()

        filter_label = QLabel("Фильтр:")
        filter_label.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 12px;")
        filter_row.addWidget(filter_label)

        # Поле ввода для фильтра по домену
        self.log_filter_input = QLineEdit()
        self.log_filter_input.setPlaceholderText("Домен (например: youtube.com)")
        self.log_filter_input.setStyleSheet("""
            QLineEdit {
                background: rgba(0,0,0,0.2);
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 4px;
                color: white;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #60cdff;
            }
        """)
        self.log_filter_input.textChanged.connect(self._apply_log_filter)
        filter_row.addWidget(self.log_filter_input, 2)

        # Комбобокс для фильтра по протоколу
        self.log_protocol_filter = QComboBox()
        self.log_protocol_filter.addItems(["Все", "TLS", "HTTP", "UDP", "SUCCESS", "FAIL"])
        self.log_protocol_filter.setStyleSheet("""
            QComboBox {
                background: rgba(0,0,0,0.2);
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 4px;
                color: white;
                padding: 6px 10px;
                font-size: 12px;
                min-width: 80px;
            }
            QComboBox:focus {
                border-color: #60cdff;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background: #2d2d2d;
                color: white;
                selection-background-color: #0078d4;
            }
        """)
        self.log_protocol_filter.currentTextChanged.connect(self._apply_log_filter)
        filter_row.addWidget(self.log_protocol_filter)

        # Кнопка сброса фильтра
        clear_filter_btn = QPushButton()
        clear_filter_btn.setIcon(qta.icon("mdi.close", color="rgba(255,255,255,0.6)"))
        clear_filter_btn.setToolTip("Сбросить фильтр")
        clear_filter_btn.setFixedSize(28, 28)
        clear_filter_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.1);
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.2);
            }
        """)
        clear_filter_btn.clicked.connect(self._clear_log_filter)
        filter_row.addWidget(clear_filter_btn)

        log_layout.addLayout(filter_row)

        # Кнопки - ряд 1
        btn_row1 = QHBoxLayout()

        self.clear_log_btn = QPushButton("Очистить лог")
        self.clear_log_btn.setIcon(qta.icon("mdi.delete", color="#ff6b6b"))
        self.clear_log_btn.clicked.connect(self._clear_log)
        self.clear_log_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 107, 107, 0.1);
                border: 1px solid rgba(255, 107, 107, 0.3);
                border-radius: 6px;
                color: #ff6b6b;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: rgba(255, 107, 107, 0.2);
            }
        """)
        btn_row1.addWidget(self.clear_log_btn)

        self.clear_learned_btn = QPushButton("Сбросить обучение")
        self.clear_learned_btn.setIcon(qta.icon("mdi.restart", color="#ff9800"))
        self.clear_learned_btn.clicked.connect(self._clear_learned)
        self.clear_learned_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 152, 0, 0.1);
                border: 1px solid rgba(255, 152, 0, 0.3);
                border-radius: 6px;
                color: #ff9800;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: rgba(255, 152, 0, 0.2);
            }
        """)
        btn_row1.addWidget(self.clear_learned_btn)

        btn_row1.addStretch()
        log_layout.addLayout(btn_row1)

        # Кнопки залоченных/заблокированных стратегий перенесены в отдельные страницы:
        # - OrchestraLockedPage (Залоченные)
        # - OrchestraBlockedPage (Заблокированные)

        log_card.add_layout(log_layout)
        self.layout.addWidget(log_card)

        # === История логов ===
        log_history_card = SettingsCard(f"История логов (макс. {MAX_ORCHESTRA_LOGS})")
        log_history_layout = QVBoxLayout()

        # Описание
        log_history_desc = QLabel("Каждый запуск оркестратора создаёт новый лог с уникальным ID. Старые логи автоматически удаляются.")
        log_history_desc.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 11px;")
        log_history_desc.setWordWrap(True)
        log_history_layout.addWidget(log_history_desc)

        # Список логов
        self.log_history_list = QListWidget()
        self.log_history_list.setMaximumHeight(150)
        self.log_history_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(0,0,0,0.2);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 4px;
                color: rgba(255,255,255,0.8);
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 4px;
            }
            QListWidget::item:selected {
                background-color: rgba(138,43,226,0.3);
            }
        """)
        self.log_history_list.itemDoubleClicked.connect(self._view_log_history)
        log_history_layout.addWidget(self.log_history_list)

        # Кнопки управления историей логов
        log_history_buttons = QHBoxLayout()

        view_log_btn = ActionButton("Просмотреть", "fa5s.eye")
        view_log_btn.clicked.connect(self._view_log_history)
        log_history_buttons.addWidget(view_log_btn)

        delete_log_btn = ActionButton("Удалить", "fa5s.trash-alt")
        delete_log_btn.clicked.connect(self._delete_log_history)
        log_history_buttons.addWidget(delete_log_btn)

        log_history_buttons.addStretch()

        clear_all_logs_btn = QPushButton("Очистить все")
        clear_all_logs_btn.setIcon(qta.icon("mdi.delete-sweep", color="#ff6b6b"))
        clear_all_logs_btn.clicked.connect(self._clear_all_log_history)
        clear_all_logs_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 107, 107, 0.1);
                border: 1px solid rgba(255, 107, 107, 0.3);
                border-radius: 6px;
                color: #ff6b6b;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(255, 107, 107, 0.2);
            }
        """)
        log_history_buttons.addWidget(clear_all_logs_btn)

        log_history_layout.addLayout(log_history_buttons)
        log_history_card.add_layout(log_history_layout)
        self.layout.addWidget(log_history_card)

        # Обновляем статус
        self._update_status(self.STATE_IDLE)

    def _update_status(self, state: str):
        """Обновляет статус на основе состояния"""
        self._current_state = state

        if state == self.STATE_RUNNING:
            self.status_icon.setPixmap(
                qta.icon("mdi.brain", color="#4CAF50").pixmap(24, 24)  # Зелёный
            )
            self.status_label.setText("✅ RUNNING - работает на лучших стратегиях")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 14px;")
        elif state == self.STATE_LEARNING:
            self.status_icon.setPixmap(
                qta.icon("mdi.brain", color="#FF9800").pixmap(24, 24)  # Оранжевый
            )
            self.status_label.setText("🔄 LEARNING - перебирает стратегии")
            self.status_label.setStyleSheet("color: #FF9800; font-size: 14px;")
        elif state == self.STATE_UNLOCKED:
            self.status_icon.setPixmap(
                qta.icon("mdi.brain", color="#F44336").pixmap(24, 24)  # Красный
            )
            self.status_label.setText("🔓 UNLOCKED - переобучение (RST блокировка)")
            self.status_label.setStyleSheet("color: #F44336; font-size: 14px;")
        else:  # STATE_IDLE
            self.status_icon.setPixmap(
                qta.icon("mdi.brain", color="#666").pixmap(24, 24)  # Серый
            )
            self.status_label.setText("⏸ IDLE - ожидание соединений")
            self.status_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 14px;")

    def _clear_log(self):
        """Очищает лог"""
        self.log_text.clear()
        self._full_log_lines = []  # Очищаем хранилище
        # Сбрасываем позицию чтобы перечитать файл с начала
        self._last_log_position = 0

    def _clear_learned(self):
        """Сбрасывает данные обучения"""
        self.clear_learned_requested.emit()
        self.append_log("[INFO] Данные обучения сброшены")
        self._update_domains({})

    def _update_all(self):
        """Обновляет статус, данные обучения, историю и whitelist"""
        try:
            app = self.window()
            if hasattr(app, 'dpi_starter') and app.dpi_starter:
                is_running = app.dpi_starter.check_process_running_wmi(silent=True)

                if not is_running:
                    self._update_status(self.STATE_IDLE)
                # Не меняем статус автоматически на LEARNING -
                # это делает _detect_state_from_line при получении логов

                # Обновляем данные обучения и историю
                self._update_learned_domains()

            # Обновляем историю логов (всегда, даже если runner не запущен)
            self._update_log_history()
        except Exception:
            pass

    def _on_log_received(self, text: str):
        """Обработчик сигнала - добавляет лог и определяет состояние"""
        print(f"[DEBUG _on_log_received] {text[:80]}...")  # DEBUG
        self.append_log(text)
        self._detect_state_from_line(text)

    def emit_log(self, text: str):
        """Публичный метод для отправки логов (вызывается из callback runner'а).
        Thread-safe: использует очередь вместо прямого emit сигнала.
        """
        # Кладём в очередь - это thread-safe операция
        self._log_queue.put(text)

    def _process_log_queue(self):
        """Обрабатывает очередь логов из main thread (вызывается таймером)"""
        # Обрабатываем до 20 сообщений за раз чтобы не блокировать UI
        for _ in range(20):
            try:
                text = self._log_queue.get_nowait()
                self.log_received.emit(text)
            except Empty:
                break

    def _get_current_log_path(self) -> str:
        """Получает путь к текущему лог-файлу из runner'а"""
        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                return app.orchestra_runner.debug_log_path
        except Exception:
            pass
        return None

    def _read_log_file(self):
        """Читает новые строки из лог-файла и определяет состояние"""
        try:
            # Получаем актуальный путь к логу из runner'а
            current_log_path = self._get_current_log_path()

            # Если путь изменился - сбрасываем позицию
            if current_log_path != self._log_file_path:
                self._log_file_path = current_log_path
                self._last_log_position = 0

            if not self._log_file_path or not os.path.exists(self._log_file_path):
                return

            with open(self._log_file_path, 'r', encoding='utf-8', errors='replace') as f:
                # Переходим к последней прочитанной позиции
                f.seek(self._last_log_position)

                # Читаем новые строки
                new_content = f.read()
                if new_content:
                    # Добавляем в лог и определяем состояние
                    for line in new_content.splitlines():
                        if line.strip():
                            self.append_log(line)
                            # Определяем состояние из лога
                            self._detect_state_from_line(line)

                    # Обновляем позицию
                    self._last_log_position = f.tell()
        except Exception as e:
            log(f"Ошибка чтения лог-файла: {e}", "DEBUG")

    def _detect_state_from_line(self, line: str):
        """Определяет состояние оркестратора из строки лога

        Форматы сообщений из orchestra_runner:
        - "[18:21:27] PRELOADED: domain.com = strategy 1 [tls]" - предзагружено (RUNNING)
        - "[17:45:13] ✓ SUCCESS: domain.com :443 strategy=1" - обычный успех
        - "[17:45:13] 🔒 LOCKED: domain.com :443 = strategy 1" - залочен (RUNNING)
        - "[17:45:13] 🔓 UNLOCKED: domain.com :443 - re-learning..." - разлочен (UNLOCKED)
        - "[17:45:13] ✗ FAIL: domain.com :443 strategy=1" - провал
        - "[17:45:13] 🔄 Strategy rotated to 2" - ротация (LEARNING)
        - "[18:08:36] ⚡ RST detected - DPI block" - RST блок (LEARNING)
        """
        # RUNNING: PRELOADED или LOCKED (есть готовые стратегии)
        if "PRELOADED:" in line or "🔒" in line or "LOCKED:" in line:
            self._update_status(self.STATE_RUNNING)
            return

        # UNLOCKED: переобучение (🔓 UNLOCKED:)
        if "🔓" in line or "UNLOCKED:" in line:
            self._update_status(self.STATE_UNLOCKED)
            return

        # LEARNING: RST detected или rotated (активный перебор стратегий)
        if "RST detected" in line or "rotated" in line.lower():
            self._update_status(self.STATE_LEARNING)
            return

        # SUCCESS/FAIL: переключаем IDLE/UNLOCKED → LEARNING (активность)
        # Не меняем RUNNING → LEARNING (SUCCESS происходит и после LOCK)
        # UNLOCKED → LEARNING: означает что переобучение идёт активно
        if "✓" in line or "SUCCESS:" in line or "✗" in line or "FAIL:" in line:
            if self._current_state in (self.STATE_IDLE, self.STATE_UNLOCKED):
                self._update_status(self.STATE_LEARNING)
            return

    def _update_learned_domains(self):
        """Обновляет данные обученных доменов из реестра через runner"""
        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                learned = app.orchestra_runner.get_learned_data()
                self._update_domains(learned)
            else:
                self._update_domains({'tls': {}, 'http': {}, 'udp': {}})
        except Exception as e:
            log(f"Ошибка чтения обученных доменов: {e}", "DEBUG")

    def _update_domains(self, _data: dict):
        """Данные обученных доменов теперь отображаются на вкладке Залоченное"""
        pass  # Виджет перемещён в orchestra_locked_page.py

    def append_log(self, text: str):
        """Добавляет строку в лог"""
        # Сохраняем в полный лог
        self._full_log_lines.append(text)
        # Ограничиваем размер
        if len(self._full_log_lines) > self._max_log_lines:
            self._full_log_lines = self._full_log_lines[-self._max_log_lines:]

        # Проверяем фильтр
        if self._matches_filter(text):
            self.log_text.append(text)
            # Прокручиваем вниз
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)

    def _matches_filter(self, text: str) -> bool:
        """Проверяет, соответствует ли строка текущему фильтру"""
        # Фильтр по домену
        domain_filter = self.log_filter_input.text().strip().lower()
        if domain_filter and domain_filter not in text.lower():
            return False

        # Фильтр по протоколу/статусу
        protocol_filter = self.log_protocol_filter.currentText()
        if protocol_filter != "Все":
            text_upper = text.upper()
            if protocol_filter == "TLS" and "[TLS]" not in text_upper and "TLS" not in text_upper:
                return False
            elif protocol_filter == "HTTP" and "[HTTP]" not in text_upper and "HTTP" not in text_upper:
                return False
            elif protocol_filter == "UDP" and "UDP" not in text_upper:
                return False
            elif protocol_filter == "SUCCESS" and "SUCCESS" not in text_upper and "✓" not in text:
                return False
            elif protocol_filter == "FAIL" and "FAIL" not in text_upper and "✗" not in text and "X " not in text:
                return False

        return True

    def _apply_log_filter(self):
        """Применяет фильтр к логу"""
        # Фильтруем все сохранённые строки
        filtered_lines = [line for line in self._full_log_lines if self._matches_filter(line)]

        # Обновляем виджет лога
        self.log_text.clear()
        for line in filtered_lines:
            self.log_text.append(line)

        # Прокручиваем вниз
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

    def _clear_log_filter(self):
        """Сбрасывает фильтр"""
        self.log_filter_input.clear()
        self.log_protocol_filter.setCurrentIndex(0)
        self._apply_log_filter()

    @pyqtSlot()
    def start_monitoring(self):
        """Запускает мониторинг"""
        # Подключаем callback к runner если он уже запущен (при автозапуске callback не устанавливается)
        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                runner = app.orchestra_runner
                if runner.output_callback is None:
                    print("[DEBUG start_monitoring] Устанавливаем callback на запущенный runner")  # DEBUG
                    runner.set_output_callback(self.emit_log)
        except Exception as e:
            print(f"[DEBUG start_monitoring] Ошибка установки callback: {e}")  # DEBUG

        # Сбрасываем позицию чтения лога при старте
        self._last_log_position = 0
        self.update_timer.start(5000)  # Обновляем каждые 5 секунд (было 500мс)
        self._update_all()  # Сразу обновляем

    def stop_monitoring(self):
        """Останавливает мониторинг"""
        self.update_timer.stop()

    def showEvent(self, event):
        """Автозапуск мониторинга при показе страницы"""
        super().showEvent(event)
        self.start_monitoring()

    def hideEvent(self, event):
        """Остановка мониторинга при скрытии страницы"""
        super().hideEvent(event)
        self.stop_monitoring()

    def set_learned_data(self, data: dict):
        """Устанавливает данные обучения"""
        self._update_domains(data)

    # ==================== LOG HISTORY METHODS ====================

    def _update_log_history(self):
        """Обновляет список истории логов"""
        self.log_history_list.clear()

        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                logs = app.orchestra_runner.get_log_history()

                for log_info in logs:
                    # Форматируем отображение
                    is_current = log_info.get('is_current', False)
                    prefix = "▶ " if is_current else "  "
                    suffix = " (текущий)" if is_current else ""

                    text = f"{prefix}{log_info['created']} | {log_info['size_str']}{suffix}"
                    item = QListWidgetItem(text)
                    item.setData(Qt.ItemDataRole.UserRole, log_info['id'])

                    if is_current:
                        item.setForeground(Qt.GlobalColor.green)

                    self.log_history_list.addItem(item)

                if not logs:
                    item = QListWidgetItem("  Нет сохранённых логов")
                    item.setForeground(Qt.GlobalColor.gray)
                    self.log_history_list.addItem(item)

        except Exception as e:
            log(f"Ошибка обновления истории логов: {e}", "DEBUG")

    def _view_log_history(self):
        """Просматривает выбранный лог из истории"""
        current = self.log_history_list.currentItem()
        if not current:
            return

        log_id = current.data(Qt.ItemDataRole.UserRole)
        if not log_id:
            return

        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                content = app.orchestra_runner.get_log_content(log_id)
                if content:
                    # Очищаем текущий лог и показываем содержимое выбранного
                    self.log_text.clear()
                    self.log_text.setPlainText(content)
                    self.append_log(f"\n[INFO] === Загружен лог: {log_id} ===")
                else:
                    self.append_log(f"[ERROR] Не удалось прочитать лог: {log_id}")
        except Exception as e:
            log(f"Ошибка просмотра лога: {e}", "DEBUG")

    def _delete_log_history(self):
        """Удаляет выбранный лог из истории"""
        current = self.log_history_list.currentItem()
        if not current:
            return

        log_id = current.data(Qt.ItemDataRole.UserRole)
        if not log_id:
            return

        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                if app.orchestra_runner.delete_log(log_id):
                    self._update_log_history()
                    self.append_log(f"[INFO] Удалён лог: {log_id}")
                else:
                    self.append_log(f"[WARNING] Не удалось удалить лог (возможно, активный)")
        except Exception as e:
            log(f"Ошибка удаления лога: {e}", "DEBUG")

    def _clear_all_log_history(self):
        """Удаляет все логи из истории"""
        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                deleted = app.orchestra_runner.clear_all_logs()
                self._update_log_history()
                if deleted > 0:
                    self.append_log(f"[INFO] Удалено {deleted} лог-файлов")
                else:
                    self.append_log("[INFO] Нет логов для удаления")
        except Exception as e:
            log(f"Ошибка очистки истории логов: {e}", "DEBUG")

    # Методы _show_block_strategy_dialog, _show_lock_strategy_dialog,
    # _show_manage_blocked_dialog, _show_manage_locked_dialog удалены -
    # функционал перенесён в отдельные страницы:
    # - OrchestraLockedPage (ui/pages/orchestra_locked_page.py)
    # - OrchestraBlockedPage (ui/pages/orchestra_blocked_page.py)

    def _show_log_context_menu(self, pos):
        """Показывает контекстное меню для строки лога"""
        from PyQt6.QtWidgets import QMenu

        # Получаем текущую строку под курсором
        cursor = self.log_text.cursorForPosition(pos)
        cursor.select(cursor.SelectionType.LineUnderCursor)
        line_text = cursor.selectedText().strip()

        if not line_text:
            return

        # Парсим строку для извлечения домена и стратегии
        parsed = self._parse_log_line_for_strategy(line_text)

        # Создаём контекстное меню
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
            QMenu::separator {
                height: 1px;
                background: #3d3d3d;
                margin: 4px 8px;
            }
        """)

        # Стандартные действия
        copy_action = QAction("📋 Копировать строку", self)
        copy_action.triggered.connect(lambda: self._copy_line_to_clipboard(line_text))
        menu.addAction(copy_action)

        if parsed:
            domain, strategy, protocol = parsed
            menu.addSeparator()

            # Проверяем, заблокирована ли уже эта стратегия
            is_blocked = False
            try:
                app = self.window()
                if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                    is_blocked = app.orchestra_runner.blocked_manager.is_blocked(domain, strategy)
            except Exception:
                pass

            if strategy > 0:
                # Действие залочивания стратегии (сайт работает)
                lock_action = QAction(f"🔒 Залочить стратегию #{strategy} для {domain}", self)
                lock_action.triggered.connect(lambda: self._lock_strategy_from_log(domain, strategy, protocol))
                menu.addAction(lock_action)

                if is_blocked:
                    # Действие разблокировки стратегии
                    unblock_action = QAction(f"✅ Разблокировать стратегию #{strategy} для {domain}", self)
                    unblock_action.triggered.connect(lambda: self._unblock_strategy_from_log(domain, strategy, protocol))
                    menu.addAction(unblock_action)
                else:
                    # Действие блокировки стратегии
                    block_action = QAction(f"🚫 Заблокировать стратегию #{strategy} для {domain}", self)
                    block_action.triggered.connect(lambda: self._block_strategy_from_log(domain, strategy, protocol))
                    menu.addAction(block_action)

            # Действие добавления в whitelist (если сайт работает)
            whitelist_action = QAction(f"⬚ Добавить {domain} в белый список", self)
            whitelist_action.triggered.connect(lambda: self._add_to_whitelist_from_log(domain))
            menu.addAction(whitelist_action)

        menu.exec(self.log_text.mapToGlobal(pos))

    def _parse_log_line_for_strategy(self, line: str) -> tuple:
        """Парсит строку лога и извлекает домен, стратегию и протокол

        Форматы строк:
        - "[20:17:14] ✓ SUCCESS: qms.ru :443 strategy=1"
        - "[19:55:15] ✓ SUCCESS: youtube.com :443 strategy=5 [tls]"
        - "[19:55:15] ✗ FAIL: youtube.com :443 strategy=5"
        - "[19:55:15] 🔒 LOCKED: youtube.com :443 = strategy 5"
        - "[19:55:15] 🔓 UNLOCKED: youtube.com :443 - re-learning..."
        - "[HH:MM:SS] ✓ SUCCESS: domain UDP strategy=1"
        """
        import re

        # Паттерн для SUCCESS/FAIL с :порт strategy=N
        # Примеры: "SUCCESS: qms.ru :443 strategy=1"
        match = re.search(r'(?:SUCCESS|FAIL):\s*(\S+)\s+:(\d+)\s+strategy[=:](\d+)', line, re.IGNORECASE)
        if match:
            domain = match.group(1)
            port = match.group(2)
            strategy = int(match.group(3))
            protocol = "tls" if port == "443" else ("http" if port == "80" else "udp")
            return (domain, strategy, protocol)

        # Паттерн для SUCCESS/FAIL с UDP strategy=N
        # Примеры: "SUCCESS: domain UDP strategy=1"
        match = re.search(r'(?:SUCCESS|FAIL):\s*(\S+)\s+UDP\s+strategy[=:](\d+)', line, re.IGNORECASE)
        if match:
            domain = match.group(1)
            strategy = int(match.group(2))
            return (domain, strategy, "udp")

        # Паттерн для LOCKED: domain :порт = strategy N
        match = re.search(r'LOCKED:\s*(\S+)\s+:(\d+)\s*=\s*strategy\s+(\d+)', line, re.IGNORECASE)
        if match:
            domain = match.group(1)
            port = match.group(2)
            strategy = int(match.group(3))
            protocol = "tls" if port == "443" else ("http" if port == "80" else "udp")
            return (domain, strategy, protocol)

        # Паттерн для UNLOCKED (без стратегии, но с доменом)
        match = re.search(r'UNLOCKED:\s*(\S+)\s+:(\d+)', line, re.IGNORECASE)
        if match:
            domain = match.group(1)
            port = match.group(2)
            protocol = "tls" if port == "443" else ("http" if port == "80" else "udp")
            # Стратегия неизвестна при UNLOCK, возвращаем 0
            return (domain, 0, protocol)

        return None

    def _copy_line_to_clipboard(self, text: str):
        """Копирует текст в буфер обмена"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.append_log("[INFO] Строка скопирована в буфер обмена")

    def _lock_strategy_from_log(self, domain: str, strategy: int, protocol: str):
        """Залочивает стратегию из контекстного меню лога"""
        if strategy == 0:
            self.append_log("[WARNING] Невозможно залочить: стратегия неизвестна")
            return

        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                runner = app.orchestra_runner
                runner.locked_manager.lock(domain, strategy, protocol)
                self.append_log(f"[INFO] 🔒 Залочена стратегия #{strategy} для {domain} [{protocol.upper()}]")
                self._update_learned_domains()
            else:
                self.append_log("[ERROR] Оркестратор не инициализирован")
        except Exception as e:
            log(f"Ошибка залочивания из контекстного меню: {e}", "ERROR")
            self.append_log(f"[ERROR] Ошибка: {e}")

    def _block_strategy_from_log(self, domain: str, strategy: int, protocol: str):
        """Блокирует стратегию из контекстного меню лога"""
        if strategy == 0:
            self.append_log("[WARNING] Невозможно заблокировать: стратегия неизвестна")
            return

        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                runner = app.orchestra_runner
                runner.blocked_manager.block(domain, strategy, protocol)
                self.append_log(f"[INFO] 🚫 Заблокирована стратегия #{strategy} для {domain} [{protocol.upper()}]")
                self._update_learned_domains()
            else:
                self.append_log("[ERROR] Оркестратор не инициализирован")
        except Exception as e:
            log(f"Ошибка блокировки из контекстного меню: {e}", "ERROR")
            self.append_log(f"[ERROR] Ошибка: {e}")

    def _unblock_strategy_from_log(self, domain: str, strategy: int, protocol: str):
        """Разблокирует стратегию из контекстного меню лога"""
        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                runner = app.orchestra_runner
                runner.blocked_manager.unblock(domain, strategy)
                self.append_log(f"[INFO] ✅ Разблокирована стратегия #{strategy} для {domain} [{protocol.upper()}]")
                self._update_learned_domains()
            else:
                self.append_log("[ERROR] Оркестратор не инициализирован")
        except Exception as e:
            log(f"Ошибка разблокировки из контекстного меню: {e}", "ERROR")
            self.append_log(f"[ERROR] Ошибка: {e}")

    def _add_to_whitelist_from_log(self, domain: str):
        """Добавляет домен в whitelist из контекстного меню лога"""
        try:
            app = self.window()
            if hasattr(app, 'orchestra_runner') and app.orchestra_runner:
                if app.orchestra_runner.add_to_whitelist(domain):
                    self.append_log(f"[INFO] ✅ Добавлен в белый список: {domain}")
                else:
                    self.append_log(f"[WARNING] Не удалось добавить: {domain}")
            else:
                self.append_log("[ERROR] Оркестратор не инициализирован")
        except Exception as e:
            log(f"Ошибка добавления в whitelist из контекстного меню: {e}", "ERROR")
            self.append_log(f"[ERROR] Ошибка: {e}")
