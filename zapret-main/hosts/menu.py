from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, 
                            QPushButton, QLabel, QScrollArea, QWidget, 
                            QGroupBox, QGridLayout)
from PyQt6.QtCore import Qt
from .proxy_domains import PROXY_DOMAINS

class HostsSelectorDialog(QDialog):
    def __init__(self, parent=None, current_active_domains=None):
        super().__init__(parent)
        self.current_active_domains = current_active_domains or set()
        self.selected_domains = set(self.current_active_domains)
        self.domain_checkboxes = {}
        
        self.setWindowTitle("Выбор сервисов для проксирования через hosts")
        self.setModal(True)
        self.resize(600, 500)
        
        self.setup_ui()
        self.apply_styles()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Заголовок
        title = QLabel("Выберите сервисы для проксирования через файл hosts:")
        title.setStyleSheet("font-size: 12pt; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Кнопки массового выбора
        buttons_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Выбрать все")
        select_all_btn.clicked.connect(self.select_all)
        buttons_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Снять все")
        deselect_all_btn.clicked.connect(self.deselect_all)
        buttons_layout.addWidget(deselect_all_btn)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        # Область прокрутки со списком доменов
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Группировка доменов по сервисам
        services = self.group_domains_by_service()
        
        for service_name, domains in services.items():
            group_box = QGroupBox(service_name)
            group_layout = QGridLayout()
            
            row = 0
            col = 0
            for domain in sorted(domains):
                checkbox = QCheckBox(domain)
                checkbox.setChecked(domain in self.current_active_domains)
                checkbox.stateChanged.connect(lambda state, d=domain: self.on_domain_toggled(d, state))
                
                self.domain_checkboxes[domain] = checkbox
                group_layout.addWidget(checkbox, row, col)
                
                col += 1
                if col >= 2:  # 2 колонки
                    col = 0
                    row += 1
            
            group_box.setLayout(group_layout)
            scroll_layout.addWidget(group_box)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Кнопки действий
        buttons_layout = QHBoxLayout()
        
        ok_button = QPushButton("Применить")
        ok_button.clicked.connect(self.accept)
        buttons_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        
        layout.addLayout(buttons_layout)
        
    def group_domains_by_service(self):
        """Группирует домены по сервисам"""
        services = {
            "ChatGPT / OpenAI": [],
            "Google AI (Gemini)": [],
            "Microsoft Copilot": [],
            "Социальные сети": [],
            "Spotify": [],
            "GitHub": [],
            "Разработка": [],
            "Другие сервисы": []
        }
        
        for domain in PROXY_DOMAINS.keys():
            if any(x in domain.lower() for x in ['openai', 'chatgpt', 'oai']):
                services["ChatGPT / OpenAI"].append(domain)
            elif any(x in domain.lower() for x in ['gemini', 'google', 'generativelanguage']):
                services["Google AI (Gemini)"].append(domain)
            elif any(x in domain.lower() for x in ['microsoft', 'bing', 'copilot', 'xbox']):
                services["Microsoft Copilot"].append(domain)
            elif any(x in domain.lower() for x in ['facebook', 'instagram', 'tiktok', 'truthsocial']):
                services["Социальные сети"].append(domain)
            elif 'spotify' in domain.lower():
                services["Spotify"].append(domain)
            elif any(x in domain.lower() for x in ['github', 'jetbrains']):
                services["GitHub"].append(domain)
            elif any(x in domain.lower() for x in ['codeium', 'elevenlabs', 'nvidia', 'intel', 'dell', 'autodesk']):
                services["Разработка"].append(domain)
            else:
                services["Другие сервисы"].append(domain)
        
        # Удаляем пустые группы
        return {k: v for k, v in services.items() if v}
    
    def on_domain_toggled(self, domain, state):
        """Обработка изменения состояния чекбокса"""
        if state == Qt.CheckState.Checked.value:
            self.selected_domains.add(domain)
        else:
            self.selected_domains.discard(domain)
    
    def select_all(self):
        """Выбрать все домены"""
        for checkbox in self.domain_checkboxes.values():
            checkbox.setChecked(True)
    
    def deselect_all(self):
        """Снять выбор со всех доменов"""
        for checkbox in self.domain_checkboxes.values():
            checkbox.setChecked(False)
    
    def get_selected_domains(self):
        """Возвращает выбранные домены"""
        return self.selected_domains
    
    def apply_styles(self):
        """Применяет стили точно как в StrategySelector"""
        # Здесь будет применён стиль точно как в strategy_menu/selector.py
        pass  # Стили будут установлены через глобальную тему
