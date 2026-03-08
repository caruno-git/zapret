import os
import sys
import traceback
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QThread
from PyQt6.QtCore import Qt

from log_tail import LogTailWorker

class Logger:
    """Simple logging system that captures console output and errors to a file"""
    
    def __init__(self, log_file_path=None):
        base_dir = os.path.dirname(
            os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
        )
        from config import LOGS_FOLDER
        self.log_file = log_file_path or os.path.join(base_dir, LOGS_FOLDER, "zapret_log.txt")

        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        with open(self.log_file, "w", encoding="utf-8-sig") as f:
            f.write(f"=== Zapret GUI Log - Started {datetime.now():%Y-%m-%d %H:%M:%S} ===\n\n")

        self.orig_stdout = sys.stdout
        self.orig_stderr = sys.stderr
        sys.stdout = sys.stderr = self           # перенаправляем
    
    # --- redirect interface ---------------------------------------------------
    def write(self, message: str):
        if self.orig_stdout:
            self.orig_stdout.write(message)
        with open(self.log_file, "a", encoding="utf-8-sig") as f:
            f.write(f"[{datetime.now():%H:%M:%S}] {message}")

    def flush(self):                              # нужен для print(...)
        if self.orig_stdout:
            self.orig_stdout.flush()
    
    # --- helper API -----------------------------------------------------------
    def log(self, message, level="INFO", component=None):
        prefix = f"[{component}][{level}]" if component else f"[{level}]"
        self.write(f"{prefix} {message}\n")

    def log_exception(self, e, context=""):
        tb = traceback.format_exc()
        self.write(f"[ERROR] Exception in {context}: {e}\n{tb}\n")

    def get_log_content(self) -> str:
        try:
            with open(self.log_file, "r", encoding="utf-8-sig") as f:
                return f.read()
        except Exception as e:
            return f"Error reading log: {e}"
    
    def log_exception(self, e, context=""):
        """Log an exception with its traceback"""
        try:
            tb = traceback.format_exc()
            self.write(f"[ERROR] Exception in {context}: {str(e)}\n{tb}\n")
        except Exception:
            # Last resort - direct write
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    f.write(f"[{timestamp}] [ERROR] Exception in {context}: {str(e)}\n")
                    f.write(f"[{timestamp}] {traceback.format_exc()}\n")
            except Exception:
                pass
    
    def get_log_content(self):
        """Return the content of the log file"""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading log: {str(e)}"

class LogViewerDialog(QDialog):
    """
    Просмотр лог-файла в реальном времени
    (работает и если файл переписывается другим потоком).
    """

    def __init__(self, parent=None, log_file=None):
        super().__init__(parent)
        self.setWindowTitle("Zapret Logs (live)")
        self.setMinimumSize(800, 600)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        # ---------- UI ----------
        layout = QVBoxLayout(self)

        self.log_text = QTextEdit(readOnly=True)
        self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_text.setFont(QFont("Courier New", 9))
        layout.addWidget(self.log_text)

        btn_layout = QHBoxLayout()
        btn_copy   = QPushButton("Copy to clipboard", clicked=self.copy_all)
        btn_clear  = QPushButton("Clear view", clicked=self.log_text.clear)
        btn_close  = QPushButton("Close", clicked=self.close)
        btn_layout.addWidget(btn_copy)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        # ---------- Tail worker ----------
        self._thread = QThread(self)
        self._worker = LogTailWorker(
            log_file or getattr(global_logger, "log_file", "application.log")
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.new_lines.connect(self._append_text)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    # ----------- slots -----------
    def _append_text(self, text: str):
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(text)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def copy_all(self):
        self.log_text.selectAll()
        self.log_text.copy()
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.End)
        self.log_text.setTextCursor(cursor)

    def closeEvent(self, event):
        """
        Останавливаем tail-воркер и дожидаемся завершения потока,
        чтобы не упасть на «Destroyed while thread is still running».
        """
        try:
            if hasattr(self, "_worker") and self._worker:
                self._worker.stop()           # просим воркер завершиться
            if hasattr(self, "_thread") and self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(2_000)      # <= 2 сек
        finally:
            super().closeEvent(event)

# ───────────────────────────────────────────────────────────────
# 3.  GLOBAL LOGGER + HELPERS
# ───────────────────────────────────────────────────────────────
try:
    global_logger = Logger()
except Exception:
    class _FallbackLogger:
        def log(self, *_a, **_kw): pass
        def log_exception(self, *_a, **_kw): pass
        def get_log_content(self): return "Logging system initialization failed."
    global_logger = _FallbackLogger()

def log(msg, level="INFO", component=None):       # удобный helper
    global_logger.log(msg, level, component)

def log_exception(e, context=""):                 # helper для исключений
    global_logger.log_exception(e, context)

def get_log_content():
    return global_logger.get_log_content()
