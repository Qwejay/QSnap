from __future__ import annotations

__app_name__ = "QSnap"
__version__ = "1.4.0"
__author__ = "QwejayHuang"
__company__ = "Qwesoft"
__description__ = "Professional Screenshot Tool with HDR & Smart UI"

import ctypes
import json
import logging
import math
import os
import shutil
import struct
import sys
import threading
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
    QEvent, QRect, QRectF, Qt, QThread, Signal, QTimer, QSize,
    QAbstractNativeEventFilter, QPropertyAnimation, QEasingCurve
)
from PySide6.QtGui import (
    QBrush, QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QIcon,
    QImage, QKeySequence, QPainter, QPainterPath, QPen,
    QPixmap, QPolygonF, QPainterPathStroker, QRegion, QScreen
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QColorDialog, QDialog,
    QFileDialog, QFrame, QHBoxLayout, QLabel,
    QMenu, QMessageBox, QPushButton, QSystemTrayIcon, QTextEdit,
    QVBoxLayout, QWidget, QKeySequenceEdit, QSlider, QTabWidget,
    QGroupBox, QSpinBox, QComboBox, QToolButton, QFontDialog, QGridLayout, QToolTip
)

if getattr(sys, "frozen", False) or "__compiled__" in globals():
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
_OCR_ENGINE_LOCK = threading.Lock()


def get_ocr_engine() -> Optional[RapidOCR]:
    global _GLOBAL_OCR_ENGINE
    if not HAS_OCR:
        return None
    with _OCR_ENGINE_LOCK:
        if _GLOBAL_OCR_ENGINE is None:
            try:
                _GLOBAL_OCR_ENGINE = RapidOCR()
                logger.info("OCR engine initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OCR: {e}")
        return _GLOBAL_OCR_ENGINE


MATERIAL_ICONS = {
    "rect": "M3 3h18v18H3V3zm16 16V5H5v14h14z",
    "circle": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z",
    "fill": "M16.56 8.94L7.62 0 6.21 1.41l2.38 2.38-5.15 5.15c-.59.59-.59 1.54 0 2.12l5.5 5.5c.29.29.68.44 1.06.44s.77-.15 1.06-.44l5.5-5.5c.59-.58.59-1.53 0-2.12zM5.21 10L10 5.21 14.79 10H5.21zM19 11.5s-2 2.17-2 3.5c0 1.1.9 2 2 2s2-.9 2-2c0-1.33-2-3.5-2-3.5z",
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

_ICON_CACHE: dict[tuple[str, str, int], QIcon] = {}


def get_svg_icon(name: str, color: str = "#475569", size: int = 24) -> QIcon:
    cache_key = (name, color, size)
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]
    try:
        path_data = MATERIAL_ICONS.get(name, MATERIAL_ICONS["rect"])
        svg_str = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="{color}" d="{path_data}"/></svg>'
        renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
        render_size = max(size * 4, 96)
        pixmap = QPixmap(render_size, render_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(painter)
        painter.end()
        icon = QIcon(pixmap)
        _ICON_CACHE[cache_key] = icon
        return icon
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
        renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
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

    def _sanitize(self):
        for k, v in self.DEFAULT_CONFIG.items():
            if k not in self.data or self.data[k] is None:
                self.data[k] = v

        try:
            self.data["pen_width"] = max(1, min(20, int(self.data.get("pen_width", 3))))
        except (ValueError, TypeError):
            self.data["pen_width"] = 3

        try:
            self.data["image_quality"] = max(50, min(100, int(self.data.get("image_quality", 95))))
        except (ValueError, TypeError):
            self.data["image_quality"] = 95

        try:
            self.data["tone_mapping_strength"] = max(0.0, min(1.0, float(self.data.get("tone_mapping_strength", 0.85))))
        except (ValueError, TypeError):
            self.data["tone_mapping_strength"] = 0.85

        if str(self.data.get("save_format", "PNG")).upper() not in ("PNG", "JPEG", "BMP"):
            self.data["save_format"] = "PNG"
        else:
            self.data["save_format"] = str(self.data["save_format"]).upper()

        for bool_key in ("enable_sound", "auto_copy", "show_magnifier", "auto_detect_window", "hdr_tone_mapping"):
            self.data[bool_key] = bool(self.data.get(bool_key, self.DEFAULT_CONFIG[bool_key]))

        save_dir = Path(str(self.data.get("last_save_dir", "")))
        if not save_dir.exists() or not save_dir.is_dir():
            fallback_dir = Path.home() / "Pictures"
            self.data["last_save_dir"] = str(fallback_dir if fallback_dir.exists() else Path.home())

    def load(self):
        if not _CONFIG_FILE.exists():
            self._sanitize()
            self.save()
            return
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update(loaded)
            else:
                raise ValueError("Config root is not a JSON object")
            self._sanitize()
        except Exception as e:
            logger.warning(f"Config file corrupted ({e}), backing up and restoring defaults.")
            try:
                backup_path = _CONFIG_FILE.with_suffix(f".corrupted.{int(time.time())}.bak")
                shutil.copy2(_CONFIG_FILE, backup_path)
            except Exception as bak_err:
                logger.error(f"Failed to backup corrupted config: {bak_err}")
            self.data = self.DEFAULT_CONFIG.copy()
            self._sanitize()
            self.save()

    def save(self):
        try:
            _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp_file = _CONFIG_FILE.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            temp_file.replace(_CONFIG_FILE)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value
        self._sanitize()
        self.save()


_config = Config()

_SPECIAL_VK_MAP = {
    "SPACE": 0x20, "ENTER": 0x0D, "RETURN": 0x0D, "ESC": 0x1B, "ESCAPE": 0x1B,
    "TAB": 0x09, "BACKSPACE": 0x08, "INSERT": 0x2D, "INS": 0x2D, "DELETE": 0x2E,
    "DEL": 0x2E, "HOME": 0x24, "END": 0x23, "PAGEUP": 0x21, "PGUP": 0x21,
    "PAGEDOWN": 0x22, "PGDN": 0x22, "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27,
    "DOWN": 0x28, "PRINTSCREEN": 0x2C, "PRTSC": 0x2C, "SNAPSHOT": 0x2C,
    "PAUSE": 0x13, "`": 0xC0, "~": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB,
    "]": 0xDD, "\\": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
}


def _parse_hotkey(hk_str: str) -> tuple[int, int]:
    if not hk_str or not hk_str.strip():
        return 0, 0
    hk_str = hk_str.split(",")[0].strip().upper().replace(" ", "")
    modifiers = 0
    vk = 0
    parts = [p for p in hk_str.split("+") if p]
    if not parts:
        return 0, 0

    for mod in parts[:-1]:
        if mod in ("CTRL", "CONTROL"):
            modifiers |= 0x0002
        elif mod == "ALT":
            modifiers |= 0x0001
        elif mod == "SHIFT":
            modifiers |= 0x0004
        elif mod in ("WIN", "META", "SUPER"):
            modifiers |= 0x0008

    last_part = parts[-1]
    if len(last_part) == 1 and last_part.isalpha():
        vk = ord(last_part)
    elif len(last_part) == 1 and last_part.isdigit():
        vk = ord(last_part)
    elif last_part.startswith("F") and last_part[1:].isdigit():
        num = int(last_part[1:])
        if 1 <= num <= 24:
            vk = 0x6F + num
    elif last_part in _SPECIAL_VK_MAP:
        vk = _SPECIAL_VK_MAP[last_part]
    return modifiers, vk


def check_hotkey_conflict_win(hk_str: str) -> tuple[bool, str]:
    if os.name != "nt":
        return True, ""
    modifiers, vk = _parse_hotkey(hk_str)
    if vk == 0:
        return False, "无效的快捷键组合，请包含有效的触发键（如字母、数字或 F1-F12）"
    try:
        if ctypes.windll.user32.RegisterHotKey(None, 0x1337, modifiers, vk):
            ctypes.windll.user32.UnregisterHotKey(None, 0x1337)
            return True, ""
        return False, f"快捷键 {hk_str} 已被其他程序占用，请尝试其他组合"
    except Exception as e:
        logger.error(f"Hotkey check failed: {e}")
        return False, "快捷键检测异常"


def _get_target_exe_path() -> str:
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return f'"{Path(sys.executable).resolve()}"'
    return f'"{Path(sys.executable).resolve()}" "{Path(sys.argv[0]).resolve()}"'


def check_autostart_win() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ
        )
        val, _ = winreg.QueryValueEx(key, __app_name__)
        winreg.CloseKey(key)
        target = _get_target_exe_path().strip().lower()
        return val.strip().lower() == target
    except FileNotFoundError:
        return False
    except Exception:
        return False


def set_autostart_win(enable: bool):
    if os.name != "nt":
        return
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        if enable:
            winreg.SetValueEx(key, __app_name__, 0, winreg.REG_SZ, _get_target_exe_path())
        else:
            try:
                winreg.DeleteValue(key, __app_name__)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        logger.error(f"Failed to set autostart: {e}")


def play_shutter_sound():
    if not _config.get("enable_sound", True) or os.name != "nt":
        return
    try:
        shutter_wav = _CONFIG_DIR / "shutter.wav"
        if not shutter_wav.exists():
            sample_rate, duration = 44100, 0.12
            n_samples = int(sample_rate * duration)
            samples = [0.0] * n_samples
            for i in range(n_samples):
                t = i / sample_rate
                click1 = math.sin(2 * math.pi * 1800 * t) * math.exp(-70 * t)
                click2 = (
                    math.sin(2 * math.pi * 1200 * (t - 0.04)) * math.exp(-60 * (t - 0.04))
                    if t > 0.04 else 0.0
                )
                samples[i] = (click1 * 0.7 + click2 * 0.5) * 0.35
            with wave.open(shutter_wav.as_posix(), "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                packed = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples)
                wf.writeframes(packed)
        import winsound
        winsound.PlaySound(
            shutter_wav.as_posix(),
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        )
    except Exception as e:
        logger.debug(f"Play shutter sound failed: {e}")


if os.name == "nt":
    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    def _physical_rect_to_logical(rect: RECT, virtual_top_left: QPoint, screens: list[QScreen], fallback_dpr: float) -> QRect:
        cx = (rect.left + rect.right) / 2.0
        cy = (rect.top + rect.bottom) / 2.0

        matched_screen: Optional[QScreen] = None
        for scr in screens:
            g = scr.geometry()
            dpr = scr.devicePixelRatio()
            phys_left = g.x() * dpr
            phys_top = g.y() * dpr
            phys_right = phys_left + g.width() * dpr
            phys_bottom = phys_top + g.height() * dpr
            if phys_left <= cx <= phys_right and phys_top <= cy <= phys_bottom:
                matched_screen = scr
                break

        if matched_screen is not None:
            g = matched_screen.geometry()
            dpr = matched_screen.devicePixelRatio()
            phys_origin_x = g.x() * dpr
            phys_origin_y = g.y() * dpr
            lx = g.x() + (rect.left - phys_origin_x) / dpr - virtual_top_left.x()
            ly = g.y() + (rect.top - phys_origin_y) / dpr - virtual_top_left.y()
            lw = (rect.right - rect.left) / dpr
            lh = (rect.bottom - rect.top) / dpr
        else:
            lx = rect.left / fallback_dpr - virtual_top_left.x()
            ly = rect.top / fallback_dpr - virtual_top_left.y()
            lw = (rect.right - rect.left) / fallback_dpr
            lh = (rect.bottom - rect.top) / fallback_dpr

        return QRect(int(round(lx)), int(round(ly)), int(round(lw)), int(round(lh)))

    def get_window_rects(virtual_top_left: QPoint, fallback_dpr: float) -> list[QRect]:
        rects: list[QRect] = []
        user32 = ctypes.windll.user32
        screens = QGuiApplication.screens()
        try:
            dwmapi = ctypes.windll.dwmapi
        except Exception:
            dwmapi = None

        def callback(hwnd, _):
            try:
                if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                    return True
                if dwmapi:
                    cloaked = ctypes.c_int(0)
                    if dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)) == 0:
                        if cloaked.value != 0:
                            return True
                rect = RECT()
                got_real_bounds = False
                if dwmapi:
                    hr = dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect))
                    if hr == 0:
                        got_real_bounds = True
                if not got_real_bounds:
                    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                        return True
                logical_rect = _physical_rect_to_logical(rect, virtual_top_left, screens, fallback_dpr)
                if logical_rect.width() > 40 and logical_rect.height() > 40:
                    rects.append(logical_rect)
            except Exception:
                pass
            return True

        try:
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(EnumWindowsProc(callback), 0)
        except Exception as e:
            logger.debug(f"EnumWindows failed: {e}")
        return rects
else:
    def get_window_rects(virtual_top_left: QPoint, fallback_dpr: float) -> list[QRect]:
        return []


def apply_hdr_tone_mapping(image: QPixmap, strength: float = 0.85) -> QPixmap:
    if not HAS_NUMPY or image.isNull():
        return image
    try:
        original_dpr = image.devicePixelRatio()
        qimg = image.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        w, h = qimg.width(), qimg.height()

        ptr = qimg.bits()
        arr = np.frombuffer(memoryview(ptr), dtype=np.uint8).reshape((h, w, 4)).copy()

        rgb = arr[:, :, :3].astype(np.float32) / 255.0
        mapped = rgb * rgb * (3.0 - 2.0 * rgb)
        blended = rgb * (1.0 - strength) + mapped * strength
        arr[:, :, :3] = np.clip(blended * 255.0, 0, 255).astype(np.uint8)

        result_qimg = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
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
        if not screens:
            raise RuntimeError("No screens detected")

        virtual_rect = QRect()
        max_dpr = 1.0
        for screen in screens:
            virtual_rect = virtual_rect.united(screen.geometry())
            max_dpr = max(max_dpr, float(screen.devicePixelRatio()))

        phys_w = max(1, int(round(virtual_rect.width() * max_dpr)))
        phys_h = max(1, int(round(virtual_rect.height() * max_dpr)))
        full_pixmap = QPixmap(phys_w, phys_h)
        full_pixmap.setDevicePixelRatio(max_dpr)
        full_pixmap.fill(Qt.GlobalColor.black)

        painter = QPainter(full_pixmap)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for screen in screens:
            grab = screen.grabWindow(0)
            if not grab.isNull():
                s_geo = screen.geometry()
                target_logical_rect = QRect(
                    s_geo.topLeft() - virtual_rect.topLeft(),
                    s_geo.size()
                )
                painter.drawPixmap(target_logical_rect, grab, grab.rect())
        painter.end()
        return full_pixmap, max_dpr, virtual_rect
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return QPixmap(), 1.0, QRect()

class DrawItem:
    supports_fill: bool = False
    filled: bool = False

    def paint(self, painter: QPainter, base_image: Optional[QImage] = None):
        pass

    def contains(self, pos: QPointF) -> bool:
        return False

    def move_by(self, delta: QPointF):
        pass

    def bounding_rect(self) -> QRectF:
        return QRectF()

    def _stroke_contains(self, path: QPainterPath, pos: QPointF, width: int) -> bool:
        stroker = QPainterPathStroker()
        stroker.setWidth(max(width + 10, 14))
        return stroker.createStroke(path).contains(pos)

    @staticmethod
    def _make_8_handles(r: QRectF, size: float = 8.0) -> list[tuple[int, QRectF]]:
        nr = r.normalized()
        half = size / 2.0
        pts = [
            (0, nr.left(), nr.top()),
            (1, nr.center().x(), nr.top()),
            (2, nr.right(), nr.top()),
            (3, nr.right(), nr.center().y()),
            (4, nr.right(), nr.bottom()),
            (5, nr.center().x(), nr.bottom()),
            (6, nr.left(), nr.bottom()),
            (7, nr.left(), nr.center().y()),
        ]
        return [(idx, QRectF(x - half, y - half, size, size)) for idx, x, y in pts]

    @staticmethod
    def _apply_rect_handle(r: QRectF, handle_id: int, pos: QPointF) -> QRectF:
        nr = QRectF(r)
        if handle_id == 0:
            nr.setTopLeft(pos)
        elif handle_id == 1:
            nr.setTop(pos.y())
        elif handle_id == 2:
            nr.setTopRight(pos)
        elif handle_id == 3:
            nr.setRight(pos.x())
        elif handle_id == 4:
            nr.setBottomRight(pos)
        elif handle_id == 5:
            nr.setBottom(pos.y())
        elif handle_id == 6:
            nr.setBottomLeft(pos)
        elif handle_id == 7:
            nr.setLeft(pos.x())
        return nr.normalized()

    def get_handles(self) -> list[tuple[int, QRectF]]:
        return self._make_8_handles(self.bounding_rect())

    def hit_handle(self, pos: QPointF) -> int:
        for idx, h_rect in self.get_handles():
            if h_rect.adjusted(-3, -3, 3, 3).contains(pos):
                return idx
        return -1

    def resize_by_handle(self, handle_id: int, pos: QPointF):
        pass


class RectItem(DrawItem):
    supports_fill = True

    def __init__(self, rect: QRectF, color: QColor, width: int = 2, filled: bool = False):
        self.rect = QRectF(rect)
        self.color = QColor(color)
        self.width = width
        self.filled = filled

    def paint(self, painter: QPainter, base_image: Optional[QImage] = None):
        r = self.rect.normalized()
        painter.setPen(QPen(self.color, self.width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
        if self.filled:
            fill_c = QColor(self.color)
            painter.setBrush(QBrush(fill_c))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(r)

    def contains(self, pos: QPointF) -> bool:
        r = self.rect.normalized()
        if self.filled and r.contains(pos):
            return True
        p = QPainterPath()
        p.addRect(r)
        return self._stroke_contains(p, pos, self.width)

    def move_by(self, delta: QPointF):
        self.rect.translate(delta)

    def bounding_rect(self) -> QRectF:
        return self.rect.normalized().adjusted(-self.width - 2, -self.width - 2, self.width + 2, self.width + 2)

    def get_handles(self) -> list[tuple[int, QRectF]]:
        return self._make_8_handles(self.rect.normalized())

    def resize_by_handle(self, handle_id: int, pos: QPointF):
        self.rect = self._apply_rect_handle(self.rect.normalized(), handle_id, pos)


class CircleItem(DrawItem):
    supports_fill = True

    def __init__(self, rect: QRectF, color: QColor, width: int = 2, filled: bool = False):
        self.rect = QRectF(rect)
        self.color = QColor(color)
        self.width = width
        self.filled = filled

    def paint(self, painter: QPainter, base_image: Optional[QImage] = None):
        r = self.rect.normalized()
        painter.setPen(QPen(self.color, self.width))
        if self.filled:
            fill_c = QColor(self.color)
            painter.setBrush(QBrush(fill_c))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(r)

    def contains(self, pos: QPointF) -> bool:
        r = self.rect.normalized()
        p = QPainterPath()
        p.addEllipse(r)
        if self.filled and p.contains(pos):
            return True
        return self._stroke_contains(p, pos, self.width)

    def move_by(self, delta: QPointF):
        self.rect.translate(delta)

    def bounding_rect(self) -> QRectF:
        return self.rect.normalized().adjusted(-self.width - 2, -self.width - 2, self.width + 2, self.width + 2)

    def get_handles(self) -> list[tuple[int, QRectF]]:
        return self._make_8_handles(self.rect.normalized())

    def resize_by_handle(self, handle_id: int, pos: QPointF):
        self.rect = self._apply_rect_handle(self.rect.normalized(), handle_id, pos)


class LineItem(DrawItem):
    def __init__(self, start: QPointF, end: QPointF, color: QColor, width: int = 2):
        self.start, self.end, self.color, self.width = QPointF(start), QPointF(end), QColor(color), width

    def paint(self, painter: QPainter, base_image: Optional[QImage] = None):
        painter.setPen(QPen(self.color, self.width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(self.start, self.end)

    def contains(self, pos: QPointF) -> bool:
        p = QPainterPath()
        p.moveTo(self.start)
        p.lineTo(self.end)
        return self._stroke_contains(p, pos, self.width)

    def move_by(self, delta: QPointF):
        self.start += delta
        self.end += delta

    def bounding_rect(self) -> QRectF:
        return QRectF(self.start, self.end).normalized().adjusted(-self.width - 4, -self.width - 4, self.width + 4, self.width + 4)

    def get_handles(self) -> list[tuple[int, QRectF]]:
        return [
            (10, QRectF(self.start.x() - 4.5, self.start.y() - 4.5, 9, 9)),
            (11, QRectF(self.end.x() - 4.5, self.end.y() - 4.5, 9, 9)),
        ]

    def resize_by_handle(self, handle_id: int, pos: QPointF):
        if handle_id == 10:
            self.start = QPointF(pos)
        elif handle_id == 11:
            self.end = QPointF(pos)


class ArrowItem(LineItem):
    def _get_arrow_geometry(self):
        dx, dy = self.start.x() - self.end.x(), self.start.y() - self.end.y()
        length = math.hypot(dx, dy)
        if length < 1e-3:
            return self.end, self.end, self.end
        nx, ny = dx / length, dy / length
        head_len = min(length * 0.85, self.width * 4.2 + 8)
        arrow_w = head_len * 0.48
        p1 = QPointF(self.end.x() + nx * head_len - ny * arrow_w, self.end.y() + ny * head_len + nx * arrow_w)
        p2 = QPointF(self.end.x() + nx * head_len + ny * arrow_w, self.end.y() + ny * head_len - nx * arrow_w)
        shaft_end = QPointF(self.end.x() + nx * (head_len * 0.7), self.end.y() + ny * (head_len * 0.7))
        return p1, p2, shaft_end

    def paint(self, painter: QPainter, base_image: Optional[QImage] = None):
        p1, p2, shaft_end = self._get_arrow_geometry()
        painter.setPen(QPen(self.color, self.width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(self.start, shaft_end)
        painter.setBrush(QBrush(self.color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([self.end, p1, p2]))

    def contains(self, pos: QPointF) -> bool:
        p = QPainterPath()
        p.moveTo(self.start)
        p.lineTo(self.end)
        p1, p2, _ = self._get_arrow_geometry()
        p.addPolygon(QPolygonF([self.end, p1, p2]))
        return self._stroke_contains(p, pos, self.width)

    def bounding_rect(self) -> QRectF:
        p1, p2, _ = self._get_arrow_geometry()
        return (
            QRectF(self.start, self.end).normalized()
            .united(QRectF(p1, p2).normalized())
            .adjusted(-self.width - 4, -self.width - 4, self.width + 4, self.width + 4)
        )


class PencilItem(DrawItem):
    def __init__(self, points: list[QPointF], color: QColor, width: int = 2, is_marker: bool = False):
        self.points = [QPointF(p) for p in points]
        self.color = QColor(color)
        self.width = width
        self.is_marker = is_marker

    def paint(self, painter: QPainter, base_image: Optional[QImage] = None):
        if not self.points:
            return
        actual_w = self.width * (4 if self.is_marker else 1)
        c = QColor(self.color)
        if self.is_marker:
            c.setAlpha(110)
        if len(self.points) == 1:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(c))
            painter.drawEllipse(self.points[0], actual_w / 2.0, actual_w / 2.0)
            return
        cap = Qt.PenCapStyle.SquareCap if self.is_marker else Qt.PenCapStyle.RoundCap
        painter.setPen(QPen(c, actual_w, Qt.PenStyle.SolidLine, cap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(self.points[0])
        for p in self.points[1:]:
            path.lineTo(p)
        painter.drawPath(path)

    def contains(self, pos: QPointF) -> bool:
        if not self.points:
            return False
        actual_w = self.width * (4 if self.is_marker else 1)
        if len(self.points) == 1:
            return math.hypot(pos.x() - self.points[0].x(), pos.y() - self.points[0].y()) <= actual_w + 6
        path = QPainterPath()
        path.moveTo(self.points[0])
        for p in self.points[1:]:
            path.lineTo(p)
        return self._stroke_contains(path, pos, actual_w)

    def move_by(self, delta: QPointF):
        for i in range(len(self.points)):
            self.points[i] += delta

    def _raw_bounds(self) -> QRectF:
        if not self.points:
            return QRectF()
        xs = [p.x() for p in self.points]
        ys = [p.y() for p in self.points]
        return QRectF(min(xs), min(ys), max(1.0, max(xs) - min(xs)), max(1.0, max(ys) - min(ys)))

    def bounding_rect(self) -> QRectF:
        if not self.points:
            return QRectF()
        actual_w = self.width * (4 if self.is_marker else 1)
        return self._raw_bounds().adjusted(-actual_w, -actual_w, actual_w, actual_w)

    def get_handles(self) -> list[tuple[int, QRectF]]:
        return self._make_8_handles(self._raw_bounds())

    def resize_by_handle(self, handle_id: int, pos: QPointF):
        old_r = self._raw_bounds()
        if old_r.width() < 2 or old_r.height() < 2:
            return
        new_r = self._apply_rect_handle(old_r, handle_id, pos)
        if new_r.width() < 4 or new_r.height() < 4:
            return
        sx = new_r.width() / old_r.width()
        sy = new_r.height() / old_r.height()
        for i, pt in enumerate(self.points):
            nx = new_r.left() + (pt.x() - old_r.left()) * sx
            ny = new_r.top() + (pt.y() - old_r.top()) * sy
            self.points[i] = QPointF(nx, ny)


class TextItem(DrawItem):
    def __init__(self, pos: QPointF, text: str, font: QFont, color: QColor):
        self.pos = QPointF(pos)
        self.text = text
        self.font = QFont(font)
        self.color = QColor(color)
        self._rect = QRectF()
        self._calculate_rect()

    def _calculate_rect(self):
        fm = QFontMetrics(self.font)
        lines = self.text.split("\n") if self.text else [""]
        max_w = max((fm.horizontalAdvance(line) for line in lines), default=20)
        line_h = fm.height()
        th = line_h * len(lines)
        self._rect = QRectF(self.pos.x(), self.pos.y(), max_w + 14, th + 10)

    def paint(self, painter: QPainter, base_image: Optional[QImage] = None):
        painter.setFont(self.font)
        fm = painter.fontMetrics()
        lines = self.text.split("\n") if self.text else [""]
        max_w = max((fm.horizontalAdvance(line) for line in lines), default=20)
        th = fm.height() * len(lines)

        rect = QRectF(self.pos.x(), self.pos.y(), max_w + 14, th + 10)
        self._rect = rect

        is_dark = (self.color.red() * 0.299 + self.color.green() * 0.587 + self.color.blue() * 0.114) < 140
        shadow_color = QColor(255, 255, 255, 215) if is_dark else QColor(0, 0, 0, 185)

        align_flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        painter.setPen(shadow_color)
        for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)]:
            painter.drawText(rect.translated(ox, oy), align_flags, self.text)

        painter.setPen(self.color)
        painter.drawText(rect, align_flags, self.text)

    def contains(self, pos: QPointF) -> bool:
        return self._rect.adjusted(-4, -4, 4, 4).contains(pos)

    def move_by(self, delta: QPointF):
        self.pos += delta
        self._rect.translate(delta)

    def bounding_rect(self) -> QRectF:
        return self._rect.adjusted(-2, -2, 2, 2)

    def get_handles(self) -> list[tuple[int, QRectF]]:
        return self._make_8_handles(self._rect)

    def resize_by_handle(self, handle_id: int, pos: QPointF):
        old_r = QRectF(self._rect)
        new_r = self._apply_rect_handle(old_r, handle_id, pos)
        if old_r.height() > 5 and new_r.height() > 10:
            ratio = new_r.height() / old_r.height()
            new_pt_size = max(8, min(96, int(round(self.font.pointSize() * ratio))))
            if new_pt_size != self.font.pointSize():
                self.font.setPointSize(new_pt_size)
                self.pos = new_r.topLeft()
                self._calculate_rect()


class StepBadgeItem(DrawItem):
    def __init__(self, pos: QPointF, number: int, color: QColor):
        self.pos = QPointF(pos)
        self.number = number
        self.color = QColor(color)
        self.radius = 13.0

    def paint(self, painter: QPainter, base_image: Optional[QImage] = None):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 75))
        painter.drawEllipse(self.pos + QPointF(0, 1.5), self.radius, self.radius)
        painter.setBrush(Qt.GlobalColor.white)
        painter.drawEllipse(self.pos, self.radius + 1.2, self.radius + 1.2)
        painter.setBrush(self.color)
        painter.drawEllipse(self.pos, self.radius, self.radius)
        painter.setPen(Qt.GlobalColor.white)
        base_fs = max(8, int(round(self.radius * (0.85 if self.number < 10 else 0.74))))
        painter.setFont(QFont("Segoe UI", base_fs, QFont.Weight.Bold))
        r = QRectF(self.pos.x() - self.radius, self.pos.y() - self.radius, self.radius * 2, self.radius * 2)
        painter.drawText(r, Qt.AlignmentFlag.AlignCenter, str(self.number))
        painter.restore()

    def contains(self, pos: QPointF) -> bool:
        return math.hypot(pos.x() - self.pos.x(), pos.y() - self.pos.y()) <= self.radius + 5

    def move_by(self, delta: QPointF):
        self.pos += delta

    def bounding_rect(self) -> QRectF:
        r = self.radius + 2
        return QRectF(self.pos.x() - r, self.pos.y() - r, r * 2, r * 2)

    def get_handles(self) -> list[tuple[int, QRectF]]:
        return self._make_8_handles(self.bounding_rect())

    def resize_by_handle(self, handle_id: int, pos: QPointF):
        dist = math.hypot(pos.x() - self.pos.x(), pos.y() - self.pos.y())
        self.radius = max(9.0, min(48.0, dist / math.sqrt(2.0)))


class MosaicItem(DrawItem):
    def __init__(self, rect: QRectF, block_size: int = 12):
        self.rect = QRectF(rect)
        self.block_size = max(6, block_size)

    def paint(self, painter: QPainter, base_image: Optional[QImage] = None):
        r = self.rect.normalized()
        if r.width() < 2 or r.height() < 2 or base_image is None or base_image.isNull():
            return

        dpr = base_image.devicePixelRatio()
        img_w, img_h = base_image.width(), base_image.height()
        logical_bounds = QRectF(0, 0, img_w / dpr, img_h / dpr)
        r = r.intersected(logical_bounds)
        if r.isEmpty():
            return

        painter.save()
        painter.setClipRect(r)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        bs = self.block_size
        start_x = int(r.left() // bs) * bs
        start_y = int(r.top() // bs) * bs
        end_x = int(math.ceil(r.right()))
        end_y = int(math.ceil(r.bottom()))

        for y in range(start_y, end_y, bs):
            for x in range(start_x, end_x, bs):
                sample_x = min(max(0, int((x + bs * 0.5) * dpr)), img_w - 1)
                sample_y = min(max(0, int((y + bs * 0.5) * dpr)), img_h - 1)
                painter.fillRect(x, y, bs, bs, base_image.pixelColor(sample_x, sample_y))
        painter.restore()

    def contains(self, pos: QPointF) -> bool:
        return self.rect.normalized().contains(pos)

    def move_by(self, delta: QPointF):
        self.rect.translate(delta)

    def bounding_rect(self) -> QRectF:
        return self.rect.normalized()

    def get_handles(self) -> list[tuple[int, QRectF]]:
        return self._make_8_handles(self.rect.normalized())

    def resize_by_handle(self, handle_id: int, pos: QPointF):
        self.rect = self._apply_rect_handle(self.rect.normalized(), handle_id, pos)

class TextAnnotationWidget(QFrame):
    committed = Signal(str, QPointF, QFont, QColor)
    cancelled = Signal()

    def __init__(
        self,
        pos: QPoint,
        initial_text: str = "",
        font: Optional[QFont] = None,
        color: Optional[QColor] = None,
        parent=None
    ):
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
        self.drag_handle.setStyleSheet("color: #9aa0a6; font-size: 14px; font-weight: bold; padding: 0 2px;")
        self.drag_handle.setCursor(Qt.CursorShape.SizeAllCursor)
        self.drag_handle.setToolTip("按住拖动文字框")
        tb_layout.addWidget(self.drag_handle)

        self.btn_font = QToolButton()
        self.btn_font.setText("字体")
        self.btn_font.setToolTip("选择字体 (Aa)")
        self.btn_font.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_font.clicked.connect(self._choose_font)
        tb_layout.addWidget(self.btn_font)

        self.btn_minus = QToolButton()
        self.btn_minus.setText("A-")
        self.btn_minus.setToolTip("缩小字号 (或 Ctrl+滚轮)")
        self.btn_minus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_minus.clicked.connect(lambda: self._change_font_size(-2))
        tb_layout.addWidget(self.btn_minus)

        self.size_label = QLabel(f"{self.current_font.pointSize()}")
        self.size_label.setStyleSheet("color: #1a73e8; font-weight: bold; font-size: 12px; min-width: 20px;")
        self.size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tb_layout.addWidget(self.size_label)

        self.btn_plus = QToolButton()
        self.btn_plus.setText("A+")
        self.btn_plus.setToolTip("放大字号 (或 Ctrl+滚轮)")
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
        self.btn_ok.setToolTip("完成 (Enter / Ctrl+Enter，换行请按 Shift+Enter)")
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
        self.edit.setAcceptRichText(False)
        self.edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.edit.setPlaceholderText("输入文字 (Shift+Enter 换行)...")
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
        QTimer.singleShot(30, self.edit.setFocus)

    def set_color(self, color: QColor):
        self.current_color = QColor(color)
        self._update_color_preview()
        self._update_edit_stylesheet()

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
            self.set_color(color)
            self.edit.setFocus()

    def _adjust_size(self):
        self.edit.document().setTextWidth(-1)
        doc_w = int(self.edit.document().idealWidth()) + 24
        doc_h = int(self.edit.document().size().height()) + 16

        edit_w = max(210, doc_w)
        edit_h = max(40, doc_h)
        self.edit.setFixedSize(edit_w, edit_h)

        tb_w = self.toolbar_widget.sizeHint().width()
        total_w = max(edit_w, tb_w) + 16
        total_h = edit_h + self.toolbar_widget.sizeHint().height() + 18
        self.resize(total_w, total_h)

        if self.parentWidget():
            pw, ph = self.parentWidget().width(), self.parentWidget().height()
            nx = max(6, min(self.x(), pw - total_w - 6))
            ny = max(6, min(self.y(), ph - total_h - 6))
            if nx != self.x() or ny != self.y():
                self.move(nx, ny)

    def eventFilter(self, obj, event):
        if obj == self.edit:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        return False
                    self.commit()
                    return True
                elif event.key() == Qt.Key.Key_Escape:
                    self.cancel()
                    return True
            elif event.type() == QEvent.Type.Wheel:
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
            new_pos = event.globalPosition().toPoint() - self._drag_start
            if self.parentWidget():
                pw, ph = self.parentWidget().width(), self.parentWidget().height()
                new_pos.setX(max(4, min(new_pos.x(), pw - self.width() - 4)))
                new_pos.setY(max(4, min(new_pos.y(), ph - self.height() - 4)))
            self.move(new_pos)
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
    fill_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FloatingToolBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            #FloatingToolBar {
                background: #ffffff;
                border: 1px solid #dbe3ef;
                border-radius: 9px;
            }
            QToolButton {
                border: none;
                border-radius: 6px;
                padding: 5px;
                background: transparent;
            }
            QToolButton:hover {
                background: #f1f5f9;
            }
            QToolButton:checked {
                background: #e8f0fe;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 5, 7, 5)
        layout.setSpacing(3)

        self.drag_handle = QLabel("⋮⋮")
        self.drag_handle.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 15px; padding: 0 2px;")
        self.drag_handle.setCursor(Qt.CursorShape.SizeAllCursor)
        self.drag_handle.setToolTip("按住拖动工具栏")
        layout.addWidget(self.drag_handle)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.buttons: dict[str, QToolButton] = {}
        tools = [
            ("rect", "矩形 (R) · 画完可拖框缩放/按 F 填充", True),
            ("circle", "椭圆 (O) · 画完可拖框缩放/按 F 填充", True),
            ("arrow", "箭头 (A) · 画完可拖动首尾端点", True),
            ("line", "直线 (L) · 画完可拖动首尾端点", True),
            ("pencil", "画笔 (P)", True),
            ("marker", "荧光笔 (H)", True),
            ("text", "文字 (T)", True),
            ("badge", "序号标注 (B) · 支持选 1–15 任意起始", True),
            ("mosaic", "马赛克 (M)", True),
            ("picker", "吸管取色 (C)", True),
        ]
        for action, tooltip, checkable in tools:
            btn = QToolButton()
            btn.setToolTip(tooltip)
            btn.setIcon(get_svg_icon(action, "#475569", 20))
            btn.setIconSize(QSize(20, 20))
            btn.setCheckable(checkable)
            self.btn_group.addButton(btn)
            btn.clicked.connect(lambda checked, a=action: self.tool_changed.emit(a))
            layout.addWidget(btn)
            self.buttons[action] = btn

        self._add_separator(layout)

        self.fill_btn = QToolButton()
        self.fill_btn.setToolTip("封闭图形填充当前颜色 (F) · 可对已选中的矩形/椭圆随时切换填充")
        self.fill_btn.setIcon(get_svg_icon("fill", "#475569", 20))
        self.fill_btn.setIconSize(QSize(20, 20))
        self.fill_btn.setCheckable(True)
        self.fill_btn.clicked.connect(lambda checked: self.fill_toggled.emit(checked))
        layout.addWidget(self.fill_btn)

        self._current_width = _config.get("pen_width", 3)
        self.width_group = QButtonGroup(self)
        self.width_group.setExclusive(True)
        self.width_buttons: dict[int, QToolButton] = {}
        for width_val, tooltip in [(2, "细 (1)"), (3, "中 (2)"), (5, "粗 (3)")]:
            w_btn = QToolButton()
            w_btn.setFixedSize(20, 20)
            w_btn.setToolTip(tooltip)
            w_btn.setCheckable(True)
            w_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            circle_size = width_val * 2
            w_btn.setStyleSheet(f"""
                QToolButton {{
                    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                        stop:0 #5f6368, stop:{circle_size/20.0} #5f6368, stop:1 transparent);
                    border: 1px solid #dadce0;
                    border-radius: 10px;
                }}
                QToolButton:checked {{
                    border: 2px solid #1a73e8;
                    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                        stop:0 #1a73e8, stop:{circle_size/20.0} #1a73e8, stop:1 #e8f0fe);
                }}
            """)
            w_btn.clicked.connect(lambda checked, w=width_val: self._on_width_changed(w))
            self.width_group.addButton(w_btn)
            self.width_buttons[width_val] = w_btn
            layout.addWidget(w_btn)
            if width_val == self._current_width:
                w_btn.setChecked(True)

        self._add_separator(layout)
        self._current_color = QColor(_config.get("default_color", "#ea4335"))
        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        for hex_val, name in [
            ("#ea4335", "红色"),
            ("#fbbc05", "黄色"),
            ("#34a853", "绿色"),
            ("#1a73e8", "蓝色"),
            ("#202124", "黑色"),
            ("#ffffff", "白色"),
        ]:
            c_btn = QToolButton()
            c_btn.setFixedSize(20, 20)
            c_btn.setToolTip(name)
            c_btn.setCheckable(True)
            c_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            c_btn.setStyleSheet(f"""
                QToolButton {{
                    background-color: {hex_val};
                    border: {'2px solid #cbd5e1' if hex_val == '#ffffff' else '1px solid #dadce0'};
                    border-radius: 10px;
                    margin: 1px;
                }}
                QToolButton:checked {{
                    border: 2px solid #1e293b;
                    margin: 0px;
                }}
            """)
            c_btn.clicked.connect(lambda checked, c=hex_val: self._set_color(c))
            self.color_group.addButton(c_btn)
            layout.addWidget(c_btn)
            if hex_val.upper() == self._current_color.name().upper():
                c_btn.setChecked(True)

        self.palette_btn = QToolButton()
        self.palette_btn.setToolTip("自定义颜色...")
        self.palette_btn.setIcon(get_svg_icon("palette", "#475569", 20))
        self.palette_btn.setIconSize(QSize(20, 20))
        self.palette_btn.clicked.connect(self._choose_color)
        layout.addWidget(self.palette_btn)

        self._add_separator(layout)
        for action, tooltip, color in [
            ("undo", "撤销 (Ctrl+Z)", "#475569"),
            ("ocr", "OCR 文字识别并核查 (Ctrl+Shift+C)", "#1a73e8"),
            ("pin", "贴图到屏幕 (F3)", "#1a73e8"),
            ("save", "保存图片 (Ctrl+S)", "#1a73e8"),
            ("close", "取消截图 (Esc)", "#ea4335"),
            ("check", "完成并复制 (Enter / 双击)", "#34a853"),
        ]:
            btn = QToolButton()
            btn.setToolTip(tooltip)
            btn.setIcon(get_svg_icon(action, color, 20))
            btn.setIconSize(QSize(20, 20))
            act_name = "finish" if action == "check" else action
            btn.clicked.connect(lambda checked, a=act_name: self.action_triggered.emit(a))
            layout.addWidget(btn)

        self._is_dragging = False
        self._drag_start_pos = QPoint()

    def _add_separator(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background-color: #e2e8f0; border: none; margin: 3px 2px;")
        layout.addWidget(sep)

    def _on_width_changed(self, width: int):
        self._current_width = width
        if width in self.width_buttons:
            self.width_buttons[width].setChecked(True)
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
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            global_pos = event.globalPosition().toPoint()
            delta = global_pos - self._drag_start_pos
            new_pos = self.pos() + delta
            if self.parentWidget():
                pw, ph = self.parentWidget().width(), self.parentWidget().height()
                new_pos.setX(max(4, min(new_pos.x(), pw - self.width() - 4)))
                new_pos.setY(max(4, min(new_pos.y(), ph - self.height() - 4)))
            self.move(new_pos)
            self._drag_start_pos = global_pos
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
        super().mouseReleaseEvent(event)


class PinnedImageWidget(QWidget):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.original_pixmap = pixmap
        self.scale_factor = 1.0
        self.opacity = 1.0
        self.drag_pos = QPoint()
        self.logical_base_size = self._compute_logical_size()
        self.setFixedSize(self.logical_base_size)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def _compute_logical_size(self) -> QSize:
        dpr = max(1.0, float(self.original_pixmap.devicePixelRatio()))
        w = max(30, int(round(self.original_pixmap.width() / dpr)))
        h = max(30, int(round(self.original_pixmap.height() / dpr)))
        return QSize(w, h)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(self.opacity)
        painter.drawPixmap(self.rect(), self.original_pixmap)
        painter.setPen(QPen(QColor(26, 115, 232, 160), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu { background: #ffffff; border: 1px solid #dbe3ef; border-radius: 8px; padding: 4px; }
                QMenu::item { padding: 6px 18px; border-radius: 4px; color: #334155; font-size: 12px; }
                QMenu::item:selected { background: #e8f0fe; color: #1a73e8; }
            """)
            menu.addAction("复制图片", lambda: QApplication.clipboard().setPixmap(self.original_pixmap))
            menu.addAction("另存为图片...", self._save_pinned_image)
            menu.addAction("恢复 100% 原始尺寸", self._reset_scale)
            menu.addSeparator()
            menu.addAction("关闭贴图 (Esc / 双击)", self.close)
            menu.exec(event.globalPosition().toPoint())

    def _save_pinned_image(self):
        last_dir = _config.get("last_save_dir", str(Path.home() / "Pictures"))
        ts = time.strftime("%Y%m%d_%H%M%S")
        fp, _ = QFileDialog.getSaveFileName(
            self,
            "保存贴图",
            str(Path(last_dir) / f"{__app_name__}_Pin_{ts}.png"),
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp)"
        )
        if fp:
            self.original_pixmap.save(fp)

    def _reset_scale(self):
        self.scale_factor = 1.0
        self.opacity = 1.0
        self.setFixedSize(self.logical_base_size)
        self.update()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.opacity = min(1.0, max(0.15, self.opacity + (0.05 if delta > 0 else -0.05)))
            self.update()
        else:
            self.scale_factor = max(0.15, min(5.0, self.scale_factor * (1.1 if delta > 0 else 0.9)))
            base_w, base_h = self.logical_base_size.width(), self.logical_base_size.height()
            self.setFixedSize(max(30, int(round(base_w * self.scale_factor))), max(30, int(round(base_h * self.scale_factor))))

    def mouseDoubleClickEvent(self, event):
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()


class OCRWorker(QThread):
    result_ready = Signal(str, bool)

    def __init__(self, img_bytes: bytes, parent=None):
        super().__init__(parent)
        self.img_bytes = img_bytes
        self._is_cancelled = False

    def run(self):
        try:
            ocr = get_ocr_engine()
            if self._is_cancelled:
                return
            if not ocr:
                self.result_ready.emit("OCR 引擎初始化失败，请确认已安装 rapidocr-onnxruntime。", False)
                return
            with _OCR_ENGINE_LOCK:
                result, _ = ocr(self.img_bytes)
            if self._is_cancelled:
                return
            if result:
                lines_data = [
                    {
                        "text": res[1],
                        "x": min(p[0] for p in res[0]),
                        "y": sum(p[1] for p in res[0]) / 4.0,
                        "h": max(1.0, max(p[1] for p in res[0]) - min(p[1] for p in res[0])),
                    }
                    for res in result if len(res) >= 2 and str(res[1]).strip()
                ]
                if not lines_data:
                    self.result_ready.emit("未识别到有效文字，请确保选区文字清晰。", False)
                    return

                lines_data.sort(key=lambda item: item["y"])
                grouped_lines: list[str] = []
                current_line: list[dict] = []
                for item in lines_data:
                    if not current_line:
                        current_line.append(item)
                    else:
                        avg_h = sum(b["h"] for b in current_line) / len(current_line)
                        avg_y = sum(b["y"] for b in current_line) / len(current_line)
                        if abs(item["y"] - avg_y) < avg_h * 0.55:
                            current_line.append(item)
                        else:
                            current_line.sort(key=lambda b: b["x"])
                            grouped_lines.append(self._smart_join(current_line))
                            current_line = [item]
                if current_line:
                    current_line.sort(key=lambda b: b["x"])
                    grouped_lines.append(self._smart_join(current_line))
                self.result_ready.emit("\n".join(grouped_lines), True)
            else:
                self.result_ready.emit("未识别到文字，请确保选区清晰。", False)
        except Exception as e:
            logger.error(f"OCR worker exception: {e}")
            self.result_ready.emit(f"OCR 引擎错误:\n{str(e)}", False)

    @staticmethod
    def _smart_join(line_items: list[dict]) -> str:
        text = ""
        for i, item in enumerate(line_items):
            curr_str = str(item["text"]).strip()
            if not curr_str:
                continue
            if i == 0 or not text:
                text += curr_str
            else:
                prev_char, curr_char = text[-1], curr_str[0]
                if prev_char.isalnum() and curr_char.isalnum() and ord(prev_char) < 128 and ord(curr_char) < 128:
                    text += " " + curr_str
                else:
                    text += curr_str
        return text

    def cancel(self):
        self._is_cancelled = True


class OCRDialog(QDialog):
    def __init__(self, result_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{__app_name__} - 核查 OCR 识别结果")
        self.resize(620, 440)
        self.setMinimumSize(460, 320)
        self.setStyleSheet("""
            QDialog { background-color: #f8fafc; }
            QLabel#Hint { color: #64748b; font-size: 12px; }
            QTextEdit {
                background: #ffffff; border: 1px solid #dbe3ef;
                border-radius: 8px; padding: 10px; font-size: 13px;
                color: #202124; font-family: Consolas, 'Microsoft YaHei';
                selection-background-color: #bfdbfe;
            }
            QPushButton {
                background: #1a73e8; color: #ffffff; border-radius: 6px;
                padding: 8px 16px; font-weight: 600; border: none;
            }
            QPushButton:hover { background: #1557b0; }
            QPushButton#CancelButton {
                background: #ffffff; color: #334155; border: 1px solid #cbd5e1;
            }
            QPushButton#CancelButton:hover { background: #f1f5f9; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        hint = QLabel("请核查识别结果；可直接在下方编辑修正文字，确认无误后点击「复制并关闭」。")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

        self.text_edit = QTextEdit(self)
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlainText(result_text)
        layout.addWidget(self.text_edit, 1)

        button_layout = QHBoxLayout()
        char_count_label = QLabel(f"共 {len(result_text)} 字符", self)
        char_count_label.setStyleSheet("color: #64748b; font-size: 12px;")
        self.text_edit.textChanged.connect(
            lambda: char_count_label.setText(f"共 {len(self.text_edit.toPlainText())} 字符")
        )
        button_layout.addWidget(char_count_label)
        button_layout.addStretch()

        self.cancel_btn = QPushButton("取消 (保留截图)", self)
        self.cancel_btn.setObjectName("CancelButton")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.copy_btn = QPushButton("复制并关闭 (Ctrl+Enter)", self)
        self.copy_btn.setToolTip("将核查后的文字复制到剪贴板，并完成本次截图")
        self.copy_btn.setDefault(True)
        self.copy_btn.setShortcut("Ctrl+Return")
        self.copy_btn.clicked.connect(self._copy_and_close)
        button_layout.addWidget(self.copy_btn)
        layout.addLayout(button_layout)

        self.text_edit.setFocus()

    def _copy_and_close(self):
        text = self.text_edit.toPlainText()
        if not text.strip():
            QMessageBox.information(self, "没有可复制的文字", "请先确认识别结果不为空。")
            self.text_edit.setFocus()
            return
        try:
            QApplication.clipboard().setText(text)
        except Exception as exc:
            QMessageBox.warning(self, "复制失败", f"无法写入剪贴板：\n{exc}")
            return
        self.accept()


class StepNumberPalette(QFrame):
    number_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StepNumberPalette")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            QFrame#StepNumberPalette {
                background: #ffffff;
                border: 1px solid #dbe3ef;
                border-radius: 10px;
            }
            QLabel { color: #475569; font-size: 11px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 9)
        layout.setSpacing(6)

        self.title = QLabel("选择起始序号 (1–15) · 后续自动递增")
        self.title.setStyleSheet("font-size: 12px; font-weight: 600; color: #1e293b; border: none;")
        layout.addWidget(self.title)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(5)
        self.number_buttons: dict[int, QToolButton] = {}
        for number in range(1, 16):
            button = QToolButton(self)
            button.setText(str(number))
            button.setFixedSize(30, 30)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"从 {number} 开始编号，之后自动递增")
            button.clicked.connect(lambda checked=False, n=number: self.number_selected.emit(n))
            self.number_buttons[number] = button
            grid.addWidget(button, (number - 1) // 5, (number - 1) % 5)
        layout.addLayout(grid)

        self.status = QLabel("当前下一个序号：1")
        self.status.setStyleSheet("font-size: 11px; color: #1a73e8; font-weight: 600; border: none;")
        layout.addWidget(self.status)
        self.current_next = 1
        self.update_active_number(1)
        self.adjustSize()

    def update_active_number(self, next_number: int):
        self.current_next = next_number
        for value, button in self.number_buttons.items():
            if value == next_number:
                button.setStyleSheet("""
                    QToolButton {
                        background: #1a73e8; color: #ffffff; border: 2px solid #1a73e8;
                        border-radius: 15px; font-weight: 700;
                    }
                    QToolButton:hover { background: #1557b0; }
                """)
            else:
                button.setStyleSheet("""
                    QToolButton {
                        background: #f1f5f9; color: #334155; border: 1px solid #e2e8f0;
                        border-radius: 15px; font-weight: 600;
                    }
                    QToolButton:hover { background: #dbeafe; color: #1d4ed8; border-color: #93c5fd; }
                """)
        self.status.setText(f"下一个序号：{next_number}（点击数字切换起点）")
        self.adjustSize()


class ShortcutHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("""
            QDialog { background: transparent; }
            QFrame#HelpCard {
                background: rgba(30, 41, 59, 245);
                border-radius: 12px;
                padding: 16px;
                border: 1px solid rgba(255,255,255,50);
            }
            QLabel { color: #f1f5f9; font-size: 12px; }
            QLabel#Title { font-size: 14px; font-weight: bold; color: #60a5fa; }
            QLabel#Key {
                background: #334155;
                padding: 3px 8px;
                border-radius: 4px;
                font-family: Consolas;
                font-weight: bold;
            }
        """)
        self.card = QFrame()
        self.card.setObjectName("HelpCard")
        lay = QVBoxLayout(self.card)
        lay.setSpacing(8)
        title = QLabel(f"⌨ {__app_name__} 快捷键指南 (点击任意处关闭)")
        title.setObjectName("Title")
        lay.addWidget(title)
        shortcuts = [
            ("Esc / 右键", "取消当前绘制 / 撤销 / 退出截图"),
            ("Enter / 双击", "完成截图并复制到剪贴板"),
            ("选中图形拖动控制点", "自由改变已画图形的大小、长宽或箭头端点"),
            ("F", "切换封闭图形（矩形/椭圆）填充当前颜色"),
            ("Ctrl + S", "保存截图到本地文件"),
            ("Ctrl + Z / Delete", "撤销上一标注 / 删除当前选中图形"),
            ("F3", "将选区贴图固定到屏幕顶层"),
            ("C", "吸管取色 (自动复制 HEX 并设为画笔色)"),
            ("R / O / L / A", "矩形 / 椭圆 / 直线 / 箭头"),
            ("P / H / T", "画笔 / 荧光笔 / 文字标注 (双击二次编辑)"),
            ("B / M", "序号标注 (支持1–15选号) / 马赛克"),
            ("1 / 2 / 3", "切换笔刷粗细 (细 / 中 / 粗)"),
            ("Ctrl+Shift+C", "OCR 识别选区文字并打开核查窗口"),
        ]
        for key, desc in shortcuts:
            row = QHBoxLayout()
            row.setSpacing(8)
            k_label = QLabel(key)
            k_label.setObjectName("Key")
            k_label.setFixedWidth(145)
            row.addWidget(k_label)
            row.addWidget(QLabel(desc))
            row.addStretch()
            lay.addLayout(row)
        main_lay = QVBoxLayout(self)
        main_lay.addWidget(self.card)
        self.adjustSize()

    def mousePressEvent(self, event):
        self.close()

    def keyPressEvent(self, event):
        self.close()


class FrozenFrameEditor(QWidget):
    STATE_IDLE = 0
    STATE_SELECTING = 1
    STATE_SELECTED = 2
    STATE_EDITING = 3
    STATE_RESIZING = 4
    STATE_MOVING = 5
    STATE_MOVING_ITEM = 6
    STATE_RESIZING_ITEM = 7

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
        self.base_image.setDevicePixelRatio(max_dpr)
        self.max_dpr = max_dpr
        self.virtual_rect = virtual_rect
        self.controller = controller

        self.state = self.STATE_IDLE
        self.active_tool = "none"
        self.current_color = QColor(_config.get("default_color", "#ea4335"))
        self.current_width = _config.get("pen_width", 3)
        self.fill_enabled = False
        self.step_counter = 1
        self._step_history: list[tuple[StepBadgeItem, int]] = []
        self._ocr_worker: Optional[OCRWorker] = None

        self.start_pos = QPoint()
        self.current_mouse_pos = QPoint()
        self.selected_rect = QRect()
        self.active_handle = -1
        self.active_item_handle = -1
        self.move_offset = QPoint()
        self._right_click_pressed = False

        self.draw_items: list[DrawItem] = []
        self.current_drawing_item: Optional[DrawItem] = None
        self.highlighted_window = QRect()
        self.selected_item: Optional[DrawItem] = None
        self.item_last_pos = QPoint()

        self.active_text_editor: Optional[TextAnnotationWidget] = None
        self._editing_original_item: Optional[TextItem] = None

        self.toolbar = FloatingToolBar(self)
        self.toolbar.hide()
        self.toolbar.tool_changed.connect(self._set_active_tool)
        self.toolbar.color_changed.connect(self._set_drawing_color)
        self.toolbar.width_changed.connect(self._set_drawing_width)
        self.toolbar.fill_toggled.connect(self._on_fill_toggled)
        self.toolbar.action_triggered.connect(self._handle_action)

        self.number_palette = StepNumberPalette(self)
        self.number_palette.number_selected.connect(self._select_step_number)
        self.number_palette.installEventFilter(self)
        self.number_palette.hide()

        badge_button = self.toolbar.buttons.get("badge")
        if badge_button:
            badge_button.installEventFilter(self)

        self.help_dialog: Optional[ShortcutHelpDialog] = None
        self.setGeometry(virtual_rect)
        self.window_rects = get_window_rects(virtual_rect.topLeft(), max_dpr)

        self.setWindowOpacity(0.0)
        self.show()
        self.activateWindow()
        self.raise_()

        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(120)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._anim.start()

    def eventFilter(self, watched, event):
        badge_button = self.toolbar.buttons.get("badge") if hasattr(self, "toolbar") else None
        if watched is badge_button:
            if event.type() == QEvent.Type.Enter:
                self._show_step_palette(near_cursor=False)
            elif event.type() == QEvent.Type.Leave:
                if self.active_tool != "badge":
                    QTimer.singleShot(180, self._hide_step_palette_if_needed)
        elif watched is getattr(self, "number_palette", None):
            if event.type() == QEvent.Type.Leave and self.active_tool != "badge":
                QTimer.singleShot(180, self._hide_step_palette_if_needed)
        return super().eventFilter(watched, event)

    def _show_step_palette(self, near_cursor: bool = False):
        if not self.toolbar.isVisible():
            return
        self.number_palette.update_active_number(self.step_counter)
        self.number_palette.adjustSize()

        pw, ph = self.number_palette.width(), self.number_palette.height()
        button = self.toolbar.buttons.get("badge")

        if near_cursor and not self.toolbar.geometry().contains(self.current_mouse_pos):
            x = self.current_mouse_pos.x() + 24
            y = self.current_mouse_pos.y() + 24
            if x + pw > self.width() - 10:
                x = self.current_mouse_pos.x() - pw - 24
            if y + ph > self.height() - 10:
                y = self.current_mouse_pos.y() - ph - 24
        elif button:
            anchor = button.mapTo(self, QPoint(button.width() // 2, button.height()))
            x = anchor.x() - pw // 2
            y = anchor.y() + 7
            if y + ph > self.height() - 8:
                button_top = button.mapTo(self, QPoint(0, 0)).y()
                y = button_top - ph - 7
        else:
            return

        x = max(8, min(x, self.width() - pw - 8))
        y = max(8, min(y, self.height() - ph - 8))
        self.number_palette.move(x, y)
        self.number_palette.show()
        self.number_palette.raise_()

    def _hide_step_palette_if_needed(self):
        if not self.number_palette.isVisible() or self.active_tool == "badge":
            return
        cursor_pos = QCursor.pos()
        button = self.toolbar.buttons.get("badge")
        if button and button.rect().contains(button.mapFromGlobal(cursor_pos)):
            return
        if self.number_palette.geometry().contains(self.mapFromGlobal(cursor_pos)):
            return
        self.number_palette.hide()

    def _select_step_number(self, number: int):
        self.step_counter = number
        self._step_history.clear()
        self.number_palette.update_active_number(number)
        if self.active_tool != "badge":
            self._set_active_tool("badge")
        self.update()

    def _forget_step_badge(self, item: DrawItem):
        if not isinstance(item, StepBadgeItem):
            return
        for index, (badge, previous_counter) in enumerate(self._step_history):
            if badge is item:
                if index == len(self._step_history) - 1:
                    self._step_history.pop()
                    self.step_counter = previous_counter
                    if hasattr(self, "number_palette"):
                        self.number_palette.update_active_number(self.step_counter)
                else:
                    self._step_history.pop(index)
                return

    def _get_magnifier_rect(self, pos: QPoint) -> QRect:
        if not _config.get("show_magnifier", True):
            return QRect()
        hud_w, hud_h = 140, 160
        x, y = pos.x(), pos.y()
        hud_x = x + 20 if x + hud_w + 30 < self.width() else x - hud_w - 20
        hud_y = y + 20 if y + hud_h + 30 < self.height() else y - hud_h - 20
        return QRect(hud_x - 5, hud_y - 5, hud_w + 10, hud_h + 10)

    def _set_drawing_color(self, color: QColor):
        self.current_color = QColor(color)
        if self.active_text_editor:
            self.active_text_editor.set_color(color)
        elif self.selected_item and hasattr(self.selected_item, "color"):
            self.selected_item.color = QColor(color)
            self.update()

    def _set_drawing_width(self, width: int):
        self.current_width = width
        if self.selected_item:
            if hasattr(self.selected_item, "width"):
                self.selected_item.width = width
                self.update()
            elif isinstance(self.selected_item, MosaicItem):
                self.selected_item.block_size = max(8, width * 3 + 3)
                self.update()

    def _on_fill_toggled(self, checked: bool):
        self.fill_enabled = checked
        self.toolbar.fill_btn.blockSignals(True)
        self.toolbar.fill_btn.setChecked(checked)
        self.toolbar.fill_btn.blockSignals(False)
        if self.selected_item and getattr(self.selected_item, "supports_fill", False):
            self.selected_item.filled = checked
            self.selected_item.color = QColor(self.current_color)
            self.update()

    def _sync_toolbar_with_selected_item(self):
        if self.selected_item and getattr(self.selected_item, "supports_fill", False):
            self.fill_enabled = bool(self.selected_item.filled)
            self.toolbar.fill_btn.blockSignals(True)
            self.toolbar.fill_btn.setChecked(self.fill_enabled)
            self.toolbar.fill_btn.blockSignals(False)

    def _set_active_tool(self, tool: str):
        self._commit_active_text_editor()
        self.active_tool = tool
        self._update_cursor(self.current_mouse_pos)
        if hasattr(self.toolbar, "buttons"):
            btn = self.toolbar.buttons.get(tool)
            if btn and btn.isCheckable():
                btn.setChecked(True)
            elif tool == "none" and self.toolbar.btn_group.checkedButton():
                self.toolbar.btn_group.setExclusive(False)
                self.toolbar.btn_group.checkedButton().setChecked(False)
                self.toolbar.btn_group.setExclusive(True)

        if hasattr(self, "number_palette"):
            if tool == "badge":
                self._show_step_palette(near_cursor=True)
            else:
                self.number_palette.hide()

    def _handle_action(self, action: str):
        self._commit_active_text_editor()
        if action == "close":
            self.close()
        elif action == "undo" and self.draw_items:
            popped_item = self.draw_items.pop()
            self._forget_step_badge(popped_item)
            if popped_item == self.selected_item:
                self.selected_item = None
            self.update()
        elif action == "finish":
            self._copy_and_exit()
        elif action == "save":
            self._save_file_dialog()
        elif action == "pin":
            self._pin_to_screen()
        elif action == "ocr":
            self._run_ocr()

    def _run_ocr(self):
        self._commit_active_text_editor()
        if self.selected_rect.isEmpty():
            QToolTip.showText(QCursor.pos(), "请先框选要识别的文字区域")
            return
        if not HAS_OCR:
            QMessageBox.warning(
                self, "OCR 组件未安装",
                "未检测到 RapidOCR。\n如需使用离线 OCR 功能，请执行：\npip install rapidocr-onnxruntime"
            )
            return
        if self.controller.is_ocr_running():
            QToolTip.showText(QCursor.pos(), "正在进行 OCR 识别，请稍候...")
            return

        pixmap = self._render_ocr_pixmap()
        if pixmap.isNull():
            QToolTip.showText(QCursor.pos(), "截图区域为空，无法识别")
            return
        buffer = QByteArray()
        io_buffer = QBuffer(buffer)
        if not io_buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not pixmap.save(io_buffer, "PNG"):
            io_buffer.close()
            QMessageBox.warning(self, "OCR 失败", "无法准备待识别的截图区域。")
            return
        io_buffer.close()

        self.selected_item = None
        worker = OCRWorker(bytes(buffer.data()), self.controller)
        self._ocr_worker = worker
        worker.result_ready.connect(self._on_ocr_result)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        QToolTip.showText(QCursor.pos(), "正在后台识别文字，完成后将弹出核查窗口...")

    def _on_ocr_result(self, text: str, success: bool):
        self._ocr_worker = None
        result_text = text.strip()
        if success and result_text:
            dialog = OCRDialog(result_text, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                QToolTip.showText(QCursor.pos(), f"OCR 完成，已复制 {len(dialog.text_edit.toPlainText())} 个字符")
                self.close()
            return

        if text.startswith("OCR 引擎错误") or text.startswith("OCR 引擎初始化失败"):
            QMessageBox.warning(self, "OCR 识别失败", text)
        else:
            QMessageBox.information(self, "未识别到文字", "未能在选区内识别出文字，请调整选区后重试。")

    def _render_ocr_pixmap(self) -> QPixmap:
        r = self.selected_rect.normalized().intersected(self.rect())
        if r.isEmpty():
            return QPixmap()

        dpr = self.max_dpr
        phys_w = max(1, int(round(r.width() * dpr)))
        phys_h = max(1, int(round(r.height() * dpr)))
        cropped = QPixmap(phys_w, phys_h)
        cropped.setDevicePixelRatio(dpr)
        cropped.fill(Qt.GlobalColor.transparent)
        painter = QPainter(cropped)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(-r.topLeft(), self.full_pixmap)
        painter.end()
        return cropped

    def _render_final_snipped_pixmap(self) -> QPixmap:
        r = self.selected_rect.normalized().intersected(self.rect())
        if r.isEmpty():
            return QPixmap()

        dpr = self.max_dpr
        phys_w = max(1, int(round(r.width() * dpr)))
        phys_h = max(1, int(round(r.height() * dpr)))

        cropped = QPixmap(phys_w, phys_h)
        cropped.setDevicePixelRatio(dpr)
        cropped.fill(Qt.GlobalColor.transparent)

        painter = QPainter(cropped)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(-r.topLeft(), self.full_pixmap)

        painter.translate(-r.topLeft())
        for item in self.draw_items:
            item.paint(painter, self.base_image)

        painter.end()
        return cropped

    def _copy_and_exit(self):
        self._commit_active_text_editor()
        if self.selected_rect.isEmpty():
            self.close()
            return
        self.selected_item = None
        pixmap = self._render_final_snipped_pixmap()
        if not pixmap.isNull() and _config.get("auto_copy", True):
            QApplication.clipboard().setPixmap(pixmap)
        play_shutter_sound()
        self.close()

    def _pin_to_screen(self):
        self._commit_active_text_editor()
        if self.selected_rect.isEmpty():
            return
        self.selected_item = None
        snipped = self._render_final_snipped_pixmap()
        if snipped.isNull():
            return
        pinned = PinnedImageWidget(snipped)
        pinned.move(self.mapToGlobal(self.selected_rect.normalized().topLeft()))
        pinned.show()
        self.controller.register_pinned(pinned)
        self.close()

    def _save_file_dialog(self):
        self._commit_active_text_editor()
        if self.selected_rect.isEmpty():
            return
        self.selected_item = None
        last_dir = _config.get("last_save_dir", str(Path.home() / "Pictures"))
        pref_fmt = str(_config.get("save_format", "PNG")).upper()
        ext_map = {"PNG": "png", "JPEG": "jpg", "BMP": "bmp"}
        ext = ext_map.get(pref_fmt, "png")
        filter_map = {
            "PNG": "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp)",
            "JPEG": "JPEG (*.jpg *.jpeg);;PNG (*.png);;BMP (*.bmp)",
            "BMP": "BMP (*.bmp);;PNG (*.png);;JPEG (*.jpg *.jpeg)",
        }

        ts = time.strftime("%Y%m%d_%H%M%S")
        default_path = str(Path(last_dir) / f"{__app_name__}_{ts}.{ext}")
        fp, _ = QFileDialog.getSaveFileName(
            self,
            "保存截图",
            default_path,
            filter_map.get(pref_fmt, filter_map["PNG"])
        )
        if fp:
            try:
                pixmap = self._render_final_snipped_pixmap()
                if pixmap.isNull():
                    raise RuntimeError("生成的截图为空")
                lower_fp = fp.lower()
                if lower_fp.endswith((".jpg", ".jpeg")):
                    ok = pixmap.save(fp, "JPEG", _config.get("image_quality", 95))
                elif lower_fp.endswith(".bmp"):
                    ok = pixmap.save(fp, "BMP")
                else:
                    ok = pixmap.save(fp, "PNG")
                if not ok:
                    raise IOError("无法写入目标图像文件，请检查路径权限或磁盘空间")
                _config.set("last_save_dir", str(Path(fp).parent))
                play_shutter_sound()
                self.close()
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"无法保存文件:\n{str(e)}")

    def closeEvent(self, event):
        if self._ocr_worker and self._ocr_worker.isRunning():
            self._ocr_worker.cancel()
        super().closeEvent(event)

    def _get_handle_rects(self, r: QRect) -> list[tuple[int, QRect]]:
        if r.isEmpty():
            return []
        nr, sz, half = r.normalized(), 10, 5
        pts = [
            (0, nr.left(), nr.top()),
            (1, nr.center().x(), nr.top()),
            (2, nr.right(), nr.top()),
            (3, nr.right(), nr.center().y()),
            (4, nr.right(), nr.bottom()),
            (5, nr.center().x(), nr.bottom()),
            (6, nr.left(), nr.bottom()),
            (7, nr.left(), nr.center().y()),
        ]
        return [(idx, QRect(x - half, y - half, sz, sz)) for idx, x, y in pts]

    def _hit_test(self, pos: QPoint) -> int:
        if self.selected_rect.isEmpty():
            return -1
        for idx, rect in self._get_handle_rects(self.selected_rect):
            if rect.adjusted(-2, -2, 2, 2).contains(pos):
                return idx
        if self.selected_rect.normalized().contains(pos):
            return 8
        return -1

    @staticmethod
    def _cursor_for_handle(handle_id: int) -> Qt.CursorShape:
        if handle_id in (0, 4):
            return Qt.CursorShape.SizeFDiagCursor
        if handle_id in (2, 6):
            return Qt.CursorShape.SizeBDiagCursor
        if handle_id in (1, 5):
            return Qt.CursorShape.SizeVerCursor
        if handle_id in (3, 7):
            return Qt.CursorShape.SizeHorCursor
        if handle_id in (10, 11):
            return Qt.CursorShape.CrossCursor
        return Qt.CursorShape.SizeAllCursor

    def _update_cursor(self, pos: QPoint):
        if self.state in (self.STATE_IDLE, self.STATE_SELECTING):
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif self.state == self.STATE_RESIZING_ITEM:
            self.setCursor(self._cursor_for_handle(self.active_item_handle))
        elif self.state == self.STATE_MOVING_ITEM:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif self.state == self.STATE_SELECTED:
            if self.active_tool == "picker":
                self.setCursor(Qt.CursorShape.CrossCursor)
                return
            if self.selected_item:
                h_id = self.selected_item.hit_handle(QPointF(pos))
                if h_id != -1:
                    self.setCursor(self._cursor_for_handle(h_id))
                    return
            for item in reversed(self.draw_items):
                if item.contains(QPointF(pos)):
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                    return
            if self.active_tool != "none":
                self.setCursor(
                    Qt.CursorShape.IBeamCursor if self.active_tool == "text" else Qt.CursorShape.CrossCursor
                )
                return
            hit = self._hit_test(pos)
            if hit in (0, 1, 2, 3, 4, 5, 6, 7):
                self.setCursor(self._cursor_for_handle(hit))
            elif hit == 8:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)

    def contextMenuEvent(self, event):
        event.accept()

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
                    return

            if self.number_palette.isVisible() and self.number_palette.geometry().contains(pos):
                return super().mousePressEvent(event)

            if self.active_tool == "picker":
                rx = int(pos.x() * self.max_dpr)
                ry = int(pos.y() * self.max_dpr)
                img_w, img_h = self.base_image.width(), self.base_image.height()
                rx, ry = min(max(0, rx), img_w - 1), min(max(0, ry), img_h - 1)
                picked_color = self.base_image.pixelColor(rx, ry)
                hex_name = picked_color.name().upper()
                QApplication.clipboard().setText(hex_name)
                self.current_color = picked_color
                self.toolbar._set_color(hex_name)
                QToolTip.showText(QCursor.pos(), f"已复制颜色 {hex_name}")
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
                if self.selected_item:
                    item_h = self.selected_item.hit_handle(QPointF(pos))
                    if item_h != -1:
                        self.state = self.STATE_RESIZING_ITEM
                        self.active_item_handle = item_h
                        self._update_cursor(pos)
                        self.update()
                        event.accept()
                        return

                for item in reversed(self.draw_items):
                    if item.contains(QPointF(pos)):
                        self.selected_item = item
                        self._sync_toolbar_with_selected_item()
                        self.state = self.STATE_MOVING_ITEM
                        self.item_last_pos = pos
                        self.update()
                        event.accept()
                        return

                if self.selected_item is not None:
                    self.selected_item = None
                    self.update()

                hit = self._hit_test(pos)
                if hit != -1 and self.active_tool == "none":
                    if hit == 8:
                        self.state = self.STATE_MOVING
                        self.move_offset = pos - self.selected_rect.topLeft()
                        self.toolbar.hide()
                    else:
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
                        new_highlight = rect.intersected(self.rect())
                        break
                if new_highlight != self.highlighted_window:
                    if not self.highlighted_window.isEmpty():
                        update_region = update_region.united(self.highlighted_window.adjusted(-4, -4, 4, 4))
                    self.highlighted_window = new_highlight
                    if not self.highlighted_window.isEmpty():
                        update_region = update_region.united(self.highlighted_window.adjusted(-4, -4, 4, 4))

            if not update_region.isEmpty():
                self.update(update_region)

        elif self.state == self.STATE_SELECTING:
            self.selected_rect = QRect(self.start_pos, pos).normalized().intersected(self.rect())
            self.update()
        elif self.state == self.STATE_RESIZING:
            self._handle_resize(pos)
            self.update()
        elif self.state == self.STATE_MOVING:
            new_tl = pos - self.move_offset
            nx = max(0, min(new_tl.x(), self.width() - self.selected_rect.width()))
            ny = max(0, min(new_tl.y(), self.height() - self.selected_rect.height()))
            self.selected_rect.moveTopLeft(QPoint(nx, ny))
            self.update()
        elif self.state == self.STATE_MOVING_ITEM:
            delta = pos - self.item_last_pos
            if self.selected_item:
                self.selected_item.move_by(QPointF(delta))
            self.item_last_pos = pos
            self.update()
        elif self.state == self.STATE_RESIZING_ITEM:
            if self.selected_item and self.active_item_handle != -1:
                clamped_pt = QPointF(
                    max(float(self.selected_rect.left()), min(float(pos.x()), float(self.selected_rect.right()))),
                    max(float(self.selected_rect.top()), min(float(pos.y()), float(self.selected_rect.bottom())))
                )
                self.selected_item.resize_by_handle(self.active_item_handle, clamped_pt)
                self.update()
        elif self.state == self.STATE_EDITING:
            self._handle_drawing_move(pos)
            self.update()

        event.accept()

    def _handle_resize(self, pos: QPoint):
        clamped_pos = QPoint(max(0, min(pos.x(), self.width())), max(0, min(pos.y(), self.height())))
        r = self.selected_rect
        if self.active_handle == 0:
            r.setTopLeft(clamped_pos)
        elif self.active_handle == 1:
            r.setTop(clamped_pos.y())
        elif self.active_handle == 2:
            r.setTopRight(clamped_pos)
        elif self.active_handle == 3:
            r.setRight(clamped_pos.x())
        elif self.active_handle == 4:
            r.setBottomRight(clamped_pos)
        elif self.active_handle == 5:
            r.setBottom(clamped_pos.y())
        elif self.active_handle == 6:
            r.setBottomLeft(clamped_pos)
        elif self.active_handle == 7:
            r.setLeft(clamped_pos.x())
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
                elif self.active_tool != "none":
                    self._set_active_tool("none")
                    self.update()
                elif self.draw_items:
                    popped = self.draw_items.pop()
                    self._forget_step_badge(popped)
                    self.update()
                elif self.state == self.STATE_SELECTED:
                    self.selected_rect = QRect()
                    self.toolbar.hide()
                    self.number_palette.hide()
                    self.state = self.STATE_IDLE
                    self.update()
                else:
                    self.close()
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

            elif self.state in (self.STATE_MOVING_ITEM, self.STATE_RESIZING_ITEM):
                self.active_item_handle = -1
                self.state = self.STATE_SELECTED
                self._update_cursor(event.position().toPoint())
                self.update()

            elif self.state == self.STATE_EDITING:
                if self.current_drawing_item:
                    is_valid = True
                    if isinstance(self.current_drawing_item, (RectItem, CircleItem, MosaicItem)):
                        r = self.current_drawing_item.rect.normalized()
                        if r.width() < 3 and r.height() < 3:
                            is_valid = False
                    elif isinstance(self.current_drawing_item, (LineItem, ArrowItem)):
                        if math.hypot(
                            self.current_drawing_item.end.x() - self.current_drawing_item.start.x(),
                            self.current_drawing_item.end.y() - self.current_drawing_item.start.y()
                        ) < 3:
                            is_valid = False

                    if is_valid:
                        self.draw_items.append(self.current_drawing_item)
                        self.selected_item = self.current_drawing_item
                        self._sync_toolbar_with_selected_item()
                        if isinstance(self.current_drawing_item, StepBadgeItem):
                            self._step_history.append((self.current_drawing_item, self.step_counter))
                            self.step_counter = self.current_drawing_item.number + 1
                            self.number_palette.update_active_number(self.step_counter)
                    self.current_drawing_item = None
                self.state = self.STATE_SELECTED
                self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            for item in reversed(self.draw_items):
                if isinstance(item, TextItem) and item.contains(QPointF(pos)):
                    self._editing_original_item = item
                    self.draw_items.remove(item)
                    self.selected_item = None
                    self.update()
                    self._spawn_text_editor(item.pos.toPoint(), item.text, item.font, item.color)
                    event.accept()
                    return

            if self.state == self.STATE_SELECTED and self.selected_rect.contains(pos):
                self._copy_and_exit()

    def _spawn_text_editor(
        self,
        pos: QPoint,
        text: str = "",
        font: Optional[QFont] = None,
        color: Optional[QColor] = None
    ):
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
            new_item = TextItem(pos, text, font, color)
            self.draw_items.append(new_item)
            self.selected_item = new_item
        self._editing_original_item = None
        if self.active_text_editor:
            self.active_text_editor.deleteLater()
            self.active_text_editor = None
        self.update()

    def _on_text_widget_cancelled(self):
        if self._editing_original_item is not None:
            self.draw_items.append(self._editing_original_item)
            self.selected_item = self._editing_original_item
            self._editing_original_item = None
        if self.active_text_editor:
            self.active_text_editor.deleteLater()
            self.active_text_editor = None
        self.update()

    def _handle_drawing_press(self, pos: QPoint):
        w = self.current_width
        if self.active_tool == "rect":
            self.current_drawing_item = RectItem(QRectF(pos, pos), self.current_color, w, self.fill_enabled)
        elif self.active_tool == "circle":
            self.current_drawing_item = CircleItem(QRectF(pos, pos), self.current_color, w, self.fill_enabled)
        elif self.active_tool == "line":
            self.current_drawing_item = LineItem(QPointF(pos), QPointF(pos), self.current_color, w)
        elif self.active_tool == "arrow":
            self.current_drawing_item = ArrowItem(QPointF(pos), QPointF(pos), self.current_color, w)
        elif self.active_tool == "pencil":
            self.current_drawing_item = PencilItem([QPointF(pos)], self.current_color, w, False)
        elif self.active_tool == "marker":
            self.current_drawing_item = PencilItem([QPointF(pos)], self.current_color, w, True)
        elif self.active_tool == "badge":
            self.current_drawing_item = StepBadgeItem(QPointF(pos), self.step_counter, self.current_color)
        elif self.active_tool == "mosaic":
            block_sz = max(8, w * 3 + 3)
            self.current_drawing_item = MosaicItem(QRectF(pos, pos), block_sz)

    def _handle_drawing_move(self, pos: QPoint):
        if not self.current_drawing_item:
            return
        clamped_pos = QPointF(
            max(float(self.selected_rect.left()), min(float(pos.x()), float(self.selected_rect.right()))),
            max(float(self.selected_rect.top()), min(float(pos.y()), float(self.selected_rect.bottom())))
        )
        if isinstance(self.current_drawing_item, (RectItem, CircleItem, MosaicItem)):
            self.current_drawing_item.rect = QRectF(QPointF(self.start_pos), clamped_pos).normalized()
        elif isinstance(self.current_drawing_item, (ArrowItem, LineItem)):
            self.current_drawing_item.end = clamped_pos
        elif isinstance(self.current_drawing_item, PencilItem):
            if not self.current_drawing_item.points or math.hypot(
                clamped_pos.x() - self.current_drawing_item.points[-1].x(),
                clamped_pos.y() - self.current_drawing_item.points[-1].y()
            ) >= 1.5:
                self.current_drawing_item.points.append(clamped_pos)
        elif isinstance(self.current_drawing_item, StepBadgeItem):
            self.current_drawing_item.pos = clamped_pos

    def _position_toolbar(self):
        if self.selected_rect.isEmpty():
            self.toolbar.hide()
            return
        r = self.selected_rect.normalized()
        tb_size = self.toolbar.sizeHint()
        tb_w, tb_h = tb_size.width(), tb_size.height()
        tb_x = r.right() - tb_w
        tb_y = r.bottom() + 8
        if tb_y + tb_h > self.height() - 10:
            tb_y = r.top() - tb_h - 8
        if tb_y < 10:
            tb_y = r.bottom() - tb_h - 8
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
        if not target_rect.isEmpty():
            path.addRect(QRectF(target_rect))
        painter.fillPath(path, QColor(0, 0, 0, 115))

        if not target_rect.isEmpty():
            painter.save()
            painter.setClipRect(target_rect)
            for item in self.draw_items:
                item.paint(painter, self.base_image)
            if self.current_drawing_item:
                self.current_drawing_item.paint(painter, self.base_image)

            if self.selected_item and self.state in (
                self.STATE_SELECTED, self.STATE_MOVING_ITEM, self.STATE_RESIZING_ITEM
            ):
                if not isinstance(self.selected_item, (LineItem, ArrowItem)):
                    b_rect = self.selected_item.bounding_rect()
                    painter.setPen(QPen(QColor("#1a73e8"), 1.2, Qt.PenStyle.DashLine))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(b_rect)

                painter.setBrush(QBrush(Qt.GlobalColor.white))
                painter.setPen(QPen(QColor("#1a73e8"), 1.6))
                for h_id, h_rect in self.selected_item.get_handles():
                    if h_id in (10, 11):
                        painter.drawEllipse(h_rect)
                    else:
                        painter.drawRect(h_rect)
            painter.restore()

            painter.setPen(QPen(QColor("#1a73e8"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(target_rect)

            if self.state in (
                self.STATE_SELECTED, self.STATE_EDITING, self.STATE_MOVING_ITEM, self.STATE_RESIZING_ITEM
            ):
                painter.setBrush(QBrush(Qt.GlobalColor.white))
                painter.setPen(QPen(QColor("#1a73e8"), 1.5))
                for _, h_rect in self._get_handle_rects(target_rect):
                    painter.drawRect(h_rect)

            phys_w = int(round(target_rect.width() * self.max_dpr))
            phys_h = int(round(target_rect.height() * self.max_dpr))
            dim_str = f" {phys_w} × {phys_h} px "
            painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            fm = painter.fontMetrics()
            tw, th = fm.horizontalAdvance(dim_str) + 12, fm.height() + 6
            bx, by = target_rect.left(), target_rect.top() - th - 6
            if by < 5:
                by = target_rect.top() + 6

            badge_rect = QRectF(bx, by, tw, th)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(30, 41, 59, 225)))
            painter.drawRoundedRect(badge_rect, 4, 4)
            painter.setPen(QPen(Qt.GlobalColor.white))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, dim_str)

        if _config.get("show_magnifier", True) and (
            self.state in (self.STATE_IDLE, self.STATE_SELECTING) or self.active_tool == "picker"
        ):
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
                px = min(max(0, rx - half + gx), img_w - 1)
                py = min(max(0, ry - half + gy), img_h - 1)
                painter.fillRect(
                    hud_x + gx * grid_size,
                    hud_y + gy * 7,
                    grid_size,
                    7,
                    QBrush(self.base_image.pixelColor(px, py))
                )

        painter.setPen(QPen(QColor("#1a73e8"), 2))
        painter.drawRect(hud_x + half * grid_size, hud_y + half * 7, grid_size, 7)
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        painter.drawText(hud_x + 6, hud_y + 92, f"#{rgb.red():02X}{rgb.green():02X}{rgb.blue():02X}")
        painter.drawText(hud_x + 6, hud_y + 107, f"RGB:({rgb.red()},{rgb.green()},{rgb.blue()})")
        painter.drawText(hud_x + 6, hud_y + 122, f"POS: {rx}, {ry}")
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
                self._forget_step_badge(self.selected_item)
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
            elif self.active_tool != "none":
                self._set_active_tool("none")
                self.update()
            else:
                self.close()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not self.selected_rect.isEmpty():
                self._copy_and_exit()
        elif key == Qt.Key.Key_F1:
            if not self.help_dialog:
                self.help_dialog = ShortcutHelpDialog(self)
            self.help_dialog.move(self.rect().center() - self.help_dialog.rect().center())
            self.help_dialog.show()
        elif key == Qt.Key.Key_F and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._on_fill_toggled(not self.fill_enabled)
        elif key == Qt.Key.Key_C and event.modifiers() == (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            self._run_ocr()
        elif key == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self._set_active_tool("picker")
        elif key == Qt.Key.Key_F3:
            if not self.selected_rect.isEmpty():
                self._pin_to_screen()
        elif event.matches(QKeySequence.StandardKey.Undo):
            self._handle_action("undo")
        elif event.matches(QKeySequence.StandardKey.Save):
            self._save_file_dialog()
        elif key == Qt.Key.Key_R:
            self._set_active_tool("rect")
        elif key == Qt.Key.Key_O:
            self._set_active_tool("circle")
        elif key == Qt.Key.Key_L:
            self._set_active_tool("line")
        elif key == Qt.Key.Key_A:
            self._set_active_tool("arrow")
        elif key == Qt.Key.Key_P:
            self._set_active_tool("pencil")
        elif key == Qt.Key.Key_H:
            self._set_active_tool("marker")
        elif key == Qt.Key.Key_T:
            self._set_active_tool("text")
        elif key == Qt.Key.Key_B:
            self._set_active_tool("badge")
        elif key == Qt.Key.Key_M:
            self._set_active_tool("mosaic")
        elif key == Qt.Key.Key_1:
            self.toolbar._on_width_changed(2)
        elif key == Qt.Key.Key_2:
            self.toolbar._on_width_changed(3)
        elif key == Qt.Key.Key_3:
            self.toolbar._on_width_changed(5)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{__app_name__} - 设置")
        self.setMinimumSize(560, 480)

        self.setStyleSheet("""
            QDialog { background-color: #f8fafc; }
            QTabWidget::pane {
                border: 1px solid #dbe3ef;
                border-radius: 8px;
                background: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #475569;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #1a73e8;
                border-bottom: 2px solid #1a73e8;
            }
            QTabBar::tab:hover { background: #e8f0fe; }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 14px;
                font-weight: bold;
                color: #1e293b;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QLabel { color: #475569; font-size: 13px; }
            QCheckBox { color: #1e293b; font-size: 13px; spacing: 8px; }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #cbd5e1;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #1a73e8;
                border-color: #1a73e8;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTgiIGhlaWdodD0iMTgiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTkgMTYuMTdMNC44MyAxMmwtMS40MiAxLjQxTDkgMTkgMjEgN2wtMS40MS0xLjQxeiIgZmlsbD0id2hpdGUiLz4KPC9zdmc+);
            }
            QSlider::groove:horizontal {
                border: 1px solid #cbd5e1;
                height: 4px;
                background: #e2e8f0;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #1a73e8;
                border: 2px solid #1a73e8;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover { background: #1557b0; border-color: #1557b0; }
            QPushButton {
                background: #1a73e8;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                border: none;
                min-height: 20px;
            }
            QPushButton:hover { background: #1557b0; }
            QPushButton#Secondary {
                background: #ffffff;
                color: #334155;
                border: 1px solid #cbd5e1;
            }
            QPushButton#Secondary:hover { background: #f1f5f9; }
            QKeySequenceEdit, QSpinBox, QComboBox {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                color: #1e293b;
                min-height: 22px;
            }
            QKeySequenceEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #1a73e8; }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #1e293b;
                selection-background-color: #e8f0fe;
                selection-color: #1a73e8;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        tabs = QTabWidget()

        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        basic_layout.setSpacing(12)

        func_group = QGroupBox("截图与交互")
        func_layout = QVBoxLayout()
        func_layout.setSpacing(10)
        self.cb_sound = QCheckBox("启用快门声音反馈")
        self.cb_sound.setChecked(_config.get("enable_sound", True))
        self.cb_auto_copy = QCheckBox("完成截图时自动复制到剪贴板")
        self.cb_auto_copy.setChecked(_config.get("auto_copy", True))
        self.cb_magnifier = QCheckBox("取色与框选时显示坐标放大镜")
        self.cb_magnifier.setChecked(_config.get("show_magnifier", True))
        self.cb_detect_window = QCheckBox("鼠标移动时智能高亮窗口边界")
        self.cb_detect_window.setChecked(_config.get("auto_detect_window", True))
        for cb in (self.cb_sound, self.cb_auto_copy, self.cb_magnifier, self.cb_detect_window):
            func_layout.addWidget(cb)
        func_group.setLayout(func_layout)
        basic_layout.addWidget(func_group)

        sys_group = QGroupBox("系统与快捷键")
        sys_layout = QVBoxLayout()
        sys_layout.setSpacing(10)
        self.cb_autostart = QCheckBox("开机自动启动 QSnap")
        self.cb_autostart.setChecked(check_autostart_win())
        sys_layout.addWidget(self.cb_autostart)

        hk_row = QHBoxLayout()
        hk_row.addWidget(QLabel("全局截图快捷键:"))
        self.hotkey_edit = QKeySequenceEdit()
        self.hotkey_edit.setKeySequence(QKeySequence(_config.get("hotkey", "Ctrl+Alt+A")))
        hk_row.addWidget(self.hotkey_edit, 1)
        sys_layout.addLayout(hk_row)

        hk_hint = QLabel("提示：修改快捷键保存后立即生效（推荐 Ctrl+Alt+A 或 Ctrl+Shift+X）。")
        hk_hint.setStyleSheet("color: #64748b; font-size: 12px;")
        sys_layout.addWidget(hk_hint)
        sys_group.setLayout(sys_layout)
        basic_layout.addWidget(sys_group)
        basic_layout.addStretch()
        tabs.addTab(basic_tab, "常规与热键")

        output_tab = QWidget()
        output_layout = QVBoxLayout(output_tab)
        output_layout.setSpacing(12)

        quality_group = QGroupBox("图像输出与默认笔刷")
        quality_gl = QVBoxLayout()
        quality_gl.setSpacing(10)

        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("默认保存格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG", "BMP"])
        self.format_combo.setCurrentText(_config.get("save_format", "PNG"))
        format_layout.addWidget(self.format_combo)
        format_layout.addSpacing(24)
        format_layout.addWidget(QLabel("默认笔刷粗细:"))
        self.pen_width_spin = QSpinBox()
        self.pen_width_spin.setRange(1, 10)
        self.pen_width_spin.setValue(_config.get("pen_width", 3))
        format_layout.addWidget(self.pen_width_spin)
        format_layout.addStretch()
        quality_gl.addLayout(format_layout)

        quality_gl.addWidget(QLabel("JPEG 保存质量:"))
        quality_slider_layout = QHBoxLayout()
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(50, 100)
        self.quality_slider.setValue(_config.get("image_quality", 95))
        self.quality_value_label = QLabel(f"{self.quality_slider.value()}%")
        self.quality_slider.valueChanged.connect(lambda v: self.quality_value_label.setText(f"{v}%"))
        quality_slider_layout.addWidget(self.quality_slider)
        quality_slider_layout.addWidget(self.quality_value_label)
        quality_gl.addLayout(quality_slider_layout)
        quality_group.setLayout(quality_gl)
        output_layout.addWidget(quality_group)

        hdr_group = QGroupBox("HDR 色调映射")
        hdr_gl = QVBoxLayout()
        hdr_gl.setSpacing(10)
        self.cb_hdr_tone_mapping = QCheckBox("启用 HDR 色调映射（修复开启 HDR 后截图过曝或发灰）")
        self.cb_hdr_tone_mapping.setChecked(_config.get("hdr_tone_mapping", False))
        if not HAS_NUMPY:
            self.cb_hdr_tone_mapping.setEnabled(False)
            self.cb_hdr_tone_mapping.setText("启用 HDR 色调映射（需安装 numpy）")
        hdr_gl.addWidget(self.cb_hdr_tone_mapping)

        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("映射强度:"))
        self.tone_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.tone_strength_slider.setRange(0, 100)
        self.tone_strength_slider.setValue(int(_config.get("tone_mapping_strength", 0.85) * 100))
        self.tone_strength_slider.setEnabled(self.cb_hdr_tone_mapping.isChecked() and HAS_NUMPY)
        self.tone_strength_label = QLabel(f"{self.tone_strength_slider.value()}%")
        self.tone_strength_slider.valueChanged.connect(lambda v: self.tone_strength_label.setText(f"{v}%"))
        self.cb_hdr_tone_mapping.toggled.connect(self.tone_strength_slider.setEnabled)
        slider_layout.addWidget(self.tone_strength_slider)
        slider_layout.addWidget(self.tone_strength_label)
        hdr_gl.addLayout(slider_layout)
        hdr_group.setLayout(hdr_gl)
        output_layout.addWidget(hdr_group)
        output_layout.addStretch()
        tabs.addTab(output_tab, "图像与 HDR")

        about_tab = QWidget()
        about_layout = QVBoxLayout(about_tab)
        about_layout.setSpacing(16)
        about_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_content = QFrame()
        about_content.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #eff6ff, stop:1 #dbeafe);
                border-radius: 12px;
                padding: 24px;
            }
        """)
        about_cl = QVBoxLayout(about_content)
        about_cl.setSpacing(10)
        about_cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_title = QLabel(f"<h1 style='color:#1a73e8; margin:0;'>{__app_name__}</h1>")
        app_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_cl.addWidget(app_title)
        version_label = QLabel(f"<p style='font-size:14px; color:#475569;'><b>版本:</b> v{__version__}</p>")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_cl.addWidget(version_label)
        desc_label = QLabel(f"<p style='color:#1e293b;'>{__description__}</p>")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_cl.addWidget(desc_label)
        author_label = QLabel(f"<p style='color:#475569;'>作者: {__author__} | {__company__}</p>")
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_cl.addWidget(author_label)
        tech_label = QLabel(
            "<p style='color:#64748b; font-size:12px;'>"
            "基于 PySide6 (Qt6) 构建 · 原生支持多显示器混合高 DPI 缩放<br>"
            "支持已绘制图形拖拽控制点缩放长宽、封闭图形一键填充颜色<br>"
            "开源许可 · GPL-3.0 License</p>"
        )
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
        new_hotkey = self.hotkey_edit.keySequence().toString().strip()
        if not new_hotkey:
            QMessageBox.warning(self, "快捷键为空", "请设置有效的全局截图快捷键。")
            return
        if new_hotkey != _config.get("hotkey"):
            ok, msg = check_hotkey_conflict_win(new_hotkey)
            if not ok:
                QMessageBox.warning(self, "快捷键不可用", msg)
                return
            _config.set("hotkey", new_hotkey)

        _config.set("enable_sound", self.cb_sound.isChecked())
        _config.set("auto_copy", self.cb_auto_copy.isChecked())
        _config.set("show_magnifier", self.cb_magnifier.isChecked())
        _config.set("auto_detect_window", self.cb_detect_window.isChecked())
        _config.set("hdr_tone_mapping", self.cb_hdr_tone_mapping.isChecked())
        _config.set("tone_mapping_strength", self.tone_strength_slider.value() / 100.0)
        _config.set("save_format", self.format_combo.currentText())
        _config.set("image_quality", self.quality_slider.value())
        _config.set("pen_width", self.pen_width_spin.value())
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
            QApplication.processEvents()

        logger.info("Starting freeze-frame capture...")
        try:
            frozen_pixmap, max_dpr, virtual_rect = capture_full_desktop_instant()
            if frozen_pixmap.isNull():
                return

            if _config.get("hdr_tone_mapping", False):
                frozen_pixmap = apply_hdr_tone_mapping(
                    frozen_pixmap, _config.get("tone_mapping_strength", 0.85)
                )

            self.active_editor = FrozenFrameEditor(frozen_pixmap, max_dpr, virtual_rect, self)
            self.active_editor.destroyed.connect(lambda: setattr(self, "active_editor", None))
        except Exception as e:
            logger.error(f"Failed to start snipping: {e}")

    def register_pinned(self, widget: PinnedImageWidget):
        self.pinned_widgets.append(widget)
        widget.destroyed.connect(
            lambda: self.pinned_widgets.remove(widget) if widget in self.pinned_widgets else None
        )

    def is_ocr_running(self) -> bool:
        return any(worker.isRunning() for worker in self.findChildren(OCRWorker))

    def shutdown(self):
        if self.active_editor:
            try:
                self.active_editor.close()
            except RuntimeError:
                pass
            self.active_editor = None
        for pinned in list(self.pinned_widgets):
            try:
                pinned.close()
            except RuntimeError:
                pass
        self.pinned_widgets.clear()
        for worker in self.findChildren(OCRWorker):
            if worker.isRunning():
                worker.cancel()
                worker.wait(2000)


class NativeHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, hotkey_id: int, callback):
        super().__init__()
        self.hotkey_id = hotkey_id
        self.callback = callback

    def nativeEventFilter(self, eventType, message):
        if eventType in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == 0x0312 and msg.wParam == self.hotkey_id:
                    QTimer.singleShot(0, self.callback)
                    return True, 0
            except Exception as e:
                logger.debug(f"NativeHotkeyFilter error: {e}")
        return False, 0


class TrayApp(QObject):
    def __init__(self):
        super().__init__()
        self.controller = ScreenshotController()
        self.hotkey_id = 1
        self.hotkey_filter: Optional[NativeHotkeyFilter] = None
        self._hotkey_registered = False

        self.tray_icon = QSystemTrayIcon(get_logo_icon(32), QApplication.instance())
        self._update_tray_tooltip()

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background: #ffffff; border: 1px solid #dbe3ef; border-radius: 8px; padding: 4px; }
            QMenu::item { padding: 6px 20px; border-radius: 4px; color: #1e293b; }
            QMenu::item:selected { background: #e8f0fe; color: #1a73e8; }
        """)
        menu.addAction("开始截图").triggered.connect(self.controller.start_snipping)
        menu.addAction("设置...").triggered.connect(self.show_settings)
        menu.addAction("关于 QSnap").triggered.connect(self.show_about)
        menu.addSeparator()
        menu.addAction("退出").triggered.connect(QApplication.instance().quit)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
        self.register_hotkey()

    def _update_tray_tooltip(self):
        hk = _config.get("hotkey", "Ctrl+Alt+A")
        self.tray_icon.setToolTip(f"{__app_name__} v{__version__}\n截图快捷键：{hk}")

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.controller.start_snipping()

    def register_hotkey(self):
        if os.name != "nt":
            return
        self.unregister_hotkey()
        hotkey_str = _config.get("hotkey", "Ctrl+Alt+A")
        modifiers, vk = _parse_hotkey(hotkey_str)
        if vk == 0:
            logger.warning(f"Invalid hotkey format: {hotkey_str}")
            return
        user32 = ctypes.windll.user32
        if user32.RegisterHotKey(None, self.hotkey_id, modifiers, vk):
            self._hotkey_registered = True
            if not self.hotkey_filter:
                self.hotkey_filter = NativeHotkeyFilter(self.hotkey_id, self.controller.start_snipping)
                QApplication.instance().installNativeEventFilter(self.hotkey_filter)
            self._update_tray_tooltip()
            logger.info(f"Global hotkey registered: {hotkey_str}")
        else:
            logger.warning(f"Hotkey conflict: {hotkey_str} is already occupied.")
            self.tray_icon.showMessage(
                f"{__app_name__} 快捷键冲突",
                f"全局快捷键 {hotkey_str} 已被其他软件占用，请在托盘右键「设置」中更换。",
                QSystemTrayIcon.MessageIcon.Warning,
                3500
            )

    def unregister_hotkey(self):
        if os.name == "nt" and self._hotkey_registered:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, self.hotkey_id)
            except Exception as e:
                logger.debug(f"UnregisterHotKey failed: {e}")
            self._hotkey_registered = False

    def show_settings(self):
        self.unregister_hotkey()
        dialog = SettingsDialog()
        dialog.exec()
        self.register_hotkey()

    def show_about(self):
        dialog = QDialog()
        dialog.setWindowTitle(f"关于 {__app_name__}")
        dialog.setFixedSize(410, 290)
        dialog.setStyleSheet("background: #ffffff;")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(10)

        title_label = QLabel(
            f"<b><span style='font-size:28px; color:#1a73e8;'>{__app_name__}</span></b> "
            f"<span style='font-size:14px; color:#64748b;'>v{__version__}</span>"
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        desc = QLabel(f"<p style='color:#1e293b; font-size:13px; text-align:center;'>{__description__}</p>")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(line)

        footer = QLabel(
            f"<p style='color:#475569; font-size:12px; line-height: 1.55;'>"
            f"✓ 已绘图形支持拖动 8 控制点自由缩放长宽与调整端点<br>"
            f"✓ 封闭图形（矩形/椭圆）支持一键切换填充当前颜色 (F)<br>"
            f"✓ 原生适配多显示器混合高 DPI 缩放與窗口智能探测<br>"
            f"✓ 1–15 任意起始序号标注、零拷贝马赛克与离线 OCR 核查<br>"
            f"✓ 作者: {__author__} ({__company__})</p>"
        )
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        dialog.exec()


def main():
    mutex = None
    if os.name == "nt":
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, f"Global\\{__app_name__}_SingleInstance_Mutex")
        if ctypes.windll.kernel32.GetLastError() == 183:
            logger.warning("Another instance is already running. Exiting.")
            if mutex:
                ctypes.windll.kernel32.CloseHandle(mutex)
            sys.exit(0)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(__company__)
    app.setWindowIcon(get_logo_icon(64))

    tray_app: Optional[TrayApp] = None
    try:
        tray_app = TrayApp()
        app.aboutToQuit.connect(tray_app.unregister_hotkey)
        app.aboutToQuit.connect(tray_app.controller.shutdown)
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