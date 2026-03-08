# ui/pages/premium_page.py
"""Страница управления Premium подпиской"""

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QFrame, QGraphicsOpacityEffect,
    QMessageBox
)
from PyQt6.QtGui import QFont
import qtawesome as qta
import webbrowser
from datetime import datetime

from .base_page import BasePage
from ui.sidebar import SettingsCard, ActionButton


class WorkerThread(QThread):
    """Поток для выполнения операций"""
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, target, args=None):
        super().__init__()
        self.target = target
        self.args = args or ()
        
    def run(self):
        try:
            result = self.target(*self.args)
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))


class AnimatedCard(SettingsCard):
    """Карточка с анимацией появления"""
    
    def __init__(self, title: str = "", delay: int = 0, parent=None):
        super().__init__(title, parent)
        self.delay = delay
        
        # Эффект прозрачности для анимации
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)
        
    def animate_in(self):
        """Запускает анимацию появления"""
        QTimer.singleShot(self.delay, self._do_animate)
        
    def _do_animate(self):
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(400)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.start()


class StatusBadge(QFrame):
    """Бейдж статуса подписки"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBadge")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Иконка
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        layout.addWidget(self.icon_label)
        
        # Текст статуса
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        self.status_label = QLabel("Проверка...")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 15px;
                font-weight: 600;
            }
        """)
        text_layout.addWidget(self.status_label)
        
        self.details_label = QLabel("")
        self.details_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-size: 12px;
            }
        """)
        text_layout.addWidget(self.details_label)
        
        layout.addLayout(text_layout, 1)
        
        self._update_style("neutral")
        
    def set_status(self, text: str, details: str = "", status: str = "neutral"):
        """Устанавливает статус"""
        self.status_label.setText(text)
        self.details_label.setText(details)
        self._update_style(status)
        
    def _update_style(self, status: str):
        colors = {
            'active': ('#6ccb5f', 'rgba(108, 203, 95, 0.15)'),
            'warning': ('#ffc107', 'rgba(255, 193, 7, 0.15)'),
            'expired': ('#ff6b6b', 'rgba(255, 107, 107, 0.15)'),
            'neutral': ('#60cdff', 'rgba(96, 205, 255, 0.1)'),
        }
        
        icon_color, bg_color = colors.get(status, colors['neutral'])
        
        # Иконка
        if status == 'active':
            self.icon_label.setPixmap(qta.icon('fa5s.check-circle', color=icon_color).pixmap(24, 24))
        elif status == 'warning':
            self.icon_label.setPixmap(qta.icon('fa5s.exclamation-triangle', color=icon_color).pixmap(24, 24))
        elif status == 'expired':
            self.icon_label.setPixmap(qta.icon('fa5s.times-circle', color=icon_color).pixmap(24, 24))
        else:
            self.icon_label.setPixmap(qta.icon('fa5s.question-circle', color=icon_color).pixmap(24, 24))
        
        self.setStyleSheet(f"""
            QFrame#statusBadge {{
                background-color: {bg_color};
                border: none;
                border-radius: 8px;
            }}
        """)


class PremiumPage(BasePage):
    """Страница управления Premium подпиской"""
    
    # Сигнал обновления статуса подписки
    subscription_updated = pyqtSignal(bool, int)  # is_premium, days_remaining
    
    def __init__(self, parent=None):
        super().__init__("Premium", "Управление подпиской Zapret Premium", parent)
        
        self.checker = None
        self.current_thread = None
        self._animated_cards = []
        
        self._build_ui()
        
        # Инициализируем checker лениво при первом показе
        self._initialized = False
        
    def showEvent(self, event):
        """При показе страницы запускаем анимации и проверку"""
        super().showEvent(event)
        
        if not self._initialized:
            self._initialized = True
            self._init_checker()
            self._animate_cards()
            QTimer.singleShot(500, self._check_status)
            QTimer.singleShot(800, self._test_connection)  # Автопроверка соединения
        
    def _init_checker(self):
        """Инициализирует checker"""
        try:
            from donater.donate import SimpleDonateChecker, RegistryManager
            self.checker = SimpleDonateChecker()
            self.RegistryManager = RegistryManager
            self._update_device_info()
        except Exception as e:
            from log import log
            log(f"Ошибка инициализации PremiumPage checker: {e}", "ERROR")
            
    def _animate_cards(self):
        """Запускает анимации появления карточек"""
        for card in self._animated_cards:
            card.animate_in()
        
    def _build_ui(self):
        # ═══════════════════════════════════════════════════════════
        # СТАТУС ПОДПИСКИ
        # ═══════════════════════════════════════════════════════════
        self.add_section_title("Статус подписки")
        
        status_card = AnimatedCard(delay=0)
        self._animated_cards.append(status_card)
        
        status_layout = QVBoxLayout()
        status_layout.setSpacing(16)
        
        # Бейдж статуса
        self.status_badge = StatusBadge()
        status_layout.addWidget(self.status_badge)
        
        # Дополнительная информация
        self.days_label = QLabel("")
        self.days_label.setStyleSheet("""
            QLabel {
                color: #60cdff;
                font-size: 24px;
                font-weight: 700;
            }
        """)
        self.days_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.days_label)
        
        status_card.add_layout(status_layout)
        self.add_widget(status_card)
        
        self.add_spacing(8)
        
        # ═══════════════════════════════════════════════════════════
        # АКТИВАЦИЯ КЛЮЧА
        # ═══════════════════════════════════════════════════════════
        self.activation_section_title = self.add_section_title("Активация ключа", return_widget=True)
        
        self.activation_card = AnimatedCard(delay=100)
        activation_card = self.activation_card  # для совместимости с остальным кодом
        self._animated_cards.append(activation_card)
        
        activation_layout = QVBoxLayout()
        activation_layout.setSpacing(12)
        
        # Инструкции (обычный QLabel)
        instructions = QLabel(
            "1. Откройте Telegram бота @zapretvpns_bot\n"
            "2. Выберите подходящий тариф и оплатите\n"
            "3. Получите ключ командой /newkey\n"
            "4. Введите ключ ниже и нажмите «Активировать»"
        )
        instructions.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 6px;
                color: rgba(255, 255, 255, 0.7);
                padding: 12px 16px;
                font-size: 12px;
                line-height: 1.5;
            }
        """)
        instructions.setWordWrap(True)
        activation_layout.addWidget(instructions)
        
        # Кнопка открытия бота
        from config.telegram_links import open_telegram_link
        open_bot_btn = ActionButton("Открыть Telegram бота", "fa5b.telegram")
        open_bot_btn.setFixedHeight(40)
        open_bot_btn.clicked.connect(lambda: open_telegram_link("zapretvpns_bot"))
        activation_layout.addWidget(open_bot_btn)
        
        # ═══════════════════════════════════════════════════════════
        # Контейнер для поля ввода ключа (скрывается при активной подписке)
        # ═══════════════════════════════════════════════════════════
        self.key_input_container = QWidget()
        key_container_layout = QVBoxLayout(self.key_input_container)
        key_container_layout.setContentsMargins(0, 0, 0, 0)
        key_container_layout.setSpacing(8)
        
        # Поле ввода ключа
        key_layout = QHBoxLayout()
        key_layout.setSpacing(8)
        
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.key_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                color: #ffffff;
                padding: 12px 16px;
                font-size: 14px;
                font-family: 'JetBrains Mono', 'Consolas', monospace;
            }
            QLineEdit:focus {
                border-color: #60cdff;
                background-color: rgba(255, 255, 255, 0.08);
            }
        """)
        key_layout.addWidget(self.key_input, 1)
        
        self.activate_btn = ActionButton("Активировать", "fa5s.key", accent=True)
        self.activate_btn.setFixedHeight(36)
        self.activate_btn.setMinimumWidth(140)
        self.activate_btn.clicked.connect(self._activate_key)
        key_layout.addWidget(self.activate_btn)
        
        key_container_layout.addLayout(key_layout)
        
        # Статус активации
        self.activation_status = QLabel("")
        self.activation_status.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px;")
        self.activation_status.setWordWrap(True)
        key_container_layout.addWidget(self.activation_status)
        
        activation_layout.addWidget(self.key_input_container)
        
        activation_card.add_layout(activation_layout)
        self.add_widget(activation_card)
        
        self.add_spacing(8)
        
        # ═══════════════════════════════════════════════════════════
        # ИНФОРМАЦИЯ ОБ УСТРОЙСТВЕ
        # ═══════════════════════════════════════════════════════════
        self.add_section_title("Информация об устройстве")
        
        device_card = AnimatedCard(delay=200)
        self._animated_cards.append(device_card)
        
        device_layout = QVBoxLayout()
        device_layout.setSpacing(8)
        
        # ID устройства
        self.device_id_label = QLabel("ID устройства: загрузка...")
        self.device_id_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.7);
                font-size: 12px;
                font-family: 'JetBrains Mono', 'Consolas', monospace;
            }
        """)
        device_layout.addWidget(self.device_id_label)
        
        # Сохранённый ключ
        self.saved_key_label = QLabel("Сохранённый ключ: нет")
        self.saved_key_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.7);
                font-size: 12px;
            }
        """)
        device_layout.addWidget(self.saved_key_label)
        
        # Последняя проверка
        self.last_check_label = QLabel("Последняя проверка: —")
        self.last_check_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.5);
                font-size: 11px;
            }
        """)
        device_layout.addWidget(self.last_check_label)
        
        # Статус сервера
        self.server_status_label = QLabel("Сервер: проверка...")
        self.server_status_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.5);
                font-size: 11px;
            }
        """)
        device_layout.addWidget(self.server_status_label)
        
        device_card.add_layout(device_layout)
        self.add_widget(device_card)
        
        self.add_spacing(8)
        
        # ═══════════════════════════════════════════════════════════
        # ДЕЙСТВИЯ
        # ═══════════════════════════════════════════════════════════
        self.add_section_title("Действия")
        
        actions_card = AnimatedCard(delay=300)
        self._animated_cards.append(actions_card)
        
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(8)
        
        # Ряд 1: Обновить и Изменить ключ
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        
        self.refresh_btn = ActionButton("Обновить статус", "fa5s.sync")
        self.refresh_btn.setFixedHeight(36)
        self.refresh_btn.clicked.connect(self._check_status)
        row1.addWidget(self.refresh_btn)
        
        self.change_key_btn = ActionButton("Изменить ключ", "fa5s.exchange-alt")
        self.change_key_btn.setFixedHeight(36)
        self.change_key_btn.clicked.connect(self._change_key)
        row1.addWidget(self.change_key_btn)
        
        row1.addStretch()
        actions_layout.addLayout(row1)
        
        # Ряд 2: Проверить соединение и Продлить
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        
        self.test_btn = ActionButton("Проверить соединение", "fa5s.plug")
        self.test_btn.setFixedHeight(36)
        self.test_btn.clicked.connect(self._test_connection)
        row2.addWidget(self.test_btn)
        
        self.extend_btn = ActionButton("Продлить подписку", "fa5b.telegram", accent=True)
        self.extend_btn.setFixedHeight(36)
        self.extend_btn.clicked.connect(lambda: open_telegram_link("zapretvpns_bot"))
        row2.addWidget(self.extend_btn)
        
        row2.addStretch()
        actions_layout.addLayout(row2)
        
        actions_card.add_layout(actions_layout)
        self.add_widget(actions_card)
        
    def _update_device_info(self):
        """Обновляет информацию об устройстве"""
        if not self.checker:
            return
            
        try:
            # Device ID
            device_id = self.checker.device_id
            self.device_id_label.setText(f"ID устройства: {device_id[:16]}...")
            
            # Сохранённый ключ
            key_preview = self.RegistryManager.get_key_preview()
            if key_preview:
                self.saved_key_label.setText(f"Локальный маркер активации: {key_preview}")
                self.saved_key_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 12px;")
            else:
                self.saved_key_label.setText("Локальный маркер активации: не найден")
                self.saved_key_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
            
            # Последняя проверка
            last_check = self.RegistryManager.get_last_check()
            if last_check:
                self.last_check_label.setText(f"Последняя проверка: {last_check.strftime('%d.%m.%Y %H:%M')}")
            else:
                self.last_check_label.setText("Последняя проверка: —")
                
        except Exception as e:
            from log import log
            log(f"Ошибка обновления информации об устройстве: {e}", "DEBUG")
    
    def _set_activation_section_visible(self, visible: bool):
        """Показывает или скрывает поле ввода ключа (инструкция остаётся видимой)"""
        if hasattr(self, 'key_input_container') and self.key_input_container:
            self.key_input_container.setVisible(visible)
            
    def _activate_key(self):
        """Активация ключа"""
        if not self.checker:
            self._init_checker()
            if not self.checker:
                self.activation_status.setText("❌ Ошибка инициализации")
                self.activation_status.setStyleSheet("color: #ff6b6b; font-size: 12px;")
                return
        
        key = self.key_input.text().strip()
        if not key:
            self.activation_status.setText("❌ Введите ключ активации")
            self.activation_status.setStyleSheet("color: #ff6b6b; font-size: 12px;")
            return
        
        # Блокируем кнопку
        self.activate_btn.setEnabled(False)
        self.activate_btn.setText("Активация...")
        self.activation_status.setText("🔄 Проверка ключа...")
        self.activation_status.setStyleSheet("color: #60cdff; font-size: 12px;")
        
        # Запускаем в потоке
        self.current_thread = WorkerThread(self.checker.activate, args=(key,))
        self.current_thread.result_ready.connect(self._on_activation_complete)
        self.current_thread.error_occurred.connect(self._on_activation_error)
        self.current_thread.start()
        
    def _on_activation_complete(self, result):
        """Обработка результата активации"""
        success, message = result
        
        self.activate_btn.setEnabled(True)
        self.activate_btn.setText("Активировать")
        
        if success:
            self.activation_status.setText("✅ Ключ успешно активирован!")
            self.activation_status.setStyleSheet("color: #6ccb5f; font-size: 12px;")
            self._update_device_info()
            # Скрываем секцию активации после успешной активации
            self._set_activation_section_visible(False)
            self._check_status()
            # Эмитим сигнал с корректным days_remaining
            info = self.checker.get_full_subscription_info()
            days = info.get('days_remaining', 0) or 0
            self.subscription_updated.emit(True, days)
        else:
            self.activation_status.setText(f"❌ {message}")
            self.activation_status.setStyleSheet("color: #ff6b6b; font-size: 12px;")
            
    def _on_activation_error(self, error):
        """Обработка ошибки активации"""
        self.activate_btn.setEnabled(True)
        self.activate_btn.setText("Активировать")
        self.activation_status.setText(f"❌ Ошибка: {error}")
        self.activation_status.setStyleSheet("color: #ff6b6b; font-size: 12px;")
        
    def _check_status(self):
        """Проверка статуса подписки"""
        if not self.checker:
            self._init_checker()
            if not self.checker:
                self.status_badge.set_status("Ошибка", "Не удалось инициализировать", "expired")
                return
        
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Проверка...")
        self.status_badge.set_status("Проверка...", "Подключение к серверу", "neutral")
        
        self.current_thread = WorkerThread(self.checker.check_device_activation)
        self.current_thread.result_ready.connect(self._on_status_complete)
        self.current_thread.error_occurred.connect(self._on_status_error)
        self.current_thread.start()
        
    def _on_status_complete(self, result):
        """Обработка результата проверки статуса"""
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Обновить статус")
        self._update_device_info()
        
        if result is None or not isinstance(result, dict):
            self.status_badge.set_status("Ошибка", "Неверный ответ сервера", "expired")
            return
        
        if 'activated' not in result:
            self.status_badge.set_status("Ошибка", "Неполный ответ", "expired")
            return
        
        try:
            has_local_key = self.RegistryManager and self.RegistryManager.has_key()
            source = result.get('source', 'server')
            
            if result['activated'] and has_local_key:
                days_remaining = result.get('days_remaining')
                self._set_activation_section_visible(False)

                if source == 'grace':
                    hours_remaining = result.get('grace_hours_remaining')
                    details = result.get('status', '')
                    if hours_remaining:
                        details = f"Оффлайн-доступ еще {hours_remaining} ч."
                    self.status_badge.set_status("Нужна сверка с сервером", details, "warning")
                    self.days_label.setText("")
                    self.subscription_updated.emit(True, 0)
                elif days_remaining is not None:
                    if days_remaining > 30:
                        self.status_badge.set_status("Подписка активна", f"Осталось {days_remaining} дней", "active")
                        self.days_label.setText(f"Осталось дней: {days_remaining}")
                        self.days_label.setStyleSheet("color: #6ccb5f; font-size: 24px; font-weight: 700;")
                    elif days_remaining > 7:
                        self.status_badge.set_status("Подписка активна", f"Осталось {days_remaining} дней", "warning")
                        self.days_label.setText(f"⚠️ Осталось дней: {days_remaining}")
                        self.days_label.setStyleSheet("color: #ffc107; font-size: 24px; font-weight: 700;")
                    else:
                        self.status_badge.set_status("Скоро истекает!", f"Осталось {days_remaining} дней", "warning")
                        self.days_label.setText(f"⚠️ Срочно продлите! Осталось: {days_remaining}")
                        self.days_label.setStyleSheet("color: #ff6b6b; font-size: 24px; font-weight: 700;")
                    
                    # Эмитим сигнал обновления
                    self.subscription_updated.emit(True, days_remaining)
                else:
                    self.status_badge.set_status("Подписка активна", result.get('status', ''), "active")
                    self.days_label.setText("")
                    self.subscription_updated.emit(True, 0)
            else:
                self._set_activation_section_visible(True)
                
                if result['activated'] and not has_local_key:
                    self.status_badge.set_status("Требуется активация", "Введите ключ для восстановления подписки", "expired")
                else:
                    self.status_badge.set_status("Подписка не активна", result.get('status', 'Активируйте ключ'), "expired")
                
                self.days_label.setText("")
                self.subscription_updated.emit(False, 0)
                
        except Exception as e:
            self.status_badge.set_status("Ошибка", str(e), "expired")
            # При ошибке показываем секцию активации на всякий случай
            self._set_activation_section_visible(True)
            
    def _on_status_error(self, error):
        """Обработка ошибки проверки статуса"""
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Обновить статус")
        self.status_badge.set_status("Ошибка проверки", error, "expired")
        
    def _test_connection(self):
        """Тест соединения с сервером"""
        if not self.checker:
            self._init_checker()
            if not self.checker:
                self.server_status_label.setText("❌ Ошибка инициализации")
                self.server_status_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
                return
            
        self.test_btn.setEnabled(False)
        self.test_btn.setText("Проверка...")
        self.server_status_label.setText("🔄 Проверка соединения...")
        self.server_status_label.setStyleSheet("color: #60cdff; font-size: 11px;")
        
        self.current_thread = WorkerThread(self.checker.test_connection)
        self.current_thread.result_ready.connect(self._on_connection_test_complete)
        self.current_thread.error_occurred.connect(self._on_connection_test_error)
        self.current_thread.start()
        
    def _on_connection_test_complete(self, result):
        """Обработка результата теста соединения"""
        success, message = result
        self.test_btn.setEnabled(True)
        self.test_btn.setText("Проверить соединение")
        
        if success:
            self.server_status_label.setText(f"✅ {message}")
            self.server_status_label.setStyleSheet("color: #6ccb5f; font-size: 11px;")
        else:
            self.server_status_label.setText(f"❌ {message}")
            self.server_status_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
            
    def _on_connection_test_error(self, error):
        """Обработка ошибки теста соединения"""
        self.test_btn.setEnabled(True)
        self.test_btn.setText("Проверить соединение")
        self.server_status_label.setText(f"❌ Ошибка: {error}")
        self.server_status_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
        
    def _change_key(self):
        """Изменение ключа"""
        reply = QMessageBox.question(
            self, 
            "Подтверждение", 
            "Вы уверены, что хотите изменить ключ?\n"
            "Текущий ключ будет удален и подписка станет FREE\n"
            "до повторной активации.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.RegistryManager:
                self.RegistryManager.delete_key()
            self.key_input.clear()
            self.activation_status.setText("")
            self._update_device_info()
            self.status_badge.set_status("Ключ удалён", "Введите новый ключ для активации", "expired")
            self.days_label.setText("")
            
            # Показываем секцию активации
            self._set_activation_section_visible(True)
            
            # Уведомляем остальные компоненты что подписка теперь FREE
            self.subscription_updated.emit(False, 0)
            
    def closeEvent(self, event):
        """Обработка закрытия"""
        if self.current_thread and self.current_thread.isRunning():
            self.current_thread.quit()
            self.current_thread.wait()
        event.accept()

