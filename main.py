from __future__ import annotations

__app_name__ = "QSnap"
__version__ = "1.2.0"
__author__ = "QwejayHuang"
__company__ = "Qwesoft"
__description__ = "Professional Screenshot Tool with HDR & Smart UI"

import ctypes
import json
import logging
import math
import os
import struct
import sys
import time
import wave
from ctypes import wintypes
from pathlib import Path
from typing import Optional

if os.name == "nt":
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

os.environ["QT_LOGGING_RULES"] = "qt.text.font.db=false;qt.multimedia*=false;qt.qpa.window=false"

logger = logging.getLogger(__app_name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.info("NumPy not installed (optional HDR tone mapping)")

try:
    from rapidocr_onnxruntime import RapidOCR
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    logger.info("RapidOCR not installed (optional OCR feature)")

from PySide6.QtCore import (
    QByteArray, QBuffer, QIODevice, QObject, QPoint, QPointF,
    QRect, QRectF, Qt, QThread, Signal, QTimer, QSize, 
    QAbstractNativeEventFilter, QPropertyAnimation, QEasingCurve
)
from PySide6.QtGui import (
    QBrush, QColor, QCursor, QFont, QGuiApplication, QIcon,
    QImage, QKeySequence, QPainter, QPainterPath, QPen,
    QPixmap, QPolygonF, QPainterPathStroker, QRegion
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QColorDialog, QDialog,
    QFileDialog, QFrame, QHBoxLayout, QLabel, 
    QMenu, QMessageBox, QPushButton, QSystemTrayIcon, QTextEdit, 
    QVBoxLayout, QWidget, QKeySequenceEdit, QSlider, QTabWidget, 
    QGroupBox, QSpinBox, QComboBox, QToolButton, QFontDialog
)

if getattr(sys, 'frozen', False) or "__compiled__" in globals():
    _APP_DIR = Path(sys.executable).parent
else:
    _APP_DIR = Path(__file__).parent

_PORTABLE_CONFIG = _APP_DIR / "config.json"

if _PORTABLE_CONFIG.exists():
    _CONFIG_DIR = _APP_DIR
    _CONFIG_FILE = _PORTABLE_CONFIG
    logger.info("Running in Portable Mode")
else:
    _CONFIG_DIR = Path.home() / f".{__app_name__.lower()}"
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE = _CONFIG_DIR / "config.json"

_GLOBAL_OCR_ENGINE: Optional[RapidOCR] = None

def get_ocr_engine() -> Optional[RapidOCR]:
    global _GLOBAL_OCR_ENGINE
    if _GLOBAL_OCR_ENGINE is None and HAS_OCR:
        try:
            _GLOBAL_OCR_ENGINE = RapidOCR()
            logger.info("OCR engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OCR: {e}")
    return _GLOBAL_OCR_ENGINE

MATERIAL_ICONS = {
    "rect": "M3 3h18v18H3V3zm16 16V5H5v14h14z",
    "circle": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z",
    "arrow": "M19 12l-7-7v4H5v6h7v4z",
    "line": "M3 13h18v-2H3v2z M21 5L3 19l1.4 1.4L22.4 6.4z",
    "pencil": "M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z",
    "marker": "M15.5 2.5l6 6-12 12H3.5v-6l12-12zm-2 4L5.5 14.5v4h4L17.5 10.5l-4-4z",
    "text": "M5 4v3h5.5v12h3V7H19V4H5z",
    "mosaic": "M3 3h4v4H3zm7 0h4v4h-4zm7 0h4v4h-4zM3 10h4v4H3zm7 0h4v4h-4zm7 0h4v4h-4zM3 17h4v4H3zm7 0h4v4h-4zm7 0h4v4h-4z",
    "badge": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15v-6h2v6h-2zm0-8V7h2v2h-2z",
    "undo": "M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z",
    "pin": "M16 9V4l1 0V2H7v2l1 0v5c0 1.66-1.34 3-3 3v2h5.97v7l1 1 1-1v-7H19v-2c-1.66 0-3-1.34-3-3z",
    "save": "M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z",
    "close": "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z",
    "check": "M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z",
    "palette": "M12 22C6.49 22 2 17.51 2 12S6.49 2 12 2s10 4.49 10 10c0 1.38-1.12 2.5-2.5 2.5-.59 0-1.13-.21-1.55-.59-.36-.33-.86-.56-1.45-.56-1.38 0-2.5 1.12-2.5 2.5v.65C14 19.54 11.54 22 12 22z",
    "picker": "M20.71 5.63l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-3.12 3.12-1.93-1.91-1.41 1.41 1.42 1.42L3 16.25V21h4.75l8.92-8.92 1.42 1.42 1.41-1.41-1.92-1.92 3.12-3.12c.4-.4.4-1.03.01-1.42zM6.92 19L5 17.08l8.06-8.06 1.92 1.92L6.92 19z",
    "ocr": "M3 4v4h2V6h4V4H3zm18 0h-6v2h4v2h2V4zM3 20v-4H1v6h6v-2H3zm18-4h-2v4h-4v2h6v-6zm-4-9H7v10h10V7z",
}

def get_svg_icon(name: str, color: str = "#475569", size: int = 24) -> QIcon:
    try:
        path_data = MATERIAL_ICONS.get(name, MATERIAL_ICONS["rect"])
        svg_str = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="{color}" d="{path_data}"/></svg>'
        renderer = QSvgRenderer()
        renderer.load(svg_str.encode("utf-8"))
        
        render_size = max(size * 4, 96)
        pixmap = QPixmap(render_size, render_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)
    except Exception as e:
        logger.error(f"Error creating icon {name}: {e}")
        return QIcon()

def get_logo_icon(size: int = 24) -> QIcon:
    try:
        svg_str = """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
            <defs>
                <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#3b82f6" />
                    <stop offset="100%" stop-color="#1d4ed8" />
                </linearGradient>
            </defs>
            <rect width="22" height="22" x="1" y="1" rx="6" fill="url(#bg)"/>
            <path d="M7 10V7h3M14 7h3v3M17 14v3h-3M10 17H7v-3" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="12" cy="12" r="2.2" fill="#ffffff"/>
        </svg>
        """
        renderer = QSvgRenderer()
        renderer.load(svg_str.encode("utf-8"))
        render_size = max(size * 4, 96)
        pixmap = QPixmap(render_size, render_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)
    except Exception as e:
        logger.error(f"Error creating logo icon: {e}")
        return QIcon()

class Config:
    DEFAULT_CONFIG = {
        "last_save_dir": str(Path.home() / "Pictures"),
        "enable_sound": True,
        "auto_copy": True,
        "show_magnifier": True,
        "auto_detect_window": True,
        "pen_width": 3,
        "default_color": "#ea4335",
        "custom_color": "#8ab4f8",
        "hotkey": "Ctrl+Alt+A",
        "image_quality": 95,
        "save_format": "PNG",
        "hdr_tone_mapping": False,
        "tone_mapping_strength": 0.85,
    }

    def __init__(self):
        self.data = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if not _CONFIG_FILE.exists():
            self.save()
            return
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                self.data.update(json.load(f))
        except Exception:
            pass

    def save(self):
        try:
            temp_file = _CONFIG_FILE.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            temp_file.replace(_CONFIG_FILE)
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value
        self.save()

_config = Config()

def _parse_hotkey(hk_str: str) -> tuple[int, int]:
    hk_str = hk_str.split(',')[0].strip().upper().replace(' ', '')
    modifiers = 0
    vk = 0
    if "CTRL" in hk_str or "CONTROL" in hk_str: modifiers |= 0x0002
    if "ALT" in hk_str: modifiers |= 0x0001
    if "SHIFT" in hk_str: modifiers |= 0x0004
    if "WIN" in hk_str or "META" in hk_str: modifiers |= 0x0008
    
    parts = hk_str.split('+')
    if not parts: return 0, 0
    last_part = parts[-1]
    
    if len(last_part) == 1 and last_part.isalpha(): vk = ord(last_part)
    elif last_part.startswith('F') and last_part[1:].isdigit():
        num = int(last_part[1:])
        if 1 <= num <= 24: vk = 0x6F + num
    elif last_part == "SPACE": vk = 0x20
    elif last_part == "ENTER": vk = 0x0D
    elif last_part == "ESC": vk = 0x1B
    return modifiers, vk

def check_hotkey_conflict_win(hk_str: str) -> tuple[bool, str]:
    if os.name != "nt": return True, ""
    modifiers, vk = _parse_hotkey(hk_str)
    if vk == 0: return False, "无效快捷键"
    try:
        if ctypes.windll.user32.RegisterHotKey(None, 0x1337, modifiers, vk):
            ctypes.windll.user32.UnregisterHotKey(None, 0x1337)
            return True, ""
        return False, f"快捷键 {hk_str} 已被占用，请尝试其他组合"
    except Exception:
        return False, "检测失败"

def _get_target_exe_path() -> str:
    if getattr(sys, 'frozen', False) or "__compiled__" in globals():
        return str(Path(sys.executable).resolve())
    return str(Path(sys.argv[0]).resolve())

def check_autostart_win() -> bool:
    if os.name != "nt": return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, __app_name__)
        winreg.CloseKey(key)
        return val.strip('\"').strip().lower() == _get_target_exe_path().lower()
    except Exception:
        return False

def set_autostart_win(enable: bool):
    if os.name != "nt": return
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        if enable:
            winreg.SetValueEx(key, __app_name__, 0, winreg.REG_SZ, f'"{_get_target_exe_path()}"')
        else:
            try: winreg.DeleteValue(key, __app_name__)
            except FileNotFoundError: pass
        winreg.CloseKey(key)
    except Exception as e:
        logger.error(f"Failed to set autostart: {e}")

def play_shutter_sound():
    if not _config.get("enable_sound", True) or os.name != "nt": return
    try:
        shutter_wav = _CONFIG_DIR / "shutter.wav"
        if not shutter_wav.exists():
            sample_rate, duration = 44100, 0.12
            n_samples = int(sample_rate * duration)
            samples = [0.0] * n_samples
            for i in range(n_samples):
                t = i / sample_rate
                click1 = math.sin(2 * math.pi * 1800 * t) * math.exp(-70 * t)
                click2 = (math.sin(2 * math.pi * 1200 * (t - 0.04)) * math.exp(-60 * (t - 0.04)) if t > 0.04 else 0.0)
                samples[i] = (click1 * 0.7 + click2 * 0.5) * 0.35
            with wave.open(shutter_wav.as_posix(), "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                packed = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples)
                wf.writeframes(packed)
        import winsound
        winsound.PlaySound(shutter_wav.as_posix(), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass

if os.name == "nt":
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    def get_window_rects(virtual_top_left: QPoint, dpr: float) -> list[QRect]:
        rects = []
        user32 = ctypes.windll.user32
        try: dwmapi = ctypes.windll.dwmapi
        except Exception: dwmapi = None

        def callback(hwnd, _):
            try:
                if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd): return True
                
                if dwmapi:
                    cloaked = ctypes.c_int(0)
                    DWMWA_CLOAKED = 14
                    try:
                        dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
                        if cloaked.value != 0: return True
                    except Exception: pass

                rect = RECT()
                DWMWA_EXTENDED_FRAME_BOUNDS = 9
                got_real_bounds = False
                if dwmapi:
                    try:
                        hr = dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect))
                        if hr == 0: got_real_bounds = True
                    except Exception: pass
                
                if not got_real_bounds:
                    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)): return True

                rx = int(rect.left / dpr) - virtual_top_left.x()
                ry = int(rect.top / dpr) - virtual_top_left.y()
                w = int((rect.right - rect.left) / dpr)
                h = int((rect.bottom - rect.top) / dpr)
                
                if w > 40 and h > 40:
                    rects.append(QRect(rx, ry, w, h))
            except Exception: pass
            return True

        try:
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(EnumWindowsProc(callback), 0)
        except Exception: pass
        return rects
else:
    def get_window_rects(virtual_top_left: QPoint, dpr: float) -> list[QRect]: return []

def apply_hdr_tone_mapping(image: QPixmap, strength: float = 0.85) -> QPixmap:
    if not HAS_NUMPY or image.isNull(): return image
    try:
        original_dpr = image.devicePixelRatio()
        qimg = image.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        w, h = qimg.width(), qimg.height()
        
        ptr = qimg.bits()
        buf = memoryview(ptr)
        arr = np.frombuffer(buf, dtype=np.uint8).reshape((h, w, 4)).copy()
        
        rgb = arr[:, :, :3].astype(np.float32) / 255.0
        mapped = rgb * rgb * (3.0 - 2.0 * rgb)
        blended = rgb * (1.0 - strength) + mapped * strength
        arr[:, :, :3] = (blended * 255.0).astype(np.uint8)
        
        result_qimg = QImage(arr.tobytes(), w, h, QImage.Format.Format_RGBA8888)
        result_qimg.setDevicePixelRatio(original_dpr)
        res = QPixmap.fromImage(result_qimg)
        res.setDevicePixelRatio(original_dpr)
        return res
    except Exception as e: 
        logger.error(f"HDR tone mapping failed: {e}")
        return image

def capture_full_desktop_instant() -> tuple[QPixmap, float, QRect]:
    try:
        screens = QGuiApplication.screens()
        if not screens: raise RuntimeError("No screens detected")
        
        virtual_rect = QRect()
        max_dpr = 1.0
        for screen in screens:
            virtual_rect = virtual_rect.united(screen.geometry())
            max_dpr = max(max_dpr, screen.devicePixelRatio())
        
        phys_w = int(virtual_rect.width() * max_dpr)
        phys_h = int(virtual_rect.height() * max_dpr)
        full_pixmap = QPixmap(phys_w, phys_h)
        full_pixmap.setDevicePixelRatio(max_dpr)
        full_pixmap.fill(Qt.GlobalColor.black)

        painter = QPainter(full_pixmap)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for screen in screens:
            grab = screen.grabWindow(0)
            if not grab.isNull():
                painter.drawPixmap(screen.geometry().topLeft() - virtual_rect.topLeft(), grab)
        painter.end()
        return full_pixmap, max_dpr, virtual_rect
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return QPixmap(), 1.0, QRect()

class DrawItem:
    def paint(self, painter: QPainter, base_pixmap: Optional[QPixmap] = None): pass
    def contains(self, pos: QPointF) -> bool: return False
    def move_by(self, delta: QPointF): pass
    def bounding_rect(self) -> QRectF: return QRectF()
    def _stroke_contains(self, path: QPainterPath, pos: QPointF, width: int) -> bool:
        stroker = QPainterPathStroker()
        stroker.setWidth(width + 10)
        return stroker.createStroke(path).contains(pos)

class RectItem(DrawItem):
    def __init__(self, rect: QRectF, color: QColor, width: int = 2):
        self.rect, self.color, self.width = rect, color, width
    def paint(self, painter: QPainter, base_pixmap: Optional[QPixmap] = None):
        painter.setPen(QPen(self.color, self.width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect)
    def contains(self, pos: QPointF) -> bool:
        p = QPainterPath()
        p.addRect(self.rect)
        return self._stroke_contains(p, pos, self.width)
    def move_by(self, delta: QPointF): self.rect.translate(delta)
    def bounding_rect(self) -> QRectF: return self.rect.normalized().adjusted(-self.width, -self.width, self.width, self.width)

class CircleItem(DrawItem):
    def __init__(self, rect: QRectF, color: QColor, width: int = 2):
        self.rect, self.color, self.width = rect, color, width
    def paint(self, painter: QPainter, base_pixmap: Optional[QPixmap] = None):
        painter.setPen(QPen(self.color, self.width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(self.rect)
    def contains(self, pos: QPointF) -> bool:
        p = QPainterPath()
        p.addEllipse(self.rect)
        return self._stroke_contains(p, pos, self.width)
    def move_by(self, delta: QPointF): self.rect.translate(delta)
    def bounding_rect(self) -> QRectF: return self.rect.normalized().adjusted(-self.width, -self.width, self.width, self.width)

class LineItem(DrawItem):
    def __init__(self, start: QPointF, end: QPointF, color: QColor, width: int = 2):
        self.start, self.end, self.color, self.width = start, end, color, width
    def paint(self, painter: QPainter, base_pixmap: Optional[QPixmap] = None):
        painter.setPen(QPen(self.color, self.width))
        painter.drawLine(self.start, self.end)
    def contains(self, pos: QPointF) -> bool:
        p = QPainterPath()
        p.moveTo(self.start); p.lineTo(self.end)
        return self._stroke_contains(p, pos, self.width)
    def move_by(self, delta: QPointF): self.start += delta; self.end += delta
    def bounding_rect(self) -> QRectF: return QRectF(self.start, self.end).normalized().adjusted(-self.width, -self.width, self.width, self.width)

class ArrowItem(DrawItem):
    def __init__(self, start: QPointF, end: QPointF, color: QColor, width: int = 2):
        self.start, self.end, self.color, self.width = start, end, color, width
    def _get_arrow_polygon(self):
        dx, dy = self.start.x() - self.end.x(), self.start.y() - self.end.y()
        length = math.hypot(dx, dy)
        if length == 0: return self.end, self.end
        nx, ny = dx / length, dy / length
        head_len, arrow_w = self.width * 4 + 5, self.width * 2 + 3
        p1 = QPointF(self.end.x() + nx * head_len - ny * arrow_w, self.end.y() + ny * head_len + nx * arrow_w)
        p2 = QPointF(self.end.x() + nx * head_len + ny * arrow_w, self.end.y() + ny * head_len - nx * arrow_w)
        return p1, p2
    def paint(self, painter: QPainter, base_pixmap: Optional[QPixmap] = None):
        painter.setPen(QPen(self.color, self.width))
        painter.drawLine(self.start, self.end)
        p1, p2 = self._get_arrow_polygon()
        painter.setBrush(QBrush(self.color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([self.end, p1, p2]))
    def contains(self, pos: QPointF) -> bool:
        p = QPainterPath()
        p.moveTo(self.start); p.lineTo(self.end)
        p1, p2 = self._get_arrow_polygon()
        p.addPolygon(QPolygonF([self.end, p1, p2]))
        return self._stroke_contains(p, pos, self.width)
    def move_by(self, delta: QPointF): self.start += delta; self.end += delta
    def bounding_rect(self) -> QRectF:
        p1, p2 = self._get_arrow_polygon()
        return QRectF(self.start, self.end).normalized().united(QRectF(p1, p2).normalized()).adjusted(-self.width, -self.width, self.width, self.width)

class PencilItem(DrawItem):
    def __init__(self, points: list[QPointF], color: QColor, width: int = 2, is_marker: bool = False):
        self.points, self.color, self.width, self.is_marker = points, color, width, is_marker
    def paint(self, painter: QPainter, base_pixmap: Optional[QPixmap] = None):
        if not self.points: return
        actual_w = self.width * (3 if self.is_marker else 1)
        c = QColor(self.color)
        if self.is_marker: c.setAlpha(100)
        if len(self.points) == 1:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(c))
            painter.drawEllipse(self.points[0], actual_w, actual_w)
            return
        painter.setPen(QPen(c, actual_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(self.points[0])
        for p in self.points[1:]: path.lineTo(p)
        painter.drawPath(path)
    def contains(self, pos: QPointF) -> bool:
        if not self.points: return False
        actual_w = self.width * (3 if self.is_marker else 1)
        if len(self.points) == 1: return math.hypot(pos.x() - self.points[0].x(), pos.y() - self.points[0].y()) <= actual_w + 5
        path = QPainterPath()
        path.moveTo(self.points[0])
        for p in self.points[1:]: path.lineTo(p)
        return self._stroke_contains(path, pos, actual_w)
    def move_by(self, delta: QPointF):
        for i in range(len(self.points)): self.points[i] += delta
    def bounding_rect(self) -> QRectF:
        if not self.points: return QRectF()
        xs, ys = [p.x() for p in self.points], [p.y() for p in self.points]
        actual_w = self.width * (3 if self.is_marker else 1)
        return QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)).adjusted(-actual_w, -actual_w, actual_w, actual_w)

class TextItem(DrawItem):
    """高可读性文字标注项，支持多行与全场景对比度阴影描边"""
    def __init__(self, pos: QPointF, text: str, font: QFont, color: QColor):
        self.pos = pos
        self.text = text
        self.font = font
        self.color = color
        self._calculate_rect()

    def _calculate_rect(self):
        fm = QFontDialog().fontMetrics() if False else None
        dummy = QImage(1, 1, QImage.Format.Format_Alpha8)
        p = QPainter(dummy)
        p.setFont(self.font)
        fm = p.fontMetrics()
        lines = self.text.split('\n')
        max_w = max((fm.horizontalAdvance(l) for l in lines), default=20)
        line_h = fm.height()
        th = line_h * len(lines)
        p.end()
        self._rect = QRectF(self.pos.x(), self.pos.y(), max_w + 12, th + 8)

    def paint(self, painter: QPainter, base_pixmap: Optional[QPixmap] = None):
        painter.setFont(self.font)
        fm = painter.fontMetrics()
        lines = self.text.split('\n')
        max_w = max((fm.horizontalAdvance(l) for l in lines), default=20)
        line_h = fm.height()
        th = line_h * len(lines)
        
        rect = QRectF(self.pos.x(), self.pos.y(), max_w + 12, th + 8)
        self._rect = rect
        
        is_dark = (self.color.red() * 0.299 + self.color.green() * 0.587 + self.color.blue() * 0.114) < 140
        shadow_color = QColor(255, 255, 255, 220) if is_dark else QColor(0, 0, 0, 190)
        
        painter.setPen(shadow_color)
        for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1)]:
            painter.drawText(rect.translated(ox, oy), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), self.text)
            
        painter.setPen(self.color)
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), self.text)

    def contains(self, pos: QPointF) -> bool:
        return self._rect.adjusted(-4, -4, 4, 4).contains(pos)

    def move_by(self, delta: QPointF):
        self.pos += delta
        self._rect.translate(delta)

    def bounding_rect(self) -> QRectF:
        return self._rect.adjusted(-4, -4, 4, 4)

class StepBadgeItem(DrawItem):
    def __init__(self, pos: QPointF, number: int, color: QColor):
        self.pos, self.number, self.color, self.radius = pos, number, color, 12
    def paint(self, painter: QPainter, base_pixmap: Optional[QPixmap] = None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 80))
        painter.drawEllipse(self.pos + QPointF(1, 1), self.radius, self.radius)
        painter.setBrush(self.color)
        painter.drawEllipse(self.pos, self.radius, self.radius)
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        r = QRectF(self.pos.x() - self.radius, self.pos.y() - self.radius, self.radius * 2, self.radius * 2)
        painter.drawText(r, Qt.AlignmentFlag.AlignCenter, str(self.number))
    def contains(self, pos: QPointF) -> bool: return math.hypot(pos.x() - self.pos.x(), pos.y() - self.pos.y()) <= self.radius + 5
    def move_by(self, delta: QPointF): self.pos += delta
    def bounding_rect(self) -> QRectF: return QRectF(self.pos.x() - self.radius, self.pos.y() - self.radius, self.radius * 2, self.radius * 2)

class MosaicItem(DrawItem):
    def __init__(self, rect: QRectF, block_size: int = 10):
        self.rect, self.block_size = rect, block_size
    def paint(self, painter: QPainter, base_pixmap: Optional[QPixmap] = None):
        r = self.rect.normalized()
        if r.isEmpty() or not base_pixmap: return
        painter.save()
        painter.setClipRect(r)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        src_img, dpr, bs = base_pixmap.toImage(), base_pixmap.devicePixelRatio(), self.block_size
        for y in range(int(r.top()), int(r.bottom()), bs):
            for x in range(int(r.left()), int(r.right()), bs):
                px = min(int((x + bs/2) * dpr), src_img.width() - 1)
                py = min(int((y + bs/2) * dpr), src_img.height() - 1)
                if px >= 0 and py >= 0: painter.fillRect(x, y, bs, bs, src_img.pixelColor(px, py))
        painter.restore()
    def contains(self, pos: QPointF) -> bool: return self.rect.normalized().contains(pos)
    def move_by(self, delta: QPointF): self.rect.translate(delta)
    def bounding_rect(self) -> QRectF: return self.rect.normalized()

class TextAnnotationWidget(QFrame):
    """
    独立封装的自适应文字卡片编辑器：
    - 集成格式微调工具条 (Font/Size/Bold/Color/OK/Cancel)
    - 绝不因点击格式按钮而失焦销毁
    - 支持 Ctrl + 滚轮实时缩放文字字号
    - 支持多行换行与自适应尺寸拉伸
    """
    committed = Signal(str, QPointF, QFont, QColor)
    cancelled = Signal()

    def __init__(self, pos: QPoint, initial_text: str = "", font: Optional[QFont] = None, color: Optional[QColor] = None, parent=None):
        super().__init__(parent)
        self.setParent(parent)
        self.start_pos = pos
        self.current_font = QFont(font) if font else QFont("Microsoft YaHei", 16, QFont.Weight.Bold)
        self.current_color = QColor(color) if color else QColor(_config.get("default_color", "#ea4335"))
        self._is_dragging = False
        self._drag_start = QPoint()

        self.setObjectName("TextAnnotationCard")
        self.setStyleSheet("""
            #TextAnnotationCard {
                background-color: #ffffff;
                border: 2px solid #1a73e8;
                border-radius: 8px;
            }
            QToolButton {
                background: transparent;
                border: none;
                border-radius: 4px;
                color: #3c4043;
                font-weight: bold;
                font-size: 13px;
                padding: 2px 6px;
            }
            QToolButton:hover {
                background-color: #f1f3f4;
            }
            QToolButton:checked {
                background-color: #e8f0fe;
                color: #1a73e8;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)

        self.toolbar_widget = QWidget(self)
        tb_layout = QHBoxLayout(self.toolbar_widget)
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(3)

        self.drag_handle = QLabel("⠿")
        self.drag_handle.setStyleSheet("color: #9aa0a6; font-size: 14px; font-weight: bold;")
        self.drag_handle.setCursor(Qt.CursorShape.SizeAllCursor)
        tb_layout.addWidget(self.drag_handle)

        self.btn_font = QToolButton()
        self.btn_font.setText("字体")
        self.btn_font.setToolTip("选择字体 (Aa)")
        self.btn_font.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_font.clicked.connect(self._choose_font)
        tb_layout.addWidget(self.btn_font)

        self.btn_minus = QToolButton()
        self.btn_minus.setText("A-")
        self.btn_minus.setToolTip("缩小字号 (或Ctrl+滚轮)")
        self.btn_minus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_minus.clicked.connect(lambda: self._change_font_size(-2))
        tb_layout.addWidget(self.btn_minus)

        self.size_label = QLabel(f"{self.current_font.pointSize()}")
        self.size_label.setStyleSheet("color: #1a73e8; font-weight: bold; font-size: 12px; min-width: 18px;")
        self.size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tb_layout.addWidget(self.size_label)

        self.btn_plus = QToolButton()
        self.btn_plus.setText("A+")
        self.btn_plus.setToolTip("放大字号 (或Ctrl+滚轮)")
        self.btn_plus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_plus.clicked.connect(lambda: self._change_font_size(2))
        tb_layout.addWidget(self.btn_plus)

        self.btn_bold = QToolButton()
        self.btn_bold.setText("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setChecked(self.current_font.bold())
        self.btn_bold.setToolTip("切换加粗")
        self.btn_bold.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_bold.clicked.connect(self._toggle_bold)
        tb_layout.addWidget(self.btn_bold)

        self.color_preview = QToolButton()
        self.color_preview.setFixedSize(18, 18)
        self.color_preview.setToolTip("选择文本颜色")
        self.color_preview.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.color_preview.clicked.connect(self._choose_color)
        self._update_color_preview()
        tb_layout.addWidget(self.color_preview)

        tb_layout.addStretch()

        self.btn_ok = QToolButton()
        self.btn_ok.setIcon(get_svg_icon("check", "#34a853", 16))
        self.btn_ok.setToolTip("完成 (Enter / Ctrl+Enter)")
        self.btn_ok.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_ok.clicked.connect(self.commit)
        tb_layout.addWidget(self.btn_ok)

        self.btn_cancel = QToolButton()
        self.btn_cancel.setIcon(get_svg_icon("close", "#ea4335", 16))
        self.btn_cancel.setToolTip("取消 (Esc)")
        self.btn_cancel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_cancel.clicked.connect(self.cancel)
        tb_layout.addWidget(self.btn_cancel)

        main_layout.addWidget(self.toolbar_widget)

        self.edit = QTextEdit(self)
        self.edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.edit.setPlaceholderText("输入文字内容...")
        self.edit.setFont(self.current_font)
        self._update_edit_stylesheet()
        
        if initial_text:
            self.edit.setPlainText(initial_text)
            self.edit.selectAll()

        self.edit.document().contentsChanged.connect(self._adjust_size)
        self.edit.installEventFilter(self)
        main_layout.addWidget(self.edit)

        self.move(pos)
        self._adjust_size()
        QTimer.singleShot(50, self.edit.setFocus)

    def _update_color_preview(self):
        self.color_preview.setStyleSheet(f"""
            QToolButton {{
                background-color: {self.current_color.name()};
                border: 1px solid #dadce0;
                border-radius: 9px;
            }}
        """)

    def _update_edit_stylesheet(self):
        self.edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent;
                border: 1px dashed #dadce0;
                border-radius: 4px;
                color: {self.current_color.name()};
                padding: 4px;
            }}
        """)

    def _choose_font(self):
        ok, font = QFontDialog.getFont(self.current_font, self, "选择字体")
        if ok:
            self.current_font = font
            self.edit.setFont(font)
            self.btn_bold.setChecked(font.bold())
            self.size_label.setText(f"{font.pointSize()}")
            self._adjust_size()
            self.edit.setFocus()

    def _change_font_size(self, delta: int):
        ps = max(9, min(96, self.current_font.pointSize() + delta))
        self.current_font.setPointSize(ps)
        self.edit.setFont(self.current_font)
        self.size_label.setText(f"{ps}")
        self._adjust_size()
        self.edit.setFocus()

    def _toggle_bold(self):
        self.current_font.setBold(self.btn_bold.isChecked())
        self.edit.setFont(self.current_font)
        self._adjust_size()
        self.edit.setFocus()

    def _choose_color(self):
        color = QColorDialog.getColor(self.current_color, self, "选择文本颜色")
        if color.isValid():
            self.current_color = color
            self._update_color_preview()
            self._update_edit_stylesheet()
            self.edit.setFocus()

    def _adjust_size(self):
        self.edit.document().setTextWidth(-1)
        doc_w = int(self.edit.document().idealWidth()) + 20
        doc_h = int(self.edit.document().size().height()) + 14
        
        edit_w = max(180, doc_w)
        edit_h = max(38, doc_h)
        self.edit.setFixedSize(edit_w, edit_h)

        tb_w = self.toolbar_widget.sizeHint().width()
        total_w = max(edit_w, tb_w) + 16
        total_h = edit_h + self.toolbar_widget.sizeHint().height() + 18
        self.resize(total_w, total_h)

    def eventFilter(self, obj, event):
        if obj == self.edit:
            if event.type() == event.Type.KeyPress:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if event.modifiers() & Qt.KeyboardModifier.ControlModifier or not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                        self.commit()
                        return True
                elif event.key() == Qt.Key.Key_Escape:
                    self.cancel()
                    return True
            elif event.type() == event.Type.Wheel:
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    delta = 2 if event.angleDelta().y() > 0 else -2
                    self._change_font_size(delta)
                    return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_start = event.globalPosition().toPoint() - self.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_start)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        super().mouseReleaseEvent(event)

    def commit(self):
        text = self.edit.toPlainText().strip()
        if text:
            target_pt = self.pos() + self.edit.pos()
            self.committed.emit(text, QPointF(target_pt), self.current_font, self.current_color)
        else:
            self.cancelled.emit()

    def cancel(self):
        self.cancelled.emit()

class FloatingToolBar(QFrame):
    action_triggered = Signal(str)
    tool_changed = Signal(str)
    color_changed = Signal(QColor)
    width_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FloatingToolBar")
        self.setStyleSheet("""
            #FloatingToolBar { background: #ffffff; border: 1px solid #d2d2d2; border-radius: 8px; }
            QToolButton { border: none; border-radius: 6px; padding: 6px; background: transparent; }
            QToolButton:hover { background: #f1f3f4; }
            QToolButton:checked { background: #e8f0fe; }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        drag_handle = QLabel("⋮⋮")
        drag_handle.setStyleSheet("color: #9aa0a6; font-weight: bold; font-size: 16px;")
        drag_handle.setCursor(Qt.CursorShape.SizeAllCursor)
        layout.addWidget(drag_handle)
        
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.buttons = {}
        tools = [
            ("rect", "矩形 (R)", True), ("circle", "椭圆 (O)", True), 
            ("arrow", "箭头 (A)", True), ("line", "直线 (L)", True), 
            ("pencil", "画笔 (P)", True), ("marker", "荧光笔 (H)", True), 
            ("text", "文本 (T)", True), ("mosaic", "马赛克 (M)", True), 
            ("badge", "序号 (B)", True), ("picker", "吸管取色 (C)", True)
        ]
        for action, tooltip, checkable in tools:
            btn = QToolButton()
            btn.setToolTip(tooltip)
            btn.setIcon(get_svg_icon(action, "#5f6368", 20))
            btn.setIconSize(QSize(20, 20))
            btn.setCheckable(checkable)
            self.btn_group.addButton(btn)
            btn.clicked.connect(lambda checked, a=action: self.tool_changed.emit(a))
            layout.addWidget(btn)
            self.buttons[action] = btn
            
        self._add_separator(layout)
        self._current_width = _config.get("pen_width", 3)
        self.width_group = QButtonGroup(self)
        self.width_group.setExclusive(True)
        for width_val, tooltip in [(2, "细 (1)"), (3, "中 (2)"), (5, "粗 (3)")]:
            w_btn = QToolButton()
            w_btn.setFixedSize(20, 20)
            w_btn.setToolTip(tooltip)
            w_btn.setCheckable(True)
            w_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            circle_size = width_val * 2
            w_btn.setStyleSheet(f"""QToolButton {{ background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #5f6368, stop:{circle_size/20.0} #5f6368, stop:1 transparent); border: 1px solid #dadce0; border-radius: 10px; }} QToolButton:checked {{ border: 2px solid #1a73e8; background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #1a73e8, stop:{circle_size/20.0} #1a73e8, stop:1 #e8f0fe); }}""")
            w_btn.clicked.connect(lambda checked, w=width_val: self._on_width_changed(w))
            self.width_group.addButton(w_btn)
            layout.addWidget(w_btn)
            if width_val == self._current_width: w_btn.setChecked(True)
            
        self._add_separator(layout)
        self._current_color = QColor(_config.get("default_color", "#ea4335"))
        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        for hex_val, name in [("#ea4335", "红色"), ("#fbbc05", "黄色"), ("#34a853", "绿色"), ("#1a73e8", "蓝色"), ("#202124", "黑色"), ("#ffffff", "白色")]:
            c_btn = QToolButton()
            c_btn.setFixedSize(20, 20)
            c_btn.setToolTip(name)
            c_btn.setCheckable(True)
            c_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            c_btn.setStyleSheet(f"""QToolButton {{ background-color: {hex_val}; border: {'2px solid #dadce0' if hex_val == '#ffffff' else '1px solid #dadce0'}; border-radius: 10px; margin: 1px; }} QToolButton:checked {{ border: 2px solid #5f6368; margin: 0px; }}""")
            c_btn.clicked.connect(lambda checked, c=hex_val: self._set_color(c))
            self.color_group.addButton(c_btn)
            layout.addWidget(c_btn)
            if hex_val.upper() == self._current_color.name().upper(): c_btn.setChecked(True)
            
        self.palette_btn = QToolButton()
        self.palette_btn.setToolTip("更多颜色...")
        self.palette_btn.setIcon(get_svg_icon("palette", "#5f6368", 20))
        self.palette_btn.setIconSize(QSize(20, 20))
        self.palette_btn.clicked.connect(self._choose_color)
        layout.addWidget(self.palette_btn)
        
        self._add_separator(layout)
        for action, tooltip, color in [("undo", "撤销 (Ctrl+Z)", "#5f6368"), ("ocr", "提取文字", "#1a73e8"), ("pin", "贴图 (F3)", "#1a73e8"), ("save", "保存 (Ctrl+S)", "#1a73e8"), ("close", "退出 (Esc)", "#ea4335"), ("check", "完成并复制 (Enter)", "#34a853")]:
            btn = QToolButton()
            btn.setToolTip(tooltip)
            btn.setIcon(get_svg_icon(action, color, 20))
            btn.setIconSize(QSize(20, 20))
            if action == "check": action = "finish"
            btn.clicked.connect(lambda checked, a=action: self.action_triggered.emit(a))
            layout.addWidget(btn)
            
        self._is_dragging = False
        self._drag_start_pos = QPoint()
        QTimer.singleShot(0, lambda: self.color_changed.emit(QColor(self._current_color)))
        QTimer.singleShot(0, lambda: self.width_changed.emit(self._current_width))

    def _add_separator(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #dadce0;")
        layout.addWidget(sep)
    def _on_width_changed(self, width: int):
        self._current_width = width
        self.width_changed.emit(width)
    def _set_color(self, hex_val: str):
        self._current_color = QColor(hex_val)
        self.color_changed.emit(QColor(hex_val))
    def _choose_color(self):
        color = QColorDialog.getColor(self._current_color, self, "选择颜色")
        if color.isValid():
            if self.color_group.checkedButton():
                self.color_group.setExclusive(False)
                self.color_group.checkedButton().setChecked(False)
                self.color_group.setExclusive(True)
            self._set_color(color.name())
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_start_pos = event.globalPosition().toPoint()
            event.accept()
        else: super().mousePressEvent(event)
    def mouseMoveEvent(self, event):
        if self._is_dragging:
            global_pos = event.globalPosition().toPoint()
            delta = global_pos - self._drag_start_pos
            self.move(self.pos() + delta)
            self._drag_start_pos = global_pos
            event.accept()
        else: super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self._is_dragging = False
        super().mouseReleaseEvent(event)

class PinnedImageWidget(QWidget):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.original_pixmap, self.scale_factor, self.opacity, self.drag_pos = pixmap, 1.0, 1.0, QPoint()
        self.setFixedSize(self.original_pixmap.size())
        self.setCursor(Qt.CursorShape.OpenHandCursor)
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(self.opacity)
        painter.drawPixmap(self.rect(), self.original_pixmap)
        painter.setPen(QPen(QColor(255, 255, 255, 140), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            menu.setStyleSheet("QMenu { background: #ffffff; border: 1px solid #e8eaed; border-radius: 8px; padding: 4px; } QMenu::item { padding: 6px 18px; border-radius: 4px; color: #3c4043; font-size: 12px; } QMenu::item:selected { background: #e8f0fe; color: #1a73e8; }")
            menu.addAction("复制图片", lambda: QApplication.clipboard().setPixmap(self.original_pixmap))
            menu.addAction("恢复 100% 大小", self._reset_scale)
            menu.addSeparator()
            menu.addAction("关闭贴图 (Esc / 双击)", self.close)
            menu.exec(event.globalPosition().toPoint())
    def _reset_scale(self):
        self.scale_factor = 1.0
        self.setFixedSize(self.original_pixmap.size())
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton: self.move(self.mapToGlobal(event.position().toPoint()) - self.drag_pos)
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.opacity = min(1.0, max(0.15, self.opacity + (0.05 if delta > 0 else -0.05)))
            self.update()
        else:
            self.scale_factor = max(0.15, min(5.0, self.scale_factor * (1.1 if delta > 0 else 0.9)))
            base_w, base_h = self.original_pixmap.width(), self.original_pixmap.height()
            self.setFixedSize(max(30, int(base_w * self.scale_factor)), max(30, int(base_h * self.scale_factor)))
    def mouseDoubleClickEvent(self, event): self.close()
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: self.close()

class OCRWorker(QThread):
    finished = Signal(str, bool)
    def __init__(self, img_bytes: bytes):
        super().__init__()
        self.img_bytes, self._is_cancelled = img_bytes, False
    def run(self):
        try:
            ocr = get_ocr_engine()
            if self._is_cancelled or not ocr: return
            result, _ = ocr(self.img_bytes)
            if self._is_cancelled: return
            if result:
                lines_data = [{"text": res[1], "x": min(p[0] for p in res[0]), "y": sum(p[1] for p in res[0]) / 4.0, "h": max(p[1] for p in res[0]) - min(p[1] for p in res[0])} for res in result]
                lines_data.sort(key=lambda item: item["y"])
                grouped_lines, current_line = [], []
                for item in lines_data:
                    if not current_line: current_line.append(item)
                    else:
                        avg_h = sum(b["h"] for b in current_line) / len(current_line)
                        if abs(item["y"] - current_line[0]["y"]) < avg_h * 0.6: current_line.append(item)
                        else:
                            current_line.sort(key=lambda b: b["x"])
                            grouped_lines.append(self._smart_join(current_line))
                            current_line = [item]
                if current_line:
                    current_line.sort(key=lambda b: b["x"])
                    grouped_lines.append(self._smart_join(current_line))
                self.finished.emit("\n".join(grouped_lines), True)
            else: self.finished.emit("未识别到文字，请确保选区清晰。", False)
        except Exception as e: self.finished.emit(f"OCR 引擎错误:\n{str(e)}", False)
    def _smart_join(self, line_items: list[dict]) -> str:
        text = ""
        for i, item in enumerate(line_items):
            curr_str = item["text"]
            if not curr_str: continue
            if i == 0: text += curr_str
            else:
                prev_char, curr_char = text[-1] if text else "", curr_str[0]
                if prev_char.isalnum() and curr_char.isalnum() and ord(prev_char) < 128 and ord(curr_char) < 128: text += " " + curr_str
                else: text += curr_str
        return text
    def cancel(self): self._is_cancelled = True

class OCRDialog(QDialog):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{__app_name__} - 文字识别 (OCR)")
        self.resize(560, 400)
        self.worker: Optional[OCRWorker] = None
        self.setStyleSheet("""
            QDialog { background-color: #f8fafc; }
            QTextEdit { background: #ffffff; border: 1px solid #e8eaed; border-radius: 8px; padding: 10px; font-size: 13px; color: #202124; line-height: 1.5; font-family: Consolas, 'Microsoft YaHei'; }
            QPushButton { background: #1a73e8; color: #ffffff; border-radius: 6px; padding: 8px 16px; font-weight: bold; border: none; }
            QPushButton:hover { background: #1557b0; }
            QPushButton:disabled { background: #dadce0; color: #80868b; }
        """)
        lay = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        lay.addWidget(self.text_edit)
        btn_lay = QHBoxLayout()
        btn_lay.addStretch()
        self.copy_btn = QPushButton("复制识别结果")
        self.copy_btn.clicked.connect(self._copy_and_close)
        btn_lay.addWidget(self.copy_btn)
        lay.addLayout(btn_lay)
        self._process_ocr(pixmap)
    def _process_ocr(self, pixmap: QPixmap):
        if not HAS_OCR:
            self.text_edit.setHtml(f"""<h3 style="color:#ea4335;">未检测到 RapidOCR</h3><pre style="background:#e8eaed; padding:8px; border-radius:4px;">pip install rapidocr-onnxruntime</pre>""")
            self.copy_btn.hide()
            return
        self.text_edit.setText("⚡ 正在执行本地 OCR 识别，请稍候...")
        self.copy_btn.setEnabled(False)
        buffer = QByteArray()
        buf_io = QBuffer(buffer)
        buf_io.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buf_io, "PNG")
        self.worker = OCRWorker(bytes(buffer.data()))
        self.worker.finished.connect(self._on_ocr_finished)
        self.worker.start()
    def _on_ocr_finished(self, text: str, success: bool):
        self.text_edit.setText(text)
        if success:
            self.copy_btn.setEnabled(True)
            self.copy_btn.show()
        else: self.copy_btn.hide()
    def _copy_and_close(self):
        QApplication.clipboard().setText(self.text_edit.toPlainText())
        self.close()
    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.quit()
            self.worker.wait(200)
        super().closeEvent(event)

class ShortcutHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("""
            QDialog { background: transparent; }
            QFrame#HelpCard { background: rgba(30, 41, 59, 245); border-radius: 12px; padding: 16px; border: 1px solid rgba(255,255,255,50); }
            QLabel { color: #f1f5f9; font-size: 12px; }
            QLabel#Title { font-size: 14px; font-weight: bold; color: #60a5fa; }
            QLabel#Key { background: #334155; padding: 3px 8px; border-radius: 4px; font-family: Consolas; font-weight: bold; }
        """)
        self.card = QFrame()
        self.card.setObjectName("HelpCard")
        lay = QVBoxLayout(self.card)
        lay.setSpacing(8)
        title = QLabel(f"⌨ {__app_name__} 快捷键指南")
        title.setObjectName("Title")
        lay.addWidget(title)
        shortcuts = [
            ("Esc / 右键", "取消当前绘制 / 退出"), ("Enter / 双击", "完成截图并复制"), ("Ctrl + S", "保存图片到本地"), ("Ctrl + Z", "撤销上一标注"),
            ("F3", "贴图到屏幕 (可缩放/调透明度)"), ("C", "吸管取色 (复制HEX并选中颜色)"), ("R / O / L / A", "矩形 / 椭圆 / 直线 / 箭头"),
            ("P / H / T", "画笔 / 荧光笔 / 文本标注"), ("双击已有文字", "重新编辑文字/修改字号/改色"), ("B / M", "步骤序号 / 马赛克遮盖"), ("1 / 2 / 3", "切换笔刷粗细 (细/中/粗)")
        ]
        for key, desc in shortcuts:
            row = QHBoxLayout()
            row.setSpacing(8)
            k_label = QLabel(key)
            k_label.setObjectName("Key")
            k_label.setFixedWidth(130)
            row.addWidget(k_label)
            row.addWidget(QLabel(desc))
            row.addStretch()
            lay.addLayout(row)
        main_lay = QVBoxLayout(self)
        main_lay.addWidget(self.card)
        self.adjustSize()
    def mousePressEvent(self, event): self.close()
    def keyPressEvent(self, event): self.close()

class FrozenFrameEditor(QWidget):
    STATE_IDLE = 0
    STATE_SELECTING = 1
    STATE_SELECTED = 2
    STATE_EDITING = 3
    STATE_RESIZING = 4
    STATE_MOVING = 5
    STATE_MOVING_ITEM = 6

    def __init__(self, frozen_pixmap: QPixmap, max_dpr: float, virtual_rect: QRect, controller):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.full_pixmap = frozen_pixmap
        self.base_image = frozen_pixmap.toImage()
        self.max_dpr = max_dpr
        self.virtual_rect = virtual_rect
        self.controller = controller

        self.state = self.STATE_IDLE
        self.active_tool = "none"
        self.current_color = QColor(_config.get("default_color", "#ea4335"))
        self.current_width = _config.get("pen_width", 3)
        self.step_counter = 1

        self.start_pos = QPoint()
        self.current_mouse_pos = QPoint()
        self.selected_rect = QRect()
        self.active_handle = -1
        self.move_offset = QPoint()
        self._right_click_pressed = False

        self.draw_items: list[DrawItem] = []
        self.current_drawing_item: Optional[DrawItem] = None
        self.highlighted_window = QRect()
        self.selected_item: Optional[DrawItem] = None
        self.item_last_pos = QPoint()

        self.active_text_editor: Optional[TextAnnotationWidget] = None

        self.toolbar = FloatingToolBar(self)
        self.toolbar.hide()
        self.toolbar.tool_changed.connect(self._set_active_tool)
        self.toolbar.color_changed.connect(self._set_drawing_color)
        self.toolbar.width_changed.connect(lambda w: setattr(self, "current_width", w))
        self.toolbar.action_triggered.connect(self._handle_action)

        self.help_dialog: Optional[ShortcutHelpDialog] = None
        self.setGeometry(virtual_rect)
        self.window_rects = get_window_rects(virtual_rect.topLeft(), max_dpr)
        
        self.setWindowOpacity(0.0)
        self.show()
        self.activateWindow()
        self.raise_()
        
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(150)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._anim.start()

    def _get_magnifier_rect(self, pos: QPoint) -> QRect:
        if not _config.get("show_magnifier", True): return QRect()
        hud_w, hud_h = 140, 160
        x, y = pos.x(), pos.y()
        hud_x = x + 20 if x + hud_w + 30 < self.width() else x - hud_w - 20
        hud_y = y + 20 if y + hud_h + 30 < self.height() else y - hud_h - 20
        return QRect(hud_x - 5, hud_y - 5, hud_w + 10, hud_h + 10)

    def _set_drawing_color(self, color: QColor):
        self.current_color = QColor(color)

    def _set_active_tool(self, tool: str):
        self._commit_active_text_editor()
        self.active_tool = tool
        self._update_cursor(self.current_mouse_pos)
        if self.selected_item:
            self.selected_item = None
            self.update()
        if hasattr(self.toolbar, "buttons"):
            btn = self.toolbar.buttons.get(tool)
            if btn and btn.isCheckable(): btn.setChecked(True)

    def _handle_action(self, action: str):
        self._commit_active_text_editor()
        if action == "close": self.close()
        elif action == "undo" and self.draw_items:
            popped_item = self.draw_items.pop()
            if isinstance(popped_item, StepBadgeItem):
                self.step_counter = max(1, self.step_counter - 1)
            if popped_item == self.selected_item:
                self.selected_item = None
            self.update()
        elif action == "finish": self._copy_and_exit()
        elif action == "save": self._save_file_dialog()
        elif action == "pin": self._pin_to_screen()
        elif action == "ocr": self._run_ocr()

    def _run_ocr(self):
        self._commit_active_text_editor()
        if self.selected_rect.isEmpty():
            QMessageBox.warning(self, "提示", "请先选择要识别的区域")
            return
        self.selected_item = None 
        dialog = OCRDialog(self._render_final_snipped_pixmap(), self)
        dialog.exec()

    def _render_final_snipped_pixmap(self) -> QPixmap:
        r = self.selected_rect.normalized()
        if r.isEmpty(): return QPixmap()
        
        dpr = self.max_dpr
        phys_w = max(1, int(r.width() * dpr))
        phys_h = max(1, int(r.height() * dpr))
        
        cropped = QPixmap(phys_w, phys_h)
        cropped.setDevicePixelRatio(dpr)
        cropped.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(cropped)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(-r.topLeft(), self.full_pixmap)
        
        painter.translate(-r.topLeft())
        for item in self.draw_items:
            item.paint(painter, self.full_pixmap)
        
        painter.end()
        return cropped

    def _copy_and_exit(self):
        self._commit_active_text_editor()
        if self.selected_rect.isEmpty():
            self.close()
            return
        self.selected_item = None 
        pixmap = self._render_final_snipped_pixmap()
        if _config.get("auto_copy", True):
            QApplication.clipboard().setPixmap(pixmap)
        play_shutter_sound()
        self.close()

    def _pin_to_screen(self):
        self._commit_active_text_editor()
        if self.selected_rect.isEmpty(): return
        self.selected_item = None
        pinned = PinnedImageWidget(self._render_final_snipped_pixmap())
        pinned.move(self.mapToGlobal(self.selected_rect.topLeft()))
        pinned.show()
        self.controller.register_pinned(pinned)
        self.close()

    def _save_file_dialog(self):
        self._commit_active_text_editor()
        if self.selected_rect.isEmpty(): return
        self.selected_item = None
        last_dir = _config.get("last_save_dir", str(Path.home() / "Pictures"))
        ts = time.strftime("%Y%m%d_%H%M%S")
        fp, _ = QFileDialog.getSaveFileName(self, "保存截图", str(Path(last_dir) / f"{__app_name__}_{ts}.png"), "PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp)")
        if fp:
            try:
                pixmap = self._render_final_snipped_pixmap()
                if fp.lower().endswith('.jpg') or fp.lower().endswith('.jpeg'):
                    pixmap.save(fp, "JPEG", _config.get("image_quality", 95))
                else: pixmap.save(fp, "PNG")
                _config.set("last_save_dir", str(Path(fp).parent))
                self.close()
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"无法保存文件:\n{str(e)}")

    def _get_handle_rects(self, r: QRect) -> list[tuple[int, QRect]]:
        if r.isEmpty(): return []
        nr, sz, half = r.normalized(), 8, 4
        pts = [
            (0, nr.left(), nr.top()), (1, nr.center().x(), nr.top()), (2, nr.right(), nr.top()),
            (3, nr.right(), nr.center().y()), (4, nr.right(), nr.bottom()), (5, nr.center().x(), nr.bottom()),
            (6, nr.left(), nr.bottom()), (7, nr.left(), nr.center().y()),
        ]
        return [(idx, QRect(x - half, y - half, sz, sz)) for idx, x, y in pts]

    def _hit_test(self, pos: QPoint) -> int:
        if self.selected_rect.isEmpty(): return -1
        for idx, rect in self._get_handle_rects(self.selected_rect):
            if rect.contains(pos): return idx
        if self.selected_rect.normalized().contains(pos): return 8
        return -1

    def _update_cursor(self, pos: QPoint):
        if self.state in (self.STATE_IDLE, self.STATE_SELECTING):
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif self.state == self.STATE_SELECTED:
            if self.active_tool == "picker":
                self.setCursor(Qt.CursorShape.CrossCursor)
                return
            if self.active_tool == "none" and self.selected_item and self.selected_item.contains(QPointF(pos)):
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                return
            if self.active_tool != "none":
                self.setCursor(Qt.CursorShape.IBeamCursor if self.active_tool == "text" else Qt.CursorShape.CrossCursor)
                return
            
            hit = self._hit_test(pos)
            if hit in (0, 4): self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif hit in (2, 6): self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif hit in (1, 5): self.setCursor(Qt.CursorShape.SizeVerCursor)
            elif hit in (3, 7): self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif hit == 8: self.setCursor(Qt.CursorShape.SizeAllCursor)
            else: self.setCursor(Qt.CursorShape.CrossCursor)
        elif self.state == self.STATE_MOVING_ITEM:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def contextMenuEvent(self, event): event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._right_click_pressed = True
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self.current_mouse_pos = pos

            if self.active_text_editor:
                editor_local = self.active_text_editor.mapFromGlobal(event.globalPosition().toPoint())
                if self.active_text_editor.rect().contains(editor_local):
                    return super().mousePressEvent(event)
                else:
                    self._commit_active_text_editor()

            if self.active_tool == "picker":
                rx, ry = int(pos.x() * self.max_dpr), int(pos.y() * self.max_dpr)
                img_w, img_h = self.base_image.width(), self.base_image.height()
                rx, ry = min(max(0, rx), img_w - 1), min(max(0, ry), img_h - 1)
                picked_color = self.base_image.pixelColor(rx, ry)
                hex_name = picked_color.name().upper()
                QApplication.clipboard().setText(hex_name)
                self.current_color = picked_color
                self.toolbar._set_color(hex_name)
                self._set_active_tool("none")
                self.update()
                event.accept()
                return

            if self.state == self.STATE_IDLE:
                self.state = self.STATE_SELECTING
                self.start_pos = pos
                self.selected_rect = QRect(pos, pos)
                self.selected_item = None
                
            elif self.state == self.STATE_SELECTED:
                hit = self._hit_test(pos)
                if hit != -1 and self.active_tool == "none":
                    if hit == 8:
                        hit_item = False
                        for item in reversed(self.draw_items):
                            if item.contains(QPointF(pos)):
                                self.selected_item = item
                                self.state = self.STATE_MOVING_ITEM
                                self.item_last_pos = pos
                                hit_item = True
                                break
                        
                        if not hit_item:
                            self.selected_item = None
                            self.state = self.STATE_MOVING
                            self.move_offset = pos - self.selected_rect.topLeft()
                            self.toolbar.hide()
                    else:         
                        self.selected_item = None
                        self.state = self.STATE_RESIZING
                        self.active_handle = hit
                        self.toolbar.hide()
                elif self.active_tool != "none" and self.selected_rect.contains(pos):
                    if self.active_tool == "text":
                        self._spawn_text_editor(pos)
                    else:
                        self.state = self.STATE_EDITING
                        self.start_pos = pos
                        self._handle_drawing_press(pos)
            self.update()
            event.accept()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        old_pos = self.current_mouse_pos
        self.current_mouse_pos = pos
        self._update_cursor(pos)

        if self.state == self.STATE_IDLE or self.active_tool == "picker": 
            update_region = QRegion()
            if _config.get("show_magnifier", True):
                update_region = update_region.united(self._get_magnifier_rect(old_pos))
                update_region = update_region.united(self._get_magnifier_rect(pos))
                
            if self.state == self.STATE_IDLE and _config.get("auto_detect_window", True):
                new_highlight = QRect()
                for rect in self.window_rects:
                    if rect.contains(pos):
                        new_highlight = rect
                        break
                if new_highlight != self.highlighted_window:
                    if not self.highlighted_window.isEmpty():
                        update_region = update_region.united(self.highlighted_window.adjusted(-4, -4, 4, 4))
                    self.highlighted_window = new_highlight
                    if not self.highlighted_window.isEmpty():
                        update_region = update_region.united(self.highlighted_window.adjusted(-4, -4, 4, 4))

            if not update_region.isEmpty(): self.update(update_region)
                
        elif self.state == self.STATE_SELECTING:
            self.selected_rect = QRect(self.start_pos, pos).normalized()
            self.update()
        elif self.state == self.STATE_RESIZING:
            self._handle_resize(pos)
            self.update()
        elif self.state == self.STATE_MOVING:
            self.selected_rect.moveTopLeft(pos - self.move_offset)
            self.update()
        elif self.state == self.STATE_MOVING_ITEM:
            delta = pos - self.item_last_pos
            if self.selected_item: self.selected_item.move_by(QPointF(delta))
            self.item_last_pos = pos
            self.update()
        elif self.state == self.STATE_EDITING:
            self._handle_drawing_move(pos)
            self.update()

        event.accept()

    def _handle_resize(self, pos: QPoint):
        r = self.selected_rect
        if self.active_handle == 0: r.setTopLeft(pos)
        elif self.active_handle == 1: r.setTop(pos.y())
        elif self.active_handle == 2: r.setTopRight(pos)
        elif self.active_handle == 3: r.setRight(pos.x())
        elif self.active_handle == 4: r.setBottomRight(pos)
        elif self.active_handle == 5: r.setBottom(pos.y())
        elif self.active_handle == 6: r.setBottomLeft(pos)
        elif self.active_handle == 7: r.setLeft(pos.x())
        self.selected_rect = r.normalized()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()
            if self._right_click_pressed:
                self._right_click_pressed = False
                if self.active_text_editor:
                    self._commit_active_text_editor()
                    return
                if self.state == self.STATE_EDITING:
                    self.current_drawing_item = None
                    self.state = self.STATE_SELECTED
                    self.update()
                elif self.selected_item:
                    self.selected_item = None
                    self.update()
                elif self.draw_items:
                    popped = self.draw_items.pop()
                    if isinstance(popped, StepBadgeItem):
                        self.step_counter = max(1, self.step_counter - 1)
                    self.update()
                elif self.state == self.STATE_SELECTED:
                    self.selected_rect = QRect()
                    self.toolbar.hide()
                    self.state = self.STATE_IDLE
                    self.update()
                else: self.close()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == self.STATE_SELECTING:
                if self.selected_rect.width() > 8 and self.selected_rect.height() > 8:
                    self.state = self.STATE_SELECTED
                    self._position_toolbar()
                else:
                    if not self.highlighted_window.isEmpty() and self.highlighted_window.contains(event.position().toPoint()):
                        self.selected_rect = self.highlighted_window
                        self.state = self.STATE_SELECTED
                        self.highlighted_window = QRect()
                        self._position_toolbar()
                    else:
                        self.selected_rect = QRect()
                        self.state = self.STATE_IDLE
                self.update()
                
            elif self.state in (self.STATE_RESIZING, self.STATE_MOVING):
                self.state = self.STATE_SELECTED
                self._position_toolbar()
                self.update()
                
            elif self.state == self.STATE_MOVING_ITEM:
                self.state = self.STATE_SELECTED
                self.update()
                
            elif self.state == self.STATE_EDITING:
                if self.current_drawing_item:
                    self.draw_items.append(self.current_drawing_item)
                    if isinstance(self.current_drawing_item, StepBadgeItem):
                        self.step_counter += 1
                    self.current_drawing_item = None
                self.state = self.STATE_SELECTED
                self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            for item in reversed(self.draw_items):
                if isinstance(item, TextItem) and item.contains(QPointF(pos)):
                    self.draw_items.remove(item)
                    self.update()
                    self._spawn_text_editor(item.pos.toPoint(), item.text, item.font, item.color)
                    event.accept()
                    return

            if self.state == self.STATE_SELECTED and self.selected_rect.contains(pos):
                self._copy_and_exit()

    def _spawn_text_editor(self, pos: QPoint, text: str = "", font: Optional[QFont] = None, color: Optional[QColor] = None):
        """唤醒全新自适应文字卡片编辑器"""
        self._commit_active_text_editor()
        
        editor_x = min(pos.x(), self.width() - 260)
        editor_y = min(pos.y(), self.height() - 130)
        safe_pos = QPoint(max(10, editor_x), max(10, editor_y))

        cur_color = color if color else self.current_color
        self.active_text_editor = TextAnnotationWidget(safe_pos, text, font, cur_color, self)
        self.active_text_editor.committed.connect(self._on_text_widget_committed)
        self.active_text_editor.cancelled.connect(self._on_text_widget_cancelled)
        self.active_text_editor.show()
        self.active_text_editor.raise_()

    def _commit_active_text_editor(self):
        if self.active_text_editor:
            self.active_text_editor.commit()

    def _on_text_widget_committed(self, text: str, pos: QPointF, font: QFont, color: QColor):
        if text.strip():
            self.draw_items.append(TextItem(pos, text, font, color))
        if self.active_text_editor:
            self.active_text_editor.deleteLater()
            self.active_text_editor = None
        self.update()

    def _on_text_widget_cancelled(self):
        if self.active_text_editor:
            self.active_text_editor.deleteLater()
            self.active_text_editor = None
        self.update()

    def _handle_drawing_press(self, pos: QPoint):
        w = self.current_width
        if self.active_tool == "rect": self.current_drawing_item = RectItem(QRectF(pos, pos), self.current_color, w)
        elif self.active_tool == "circle": self.current_drawing_item = CircleItem(QRectF(pos, pos), self.current_color, w)
        elif self.active_tool == "line": self.current_drawing_item = LineItem(QPointF(pos), QPointF(pos), self.current_color, w)
        elif self.active_tool == "arrow": self.current_drawing_item = ArrowItem(QPointF(pos), QPointF(pos), self.current_color, w)
        elif self.active_tool == "pencil": self.current_drawing_item = PencilItem([QPointF(pos)], self.current_color, w, False)
        elif self.active_tool == "marker": self.current_drawing_item = PencilItem([QPointF(pos)], self.current_color, w, True)
        elif self.active_tool == "badge": self.current_drawing_item = StepBadgeItem(QPointF(pos), self.step_counter, self.current_color)
        elif self.active_tool == "mosaic": self.current_drawing_item = MosaicItem(QRectF(pos, pos))

    def _handle_drawing_move(self, pos: QPoint):
        if not self.current_drawing_item: return
        if isinstance(self.current_drawing_item, (RectItem, CircleItem, MosaicItem)):
            self.current_drawing_item.rect = QRectF(self.start_pos, pos).normalized()
        elif isinstance(self.current_drawing_item, (ArrowItem, LineItem)):
            self.current_drawing_item.end = QPointF(pos)
        elif isinstance(self.current_drawing_item, PencilItem):
            self.current_drawing_item.points.append(QPointF(pos))

    def _position_toolbar(self):
        if self.selected_rect.isEmpty():
            self.toolbar.hide()
            return
        r, tb_size = self.selected_rect.normalized(), self.toolbar.sizeHint()
        tb_w, tb_h = tb_size.width(), tb_size.height()
        tb_x, tb_y = r.right() - tb_w + 12, r.bottom() + 8
        if tb_y + tb_h > self.height() - 10: tb_y = r.top() - tb_h - 8
        if tb_y < 10: tb_y = r.bottom() - tb_h - 8
        tb_x = max(10, min(tb_x, self.width() - tb_w - 10))
        self.toolbar.move(int(tb_x), int(tb_y))
        self.toolbar.show()
        self.toolbar.raise_()

    def paintEvent(self, event):
        painter = QPainter(self)
        
        clip_rect = event.rect()
        painter.setClipRect(clip_rect)
        painter.drawPixmap(0, 0, self.full_pixmap)
        
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.state == self.STATE_IDLE and not self.highlighted_window.isEmpty():
            painter.setPen(QPen(QColor("#1a73e8"), 2.5, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(QColor(26, 115, 232, 28)))
            painter.drawRect(self.highlighted_window)

        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        path.addRect(QRectF(self.rect()))
        
        target_rect = self.selected_rect.normalized()
        if not target_rect.isEmpty(): path.addRect(QRectF(target_rect))
        painter.fillPath(path, QColor(0, 0, 0, 115))

        if not target_rect.isEmpty():
            painter.setPen(QPen(QColor("#1a73e8"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(target_rect)
            
            if self.state in (self.STATE_SELECTED, self.STATE_EDITING, self.STATE_MOVING_ITEM):
                painter.setBrush(QBrush(Qt.GlobalColor.white))
                painter.setPen(QPen(QColor("#1a73e8"), 1.5))
                for _, h_rect in self._get_handle_rects(target_rect): painter.drawRect(h_rect)

            dim_str = f" {target_rect.width()} × {target_rect.height()} "
            painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            fm = painter.fontMetrics()
            tw, th = fm.horizontalAdvance(dim_str) + 12, fm.height() + 6
            bx, by = target_rect.left(), target_rect.top() - th - 6
            if by < 5: by = target_rect.top() + 6
            
            badge_rect = QRectF(bx, by, tw, th)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#202124")))
            painter.drawRoundedRect(badge_rect, 4, 4)
            painter.setPen(QPen(Qt.GlobalColor.white))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, dim_str)

        painter.save()
        if not target_rect.isEmpty(): painter.setClipRect(target_rect)
        
        for item in self.draw_items:
            item.paint(painter, self.full_pixmap)
            
        if self.current_drawing_item:
            self.current_drawing_item.paint(painter, self.full_pixmap)
            
        if self.selected_item and self.state in (self.STATE_SELECTED, self.STATE_MOVING_ITEM):
            b_rect = self.selected_item.bounding_rect().adjusted(-3, -3, 3, 3)
            painter.setPen(QPen(QColor("#1a73e8"), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(b_rect)
            
        painter.restore()

        if _config.get("show_magnifier", True) and (self.state in (self.STATE_IDLE, self.STATE_SELECTING) or self.active_tool == "picker"):
            self._paint_magnifier(painter, self.current_mouse_pos)

    def _paint_magnifier(self, painter: QPainter, pos: QPoint):
        x, y = pos.x(), pos.y()
        rx, ry = int(x * self.max_dpr), int(y * self.max_dpr)
        img_w, img_h = self.base_image.width(), self.base_image.height()
        rx, ry = min(max(0, rx), img_w - 1), min(max(0, ry), img_h - 1)
        rgb = self.base_image.pixelColor(rx, ry)

        hud_w, hud_h = 132, 154
        hud_x = x + 20 if x + hud_w + 30 < self.width() else x - hud_w - 20
        hud_y = y + 20 if y + hud_h + 30 < self.height() else y - hud_h - 20

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(QColor("#1a73e8"), 2))
        painter.setBrush(QBrush(QColor("#1e293b")))
        painter.drawRoundedRect(QRect(hud_x - 1, hud_y - 1, 114, 134), 6, 6)

        half = 5
        grid_size = 10
        for gx in range(11):
            for gy in range(11):
                px, py = min(max(0, rx - half + gx), img_w - 1), min(max(0, ry - half + gy), img_h - 1)
                painter.fillRect(hud_x + gx * grid_size, hud_y + gy * 7, grid_size, 7, QBrush(self.base_image.pixelColor(px, py)))

        painter.setPen(QPen(QColor("#1a73e8"), 2))
        painter.drawRect(hud_x + half * grid_size, hud_y + half * 7, grid_size, 7)
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        painter.drawText(hud_x + 6, hud_y + 92, f"#{rgb.red():02X}{rgb.green():02X}{rgb.blue():02X}")
        painter.drawText(hud_x + 6, hud_y + 107, f"RGB:({rgb.red()},{rgb.green()},{rgb.blue()})")
        painter.drawText(hud_x + 6, hud_y + 122, f"POS: {x}, {y}")
        painter.restore()

    def keyPressEvent(self, event):
        key = event.key()
        
        if self.active_text_editor:
            if key == Qt.Key.Key_Escape:
                self.active_text_editor.cancel()
                return
            super().keyPressEvent(event)
            return

        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.selected_item and self.selected_item in self.draw_items:
                if isinstance(self.selected_item, StepBadgeItem):
                    self.step_counter = max(1, self.step_counter - 1)
                self.draw_items.remove(self.selected_item)
                self.selected_item = None
                self.update()
                return

        if key == Qt.Key.Key_Escape:
            if self.state == self.STATE_EDITING:
                self.current_drawing_item = None
                self.state = self.STATE_SELECTED
                self.update()
            elif self.selected_item:
                self.selected_item = None
                self.update()
            else:
                self.close()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not self.selected_rect.isEmpty(): self._copy_and_exit()
        elif key == Qt.Key.Key_F1:
            if not self.help_dialog: self.help_dialog = ShortcutHelpDialog(self)
            self.help_dialog.move(self.rect().center() - self.help_dialog.rect().center())
            self.help_dialog.show()
        elif key == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.NoModifier: self._set_active_tool("picker")
        elif key == Qt.Key.Key_F3:
            if not self.selected_rect.isEmpty(): self._pin_to_screen()
        elif event.matches(QKeySequence.StandardKey.Undo): self._handle_action("undo")
        elif event.matches(QKeySequence.StandardKey.Save): self._save_file_dialog()
        elif key == Qt.Key.Key_R: self._set_active_tool("rect")
        elif key == Qt.Key.Key_O: self._set_active_tool("circle")
        elif key == Qt.Key.Key_L: self._set_active_tool("line")
        elif key == Qt.Key.Key_A: self._set_active_tool("arrow")
        elif key == Qt.Key.Key_P: self._set_active_tool("pencil")
        elif key == Qt.Key.Key_H: self._set_active_tool("marker")
        elif key == Qt.Key.Key_T: self._set_active_tool("text")
        elif key == Qt.Key.Key_B: self._set_active_tool("badge")
        elif key == Qt.Key.Key_M: self._set_active_tool("mosaic")
        elif key == Qt.Key.Key_1: self.toolbar._on_width_changed(2)
        elif key == Qt.Key.Key_2: self.toolbar._on_width_changed(3)
        elif key == Qt.Key.Key_3: self.toolbar._on_width_changed(5)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{__app_name__} - 设置")
        self.setMinimumSize(580, 520)
        
        self.setStyleSheet("""
            QDialog { background-color: #f8fafc; }
            QTabWidget::pane { border: 1px solid #e8eaed; border-radius: 8px; background: #ffffff; top: -1px; }
            QTabBar::tab { background: #f1f3f4; color: #5f6368; padding: 10px 20px; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; font-size: 13px; font-weight: 500; }
            QTabBar::tab:selected { background: #ffffff; color: #1a73e8; border-bottom: 2px solid #1a73e8; }
            QTabBar::tab:hover { background: #e8f0fe; }
            QGroupBox { background: #ffffff; border: 1px solid #e8eaed; border-radius: 8px; margin-top: 12px; padding-top: 12px; font-weight: bold; color: #3c4043; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QLabel { color: #5f6368; font-size: 13px; }
            QCheckBox { color: #3c4043; font-size: 13px; spacing: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 2px solid #dadce0; background: #ffffff; }
            QCheckBox::indicator:checked { background: #1a73e8; border-color: #1a73e8; image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTgiIGhlaWdodD0iMTgiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTkgMTYuMTdMNC44MyAxMmwtMS40MiAxLjQxTDkgMTkgMjEgN2wtMS40MS0xLjQxeiIgZmlsbD0id2hpdGUiLz4KPC9zdmc+); }
            QSlider::groove:horizontal { border: 1px solid #dadce0; height: 4px; background: #e8eaed; border-radius: 2px; }
            QSlider::handle:horizontal { background: #1a73e8; border: 2px solid #1a73e8; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }
            QSlider::handle:horizontal:hover { background: #1557b0; border-color: #1557b0; }
            QPushButton { background: #1a73e8; color: #ffffff; border-radius: 6px; padding: 10px 20px; font-weight: bold; border: none; min-height: 20px; }
            QPushButton:hover { background: #1557b0; }
            QPushButton#Secondary { background: #f1f3f4; color: #3c4043; }
            QPushButton#Secondary:hover { background: #e8eaed; }
            QKeySequenceEdit, QSpinBox, QComboBox { background: #ffffff; border: 1px solid #dadce0; border-radius: 6px; padding: 8px; color: #3c4043; }
            QKeySequenceEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #1a73e8; }
            QComboBox::drop-down { border: none; width: 20px; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        tabs = QTabWidget()
        
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        basic_layout.setSpacing(12)

        func_group = QGroupBox("功能选项")
        func_layout = QVBoxLayout()
        func_layout.setSpacing(10)
        self.cb_sound = QCheckBox("启用截图声音反馈"); self.cb_sound.setChecked(_config.get("enable_sound", True))
        self.cb_auto_copy = QCheckBox("自动复制截图到剪贴板"); self.cb_auto_copy.setChecked(_config.get("auto_copy", True))
        self.cb_magnifier = QCheckBox("显示屏幕放大镜"); self.cb_magnifier.setChecked(_config.get("show_magnifier", True))
        self.cb_detect_window = QCheckBox("自动检测窗口边界"); self.cb_detect_window.setChecked(_config.get("auto_detect_window", True))
        for cb in (self.cb_sound, self.cb_auto_copy, self.cb_magnifier, self.cb_detect_window): func_layout.addWidget(cb)
        func_group.setLayout(func_layout)
        basic_layout.addWidget(func_group)

        sys_group = QGroupBox("系统选项")
        sys_layout = QVBoxLayout()
        sys_layout.setSpacing(10)
        self.cb_autostart = QCheckBox("开机自启动"); self.cb_autostart.setChecked(check_autostart_win())
        sys_layout.addWidget(self.cb_autostart)
        sys_group.setLayout(sys_layout)
        basic_layout.addWidget(sys_group)
        basic_layout.addStretch()
        tabs.addTab(basic_tab, "基础设置")

        hdr_tab = QWidget()
        hdr_layout = QVBoxLayout(hdr_tab)
        hdr_layout.setSpacing(12)
        hdr_group = QGroupBox("HDR 色调映射")
        hdr_gl = QVBoxLayout()
        hdr_gl.setSpacing(10)
        self.cb_hdr_tone_mapping = QCheckBox("启用 HDR 色调映射（无损 S 曲线增强）")
        self.cb_hdr_tone_mapping.setChecked(_config.get("hdr_tone_mapping", False))
        hdr_gl.addWidget(self.cb_hdr_tone_mapping)
        hdr_gl.addWidget(QLabel("映射强度（值越大，过曝修复/对比度增强越明显）:"))
        slider_layout = QHBoxLayout()
        self.tone_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.tone_strength_slider.setRange(0, 100)
        self.tone_strength_slider.setValue(int(_config.get("tone_mapping_strength", 0.85) * 100))
        self.tone_strength_slider.setEnabled(self.cb_hdr_tone_mapping.isChecked())
        self.tone_strength_label = QLabel(f"{self.tone_strength_slider.value()}%")
        self.tone_strength_slider.valueChanged.connect(lambda v: self.tone_strength_label.setText(f"{v}%"))
        self.cb_hdr_tone_mapping.toggled.connect(self.tone_strength_slider.setEnabled)
        slider_layout.addWidget(self.tone_strength_slider); slider_layout.addWidget(self.tone_strength_label)
        hdr_gl.addLayout(slider_layout)
        info_label = QLabel("💡 提示：在普通显示器上建议保持关闭。仅当屏幕为 HDR 模式且截图发灰时开启。")
        info_label.setWordWrap(True); info_label.setStyleSheet("color: #5f6368; background: #e8f0fe; padding: 10px; border-radius: 6px;")
        hdr_gl.addWidget(info_label)
        hdr_group.setLayout(hdr_gl)
        hdr_layout.addWidget(hdr_group)
        hdr_layout.addStretch()
        tabs.addTab(hdr_tab, "HDR 处理")

        hotkey_tab = QWidget()
        hotkey_layout = QVBoxLayout(hotkey_tab)
        hotkey_layout.setSpacing(12)
        hotkey_group = QGroupBox("全局快捷键")
        hotkey_gl = QVBoxLayout()
        hotkey_gl.setSpacing(10)
        hotkey_gl.addWidget(QLabel("截图快捷键:"))
        self.hotkey_edit = QKeySequenceEdit()
        self.hotkey_edit.setKeySequence(QKeySequence(_config.get("hotkey", "Ctrl+Alt+A")))
        hotkey_gl.addWidget(self.hotkey_edit)
        hotkey_info = QLabel("💡 提示：修改快捷键后需重启应用生效。\n推荐组合：Ctrl+Alt+A, Ctrl+Shift+X")
        hotkey_info.setWordWrap(True); hotkey_info.setStyleSheet("color: #5f6368; background: #fff3cd; padding: 10px; border-radius: 6px;")
        hotkey_gl.addWidget(hotkey_info)
        hotkey_group.setLayout(hotkey_gl)
        hotkey_layout.addWidget(hotkey_group)
        hotkey_layout.addStretch()
        tabs.addTab(hotkey_tab, "快捷键")

        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        advanced_layout.setSpacing(12)
        quality_group = QGroupBox("图片保存设置")
        quality_gl = QVBoxLayout(); quality_gl.setSpacing(10)
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("默认保存格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG", "BMP"]); self.format_combo.setCurrentText(_config.get("save_format", "PNG"))
        format_layout.addWidget(self.format_combo); format_layout.addStretch()
        quality_gl.addLayout(format_layout)
        quality_gl.addWidget(QLabel("JPEG 压缩质量:"))
        quality_slider_layout = QHBoxLayout()
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(50, 100); self.quality_slider.setValue(_config.get("image_quality", 95))
        self.quality_value_label = QLabel(f"{self.quality_slider.value()}%")
        self.quality_slider.valueChanged.connect(lambda v: self.quality_value_label.setText(f"{v}%"))
        quality_slider_layout.addWidget(self.quality_slider); quality_slider_layout.addWidget(self.quality_value_label)
        quality_gl.addLayout(quality_slider_layout)
        quality_group.setLayout(quality_gl)
        advanced_layout.addWidget(quality_group)
        pen_group = QGroupBox("默认笔刷设置")
        pen_layout = QVBoxLayout(); pen_layout.setSpacing(10)
        pen_width_layout = QHBoxLayout()
        pen_width_layout.addWidget(QLabel("默认笔刷粗细:"))
        self.pen_width_spin = QSpinBox()
        self.pen_width_spin.setRange(1, 10); self.pen_width_spin.setValue(_config.get("pen_width", 3))
        pen_width_layout.addWidget(self.pen_width_spin); pen_width_layout.addStretch()
        pen_layout.addLayout(pen_width_layout)
        pen_group.setLayout(pen_layout)
        advanced_layout.addWidget(pen_group)
        advanced_layout.addStretch()
        tabs.addTab(advanced_tab, "高级设置")

        about_tab = QWidget()
        about_layout = QVBoxLayout(about_tab)
        about_layout.setSpacing(16); about_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_content = QFrame()
        about_content.setStyleSheet("QFrame { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #e8f0fe, stop:1 #d2e3fc); border-radius: 12px; padding: 24px; }")
        about_cl = QVBoxLayout(about_content)
        about_cl.setSpacing(12); about_cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_title = QLabel(f"<h1 style='color:#1a73e8;'>{__app_name__}</h1>")
        app_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_cl.addWidget(app_title)
        version_label = QLabel(f"<p style='font-size:14px; color:#5f6368;'><b>版本:</b> {__version__}</p>")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_cl.addWidget(version_label)
        desc_label = QLabel(f"<p style='color:#3c4043;'>{__description__}</p>")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_cl.addWidget(desc_label)
        author_label = QLabel(f"<p style='color:#5f6368;'>作者: {__author__} | {__company__}</p>")
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_cl.addWidget(author_label)
        tech_label = QLabel("<p style='color:#5f6368; font-size:11px;'>基于 PySide6 (Qt6) 构建<br>原生支持高 DPI 多屏缩放感知与高级文字编辑标注<br>开源项目 · GPL-3.0 License</p>")
        tech_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_cl.addWidget(tech_label)
        about_layout.addWidget(about_content)
        tabs.addTab(about_tab, "关于")

        layout.addWidget(tabs)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("Secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _save_and_close(self):
        _config.set("enable_sound", self.cb_sound.isChecked())
        _config.set("auto_copy", self.cb_auto_copy.isChecked())
        _config.set("show_magnifier", self.cb_magnifier.isChecked())
        _config.set("auto_detect_window", self.cb_detect_window.isChecked())
        _config.set("hdr_tone_mapping", self.cb_hdr_tone_mapping.isChecked())
        _config.set("tone_mapping_strength", self.tone_strength_slider.value() / 100.0)
        _config.set("save_format", self.format_combo.currentText())
        _config.set("image_quality", self.quality_slider.value())
        _config.set("pen_width", self.pen_width_spin.value())
        new_hotkey = self.hotkey_edit.keySequence().toString()
        if new_hotkey != _config.get("hotkey"):
            ok, msg = check_hotkey_conflict_win(new_hotkey)
            if ok:
                _config.set("hotkey", new_hotkey)
                QMessageBox.information(self, "提示", "快捷键已更新，重启应用后生效。")
            else:
                QMessageBox.warning(self, "快捷键冲突", msg)
                return
        set_autostart_win(self.cb_autostart.isChecked())
        self.accept()

class ScreenshotController(QObject):
    def __init__(self):
        super().__init__()
        self.active_editor: Optional[FrozenFrameEditor] = None
        self.pinned_widgets: list[PinnedImageWidget] = []

    def start_snipping(self):
        if self.active_editor:
            try:
                self.active_editor.close()
                self.active_editor.deleteLater()
            except RuntimeError:
                pass
            self.active_editor = None

        logger.info("📸 Starting freeze-frame capture...")
        try:
            frozen_pixmap, max_dpr, virtual_rect = capture_full_desktop_instant()
            if frozen_pixmap.isNull(): return

            if _config.get("hdr_tone_mapping", False):
                frozen_pixmap = apply_hdr_tone_mapping(frozen_pixmap, _config.get("tone_mapping_strength", 0.85))

            self.active_editor = FrozenFrameEditor(frozen_pixmap, max_dpr, virtual_rect, self)
        except Exception as e:
            logger.error(f"Failed to start snipping: {e}")

    def register_pinned(self, widget: PinnedImageWidget):
        self.pinned_widgets.append(widget)
        widget.destroyed.connect(lambda: self.pinned_widgets.remove(widget) if widget in self.pinned_widgets else None)

class NativeHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, hotkey_id, callback):
        super().__init__()
        self.hotkey_id = hotkey_id
        self.callback = callback
    def nativeEventFilter(self, eventType, message):
        if eventType in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(message.__int__())
            if msg.message == 0x0312 and msg.wParam == self.hotkey_id:
                self.callback()
                return True, 0
        return False, 0

class TrayApp(QObject):
    def __init__(self):
        super().__init__()
        self.controller = ScreenshotController()
        self.hotkey_id = 1
        self.hotkey_filter = None

        self.tray_icon = QSystemTrayIcon(get_logo_icon(32), QApplication.instance())
        self.tray_icon.setToolTip(f"{__app_name__} v{__version__}")
        
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background: white; border: 1px solid #ccc; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 6px 20px; border-radius: 4px; }
            QMenu::item:selected { background: #e8f0fe; color: #1a73e8; }
        """)
        menu.addAction("截图").triggered.connect(self.controller.start_snipping)
        menu.addAction("设置").triggered.connect(self.show_settings)
        menu.addAction("关于").triggered.connect(self.show_about)
        menu.addSeparator()
        menu.addAction("退出").triggered.connect(QApplication.instance().quit)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
        self.register_hotkey()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger: self.controller.start_snipping()

    def register_hotkey(self):
        if os.name != "nt": return
        hotkey_str = _config.get("hotkey", "Ctrl+Alt+A")
        modifiers, vk = _parse_hotkey(hotkey_str)
        if vk == 0: return
        user32 = ctypes.windll.user32
        if user32.RegisterHotKey(None, self.hotkey_id, modifiers, vk):
            if not self.hotkey_filter:
                self.hotkey_filter = NativeHotkeyFilter(self.hotkey_id, self.controller.start_snipping)
                QApplication.instance().installNativeEventFilter(self.hotkey_filter)

    def unregister_hotkey(self):
        if os.name == "nt": ctypes.windll.user32.UnregisterHotKey(None, self.hotkey_id)

    def show_settings(self):
        self.unregister_hotkey()
        dialog = SettingsDialog()
        dialog.exec()
        self.register_hotkey()

    def show_about(self):
        dialog = QDialog()
        dialog.setWindowTitle("关于 QSnap")
        dialog.setFixedSize(380, 260)
        dialog.setStyleSheet("background: #ffffff;")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(30, 30, 30, 30); layout.setSpacing(10)
        
        title_label = QLabel(f"<b><span style='font-size:28px; color:#1a73e8;'>QSnap</span></b> <span style='font-size:14px; color:#5f6368;'>v{__version__}</span>")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        desc = QLabel(f"<p style='color:#3c4043; font-size:13px; text-align:center;'>{__description__}</p>")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #e8eaed;")
        layout.addWidget(line)
        
        footer = QLabel("<p style='color:#70757a; font-size:12px; line-height: 1.5;'>✓ 全新沉浸式文字卡片编辑器 (支持二次修改)<br>✓ 修复高分屏缩放与像素拉伸放大<br>✓ 吸管取色与剪贴板一键同步<br>✓ 基于 Qt6 引擎构建<br>✓ 作者: {}</p>".format(__author__))
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)
        
        dialog.exec()

def main():
    mutex = None
    if os.name == "nt":
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, f"Global\\{__app_name__}_SingleInstance_Mutex")
        if ctypes.windll.kernel32.GetLastError() == 183:
            logger.warning("Another instance is already running. Exiting.")
            sys.exit(0)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(__company__)
    
    try:
        tray_app = TrayApp()
        exit_code = app.exec()
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        exit_code = 1
    finally:
        if mutex and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle(mutex)
        sys.exit(exit_code)

if __name__ == "__main__":
    main()