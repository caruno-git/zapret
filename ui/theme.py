# ui/theme.py
import os
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, pyqtProperty, QThread, QObject, pyqtSignal
from PyQt6.QtGui import QPixmap, QPalette, QBrush, QPainter, QColor
from PyQt6.QtWidgets import QPushButton, QMessageBox, QApplication, QMenu, QWidget
from config import reg, HKCU, THEME_FOLDER
from log import log
from typing import Optional, Tuple
import time

# Константы - Windows 11 style мягкие цвета
# bg_color - цвет фона окна (для цветных тем - тёмный оттенок основного цвета)
THEMES = {
    # Мягкие пастельные оттенки в стиле Windows 11
    # Темная синяя - оставляем оригинальный тёмно-серый фон
    "Темная синяя": {"file": "dark_blue.xml", "status_color": "#ffffff", "button_color": "76, 142, 231", "bg_color": "30, 32, 32"},
    # Бирюзовая - тёмный бирюзовый фон
    "Темная бирюзовая": {"file": "dark_cyan.xml", "status_color": "#ffffff", "button_color": "56, 178, 205", "bg_color": "20, 35, 38"},
    # Янтарная - тёмный янтарный/коричневый фон
    "Темная янтарная": {"file": "dark_amber.xml", "status_color": "#ffffff", "button_color": "234, 162, 62", "bg_color": "38, 32, 20"},
    # Розовая - тёмный розовато-фиолетовый фон
    "Темная розовая": {"file": "dark_pink.xml", "status_color": "#ffffff", "button_color": "232, 121, 178", "bg_color": "38, 24, 32"},
    # Светлые темы
    "Светлая синяя": {"file": "light_blue.xml", "status_color": "#000000", "button_color": "68, 136, 217", "bg_color": "230, 235, 245"},
    "Светлая бирюзовая": {"file": "light_cyan.xml", "status_color": "#000000", "button_color": "48, 185, 206", "bg_color": "225, 242, 245"},
    # РКН Тян - используют кастомный фон (изображения)
    "РКН Тян": {"file": "dark_blue.xml", "status_color": "#ffffff", "button_color": "99, 117, 198", "bg_color": "32, 32, 32"},
    "РКН Тян 2": {"file": "dark_purple.xml", "status_color": "#ffffff", "button_color": "186, 125, 186", "bg_color": "32, 32, 32"},
    
    # Премиум AMOLED темы - чёрный фон для экономии энергии
    "AMOLED Синяя": {"file": "dark_blue.xml", "status_color": "#ffffff", "button_color": "62, 148, 255", "amoled": True, "bg_color": "0, 0, 0"},
    "AMOLED Зеленая": {"file": "dark_teal.xml", "status_color": "#ffffff", "button_color": "76, 217, 147", "amoled": True, "bg_color": "0, 0, 0"},
    "AMOLED Фиолетовая": {"file": "dark_purple.xml", "status_color": "#ffffff", "button_color": "178, 142, 246", "amoled": True, "bg_color": "0, 0, 0"},
    "AMOLED Красная": {"file": "dark_red.xml", "status_color": "#ffffff", "button_color": "235, 108, 108", "amoled": True, "bg_color": "0, 0, 0"},
    
    # Полностью черная тема (премиум)
    "Полностью черная": {
        "file": "dark_blue.xml", 
        "status_color": "#ffffff", 
        "button_color": "48, 48, 48",
        "pure_black": True,
        "bg_color": "0, 0, 0"
    },
}

# Windows 11 style gradient button
BUTTON_STYLE = """
QPushButton {{
    border: none;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba({0}, 255),
        stop:0.4 rgba({0}, 230),
        stop:1 rgba({0}, 200)
    );
    color: #fff;
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 600;
    font-size: 9pt;
    min-height: 28px;
}}
QPushButton:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba({0}, 255),
        stop:0.3 rgba({0}, 255),
        stop:1 rgba({0}, 220)
    );
    border: 1px solid rgba(255, 255, 255, 0.15);
}}
QPushButton:pressed {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba({0}, 180),
        stop:1 rgba({0}, 160)
    );
}}
"""

COMMON_STYLE = "font-family: 'Segoe UI Variable', 'Segoe UI', Arial, sans-serif;"
BUTTON_HEIGHT = 28

# Радиус скругления углов окна
WINDOW_BORDER_RADIUS = 10


# ═══════════════════════════════════════════════════════════════════════════════
# ЭФФЕКТ РАЗМЫТИЯ (Acrylic/Mica) для Windows 10/11
# ═══════════════════════════════════════════════════════════════════════════════

class BlurEffect:
    """Класс для управления эффектом размытия окна (Windows Acrylic/Mica)."""

    # Константы Windows API
    DWMWA_SYSTEMBACKDROP_TYPE = 38
    DWMSBT_NONE = 1           # Без эффекта
    DWMSBT_MAINWINDOW = 2     # Mica
    DWMSBT_TRANSIENTWINDOW = 3  # Acrylic
    DWMSBT_TABBEDWINDOW = 4   # Tabbed

    # Для Windows 10 (Acrylic через AccentPolicy)
    ACCENT_DISABLED = 0
    ACCENT_ENABLE_BLURBEHIND = 3
    ACCENT_ENABLE_ACRYLICBLURBEHIND = 4

    # Window Corner Preference для Windows 11 (убирает белые треугольники)
    DWMWA_WINDOW_CORNER_PREFERENCE = 33
    DWMWCP_DEFAULT = 0       # Системное поведение
    DWMWCP_DONOTROUND = 1    # Без скругления (для frameless + CSS border-radius)
    DWMWCP_ROUND = 2         # Системное скругление
    DWMWCP_ROUNDSMALL = 3    # Малое скругление

    _enabled = False
    _hwnd = None

    @classmethod
    def is_supported(cls) -> bool:
        """Проверяет поддержку blur эффекта на текущей системе."""
        import sys
        if sys.platform != 'win32':
            return False
        try:
            import ctypes
            # Проверяем версию Windows
            version = sys.getwindowsversion()
            # Windows 10 build 17134+ или Windows 11
            return version.major >= 10 and version.build >= 17134
        except Exception:
            return False

    @classmethod
    def enable(cls, hwnd: int, blur_type: str = "acrylic") -> bool:
        """
        Включает эффект размытия для окна.

        Args:
            hwnd: Handle окна (HWND)
            blur_type: Тип размытия - "acrylic", "mica" или "blur"

        Returns:
            True если успешно, False если ошибка
        """
        if not cls.is_supported():
            log("❌ Blur эффект не поддерживается на этой системе", "WARNING")
            return False

        try:
            import ctypes
            from ctypes import windll, byref, c_int, sizeof, Structure, POINTER, c_uint, c_void_p
            import sys

            cls._hwnd = hwnd
            version = sys.getwindowsversion()

            # Windows 11 (build 22000+) - используем новый API
            if version.build >= 22000:
                return cls._enable_windows11(hwnd, blur_type)
            else:
                # Windows 10 - используем AccentPolicy
                return cls._enable_windows10(hwnd, blur_type)

        except Exception as e:
            log(f"❌ Ошибка включения blur эффекта: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            return False

    @classmethod
    def _enable_windows11(cls, hwnd: int, blur_type: str) -> bool:
        """Включает blur на Windows 11 через DwmSetWindowAttribute."""
        try:
            import ctypes
            from ctypes import windll, byref, c_int, sizeof

            dwmapi = windll.dwmapi

            # ВАЖНО: Отключаем системное скругление углов чтобы убрать белые треугольники
            # Приложение использует frameless окно с CSS border-radius
            corner_preference = c_int(cls.DWMWCP_DONOTROUND)
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                cls.DWMWA_WINDOW_CORNER_PREFERENCE,
                byref(corner_preference),
                sizeof(corner_preference)
            )

            # Выбираем тип backdrop
            if blur_type == "mica":
                backdrop_type = cls.DWMSBT_MAINWINDOW
            elif blur_type == "acrylic":
                backdrop_type = cls.DWMSBT_TRANSIENTWINDOW
            else:
                backdrop_type = cls.DWMSBT_TRANSIENTWINDOW

            value = c_int(backdrop_type)
            result = dwmapi.DwmSetWindowAttribute(
                hwnd,
                cls.DWMWA_SYSTEMBACKDROP_TYPE,
                byref(value),
                sizeof(value)
            )

            if result == 0:
                cls._enabled = True
                log(f"✅ Windows 11 blur эффект ({blur_type}) включён", "INFO")
                return True
            else:
                log(f"⚠️ DwmSetWindowAttribute вернул код {result}", "WARNING")
                return False

        except Exception as e:
            log(f"❌ Ошибка Windows 11 blur: {e}", "ERROR")
            return False

    @classmethod
    def _enable_windows10(cls, hwnd: int, blur_type: str) -> bool:
        """Включает blur на Windows 10 через SetWindowCompositionAttribute."""
        try:
            import ctypes
            from ctypes import windll, byref, sizeof, Structure, c_int, POINTER
            from ctypes.wintypes import DWORD, BOOL

            # Структура ACCENT_POLICY
            class ACCENT_POLICY(Structure):
                _fields_ = [
                    ("AccentState", DWORD),
                    ("AccentFlags", DWORD),
                    ("GradientColor", DWORD),
                    ("AnimationId", DWORD),
                ]

            # Структура WINDOWCOMPOSITIONATTRIBDATA
            class WINDOWCOMPOSITIONATTRIBDATA(Structure):
                _fields_ = [
                    ("Attribute", DWORD),
                    ("Data", ctypes.POINTER(ACCENT_POLICY)),
                    ("SizeOfData", ctypes.c_size_t),
                ]

            # Получаем функцию SetWindowCompositionAttribute
            SetWindowCompositionAttribute = windll.user32.SetWindowCompositionAttribute
            SetWindowCompositionAttribute.argtypes = [ctypes.c_void_p, POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
            SetWindowCompositionAttribute.restype = BOOL

            # Настраиваем AccentPolicy
            # AccentFlags: 2 - показывать на неактивном окне тоже
            # GradientColor: ARGB цвет тонировки (A = прозрачность)
            accent = ACCENT_POLICY()
            accent.AccentState = cls.ACCENT_ENABLE_ACRYLICBLURBEHIND
            accent.AccentFlags = 2
            # Тёмный полупрозрачный тон: 0xCC1E1E1E (CC = ~80% непрозрачность)
            accent.GradientColor = 0xCC1E1E1E
            accent.AnimationId = 0

            # WCA_ACCENT_POLICY = 19
            data = WINDOWCOMPOSITIONATTRIBDATA()
            data.Attribute = 19
            data.Data = ctypes.pointer(accent)
            data.SizeOfData = sizeof(accent)

            result = SetWindowCompositionAttribute(hwnd, byref(data))

            if result:
                cls._enabled = True
                log("✅ Windows 10 Acrylic blur эффект включён", "INFO")
                return True
            else:
                log("⚠️ SetWindowCompositionAttribute не сработал", "WARNING")
                return False

        except Exception as e:
            log(f"❌ Ошибка Windows 10 blur: {e}", "ERROR")
            return False

    @classmethod
    def disable(cls, hwnd: int = None) -> bool:
        """Выключает эффект размытия."""
        if hwnd is None:
            hwnd = cls._hwnd

        if hwnd is None:
            return False

        try:
            import ctypes
            from ctypes import windll, byref, c_int, sizeof, Structure, POINTER
            from ctypes.wintypes import DWORD, BOOL
            import sys

            version = sys.getwindowsversion()

            if version.build >= 22000:
                # Windows 11
                dwmapi = windll.dwmapi

                # Сохраняем отключённое скругление (CSS border-radius)
                corner_preference = c_int(cls.DWMWCP_DONOTROUND)
                dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    cls.DWMWA_WINDOW_CORNER_PREFERENCE,
                    byref(corner_preference),
                    sizeof(corner_preference)
                )

                value = c_int(cls.DWMSBT_NONE)
                dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    cls.DWMWA_SYSTEMBACKDROP_TYPE,
                    byref(value),
                    sizeof(value)
                )
            else:
                # Windows 10
                class ACCENT_POLICY(Structure):
                    _fields_ = [
                        ("AccentState", DWORD),
                        ("AccentFlags", DWORD),
                        ("GradientColor", DWORD),
                        ("AnimationId", DWORD),
                    ]

                class WINDOWCOMPOSITIONATTRIBDATA(Structure):
                    _fields_ = [
                        ("Attribute", DWORD),
                        ("Data", ctypes.POINTER(ACCENT_POLICY)),
                        ("SizeOfData", ctypes.c_size_t),
                    ]

                SetWindowCompositionAttribute = windll.user32.SetWindowCompositionAttribute
                SetWindowCompositionAttribute.argtypes = [ctypes.c_void_p, POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
                SetWindowCompositionAttribute.restype = BOOL

                accent = ACCENT_POLICY()
                accent.AccentState = cls.ACCENT_DISABLED
                accent.AccentFlags = 0
                accent.GradientColor = 0
                accent.AnimationId = 0

                data = WINDOWCOMPOSITIONATTRIBDATA()
                data.Attribute = 19
                data.Data = ctypes.pointer(accent)
                data.SizeOfData = sizeof(accent)

                SetWindowCompositionAttribute(hwnd, byref(data))

            cls._enabled = False
            log("✅ Blur эффект выключен", "INFO")
            return True

        except Exception as e:
            log(f"❌ Ошибка выключения blur: {e}", "ERROR")
            return False

    @classmethod
    def is_enabled(cls) -> bool:
        """Возвращает текущее состояние blur эффекта."""
        return cls._enabled

    @classmethod
    def disable_window_rounding(cls, hwnd: int) -> bool:
        """
        Отключает системное скругление углов на Windows 11.
        Нужно вызывать для frameless окон с CSS border-radius чтобы избежать
        белых треугольников по краям.

        Args:
            hwnd: Handle окна (HWND)

        Returns:
            True если успешно или не Windows 11, False при ошибке
        """
        try:
            import sys
            version = sys.getwindowsversion()

            # Только для Windows 11 (build 22000+)
            if version.build < 22000:
                return True

            from ctypes import windll, byref, c_int, sizeof

            dwmapi = windll.dwmapi
            corner_preference = c_int(cls.DWMWCP_DONOTROUND)
            result = dwmapi.DwmSetWindowAttribute(
                hwnd,
                cls.DWMWA_WINDOW_CORNER_PREFERENCE,
                byref(corner_preference),
                sizeof(corner_preference)
            )
            if result == 0:
                log("✅ Системное скругление углов отключено", "DEBUG")
                return True
            return False
        except Exception as e:
            log(f"⚠️ Не удалось отключить скругление углов: {e}", "DEBUG")
            return False

    @classmethod
    def set_tint_color(cls, hwnd: int, argb_color: int) -> bool:
        """
        Устанавливает цвет тонировки для blur эффекта (только Windows 10).

        Args:
            hwnd: Handle окна
            argb_color: Цвет в формате 0xAARRGGBB
        """
        import sys
        version = sys.getwindowsversion()

        if version.build >= 22000:
            # Windows 11 не поддерживает тонировку через этот API
            return False

        # Переприменяем blur с новым цветом
        try:
            import ctypes
            from ctypes import windll, byref, sizeof, Structure, POINTER
            from ctypes.wintypes import DWORD, BOOL

            class ACCENT_POLICY(Structure):
                _fields_ = [
                    ("AccentState", DWORD),
                    ("AccentFlags", DWORD),
                    ("GradientColor", DWORD),
                    ("AnimationId", DWORD),
                ]

            class WINDOWCOMPOSITIONATTRIBDATA(Structure):
                _fields_ = [
                    ("Attribute", DWORD),
                    ("Data", ctypes.POINTER(ACCENT_POLICY)),
                    ("SizeOfData", ctypes.c_size_t),
                ]

            SetWindowCompositionAttribute = windll.user32.SetWindowCompositionAttribute
            SetWindowCompositionAttribute.argtypes = [ctypes.c_void_p, POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
            SetWindowCompositionAttribute.restype = BOOL

            accent = ACCENT_POLICY()
            accent.AccentState = cls.ACCENT_ENABLE_ACRYLICBLURBEHIND
            accent.AccentFlags = 2
            accent.GradientColor = argb_color
            accent.AnimationId = 0

            data = WINDOWCOMPOSITIONATTRIBDATA()
            data.Attribute = 19
            data.Data = ctypes.pointer(accent)
            data.SizeOfData = sizeof(accent)

            return bool(SetWindowCompositionAttribute(hwnd, byref(data)))

        except Exception as e:
            log(f"Ошибка установки цвета blur: {e}", "ERROR")
            return False


AMOLED_OVERRIDE_STYLE = """
QWidget {
    background-color: transparent;
    color: #ffffff;
}

/* НЕ применяем фон к виджетам с кастомным фоном */
QWidget[hasCustomBackground="true"] {
    background-color: transparent;
}

QMainWindow {
    background-color: transparent;
}

/* НЕ применяем фон к главному окну с кастомным фоном */
QMainWindow[hasCustomBackground="true"] {
    background-color: transparent;
}

QFrame#mainContainer {
    background-color: rgba(0, 0, 0, 255);
    border: 1px solid rgba(30, 30, 30, 255);
}

QFrame {
    background-color: transparent;
    border: none;
}

QLabel {
    background-color: transparent;
    color: #ffffff;
    border: none;
}

QComboBox {
    background-color: rgba(26, 26, 26, 255);
    border: 1px solid #333333;
    color: #ffffff;
    padding: 5px;
    border-radius: 4px;
}

QComboBox::drop-down {
    background-color: transparent;
    border: none;
}

QComboBox QAbstractItemView {
    background-color: rgba(0, 0, 0, 250);
    border: 1px solid #333333;
    selection-background-color: #333333;
    color: #ffffff;
}

QStackedWidget {
    background-color: transparent;
    border: none;
}

QStackedWidget > QPushButton {
    border: none;
}

QFrame[frameShape="4"] {
    color: #333333;
    max-height: 1px;
}
"""

PURE_BLACK_OVERRIDE_STYLE = """
QWidget {
    background-color: transparent;
    color: #ffffff;
}

/* НЕ применяем фон к виджетам с кастомным фоном */
QWidget[hasCustomBackground="true"] {
    background-color: transparent;
}

QMainWindow {
    background-color: transparent;
}

/* НЕ применяем фон к главному окну с кастомным фоном */
QMainWindow[hasCustomBackground="true"] {
    background-color: transparent;
}

QFrame#mainContainer {
    background-color: rgba(0, 0, 0, 255);
    border: 1px solid rgba(30, 30, 30, 255);
}

QFrame {
    background-color: transparent;
    border: none;
}

QLabel {
    background-color: transparent;
    color: #ffffff;
}

QComboBox {
    background-color: rgba(0, 0, 0, 250);
    border: none;
    color: #ffffff;
    padding: 5px;
    border-radius: 4px;
}

QComboBox::drop-down {
    background-color: transparent;
    border: none;
}

QComboBox QAbstractItemView {
    background-color: rgba(0, 0, 0, 250);
    border: none;
    selection-background-color: #1a1a1a;
    color: #ffffff;
}

QStackedWidget {
    background-color: transparent;
}

QPushButton {
    background-color: #1a1a1a;
    border: 1px solid #333333;
    color: #ffffff;
}

QPushButton:hover {
    background-color: #333333;
    border: none;
}

QPushButton:pressed {
    background-color: #0a0a0a;
}

QFrame[frameShape="4"] {
    color: #1a1a1a;
}
"""

def get_selected_theme(default: str | None = None) -> str | None:
    """Возвращает сохранённую тему или default"""
    from config import REGISTRY_PATH
    from log import log
    saved = reg(REGISTRY_PATH, "SelectedTheme")
    log(f"📦 Чтение темы из реестра [{REGISTRY_PATH}]: '{saved}' (default: '{default}')", "DEBUG")
    return saved or default

def set_selected_theme(theme_name: str) -> bool:
    """Записывает строку SelectedTheme"""
    from config import REGISTRY_PATH
    from log import log
    result = reg(REGISTRY_PATH, "SelectedTheme", theme_name)
    log(f"💾 Сохранение темы в реестр [{REGISTRY_PATH}]: '{theme_name}' -> {result}", "DEBUG")
    return result

def load_cached_css_sync(theme_name: str = None) -> str | None:
    """
    Синхронно загружает CSS из кеша для быстрого применения при старте.
    Возвращает CSS строку или None если кеш не найден.
    """
    from config import THEME_FOLDER
    import os
    
    if theme_name is None:
        theme_name = get_selected_theme("Темная синяя")
    
    if theme_name not in THEMES:
        theme_name = "Темная синяя"
    
    info = THEMES[theme_name]
    cache_dir = os.path.join(THEME_FOLDER, "cache")
    cache_file = os.path.join(cache_dir, f"{info['file'].replace('.xml', '')}.css")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                css = f.read()
            
            # ✅ Проверяем что кеш содержит динамические стили (проверка по маркеру версии)
            # Маркер добавляется в ThemeBuildWorker при генерации CSS
            if "/* THEME_VERSION:v2 */" not in css:
                log(f"⚠️ Кеш CSS устарел (нет маркера версии v2), удаляем: {cache_file}", "WARNING")
                try:
                    os.remove(cache_file)
                except:
                    pass
                return None
            
            log(f"📦 Загружен CSS из кеша: {len(css)} символов для '{theme_name}'", "DEBUG")
            return css
        except Exception as e:
            log(f"Ошибка чтения кеша CSS: {e}", "WARNING")
    
    return None

def get_theme_bg_color(theme_name: str) -> str:
    """Возвращает цвет фона для указанной темы в формате 'R, G, B'"""
    theme_info = THEMES.get(theme_name, {})
    # По умолчанию возвращаем тёмно-серый (как в оригинале)
    return theme_info.get("bg_color", "32, 32, 32")

def get_theme_content_bg_color(theme_name: str) -> str:
    """Возвращает цвет фона контентной области (чуть светлее основного)"""
    bg = get_theme_bg_color(theme_name)
    try:
        r, g, b = [int(x.strip()) for x in bg.split(',')]
        # Делаем чуть светлее для контентной области
        r = min(255, r + 7)
        g = min(255, g + 7)
        b = min(255, b + 7)
        return f"{r}, {g}, {b}"
    except:
        return "39, 39, 39"
   
class ThemeBuildWorker(QObject):
    """Воркер для полной подготовки CSS темы в фоновом потоке.
    
    Делает ВСЮ тяжёлую работу в фоне:
    - Чтение кеша
    - Генерация CSS через qt_material (если кеша нет)
    - Сборка финального CSS со всеми оверлеями
    
    В главном потоке остаётся только setStyleSheet() - одна операция.
    """
    
    finished = pyqtSignal(str, str)  # final_css, theme_name
    error = pyqtSignal(str)
    progress = pyqtSignal(str)  # status message
    
    def __init__(self, theme_file: str, theme_name: str, cache_file: str, 
                 is_amoled: bool = False, is_pure_black: bool = False, is_rkn_tyan: bool = False, is_rkn_tyan_2: bool = False):
        super().__init__()
        self.theme_file = theme_file
        self.theme_name = theme_name
        self.cache_file = cache_file
        self.is_amoled = is_amoled
        self.is_pure_black = is_pure_black
        self.is_rkn_tyan = is_rkn_tyan
        self.is_rkn_tyan_2 = is_rkn_tyan_2
    
    def run(self):
        """Подготавливает полный CSS в фоновом потоке"""
        try:
            import os
            import re
            start_time = time.time()
            base_css = None
            from_cache = False
            
            # 1. Пробуем загрузить из кеша (быстро) - кеш уже оптимизирован
            if os.path.exists(self.cache_file):
                try:
                    self.progress.emit("Загрузка темы из кеша...")
                    with open(self.cache_file, 'r', encoding='utf-8') as f:
                        base_css = f.read()
                    if base_css:
                        from_cache = True
                        log(f"🎨 ThemeBuildWorker: загружен CSS из кеша ({len(base_css)} символов)", "DEBUG")
                except Exception as e:
                    log(f"⚠ Ошибка чтения кеша: {e}", "WARNING")
                    base_css = None
            
            # 2. Если кеша нет - генерируем через qt_material и оптимизируем
            if not base_css:
                import qt_material
                self.progress.emit("Генерация CSS темы...")
                log(f"🎨 ThemeBuildWorker: генерация CSS для {self.theme_file}", "DEBUG")
                
                base_css = qt_material.build_stylesheet(theme=self.theme_file)
                original_size = len(base_css)
                
                # === ОПТИМИЗАЦИЯ CSS ===
                self.progress.emit("Оптимизация CSS...")
                
                # 2.1 Удаляем проблемные icon:/ ссылки которые замедляют парсинг Qt
                base_css = re.sub(r'url\(["\']?icon:[^)]+\)', 'none', base_css)
                
                # 2.2 Минификация CSS - удаляем лишние пробелы и переносы
                base_css = re.sub(r'/\*[^*]*\*+([^/*][^*]*\*+)*/', '', base_css)  # Удаляем комментарии
                base_css = re.sub(r'\s+', ' ', base_css)  # Множественные пробелы -> один
                base_css = re.sub(r'\s*([{};:,>])\s*', r'\1', base_css)  # Убираем пробелы вокруг символов
                base_css = base_css.strip()
                
                optimized_size = len(base_css)
                log(f"🎨 CSS оптимизирован: {original_size} -> {optimized_size} байт ({100-optimized_size*100//original_size}% сжатие)", "DEBUG")
                
                # Кешируем ОПТИМИЗИРОВАННЫЙ CSS для будущих запусков
                try:
                    os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
                    with open(self.cache_file, 'w', encoding='utf-8') as f:
                        f.write(base_css)
                    log(f"✅ Оптимизированный CSS закеширован в {self.cache_file}", "DEBUG")
                except Exception as e:
                    log(f"⚠ Не удалось закешировать CSS: {e}", "WARNING")
            
            # 3. Собираем финальный CSS со всеми оверлеями (тоже в фоне!)
            self.progress.emit("Подготовка стилей...")
            all_styles = [base_css]
            
            # ✅ ГЕНЕРИРУЕМ динамический STYLE_SHEET с правильными цветами для темы
            theme_bg = get_theme_bg_color(self.theme_name)
            content_bg = get_theme_content_bg_color(self.theme_name)
            is_light = "Светлая" in self.theme_name
            text_color = "#000000" if is_light else "#ffffff"
            border_color = "200, 200, 200" if is_light else "80, 80, 80"
            titlebar_bg_adjust = 10 if is_light else -4  # Светлее/темнее для titlebar

            # Проверяем состояние blur для определения прозрачности
            try:
                from config.reg import get_blur_effect_enabled
                blur_enabled = get_blur_effect_enabled()
            except:
                blur_enabled = False

            # Непрозрачность: меньше при blur, полностью непрозрачно без него
            base_alpha = 240 if blur_enabled else 255
            border_alpha = 200 if blur_enabled else 255

            # Вычисляем цвет titlebar (чуть темнее основного)
            try:
                r, g, b = [int(x.strip()) for x in theme_bg.split(',')]
                tr = max(0, min(255, r + titlebar_bg_adjust))
                tg = max(0, min(255, g + titlebar_bg_adjust))
                tb = max(0, min(255, b + titlebar_bg_adjust))
                titlebar_bg = f"{tr}, {tg}, {tb}"
            except:
                titlebar_bg = theme_bg

            dynamic_style_sheet = f"""
/* === ПЕРЕКРЫВАЕМ ДЕФОЛТНЫЕ СТИЛИ qt_material === */
QWidget {{
    font-family: 'Segoe UI', Arial, sans-serif;
    background-color: transparent !important;
}}

QMainWindow {{
    background-color: rgba({theme_bg}, 255) !important;
}}

/* Главное окно приложения (LupiDPIApp) */
LupiDPIApp {{
    background-color: transparent !important;
}}

/* Стили для кастомного контейнера со скругленными углами */
QFrame#mainContainer {{
    background-color: rgba({theme_bg}, {base_alpha}) !important;
    border-radius: 10px !important;
    border: 1px solid rgba({border_color}, {border_alpha}) !important;
}}

/* Кастомный titlebar */
QWidget#customTitleBar {{
    background-color: rgba({titlebar_bg}, {base_alpha}) !important;
    border-top-left-radius: 10px !important;
    border-top-right-radius: 10px !important;
    border-bottom: 1px solid rgba({border_color}, {border_alpha}) !important;
}}

QLabel#titleLabel {{
    color: {text_color} !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    background-color: transparent !important;
}}

/* Область контента с цветом темы */
QWidget#contentArea {{
    background-color: rgba({content_bg}, 0.95) !important;
    border-top-right-radius: 10px !important;
    border-bottom-right-radius: 10px !important;
}}

/* Прозрачный фон для остальных виджетов */
QStackedWidget {{
    background-color: transparent !important;
}}

QFrame {{
    background-color: transparent !important;
}}

/* Скроллбары в стиле Windows 11 */
QScrollBar:vertical {{
    background: rgba(255, 255, 255, 0.03);
    width: 8px;
    border-radius: 4px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.15);
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: rgba(255, 255, 255, 0.25);
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: rgba(255, 255, 255, 0.03);
    height: 8px;
    border-radius: 4px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: rgba(255, 255, 255, 0.15);
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background: rgba(255, 255, 255, 0.25);
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
"""
            all_styles.append(dynamic_style_sheet)
            
            # ✅ Добавляем маркер версии для валидации кеша
            all_styles.append("/* THEME_VERSION:v2 */")
            
            if self.is_rkn_tyan or self.is_rkn_tyan_2:
                all_styles.append("""
                    QWidget[hasCustomBackground="true"] { background: transparent !important; }
                    QWidget[hasCustomBackground="true"] > QWidget { background: transparent; }
                """)
            
            if self.is_pure_black:
                all_styles.append(PURE_BLACK_OVERRIDE_STYLE)
            elif self.is_amoled:
                all_styles.append(AMOLED_OVERRIDE_STYLE)
            
            # Объединяем всё в одну строку
            final_css = "\n".join(all_styles)
            
            elapsed = time.time() - start_time
            cache_status = "из кеша" if from_cache else "сгенерирован"
            log(f"✅ ThemeBuildWorker: CSS {cache_status} за {elapsed:.2f}с ({len(final_css)} символов)", "DEBUG")
            
            self.finished.emit(final_css, self.theme_name)
            
        except Exception as e:
            log(f"❌ ThemeBuildWorker ошибка: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "ERROR")
            self.error.emit(str(e))


class PremiumCheckWorker(QObject):
    """Воркер для асинхронной проверки премиум статуса"""
    
    finished = pyqtSignal(bool, str, object)  # is_premium, message, days
    error = pyqtSignal(str)
    
    def __init__(self, donate_checker):
        super().__init__()
        self.donate_checker = donate_checker
    
    def run(self):
        """Выполнить проверку подписки"""
        try:
            log("Начало асинхронной проверки подписки", "DEBUG")
            start_time = time.time()
            
            if not self.donate_checker:
                self.finished.emit(False, "Checker не доступен", None)
                return
            
            # Проверяем тип checker'а
            checker_type = self.donate_checker.__class__.__name__
            if checker_type == 'DummyChecker':
                self.finished.emit(False, "Dummy checker", None)
                return
            
            # Выполняем проверку
            is_premium, message, days = self.donate_checker.check_subscription_status()
            
            elapsed = time.time() - start_time
            log(f"Асинхронная проверка завершена за {elapsed:.2f}с: premium={is_premium}", "DEBUG")
            
            self.finished.emit(is_premium, message, days)
            
        except Exception as e:
            log(f"Ошибка в PremiumCheckWorker: {e}", "❌ ERROR")
            self.error.emit(str(e))
            self.finished.emit(False, f"Ошибка: {e}", None)


class RippleButton(QPushButton):
    def __init__(self, text, parent=None, color=""):
        super().__init__(text, parent)
        self._ripple_pos = QPoint()
        self._ripple_radius = 0
        self._ripple_opacity = 0
        self._bgcolor = color
        
        # Настройка анимаций
        self._ripple_animation = QPropertyAnimation(self, b"rippleRadius", self)
        self._ripple_animation.setDuration(350)
        self._ripple_animation.setStartValue(0)
        self._ripple_animation.setEndValue(100)
        self._ripple_animation.setEasingCurve(QEasingCurve.Type.OutQuad)

        self._fade_animation = QPropertyAnimation(self, b"rippleOpacity", self)
        self._fade_animation.setDuration(350)
        self._fade_animation.setStartValue(0.4)
        self._fade_animation.setEndValue(0)

    @pyqtProperty(float)
    def rippleRadius(self):
        return self._ripple_radius

    @rippleRadius.setter
    def rippleRadius(self, value):
        self._ripple_radius = value
        self.update()

    @pyqtProperty(float)
    def rippleOpacity(self):
        return self._ripple_opacity

    @rippleOpacity.setter
    def rippleOpacity(self, value):
        self._ripple_opacity = value
        self.update()

    def mousePressEvent(self, event):
        self._ripple_pos = event.pos()
        self._ripple_opacity = 0.4
        
        # Вычисляем максимальный радиус
        max_radius = max(
            self._ripple_pos.x(),
            self._ripple_pos.y(),
            self.width() - self._ripple_pos.x(),
            self.height() - self._ripple_pos.y()
        ) * 1.5
        
        self._ripple_animation.setEndValue(max_radius)
        self._ripple_animation.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._fade_animation.start()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._ripple_radius > 0 and self._ripple_opacity > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setOpacity(self._ripple_opacity)
            
            painter.setBrush(QColor(255, 255, 255, 80))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                self._ripple_pos,
                int(self._ripple_radius),
                int(self._ripple_radius)
            )
            painter.end()



class DualActionRippleButton(RippleButton):
    """Кнопка с разными действиями для левого и правого клика"""
    
    def __init__(self, text, parent=None, color="0, 119, 255"):
        super().__init__(text, parent, color)
        self.right_click_callback = None
    
    def set_right_click_callback(self, callback):
        """Устанавливает функцию для правого клика"""
        self.right_click_callback = callback
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            if self.right_click_callback:
                self.right_click_callback()
            event.accept()
        else:
            super().mousePressEvent(event)


class HoverTextButton(DualActionRippleButton):
    """Кнопка с изменением текста при наведении курсора.
    
    Поддерживает массив hover-текстов, которые пролистываются при каждом наведении.
    """
    
    def __init__(self, default_text: str, hover_texts: list | str, parent=None, color="0, 119, 255"):
        """
        Args:
            default_text: Текст по умолчанию (когда курсор не на кнопке)
            hover_texts: Один текст или список текстов для показа при наведении
            parent: Родительский виджет
            color: RGB цвет кнопки
        """
        super().__init__(default_text, parent, color)
        self._default_text = default_text
        
        # Поддержка как одного текста, так и списка
        if isinstance(hover_texts, str):
            self._hover_texts = [hover_texts]
        else:
            self._hover_texts = list(hover_texts)
        
        self._current_hover_index = 0
        
    def set_texts(self, default_text: str, hover_texts: list | str):
        """Устанавливает тексты для обычного состояния и при наведении"""
        self._default_text = default_text
        
        if isinstance(hover_texts, str):
            self._hover_texts = [hover_texts]
        else:
            self._hover_texts = list(hover_texts)
        
        self._current_hover_index = 0
        self.setText(self._default_text)
        
    def enterEvent(self, event):
        """При наведении курсора показываем текущий hover текст"""
        if self._hover_texts:
            self.setText(self._hover_texts[self._current_hover_index])
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """При уходе курсора возвращаем обычный текст и переключаем индекс"""
        self.setText(self._default_text)
        
        # Переключаем на следующий hover текст для следующего наведения
        if self._hover_texts:
            self._current_hover_index = (self._current_hover_index + 1) % len(self._hover_texts)
        
        super().leaveEvent(event)


class ThemeManager:
    """Класс для управления темами приложения"""

    def __init__(self, app, widget, status_label=None, theme_folder=None, donate_checker=None, apply_on_init=True):
        self.app = app
        self.widget = widget
        # status_label больше не используется в новом интерфейсе
        self.theme_folder = theme_folder
        self.donate_checker = donate_checker
        self._fallback_due_to_premium: str | None = None
        self._theme_applied = False
        
        # Кеш для премиум статуса
        self._premium_cache: Optional[Tuple[bool, str, Optional[int]]] = None
        self._cache_time: Optional[float] = None
        self._cache_duration = 60  # 60 секунд кеша
        
        # Потоки для асинхронных проверок
        self._check_thread: Optional[QThread] = None
        self._check_worker: Optional[PremiumCheckWorker] = None
        
        # Потоки для асинхронной генерации CSS темы
        self._theme_build_thread: Optional[QThread] = None
        self._theme_build_worker: Optional[ThemeBuildWorker] = None
        self._pending_theme_data: Optional[dict] = None  # Данные темы для применения после генерации CSS
        
        # Хеш текущего CSS для оптимизации (не применять повторно)
        self._current_css_hash: Optional[int] = None

        # список тем с премиум-статусом
        self.themes = []
        for name, info in THEMES.items():
            is_premium = (name == "РКН Тян" or 
                         name == "РКН Тян 2" or
                         name.startswith("AMOLED") or 
                         name == "Полностью черная" or
                         info.get("amoled", False) or
                         info.get("pure_black", False))
            self.themes.append({'name': name, 'premium': is_premium})

        # выбираем стартовую тему
        saved = get_selected_theme()
        log(f"🎨 ThemeManager: saved='{saved}', in THEMES={saved in THEMES if saved else False}", "DEBUG")
        
        if saved and saved in THEMES:
            if self._is_premium_theme(saved):
                # Используем кешированный результат или считаем что нет премиума при старте
                self.current_theme = "Темная синяя"
                self._fallback_due_to_premium = saved
                log(f"Премиум тема {saved} отложена до проверки подписки", "INFO")
            else:
                self.current_theme = saved
                log(f"🎨 Загружена обычная тема: '{saved}'", "DEBUG")
        else:
            self.current_theme = "Темная синяя"
            log(f"🎨 Тема не найдена, используем 'Темная синяя'", "DEBUG")

        # Тема применяется асинхронно через apply_theme_async() после инициализации
        # apply_on_init больше не используется - всегда False
        if apply_on_init:
            # Для обратной совместимости - используем async
            self.apply_theme_async(self.current_theme, persist=False)
        # Минимальный CSS теперь применяется в main.py ДО показа окна

    def __del__(self):
        """Деструктор для очистки ресурсов"""
        try:
            # Останавливаем поток если он запущен
            if hasattr(self, '_check_thread') and self._check_thread is not None:
                try:
                    if self._check_thread.isRunning():
                        self._check_thread.quit()
                        self._check_thread.wait(500)  # Ждем максимум 0.5 секунды
                except RuntimeError:
                    pass
        except Exception:
            pass

    def cleanup(self):
        """Безопасная очистка всех ресурсов"""
        try:
            # Очищаем кеш
            self._premium_cache = None
            self._cache_time = None
            
            # Останавливаем поток проверки
            if hasattr(self, '_check_thread') and self._check_thread is not None:
                try:
                    if self._check_thread.isRunning():
                        log("Останавливаем поток проверки премиума", "DEBUG")
                        self._check_thread.quit()
                        if not self._check_thread.wait(1000):
                            log("Принудительное завершение потока", "WARNING")
                            self._check_thread.terminate()
                            self._check_thread.wait()
                except RuntimeError:
                    pass
                finally:
                    self._check_thread = None
                    self._check_worker = None
                    
            log("ThemeManager очищен", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка при очистке ThemeManager: {e}", "ERROR")

    def _is_premium_theme(self, theme_name: str) -> bool:
        """Проверяет, является ли тема премиум"""
        clean_name = self.get_clean_theme_name(theme_name)
        theme_info = THEMES.get(clean_name, {})
        return (clean_name in ["РКН Тян", "РКН Тян 2", "Полностью черная"] or 
                clean_name.startswith("AMOLED") or
                theme_info.get("amoled", False) or
                theme_info.get("pure_black", False))

    def _is_premium_available(self) -> bool:
        """Проверяет доступность премиума (использует кеш)"""
        if not self.donate_checker:
            return False
        
        # Проверяем кеш
        if self._premium_cache and self._cache_time:
            cache_age = time.time() - self._cache_time
            if cache_age < self._cache_duration:
                log(f"Используем кешированный премиум статус: {self._premium_cache[0]}", "DEBUG")
                return self._premium_cache[0]
        
        # Если кеша нет, возвращаем False и запускаем асинхронную проверку
        log("Кеш премиума отсутствует, запускаем асинхронную проверку", "DEBUG")
        self._start_async_premium_check()
        return False

    def _start_async_premium_check(self):
        """Запускает асинхронную проверку премиум статуса"""
        if not self.donate_checker:
            return
        
        # ✅ ДОБАВИТЬ ЗАЩИТУ
        if hasattr(self, '_check_in_progress') and self._check_in_progress:
            log("Проверка премиума уже выполняется, пропускаем", "DEBUG")
            return
        
        self._check_in_progress = True
            
        # Проверяем тип checker'а
        checker_type = self.donate_checker.__class__.__name__
        if checker_type == 'DummyChecker':
            log("DummyChecker обнаружен, пропускаем асинхронную проверку", "DEBUG")
            return
        
        # Проверяем существование потока перед проверкой isRunning
        if self._check_thread is not None:
            try:
                if self._check_thread.isRunning():
                    log("Асинхронная проверка уже выполняется", "DEBUG")
                    return
            except RuntimeError:
                # Поток был удален, сбрасываем ссылку
                log("Предыдущий поток был удален, создаем новый", "DEBUG")
                self._check_thread = None
                self._check_worker = None
        
        log("Запуск асинхронной проверки премиум статуса", "DEBUG")
        
        # Очищаем старые ссылки перед созданием новых
        if self._check_thread is not None:
            try:
                if self._check_thread.isRunning():
                    self._check_thread.quit()
                    self._check_thread.wait(1000)  # Ждем максимум 1 секунду
            except RuntimeError:
                pass
            self._check_thread = None
            self._check_worker = None
        
        # Создаем воркер и поток
        self._check_thread = QThread()
        self._check_worker = PremiumCheckWorker(self.donate_checker)
        self._check_worker.moveToThread(self._check_thread)
        
        # Подключаем сигналы
        self._check_thread.started.connect(self._check_worker.run)
        self._check_worker.finished.connect(self._on_premium_check_finished)
        self._check_worker.error.connect(self._on_premium_check_error)
        
        # Правильная очистка потока после завершения
        def cleanup_thread():
            try:
                self._check_in_progress = False
                if self._check_worker:
                    self._check_worker.deleteLater()
                    self._check_worker = None
                if self._check_thread:
                    self._check_thread.deleteLater()
                    self._check_thread = None
            except RuntimeError:
                # Объекты уже удалены
                self._check_worker = None
                self._check_thread = None
        
        self._check_worker.finished.connect(self._check_thread.quit)
        self._check_thread.finished.connect(cleanup_thread)
        
        # Запускаем поток
        try:
            self._check_thread.start()
        except RuntimeError as e:
            log(f"Ошибка запуска потока проверки премиума: {e}", "❌ ERROR")
            self._check_thread = None
            self._check_worker = None

    def _on_premium_check_finished(self, is_premium: bool, message: str, days: Optional[int]):
        """Обработчик завершения асинхронной проверки"""
        log(f"Асинхронная проверка завершена: premium={is_premium}, msg='{message}', days={days}", "DEBUG")
        
        # Обновляем кеш
        self._premium_cache = (is_premium, message, days)
        self._cache_time = time.time()
        
        # Обновляем заголовок окна
        if hasattr(self.widget, "update_title_with_subscription_status"):
            try:
                self.widget.update_title_with_subscription_status(is_premium, self.current_theme, days)
            except Exception as e:
                log(f"Ошибка обновления заголовка: {e}", "❌ ERROR")
        
        # Если есть отложенная премиум тема и премиум доступен, применяем её асинхронно
        if self._fallback_due_to_premium and is_premium:
            log(f"Восстанавливаем отложенную премиум тему: {self._fallback_due_to_premium}", "INFO")
            theme_to_restore = self._fallback_due_to_premium
            self._fallback_due_to_premium = None
            self.apply_theme_async(theme_to_restore, persist=True)
        
        # Обновляем список доступных тем в UI
        if hasattr(self.widget, 'theme_handler'):
            try:
                self.widget.theme_handler.update_available_themes()
            except Exception as e:
                log(f"Ошибка обновления списка тем: {e}", "DEBUG")

    def _on_premium_check_error(self, error: str):
        """Обработчик ошибки асинхронной проверки"""
        log(f"Ошибка асинхронной проверки премиума: {error}", "❌ ERROR")
        
        # Устанавливаем кеш с негативным результатом
        self._premium_cache = (False, f"Ошибка: {error}", None)
        self._cache_time = time.time()

    def reapply_saved_theme_if_premium(self):
        """Восстанавливает премиум-тему после инициализации DonateChecker"""
        log(f"🔄 reapply_saved_theme_if_premium: fallback={self._fallback_due_to_premium}", "DEBUG")
        # Запускаем асинхронную проверку
        self._start_async_premium_check()

    def get_available_themes(self):
        """Возвращает список доступных тем с учетом статуса подписки"""
        themes = []
        
        # Используем кешированный результат
        is_premium = False
        if self._premium_cache:
            is_premium = self._premium_cache[0]
        
        for theme_info in self.themes:
            theme_name = theme_info['name']
            
            if theme_info['premium'] and not is_premium:
                # Разные метки для разных типов премиум тем
                if theme_name.startswith("AMOLED"):
                    themes.append(f"{theme_name} (AMOLED Premium)")
                elif theme_name == "Полностью черная":
                    themes.append(f"{theme_name} (Pure Black Premium)")
                else:
                    themes.append(f"{theme_name} (заблокировано)")
            else:
                themes.append(theme_name)
                
        return themes

    def get_clean_theme_name(self, display_name):
        """Извлекает чистое имя темы из отображаемого названия"""
        clean_name = display_name
        suffixes = [" (заблокировано)", " (AMOLED Premium)", " (Pure Black Premium)"]
        for suffix in suffixes:
            clean_name = clean_name.replace(suffix, "")
        return clean_name

    def _is_amoled_theme(self, theme_name: str) -> bool:
        """Проверяет, является ли тема AMOLED"""
        clean_name = self.get_clean_theme_name(theme_name)
        theme_info = THEMES.get(clean_name, {})
        return (clean_name.startswith("AMOLED") or 
                theme_info.get("amoled", False))

    def _is_pure_black_theme(self, theme_name: str) -> bool:
        """Проверяет, является ли тема полностью черной"""
        clean_name = self.get_clean_theme_name(theme_name)
        theme_info = THEMES.get(clean_name, {})
        return (clean_name == "Полностью черная" or 
                theme_info.get("pure_black", False))

    def _apply_rkn_with_protection(self):
        """Применяет фон РКН Тян с защитой от перезаписи"""
        try:
            log("Применение фона РКН Тян с защитой", "DEBUG")
            success = self.apply_rkn_background()
            if success:
                # Дополнительная защита - повторная проверка через 200мс
                QTimer.singleShot(200, self._verify_rkn_background)
                log("Фон РКН Тян успешно применён", "INFO")
            else:
                log("Не удалось применить фон РКН Тян", "WARNING")
        except Exception as e:
            log(f"Ошибка при применении фона РКН Тян: {e}", "❌ ERROR")

    def _verify_rkn_background(self):
        """Проверяет что фон РКН Тян всё ещё применён"""
        try:
            # Определяем правильный виджет
            target_widget = self.widget
            if hasattr(self.widget, 'main_widget'):
                target_widget = self.widget.main_widget
            
            if not target_widget.autoFillBackground() or not target_widget.property("hasCustomBackground"):
                log("Фон РКН Тян был сброшен, восстанавливаем", "WARNING")
                self.apply_rkn_background()
            else:
                log("Фон РКН Тян успешно сохранён", "DEBUG")
        except Exception as e:
            log(f"Ошибка проверки фона РКН Тян: {e}", "ERROR")

    def _apply_rkn2_with_protection(self):
        """Применяет фон РКН Тян 2 с защитой от перезаписи"""
        try:
            log("Применение фона РКН Тян 2 с защитой", "DEBUG")
            success = self.apply_rkn2_background()
            if success:
                # Дополнительная защита - повторная проверка через 200мс
                QTimer.singleShot(200, self._verify_rkn2_background)
                log("Фон РКН Тян 2 успешно применён", "INFO")
            else:
                log("Не удалось применить фон РКН Тян 2", "WARNING")
        except Exception as e:
            log(f"Ошибка при применении фона РКН Тян 2: {e}", "❌ ERROR")

    def _verify_rkn2_background(self):
        """Проверяет что фон РКН Тян 2 всё ещё применён"""
        try:
            # Определяем правильный виджет
            target_widget = self.widget
            if hasattr(self.widget, 'main_widget'):
                target_widget = self.widget.main_widget
            
            if not target_widget.autoFillBackground() or not target_widget.property("hasCustomBackground"):
                log("Фон РКН Тян 2 был сброшен, восстанавливаем", "WARNING")
                self.apply_rkn2_background()
            else:
                log("Фон РКН Тян 2 успешно сохранён", "DEBUG")
        except Exception as e:
            log(f"Ошибка проверки фона РКН Тян 2: {e}", "ERROR")

    def apply_theme_async(self, theme_name: str | None = None, *, persist: bool = True, 
                          progress_callback=None, done_callback=None) -> None:
        """
        Асинхронно применяет тему (не блокирует UI).
        CSS генерируется в фоновом потоке, применяется в главном.
        
        Args:
            theme_name: Имя темы (если None, используется текущая)
            persist: Сохранять ли выбор в реестр
            progress_callback: Функция для обновления прогресса (str)
            done_callback: Функция вызываемая после завершения (bool success, str message)
        """
        if theme_name is None:
            theme_name = self.current_theme
            
        clean = self.get_clean_theme_name(theme_name)
        
        # Защита от множественных одновременных вызовов для одной и той же темы
        if self._theme_build_thread and self._theme_build_thread.isRunning():
            if hasattr(self, '_pending_theme_data') and self._pending_theme_data:
                pending_theme = self._pending_theme_data.get('theme_name')
                if pending_theme == clean:
                    log(f"⏭️ Тема '{clean}' уже применяется, игнорируем повторный вызов", "DEBUG")
                    return
        
        # Проверка премиум (используем кеш, не блокируем UI)
        if self._is_premium_theme(clean):
            is_available = self._premium_cache[0] if self._premium_cache else False
            if not is_available:
                theme_type = self._get_theme_type_name(clean)
                QMessageBox.information(
                    self.widget, f"{theme_type}",
                    f"{theme_type} «{clean}» доступна только для подписчиков Zapret Premium."
                )
                self._start_async_premium_check()
                if done_callback:
                    done_callback(False, "need premium")
                return
        
        try:
            info = THEMES[clean]
            
            # Пути к кешу
            cache_dir = os.path.join(self.theme_folder or "themes", "cache")
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, f"{info['file'].replace('.xml', '')}.css")
            
            # ВСЯ работа делается в фоновом потоке (включая чтение кеша!)
            log(f"🎨 Запуск асинхронной подготовки CSS для темы: {clean}", "DEBUG")
            
            if progress_callback:
                progress_callback("Подготовка темы...")
            
            # Сохраняем данные для применения после генерации
            self._pending_theme_data = {
                'theme_name': clean,
                'persist': persist,
                'done_callback': done_callback,
                'progress_callback': progress_callback
            }
            
            # Останавливаем предыдущий поток если есть
            if self._theme_build_thread is not None:
                try:
                    if self._theme_build_thread.isRunning():
                        log("⏸️ Останавливаем предыдущий поток генерации CSS...", "DEBUG")
                        # Отключаем сигналы чтобы избежать конфликтов
                        if self._theme_build_worker:
                            try:
                                self._theme_build_worker.finished.disconnect()
                                self._theme_build_worker.error.disconnect()
                            except:
                                pass
                        self._theme_build_thread.quit()
                        if not self._theme_build_thread.wait(1000):  # Увеличил таймаут
                            log("⚠️ Поток не остановился за 1 секунду, принудительно завершаем", "WARNING")
                            self._theme_build_thread.terminate()
                        self._theme_build_thread.wait(500)
                except RuntimeError as e:
                    log(f"RuntimeError при остановке потока: {e}", "DEBUG")
                except Exception as e:
                    log(f"Ошибка остановки потока: {e}", "DEBUG")
                finally:
                    self._theme_build_thread = None
                    self._theme_build_worker = None
            
            # Создаём воркер с полными параметрами темы
            self._theme_build_thread = QThread()
            self._theme_build_worker = ThemeBuildWorker(
                theme_file=info["file"],
                theme_name=clean,
                cache_file=cache_file,
                is_amoled=self._is_amoled_theme(clean),
                is_pure_black=self._is_pure_black_theme(clean),
                is_rkn_tyan=(clean == "РКН Тян"),
                is_rkn_tyan_2=(clean == "РКН Тян 2")
            )
            self._theme_build_worker.moveToThread(self._theme_build_thread)
            
            # Подключаем сигналы
            self._theme_build_thread.started.connect(self._theme_build_worker.run)
            self._theme_build_worker.finished.connect(self._on_theme_css_ready)
            self._theme_build_worker.error.connect(self._on_theme_build_error)
            if progress_callback:
                self._theme_build_worker.progress.connect(progress_callback)
            
            # Очистка после завершения
            self._theme_build_worker.finished.connect(self._theme_build_thread.quit)
            self._theme_build_thread.finished.connect(self._cleanup_theme_build_thread)
            
            # Запускаем
            self._theme_build_thread.start()
            
        except Exception as e:
            log(f"Ошибка запуска асинхронного применения темы: {e}", "❌ ERROR")
            if done_callback:
                done_callback(False, str(e))
    
    def _on_theme_css_ready(self, final_css: str, theme_name: str):
        """Обработчик готовности CSS (вызывается из главного потока).
        
        CSS уже полностью подготовлен в фоне - здесь только setStyleSheet()!
        """
        try:
            if not self._pending_theme_data:
                log("⚠ CSS готов, но pending_theme_data отсутствует", "WARNING")
                return
            
            data = self._pending_theme_data
            self._pending_theme_data = None
            
            persist = data['persist']
            done_callback = data.get('done_callback')
            progress_callback = data.get('progress_callback')
            
            if progress_callback:
                progress_callback("Применяем тему...")
            
            log(f"🎨 CSS готов ({len(final_css)} символов), применяем: {theme_name}", "DEBUG")
            
            # Применяем готовый CSS - это ЕДИНСТВЕННАЯ синхронная операция!
            self._apply_css_only(final_css, theme_name, persist)
            
            if done_callback:
                try:
                    done_callback(True, "ok")
                except Exception as cb_error:
                    log(f"Ошибка в done_callback: {cb_error}", "WARNING")
                
        except Exception as e:
            log(f"Ошибка применения готового CSS: {e}", "❌ ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            
            # Безопасно вызываем callback
            if done_callback:
                try:
                    done_callback(False, str(e))
                except Exception as cb_error:
                    log(f"Ошибка в error callback: {cb_error}", "WARNING")
    
    def _on_theme_build_error(self, error: str):
        """Обработчик ошибки генерации CSS"""
        log(f"❌ Ошибка генерации CSS темы: {error}", "ERROR")
        
        if self._pending_theme_data:
            done_callback = self._pending_theme_data.get('done_callback')
            self._pending_theme_data = None
            if done_callback:
                done_callback(False, error)
    
    def _cleanup_theme_build_thread(self):
        """Очистка потока генерации CSS"""
        try:
            if self._theme_build_worker:
                self._theme_build_worker.deleteLater()
                self._theme_build_worker = None
            if self._theme_build_thread:
                self._theme_build_thread.deleteLater()
                self._theme_build_thread = None
        except RuntimeError:
            self._theme_build_worker = None
            self._theme_build_thread = None
    
    def _apply_css_only(self, final_css: str, theme_name: str, persist: bool):
        """Применяет готовый CSS - ЕДИНСТВЕННАЯ синхронная операция.

        CSS уже полностью собран в фоновом потоке.
        Здесь только setStyleSheet() и пост-обработка.
        """
        import time as _time
        from PyQt6.QtWidgets import QApplication

        try:
            # Проверяем что виджеты ещё существуют
            if not self.widget or not self.app:
                log("⚠️ Виджет или приложение удалены, пропускаем применение темы", "WARNING")
                return

            clean = theme_name

            # Проверяем хеш CSS - не применяем если не изменился
            css_hash = hash(final_css)
            if self._current_css_hash == css_hash and self.current_theme == clean:
                log(f"⏭ CSS не изменился, пропускаем setStyleSheet", "DEBUG")
                return

            # Определяем правильный виджет для сброса фона
            target_widget = self.widget
            if hasattr(self.widget, 'main_widget') and self.widget.main_widget:
                target_widget = self.widget.main_widget

            # Сбрасываем фон если это НЕ РКН Тян и НЕ РКН Тян 2
            if clean not in ("РКН Тян", "РКН Тян 2"):
                target_widget.setAutoFillBackground(False)
                target_widget.setProperty("hasCustomBackground", False)

            main_window = self.widget

            # Показываем курсор ожидания
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            # ═══════════════════════════════════════════════════════════════
            # ОПТИМИЗАЦИЯ: Скрываем тяжёлые виджеты во время применения CSS
            # Qt быстрее применяет стили к скрытым виджетам
            # ═══════════════════════════════════════════════════════════════
            hidden_widgets = []

            # Скрываем pages_stack (основной контент со всеми страницами)
            if hasattr(main_window, 'pages_stack'):
                pages_stack = main_window.pages_stack
                if pages_stack.isVisible():
                    pages_stack.hide()
                    hidden_widgets.append(pages_stack)

            # Скрываем side_nav (навигация с кнопками)
            if hasattr(main_window, 'side_nav'):
                side_nav = main_window.side_nav
                if side_nav.isVisible():
                    side_nav.hide()
                    hidden_widgets.append(side_nav)

            was_updates_enabled = main_window.updatesEnabled()
            main_window.setUpdatesEnabled(False)

            try:
                # ✅ Применяем CSS только к QApplication - виджеты унаследуют стили
                _t = _time.perf_counter()
                self.app.setStyleSheet(final_css)

                # ✅ Сбрасываем палитру чтобы CSS точно применился
                from PyQt6.QtGui import QPalette
                main_window.setPalette(QPalette())

                elapsed_ms = (_time.perf_counter()-_t)*1000
                log(f"  setStyleSheet took {elapsed_ms:.0f}ms (app only + palette reset)", "DEBUG")
            finally:
                main_window.setUpdatesEnabled(was_updates_enabled)
                # Возвращаем видимость скрытых виджетов
                for widget in hidden_widgets:
                    widget.show()
                # Восстанавливаем курсор
                QApplication.restoreOverrideCursor()
            
            # ⚠️ НЕ обновляем стили здесь - это делается в main.py после показа окна
            # Обновление до показа окна не эффективно для невидимых виджетов
            
            # Сохраняем хеш примененного CSS
            self._current_css_hash = css_hash
            self._theme_applied = True
            
            if persist:
                result = set_selected_theme(clean)
                log(f"💾 Тема сохранена в реестр: '{clean}' -> {result}", "DEBUG")
            else:
                log(f"⏭️ Тема НЕ сохранена в реестр (persist=False): '{clean}'", "DEBUG")
            self.current_theme = clean
            
            # Обновление заголовка (отложенно) - используем слабую ссылку
            try:
                import weakref
                weak_self = weakref.ref(self)
                QTimer.singleShot(10, lambda: weak_self() and weak_self()._update_title_async(clean))
            except Exception as e:
                log(f"Ошибка отложенного обновления заголовка: {e}", "DEBUG")
            
            # Фон РКН Тян / РКН Тян 2 - используем слабую ссылку
            if clean == "РКН Тян":
                try:
                    import weakref
                    weak_self = weakref.ref(self)
                    QTimer.singleShot(50, lambda: weak_self() and weak_self()._apply_rkn_with_protection())
                except Exception as e:
                    log(f"Ошибка отложенного применения фона РКН Тян: {e}", "DEBUG")
            elif clean == "РКН Тян 2":
                try:
                    import weakref
                    weak_self = weakref.ref(self)
                    QTimer.singleShot(50, lambda: weak_self() and weak_self()._apply_rkn2_with_protection())
                except Exception as e:
                    log(f"Ошибка отложенного применения фона РКН Тян 2: {e}", "DEBUG")
                
        except Exception as e:
            log(f"Ошибка в _apply_css_only: {e}", "❌ ERROR")

    def apply_rkn_background(self):
        """Применяет фоновое изображение для темы РКН Тян"""
        try:
            # ✅ ИСПРАВЛЕНИЕ: Определяем правильный виджет для применения фона
            target_widget = self.widget
            
            # Если widget имеет main_widget, применяем к нему
            if hasattr(self.widget, 'main_widget'):
                target_widget = self.widget.main_widget
                log("Применяем фон РКН Тян к main_widget", "DEBUG")
            else:
                log("Применяем фон РКН Тян к основному виджету", "DEBUG")
            
            img_path = os.path.join(self.theme_folder or THEME_FOLDER, "rkn_tyan", "rkn_background.jpg")
            
            if not os.path.exists(img_path):
                log(f"Фон РКН Тян не найден по пути: {img_path}", "WARNING")
                return False

            if os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                if not pixmap.isNull():
                    # Помечаем виджет
                    target_widget.setProperty("hasCustomBackground", True)
                    
                    # Устанавливаем палитру для target_widget
                    palette = target_widget.palette()
                    brush = QBrush(pixmap.scaled(
                        target_widget.size(),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    ))
                    palette.setBrush(QPalette.ColorRole.Window, brush)
                    target_widget.setPalette(palette)
                    target_widget.setAutoFillBackground(True)
                    
                    # Защитный стиль
                    widget_style = """
                    QWidget {
                        background: transparent !important;
                    }
                    """
                    existing_style = target_widget.styleSheet()
                    if "background: transparent" not in existing_style:
                        target_widget.setStyleSheet(existing_style + widget_style)
                    
                    log(f"Фон РКН Тян успешно установлен на {target_widget.__class__.__name__}", "INFO")
                    return True
                    
        except Exception as e:
            log(f"Ошибка при применении фона РКН Тян: {str(e)}", "❌ ERROR")
        
        return False

    def apply_rkn2_background(self):
        """Применяет фоновое изображение для темы РКН Тян 2"""
        try:
            # Определяем правильный виджет для применения фона
            target_widget = self.widget
            
            # Если widget имеет main_widget, применяем к нему
            if hasattr(self.widget, 'main_widget'):
                target_widget = self.widget.main_widget
                log("Применяем фон РКН Тян 2 к main_widget", "DEBUG")
            else:
                log("Применяем фон РКН Тян 2 к основному виджету", "DEBUG")
            
            img_path = os.path.join(self.theme_folder or THEME_FOLDER, "rkn_tyan_2", "rkn_background_2.jpg")
            
            if not os.path.exists(img_path):
                log(f"Фон РКН Тян 2 не найден по пути: {img_path}", "WARNING")
                return False

            if os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                if not pixmap.isNull():
                    # Помечаем виджет
                    target_widget.setProperty("hasCustomBackground", True)
                    
                    # Устанавливаем палитру для target_widget
                    palette = target_widget.palette()
                    brush = QBrush(pixmap.scaled(
                        target_widget.size(),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    ))
                    palette.setBrush(QPalette.ColorRole.Window, brush)
                    target_widget.setPalette(palette)
                    target_widget.setAutoFillBackground(True)
                    
                    # Защитный стиль
                    widget_style = """
                    QWidget {
                        background: transparent !important;
                    }
                    """
                    existing_style = target_widget.styleSheet()
                    if "background: transparent" not in existing_style:
                        target_widget.setStyleSheet(existing_style + widget_style)
                    
                    log(f"Фон РКН Тян 2 успешно установлен на {target_widget.__class__.__name__}", "INFO")
                    return True
                    
        except Exception as e:
            log(f"Ошибка при применении фона РКН Тян 2: {str(e)}", "❌ ERROR")
        
        return False

    def _update_title_async(self, current_theme):
        """Асинхронно обновляет заголовок окна"""
        try:
            # Используем кешированный результат если есть
            if self._premium_cache and hasattr(self.widget, "update_title_with_subscription_status"):
                is_premium, message, days = self._premium_cache
                self.widget.update_title_with_subscription_status(is_premium, current_theme, days)
            else:
                # Показываем FREE статус и запускаем асинхронную проверку
                if hasattr(self.widget, "update_title_with_subscription_status"):
                    self.widget.update_title_with_subscription_status(False, current_theme, None)
                # Запускаем асинхронную проверку
                self._start_async_premium_check()
                
        except Exception as e:
            log(f"Ошибка обновления заголовка: {e}", "❌ ERROR")

    def _get_theme_type_name(self, theme_name: str) -> str:
        """Возвращает красивое название типа темы"""
        if theme_name.startswith("AMOLED"):
            return "AMOLED тема"
        elif theme_name == "Полностью черная":
            return "Pure Black тема"
        elif theme_name in ("РКН Тян", "РКН Тян 2"):
            return "Премиум-тема"
        else:
            return "Премиум-тема"

    def _apply_pure_black_enhancements_inline(self):
        """Возвращает CSS для улучшений полностью черной темы (для inline применения)"""
        # Применяется через combined_style в apply_theme
        pass

    def apply_pure_black_enhancements(self):
        """Применяет дополнительные улучшения для полностью черной темы (legacy)"""
        try:
            additional_style = self._get_pure_black_enhancement_css()
            current_style = self.app.styleSheet()
            self.app.setStyleSheet(current_style + additional_style)
            log("Pure Black улучшения применены", "DEBUG")
        except Exception as e:
            log(f"Ошибка при применении Pure Black улучшений: {e}", "DEBUG")
    
    def _get_pure_black_enhancement_css(self) -> str:
        """Возвращает CSS улучшений для Pure Black темы"""
        return """
            QFrame[frameShape="4"] {
                color: #1a1a1a;
            }
            QPushButton:focus {
                border: 2px solid rgba(255, 255, 255, 0.2);
            }
            QComboBox:focus {
                border: 2px solid rgba(255, 255, 255, 0.2);
            }
            QLabel[objectName="title_label"] {
                text-shadow: 0px 0px 5px rgba(255, 255, 255, 0.1);
            }
            """


    def _apply_amoled_enhancements_inline(self):
        """Возвращает CSS для улучшений AMOLED темы (для inline применения)"""
        # Применяется через combined_style в apply_theme
        pass

    def apply_amoled_enhancements(self):
        """Применяет дополнительные улучшения для AMOLED тем (legacy)"""
        try:
            additional_style = self._get_amoled_enhancement_css()
            current_style = self.app.styleSheet()
            self.app.setStyleSheet(current_style + additional_style)
            log("AMOLED улучшения применены", "DEBUG")
        except Exception as e:
            log(f"Ошибка при применении AMOLED улучшений: {e}", "DEBUG")
    
    def _get_amoled_enhancement_css(self) -> str:
        """Возвращает CSS улучшений для AMOLED темы"""
        return """
            /* Убираем все лишние рамки */
            QFrame {
                border: none;
            }
            /* Рамка только при наведении на кнопки */
            QPushButton:hover {
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            /* Убираем text-shadow который создает размытие */
            QLabel {
                text-shadow: none;
            }
            /* Фокус на комбобоксе */
            QComboBox:focus {
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            /* Только горизонтальные линии оставляем видимыми */
            QFrame[frameShape="4"] {
                color: #222222;
                max-height: 1px;
                border: none;
            }
            /* Убираем отступы где возможно */
            QWidget {
                outline: none;
            }
            /* Компактные отступы для контейнеров */
            QStackedWidget {
                margin: 0;
                padding: 0;
            }
            """

    def _update_color_in_style(self, current_style, new_color):
        """Обновляет цвет в существующем стиле"""
        import re
        if 'color:' in current_style:
            updated_style = re.sub(r'color:\s*[^;]+;', f'color: {new_color};', current_style)
        else:
            updated_style = current_style + f' color: {new_color};'
        return updated_style
    
    def _set_status(self, text):
        """Устанавливает текст статуса (через главное окно)"""
        if hasattr(self.widget, 'set_status'):
            self.widget.set_status(text)


class ThemeHandler:
    def __init__(self, app_instance, target_widget=None):
        self.app = app_instance
        self.app_window = app_instance
        self.target_widget = target_widget if target_widget else app_instance
        self.theme_manager = None  # Будет установлен позже

    def set_theme_manager(self, theme_manager):
        """Устанавливает theme_manager после его создания"""
        self.theme_manager = theme_manager
        log("ThemeManager установлен в ThemeHandler", "DEBUG")

    
    def apply_theme_background(self, theme_name):
        """Применяет фон для темы"""
        # Применяем к target_widget, а не к self.app
        widget_to_style = self.target_widget
        
        if theme_name == "РКН Тян":
            # Применяем фон именно к target_widget
            if self.theme_manager and hasattr(self.theme_manager, 'apply_rkn_background'):
                self.theme_manager.apply_rkn_background()
                log(f"Фон РКН Тян применен через theme_manager", "INFO")
            else:
                log("theme_manager не доступен для применения фона РКН Тян", "WARNING")
        elif theme_name == "РКН Тян 2":
            # Применяем фон РКН Тян 2
            if self.theme_manager and hasattr(self.theme_manager, 'apply_rkn2_background'):
                self.theme_manager.apply_rkn2_background()
                log(f"Фон РКН Тян 2 применен через theme_manager", "INFO")
            else:
                log("theme_manager не доступен для применения фона РКН Тян 2", "WARNING")

    def update_subscription_status_in_title(self):
        """Обновляет статус подписки в title_label"""
        try:
            # Проверяем наличие необходимых компонентов
            if not hasattr(self.app_window, 'donate_checker') or not self.app_window.donate_checker:
                log("donate_checker не инициализирован", "⚠ WARNING")
                return
            
            if not self.theme_manager:
                log("theme_manager не инициализирован", "⚠ WARNING")
                return

            # Используем кэшированные данные для быстрого обновления
            donate_checker = self.app_window.donate_checker
            is_premium, status_msg, days_remaining = donate_checker.check_subscription_status(use_cache=True)
            current_theme = self.theme_manager.current_theme if self.theme_manager else None
            
            # Получаем полную информацию о подписке
            sub_info = donate_checker.get_full_subscription_info()
            
            # Обновляем заголовок
            self.app_window.update_title_with_subscription_status(
                sub_info['is_premium'], 
                current_theme, 
                sub_info['days_remaining'],
                sub_info.get('source', 'api')
            )
            
            # Также обновляем текст кнопки подписки если нужно
            if hasattr(self.app_window, 'update_subscription_button_text'):
                self.app_window.update_subscription_button_text(
                    sub_info['is_premium'],
                    sub_info['days_remaining']
                )
            
            log(f"Заголовок обновлен для темы '{current_theme}'", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка при обновлении статуса подписки: {e}", "❌ ERROR")
            # В случае ошибки показываем базовый заголовок
            try:
                self.app_window.update_title_with_subscription_status(False, None, 0)
            except:
                pass  # Игнорируем вторичные ошибки
    
    def change_theme(self, theme_name):
        """Обработчик изменения темы (асинхронная версия - не блокирует UI)"""
        try:
            if not self.theme_manager:
                self.theme_manager = getattr(self.app_window, 'theme_manager', None)
                if not self.theme_manager:
                    return
            
            clean_theme_name = self.theme_manager.get_clean_theme_name(theme_name)
            
            # Показываем статус
            if hasattr(self.app_window, 'set_status'):
                self.app_window.set_status("🎨 Применяем тему...")
            
            # Применяем тему АСИНХРОННО (не блокирует UI!)
            self.theme_manager.apply_theme_async(
                clean_theme_name,
                persist=True,
                progress_callback=self._on_theme_progress,
                done_callback=lambda success, msg: self._on_theme_change_done(success, msg, theme_name)
            )
                
        except Exception as e:
            log(f"Ошибка смены темы: {e}", "ERROR")
    
    def _on_theme_progress(self, status: str):
        """Обработчик прогресса смены темы"""
        if hasattr(self.app_window, 'set_status'):
            self.app_window.set_status(f"🎨 {status}")
    
    def _on_theme_change_done(self, success: bool, message: str, theme_name: str):
        """Обработчик завершения смены темы"""
        try:
            if not success:
                log(f"Ошибка смены темы: {message}", "WARNING")
                # Возвращаем выбор на текущую тему в галерее
                if hasattr(self.app_window, 'appearance_page') and self.theme_manager:
                    self.app_window.appearance_page.set_current_theme(self.theme_manager.current_theme)
                if hasattr(self.app_window, 'set_status'):
                    self.app_window.set_status(f"⚠ {message}")
                return
            
            # Успех - обновляем UI
            if hasattr(self.app_window, 'set_status'):
                self.app_window.set_status("✅ Тема применена")
            
            # Отложенное обновление UI
            QTimer.singleShot(100, lambda: self._post_theme_change_update(theme_name))
                
        except Exception as e:
            log(f"Ошибка в _on_theme_change_done: {e}", "ERROR")
    
    def _post_theme_change_update(self, theme_name: str):
        """Выполняет все обновления UI после смены темы за один раз"""
        try:
            # Обновляем выбранную тему в галерее
            if hasattr(self.app_window, 'appearance_page'):
                self.app_window.appearance_page.set_current_theme(theme_name)
            
            # Обновляем цвета кастомного titlebar
            self._update_titlebar_theme(theme_name)
            
            # Обновляем статус подписки
            self.update_subscription_status_in_title()
        except Exception as e:
            log(f"Ошибка в _post_theme_change_update: {e}", "DEBUG")

    def _update_titlebar_theme(self, theme_name: str):
        """Обновляет цвета кастомного titlebar в соответствии с темой"""
        try:
            if not hasattr(self.app_window, 'title_bar'):
                return
            
            if not hasattr(self.app_window, 'container'):
                return
            
            clean_name = self.theme_manager.get_clean_theme_name(theme_name) if self.theme_manager else theme_name

            # Получаем цвет фона из конфигурации темы
            theme_bg = get_theme_bg_color(clean_name)
            theme_content_bg = get_theme_content_bg_color(clean_name)

            # Проверяем состояние blur для определения непрозрачности
            try:
                from config.reg import get_blur_effect_enabled
                blur_enabled = get_blur_effect_enabled()
            except:
                blur_enabled = False

            # Непрозрачность: меньше при включённом blur, полностью непрозрачно без него
            # Базовая непрозрачность для всех элементов
            base_alpha = 240 if blur_enabled else 255
            border_alpha = 220 if blur_enabled else 255
            container_opacity = 180 if blur_enabled else 255
            container_opacity_light = 160 if blur_enabled else 255
            container_opacity_amoled = 170 if blur_enabled else 255

            # Определяем цвета в зависимости от темы
            is_light = "Светлая" in clean_name
            is_amoled = "AMOLED" in clean_name or clean_name == "Полностью черная"

            if is_amoled:
                # AMOLED и полностью черная тема
                bg_color = f"rgba(0, 0, 0, {base_alpha})"
                text_color = "#ffffff"
                container_bg = f"rgba(0, 0, 0, {container_opacity_amoled})"
                border_color = f"rgba(30, 30, 30, {border_alpha})"
                menubar_bg = f"rgba(0, 0, 0, {base_alpha})"
                menu_text = "#ffffff"
                hover_bg = "#222222"
                menu_dropdown_bg = f"rgba(10, 10, 10, {base_alpha})"
            elif is_light:
                # Светлые темы - используем цвет из конфига
                bg_color = f"rgba({theme_bg}, {base_alpha})"
                text_color = "#000000"
                container_bg = f"rgba({theme_content_bg}, {container_opacity_light})"
                border_color = f"rgba(200, 200, 200, {border_alpha})"
                menubar_bg = f"rgba({theme_bg}, {base_alpha})"
                menu_text = "#000000"
                hover_bg = "#d0d0d0"
                menu_dropdown_bg = f"rgba({theme_content_bg}, {base_alpha})"
            else:
                # Темные темы - используем цвет фона из конфига темы
                bg_color = f"rgba({theme_bg}, {base_alpha})"
                text_color = "#ffffff"
                container_bg = f"rgba({theme_bg}, {container_opacity})"
                border_color = f"rgba(80, 80, 80, {border_alpha})"
                menubar_bg = f"rgba({theme_bg}, {base_alpha})"
                menu_text = "#ffffff"
                # Рассчитываем hover_bg как более светлый оттенок
                try:
                    r, g, b = [int(x.strip()) for x in theme_bg.split(',')]
                    hover_r = min(255, r + 20)
                    hover_g = min(255, g + 20)
                    hover_b = min(255, b + 20)
                    hover_bg = f"rgb({hover_r}, {hover_g}, {hover_b})"
                except:
                    hover_bg = "#333333"
                menu_dropdown_bg = f"rgba({theme_content_bg}, {base_alpha})"
            
            # Обновляем titlebar
            self.app_window.title_bar.set_theme_colors(bg_color, text_color)
            
            # Обновляем контейнер
            self.app_window.container.setStyleSheet(f"""
                QFrame#mainContainer {{
                    background-color: {container_bg};
                    border-radius: 10px;
                    border: 1px solid {border_color};
                }}
            """)
            
            # Обновляем область контента (если есть)
            if hasattr(self.app_window, 'main_widget'):
                content_area = self.app_window.main_widget.findChild(QWidget, "contentArea")
                if content_area:
                    content_area.setStyleSheet(f"""
                        QWidget#contentArea {{
                            background-color: rgba({theme_content_bg}, 0.75);
                            border-top-right-radius: 10px;
                            border-bottom-right-radius: 10px;
                        }}
                    """)
                
                # Обновляем боковую панель (sidebar)
                side_nav = self.app_window.main_widget.findChild(QWidget, "sideNavBar")
                if side_nav:
                    # Делаем фон чуть темнее основного
                    try:
                        r, g, b = [int(x.strip()) for x in theme_bg.split(',')]
                        sidebar_r = max(0, r - 4)
                        sidebar_g = max(0, g - 4)
                        sidebar_b = max(0, b - 4)
                        sidebar_bg = f"{sidebar_r}, {sidebar_g}, {sidebar_b}"
                    except:
                        sidebar_bg = theme_bg
                    
                    side_nav.setStyleSheet(f"""
                        QWidget#sideNavBar {{
                            background-color: rgba({sidebar_bg}, 0.85);
                            border-right: 1px solid rgba(255, 255, 255, 0.06);
                }}
            """)
            
            # Обновляем стиль menubar если есть
            if hasattr(self.app_window, 'menubar_widget'):
                self.app_window.menubar_widget.setStyleSheet(f"""
                    QWidget#menubarWidget {{
                        background-color: {menubar_bg};
                        border-bottom: 1px solid {border_color};
                    }}
                """)
                
                # Обновляем стиль самого меню
                if hasattr(self.app_window, 'menu_bar'):
                    self.app_window.menu_bar.setStyleSheet(f"""
                        QMenuBar {{
                            background-color: transparent;
                            color: {menu_text};
                            border: none;
                            font-size: 11px;
                            font-family: 'Segoe UI', Arial, sans-serif;
                        }}
                        QMenuBar::item {{
                            background-color: transparent;
                            color: {menu_text};
                            padding: 4px 10px;
                            border-radius: 4px;
                            margin: 2px 1px;
                        }}
                        QMenuBar::item:selected {{
                            background-color: {hover_bg};
                        }}
                        QMenu {{
                            background-color: {menu_dropdown_bg};
                            border: 1px solid {border_color};
                            border-radius: 6px;
                            padding: 4px;
                        }}
                        QMenu::item {{
                            padding: 6px 24px 6px 12px;
                            border-radius: 4px;
                            color: {menu_text};
                        }}
                        QMenu::item:selected {{
                            background-color: {hover_bg};
                        }}
                        QMenu::separator {{
                            height: 1px;
                            background-color: {border_color};
                            margin: 4px 8px;
                        }}
                    """)
            
            log(f"Цвета titlebar обновлены для темы: {clean_name}", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка обновления titlebar: {e}", "DEBUG")

    def update_theme_gallery(self):
        """Обновляет галерею тем на странице оформления"""
        if not hasattr(self.app_window, 'appearance_page'):
            log("appearance_page не найден в app_window", "DEBUG")
            return
        
        # Проверяем theme_manager
        if not self.theme_manager:
            if hasattr(self.app_window, 'theme_manager'):
                self.theme_manager = self.app_window.theme_manager
            else:
                log("theme_manager не доступен", "DEBUG")
                return
        
        try:
            # Обновляем премиум статус
            is_premium = False
            if self.theme_manager._premium_cache:
                is_premium = self.theme_manager._premium_cache[0]
            
            self.app_window.appearance_page.set_premium_status(is_premium)
            
            # Обновляем текущую тему
            current_theme = self.theme_manager.current_theme
            self.app_window.appearance_page.set_current_theme(current_theme)
            
            log("Галерея тем обновлена", "DEBUG")
        except Exception as e:
            log(f"Ошибка обновления галереи тем: {e}", "❌ ERROR")

    def update_available_themes(self):
        """Обновляет галерею тем (для совместимости)"""
        self.update_theme_gallery()
