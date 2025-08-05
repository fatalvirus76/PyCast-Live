import sys
import subprocess
import os
import threading
import random
import json
import socket
import http.server
import socketserver
from pathlib import Path
import time
import traceback
import re
from urllib.parse import urlparse, parse_qs
import mimetypes
import io

# --- Kontrollera och instruera om beroenden ---
try:
    import pychromecast
    from pychromecast.controllers.media import MediaStatus, MediaStatusListener
    from pychromecast.error import ChromecastConnectionError
    from pychromecast.discovery import stop_discovery
    from PIL import Image
    import requests
except ImportError:
    print("Fel: Ett eller flera nödvändiga bibliotek saknas.")
    print("Se till att du har aktiverat din virtuella miljö.")
    print("Kör sedan: pip install PyQt5 pychromecast yt-dlp \"protobuf==3.20.3\" Pillow requests")
    sys.exit(1)
except Exception as e:
    print("--- ETT KRITISKT FEL INTRÄFFADE VID UPPSTART ---")
    print(f"Det verkliga felet är: {type(e).__name__}: {e}")
    traceback.print_exc()
    sys.exit(1)

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QFileDialog, QListWidget, QLabel,
    QVBoxLayout, QHBoxLayout, QWidget, QSlider, QMessageBox, QComboBox,
    QInputDialog, QListWidgetItem, QDialog, QDialogButtonBox, QCheckBox, QSpinBox, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer, QObject, QRunnable, pyqtSignal, pyqtSlot, QThreadPool, QSize
from PyQt5.QtGui import QFont, QIcon

# --- Konfigurationsfiler och mappar ---
CONFIG_DIR = Path.home() / ".pycast_live"
THUMBNAIL_DIR = CONFIG_DIR / "thumbnails"
SUBTITLE_DIR = CONFIG_DIR / "subtitles"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
RESUME_FILE = CONFIG_DIR / "resume_points.json"

# --- Filtyper som stöds ---
VALID_MEDIA_EXT = ('.mp4', '.mkv', '.avi', '.mov', '.mp3', '.flac', '.m4a')
VALID_IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
ALL_SUPPORTED_EXT = VALID_MEDIA_EXT + VALID_IMAGE_EXT


# --- Teman (QSS) ---
THEMES = {
    "Ljust": """
        QWidget { background-color: #f0f0f0; color: #000000; font-size: 8pt; }
        QPushButton { background-color: #e0e0e0; border: 1px solid #c0c0c0; padding: 5px; border-radius: 3px; }
        QPushButton:hover { background-color: #d0d0d0; }
        QListWidget, QComboBox, QSpinBox, QLineEdit { background-color: #ffffff; border: 1px solid #c0c0c0; }
        QListWidget::item { padding: 5px; }
        QSlider::groove:horizontal { border: 1px solid #bbb; background: white; height: 8px; border-radius: 4px; }
        QSlider::handle:horizontal { background: #d0d0d0; border: 1px solid #a0a0a0; width: 14px; margin: -4px 0; border-radius: 7px; }
    """,
    "Mörkt": """
        QWidget { background-color: #2b2b2b; color: #ffffff; font-size: 8pt; }
        QListWidget, QComboBox, QLineEdit, QSpinBox { background-color: #3c3c3c; color: #ffffff; border: 1px solid #555; }
        QListWidget::item { padding: 5px; }
        QListWidget::item:selected { background-color: #555; }
        QPushButton { background-color: #555; color: #ffffff; border: 1px solid #777; padding: 5px; border-radius: 3px; }
        QPushButton:hover { background-color: #666; }
        QLabel { color: #ffffff; }
        QSlider::groove:horizontal { border: 1px solid #444; background: #3c3c3c; height: 8px; border-radius: 4px; }
        QSlider::handle:horizontal { background: #777; border: 1px solid #999; width: 14px; margin: -4px 0; border-radius: 7px; }
    """,
    "Synthwave": """
        QWidget { background-color: #261D4C; color: #F6019D; font-family: 'Lucida Console', 'Courier New', monospace; font-size: 8pt; }
        QPushButton, QComboBox, QSpinBox, QLineEdit { background-color: #1A1433; color: #00F6F7; border: 2px solid #F6019D; border-radius: 5px; padding: 5px; }
        QPushButton:hover { background-color: #F6019D; color: #1A1433; }
        QListWidget { background-color: #1A1433; color: #00F6F7; border: 2px solid #00F6F7; }
        QListWidget::item:selected { background-color: #F6019D; color: #261D4C; }
        QLabel { color: #F6019D; }
        QSlider::groove:horizontal { height: 10px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00F6F7, stop:1 #F6019D); border-radius: 5px; }
        QSlider::handle:horizontal { background: #FFFFFF; border: 1px solid #261D4C; width: 16px; margin: -4px 0; border-radius: 8px; }
    """,
    "Dracula": """
        QWidget { background-color: #282a36; color: #f8f8f2; font-size: 8pt; }
        QListWidget, QComboBox, QLineEdit, QSpinBox { background-color: #282a36; color: #f8f8f2; border: 1px solid #6272a4; selection-background-color: #44475a; }
        QListWidget::item { padding: 5px; }
        QListWidget::item:selected { background-color: #44475a; border: 1px solid #bd93f9; }
        QPushButton { background-color: #44475a; color: #f8f8f2; border: 1px solid #6272a4; padding: 5px; border-radius: 3px; }
        QPushButton:hover { background-color: #6272a4; }
        QLabel { color: #f8f8f2; }
        QSlider::groove:horizontal { border: 1px solid #6272a4; background: #44475a; height: 8px; border-radius: 4px; }
        QSlider::handle:horizontal { background: #bd93f9; border: 1px solid #f8f8f2; width: 14px; margin: -4px 0; border-radius: 7px; }
        QCheckBox::indicator { background-color: #44475a; border: 1px solid #6272a4; }
        QCheckBox::indicator:checked { background-color: #bd93f9; }
    """,
    "Matrix": """
        QWidget { background-color: #000000; color: #00FF00; font-family: 'Courier New', Courier, monospace; font-size: 8pt; }
        QPushButton, QComboBox, QListWidget, QSpinBox, QLineEdit { background-color: #0D0D0D; color: #00FF00; border: 1px solid #00FF00; }
        QListWidget::item:selected { background-color: #00FF00; color: #000000; }
        QPushButton:hover { background-color: #00FF00; color: #000000; }
        QLabel { color: #00FF00; }
        QSlider::groove:horizontal { border: 1px solid #00FF00; height: 4px; background: #0D0D0D; }
        QSlider::handle:horizontal { background: #00FF00; border: 1px solid #00AA00; width: 14px; margin: -6px 0; }
    """
}

class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit((type(e), e, traceback.format_exc()))
        finally:
            self.signals.finished.emit()

class StatusListener(MediaStatusListener):
    def __init__(self, main_window):
        self.main_window = main_window

    def new_media_status(self, status: MediaStatus):
        self.main_window.signals.media_status_update.emit(status)

    def load_media_failed(self, media_session_id, error_code):
        if error_code is not None:
            print(f"Media load failed: session {media_session_id}, error {error_code}")
            self.main_window.signals.media_load_error.emit("Laddningsfel", f"Kunde inte ladda media (felkod: {error_code}).")
        else:
            print(f"Ignorerar ofarligt laddningsfel (felkod: None), session: {media_session_id}")


class Communication(QObject):
    media_status_update = pyqtSignal(MediaStatus)
    remote_command = pyqtSignal(str, object)
    media_load_error = pyqtSignal(str, str)

class FormatSelectorDialog(QDialog):
    def __init__(self, formats, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Välj kvalitet")
        self.formats = formats
        self.selected_format = None
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        for fmt in self.formats:
            self.list_widget.addItem(fmt['label'])
        self.list_widget.setCurrentRow(0)
        self.list_widget.itemDoubleClicked.connect(self.accept)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        if self.list_widget.currentRow() >= 0:
            self.selected_format = self.formats[self.list_widget.currentRow()]
        super().accept()

class EQDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Equalizer")
        self.settings = settings
        layout = QVBoxLayout()
        self.sliders = {}
        for band in ["Bas", "Mellan", "Diskant"]:
            layout.addWidget(QLabel(band))
            slider = QSlider(Qt.Horizontal)
            slider.setRange(-10, 10)
            slider.setValue(self.settings.get(f"eq_{band.lower()}", 0))
            slider.setTickPosition(QSlider.TicksBelow)
            slider.setTickInterval(1)
            layout.addWidget(slider)
            self.sliders[band.lower()] = slider
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Reset).clicked.connect(self.reset_values)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def reset_values(self):
        for slider in self.sliders.values(): slider.setValue(0)

    def accept(self):
        for band, slider in self.sliders.items():
            self.settings[f"eq_{band}"] = slider.value()
        super().accept()

def get_thumbnail_path(media_id, url=None):
    thumb_path = THUMBNAIL_DIR / f"{media_id}.jpg"
    if thumb_path.exists(): return str(thumb_path)
    if url:
        try:
            response = requests.get(url, stream=True, timeout=10)
            if response.status_code == 200:
                with open(thumb_path, 'wb') as f:
                    for chunk in response.iter_content(1024): f.write(chunk)
                img = Image.open(thumb_path)
                img.thumbnail((128, 128))
                img.save(thumb_path)
                return str(thumb_path)
        except Exception as e: print(f"Kunde inte ladda ner miniatyrbild: {e}")
    return None

def get_info(media_source, is_url, cookies_path=None):
    info = {'is_error': True, 'error_message': 'Okänt fel'}
    try:
        if is_url:
            SUBTITLE_DIR.mkdir(exist_ok=True)
            cmd = ["yt-dlp", "-j", "--no-playlist", "--write-auto-sub", "--sub-lang", "sv", "--skip-download", "--output", f"{SUBTITLE_DIR}/%(id)s.%(ext)s"]
            if cookies_path and Path(cookies_path).exists():
                cmd.extend(["--cookies", cookies_path])
            cmd.append(media_source)
            
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            out, err = proc.communicate(timeout=60)
            if proc.returncode != 0:
                info['error_message'] = f"yt-dlp misslyckades:\n{err or out}"
                return info
            data = json.loads(out)
            sub_path = SUBTITLE_DIR / f"{data.get('id')}.sv.vtt"
            info = {
                'title': data.get('title', 'Okänd Titel'), 'length': data.get('duration', 0), 'is_error': False,
                'length_str': time.strftime('%H:%M:%S', time.gmtime(data.get('duration', 0))) if data.get('duration', 0) >= 3600 else time.strftime('%M:%S', time.gmtime(data.get('duration', 0))),
                'id': data.get('id'),
                'thumbnail_path': get_thumbnail_path(data.get('id'), data.get('thumbnail')),
                'subtitle_path': str(sub_path) if sub_path.exists() else None,
                'formats': [], 'type': 'web', 'media_type': 'video', 'original_url': media_source
            }
            for f in data.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    label = f.get('format_note', f.get('resolution', 'N/A'))
                    info['formats'].append({'label': label, 'url': f['url'], 'media_type': 'video'})
            for f in data.get('formats', []):
                if f.get('vcodec') == 'none' and f.get('acodec') != 'none': 
                    label = f"Endast ljud ({f.get('acodec')})"
                    info['formats'].append({'label': label, 'url': f['url'], 'media_type': 'audio'})
        else:
            p_media_source = Path(media_source)
            media_id = hex(hash(media_source) & 0xffffffff)[2:]
            thumb_path = THUMBNAIL_DIR / f"{media_id}.jpg"

            if p_media_source.suffix.lower() in VALID_IMAGE_EXT:
                if not thumb_path.exists():
                    try:
                        img = Image.open(media_source)
                        img.thumbnail((128, 128))
                        img.convert('RGB').save(thumb_path, "JPEG")
                    except Exception as e:
                        print(f"Kunde inte skapa miniatyrbild för {p_media_source.name}: {e}")
                        thumb_path = None
                
                info = {
                    'src': media_source, 'type': 'local', 'title': p_media_source.name, 
                    'length': 0, 'is_error': False, 'length_str': "Bild", 
                    'thumbnail_path': str(thumb_path) if thumb_path else None,
                    'media_type': 'image'
                }
                return info
            
            if not thumb_path.exists():
                subprocess.run(["ffmpeg", "-i", media_source, "-ss", "00:00:05", "-vframes", "1", str(thumb_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)

            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", media_source]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            out, _ = proc.communicate(timeout=15)
            data = json.loads(out)
            duration = float(data.get('format', {}).get('duration', 0))
            streams = data.get('streams', [])
            video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
            audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
            
            length_str_format = '%H:%M:%S' if duration >= 3600 else '%M:%S'

            info = {
                'src': media_source, 'type': 'local', 'title': Path(media_source).name, 'length': duration, 'is_error': False,
                'length_str': time.strftime(length_str_format, time.gmtime(duration)), 
                'thumbnail_path': str(thumb_path) if thumb_path.exists() else None,
                'media_type': 'audio' if not video_stream and audio_stream else 'video',
                'audio_codec': audio_stream.get('codec_name') if audio_stream else None
            }
    except Exception:
        info['error_message'] = f"Fel vid info-hämtning: {traceback.format_exc()}"
    return info

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ÄNDRING: Uppdaterad version och titel
        self.setWindowTitle("PyCast Live v4.9 (Snabbare & Filräknare)")
        self.setMinimumSize(800, 600)
        
        self.threadpool = QThreadPool()
        # ÄNDRING: Öka antalet trådar för att snabba på inläsning av många filer
        self.threadpool.setMaxThreadCount(20)
        
        self.ensure_config_dirs()
        default_settings = {
            'volume': 50, 'theme': 'Mörkt', 'eq_bas': 0, 'eq_mellan': 0, 'eq_diskant': 0, 
            'cookies_path': '', 'image_autoplay_duration': 10
        }
        self.settings = self.load_json(SETTINGS_FILE, default_settings)
        self.resume_points = self.load_json(RESUME_FILE, {})

        self.browser, self.cast_device, self.media_controller, self.status_listener = None, None, None, None
        self.last_player_state = None
        self.found_casts = []
        
        self.signals = Communication()
        self.signals.media_status_update.connect(self.update_media_status)
        self.signals.remote_command.connect(self.handle_remote_command)
        self.signals.media_load_error.connect(self.show_error_message)
        
        self.current_index, self.videos = -1, []
        self.is_playing, self.server_proc, self.remote_proc = False, None, None
        self.seek_lock, self.slider_is_pressed, self.total_secs = False, False, 0
        self.image_autoplay_timer = None

        self.init_ui()
        self.apply_theme()
        self.on_scan()

    def init_ui(self):
        self.setAcceptDrops(True)
        layout_main = QVBoxLayout()
        # --- Top row ---
        h_top = QHBoxLayout()
        h_top.addWidget(QLabel("Chromecast:"))
        self.device_combo, self.btn_scan = QComboBox(), QPushButton("Uppdatera")
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        self.btn_scan.clicked.connect(self.on_scan)
        h_top.addWidget(self.device_combo), h_top.addWidget(self.btn_scan), h_top.addStretch()
        self.btn_remote = QPushButton("Fjärrkontroll")
        self.btn_remote.clicked.connect(self.toggle_remote)
        h_top.addWidget(self.btn_remote)
        h_top.addWidget(QLabel("Tema:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.setCurrentText(self.settings.get('theme', 'Mörkt'))
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        h_top.addWidget(self.theme_combo)
        layout_main.addLayout(h_top)

        # Sökfält
        h_search = QHBoxLayout()
        h_search.addWidget(QLabel("Sök:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filtrera spellistan...")
        self.search_input.textChanged.connect(self.on_search_changed)
        h_search.addWidget(self.search_input)
        layout_main.addLayout(h_search)

        # --- Playlist ---
        self.playlist = QListWidget()
        self.playlist.setDragDropMode(QListWidget.InternalMove)
        self.playlist.itemDoubleClicked.connect(lambda item: self.cast_video(self.playlist.row(item)))
        self.playlist.model().rowsMoved.connect(self.on_playlist_reordered)
        self.playlist.itemSelectionChanged.connect(self.on_playlist_selection_changed)
        self.playlist.setIconSize(QSize(128, 72))
        layout_main.addWidget(self.playlist)
        # --- Add files buttons ---
        h_add = QHBoxLayout()
        buttons = [("Lägg till URL", self.on_add_url), ("Lägg till filer", self.on_add_file), ("Lägg till mapp", self.on_add_dir),
                   ("Spara lista", self.on_save_list), ("Ladda lista", self.on_load_list), ("Ställ in Cookies", self.on_set_cookies)]
        for text, cb in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(cb)
            h_add.addWidget(btn)
        layout_main.addLayout(h_add)
        # --- Playlist management buttons ---
        h_playlist_actions = QHBoxLayout()
        
        # ÄNDRING: Lade till en filräknare
        self.status_label = QLabel("0 filer laddade")
        h_playlist_actions.addWidget(self.status_label)
        
        h_playlist_actions.addStretch()
        self.btn_clear = QPushButton("Rensa")
        self.btn_clear.clicked.connect(self.on_clear_list)
        h_playlist_actions.addWidget(self.btn_clear)
        self.btn_remove = QPushButton("Ta bort")
        self.btn_remove.clicked.connect(self.on_remove_selected)
        h_playlist_actions.addWidget(self.btn_remove)
        self.btn_shuffle = QPushButton("Slumpa")
        self.btn_shuffle.clicked.connect(self.on_shuffle)
        h_playlist_actions.addWidget(self.btn_shuffle)
        layout_main.addLayout(h_playlist_actions)
        # --- Media controls ---
        h_control = QHBoxLayout()
        self.btn_play = QPushButton("▶️")
        self.btn_stop = QPushButton("⏹")
        
        ctrl_buttons = [("⏮", self.on_prev), (self.btn_play, self.on_play), ("⏸", self.on_pause), (self.btn_stop, self.on_stop), ("⏭", self.on_next)]
        for btn_data, cb in ctrl_buttons:
            btn = btn_data if isinstance(btn_data, QPushButton) else QPushButton(btn_data)
            btn.clicked.connect(cb)
            btn.setFixedWidth(40)
            h_control.addWidget(btn)

        self.btn_play_local = QPushButton("Spela Lokalt")
        self.btn_play_local.setToolTip("Spela den valda filen med datorns standardspelare")
        self.btn_play_local.clicked.connect(self.on_play_locally)
        h_control.addWidget(self.btn_play_local)
        h_control.addSpacing(10)

        btn_restart = QPushButton("🔄")
        btn_restart.setToolTip("Starta om castingen av den nuvarande filen")
        btn_restart.clicked.connect(self.on_restart_cast)
        btn_restart.setFixedWidth(40)
        h_control.addWidget(btn_restart)
        
        h_control.addWidget(QLabel("Volym:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.settings.get('volume', 50))
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.valueChanged.connect(self.set_volume)
        h_control.addWidget(self.volume_slider)
        
        self.btn_eq = QPushButton("EQ")
        self.btn_eq.clicked.connect(self.open_eq_dialog)
        h_control.addWidget(self.btn_eq)
        
        h_control.addSpacing(10)
        h_control.addWidget(QLabel("Rotation:"))
        self.rotation_combo = QComboBox()
        self.rotation_combo.addItems(["0°", "90°", "180°", "270°"])
        self.rotation_combo.setToolTip("Ange rotation för den valda filen.\nGäller vid nästa uppspelning.")
        self.rotation_combo.currentIndexChanged.connect(self.on_rotation_changed)
        h_control.addWidget(self.rotation_combo)
        
        h_control.addStretch()
        
        self.autoplay_checkbox = QCheckBox("Autoplay")
        self.autoplay_checkbox.setChecked(True)
        self.autoplay_checkbox.setToolTip("Spela nästa i kön automatiskt")
        h_control.addWidget(self.autoplay_checkbox)
        
        h_control.addWidget(QLabel("Bildtid (s):"))
        self.image_duration_spinbox = QSpinBox()
        self.image_duration_spinbox.setRange(1, 300)
        self.image_duration_spinbox.setValue(self.settings.get('image_autoplay_duration', 10))
        self.image_duration_spinbox.setToolTip("Visningstid i sekunder för varje bild vid autoplay.")
        self.image_duration_spinbox.valueChanged.connect(self.save_image_duration)
        h_control.addWidget(self.image_duration_spinbox)
        
        layout_main.addLayout(h_control)
        # --- Seek bar ---
        h_seek = QHBoxLayout()
        self.slider = QSlider(Qt.Horizontal)
        self.lbl_time = QLabel("--:-- / --:--")
        self.slider.sliderReleased.connect(self.on_slider_released)
        self.slider.sliderPressed.connect(self.on_slider_pressed)
        
        self.btn_jump_to_time = QPushButton("Hoppa till...")
        self.btn_jump_to_time.clicked.connect(self.on_jump_to_time)
        
        h_seek.addWidget(self.slider)
        h_seek.addWidget(self.lbl_time)
        h_seek.addWidget(self.btn_jump_to_time)
        layout_main.addLayout(h_seek)

        container = QWidget()
        container.setLayout(layout_main)
        self.setCentralWidget(container)

    # ÄNDRING: Ny metod för att uppdatera filräknaren
    def update_status_label(self):
        count = len(self.videos)
        text = "fil" if count == 1 else "filer"
        self.status_label.setText(f"{count} {text} laddade")

    def on_search_changed(self, text):
        search_term = text.lower()
        for i in range(self.playlist.count()):
            item = self.playlist.item(i)
            if search_term in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def on_rotation_changed(self, index):
        row = self.playlist.currentRow()
        if 0 <= row < len(self.videos):
            rotation_map = {0: 0, 1: 90, 2: 180, 3: 270}
            rotation = rotation_map.get(index, 0)
            self.videos[row]['rotation'] = rotation

    def on_playlist_selection_changed(self):
        row = self.playlist.currentRow()
        self.rotation_combo.blockSignals(True)
        if 0 <= row < len(self.videos):
            rotation = self.videos[row].get('rotation', 0)
            if rotation == 90: index = 1
            elif rotation == 180: index = 2
            elif rotation == 270: index = 3
            else: index = 0
            self.rotation_combo.setCurrentIndex(index)
            self.rotation_combo.setEnabled(True)
        else:
            self.rotation_combo.setCurrentIndex(0)
            self.rotation_combo.setEnabled(False)
        self.rotation_combo.blockSignals(False)

    def on_play_locally(self):
        row = self.playlist.currentRow()
        if row < 0:
            QMessageBox.information(self, "Inget valt", "Välj en fil i spellistan att spela upp lokalt.")
            return

        video_info = self.videos[row]
        if video_info.get('type') != 'local':
            QMessageBox.warning(self, "Fel mediatyp", "Denna funktion kan endast användas för lokala filer, inte webbadresser.")
            return

        filepath = video_info.get('src')
        if not filepath or not os.path.exists(filepath):
            QMessageBox.critical(self, "Fel", f"Filen kunde inte hittas:\n{filepath}")
            return

        try:
            if sys.platform == "win32":
                os.startfile(filepath)
            elif sys.platform == "darwin": # macOS
                subprocess.run(["open", filepath])
            else: # Linux
                subprocess.run(["xdg-open", filepath])
        except Exception as e:
            QMessageBox.critical(self, "Fel vid uppspelning", f"Kunde inte öppna filen med systemets standardspelare.\n\nFel: {e}")

    def save_image_duration(self, value):
        self.settings['image_autoplay_duration'] = value
    
    def cancel_image_timer(self):
        if self.image_autoplay_timer and self.image_autoplay_timer.isActive():
            self.image_autoplay_timer.stop()
        self.image_autoplay_timer = None

    def open_eq_dialog(self):
        dialog = EQDialog(self.settings, self)
        if dialog.exec_() == QDialog.Accepted:
            self.save_json(SETTINGS_FILE, self.settings)
            QMessageBox.information(self, "EQ Sparad", "Dina equalizer-inställningar har sparats.")

    def on_set_cookies(self):
        path, _ = QFileDialog.getOpenFileName(self, "Välj cookies-fil", "", "Textfiler (*.txt);;Alla filer (*)")
        if path:
            self.settings['cookies_path'] = path
            self.save_json(SETTINGS_FILE, self.settings)
            QMessageBox.information(self, "Cookies sparade", f"Sökvägen till din cookies-fil har sparats:\n{path}")

    def show_error_message(self, title, message):
        QTimer.singleShot(0, lambda: QMessageBox.critical(self, title, message))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        
        urls = event.mimeData().urls()
        local_files = [u.toLocalFile() for u in urls if u.isLocalFile()]
        web_links = [u.toString() for u in urls if not u.isLocalFile()]

        if local_files:
            valid_files = [f for f in local_files if f.lower().endswith(ALL_SUPPORTED_EXT)]
            if valid_files: self.add_files(valid_files)

        if web_links:
            for link in web_links: self.on_add_url(url=link)
    
    def add_files(self, filelist):
        for fn in filelist:
            if not any(fn == v.get('src') for v in self.videos):
                self.execute_in_background(get_info, fn, is_url=False, on_result=self.on_info_ready)

    def on_add_url(self, url=None):
        if not url:
            url, ok = QInputDialog.getText(self, "Lägg till URL", "Klistra in en länk:")
            if not (ok and url): return
        cookies_path = self.settings.get('cookies_path')
        self.execute_in_background(get_info, url, is_url=True, cookies_path=cookies_path, on_result=self.on_url_info_ready)
    
    def on_url_info_ready(self, info):
        if info.get('is_error'):
            QMessageBox.critical(self, "Fel", info.get('error_message', 'Okänt fel vid URL-hämtning.'))
            return
        if not info.get('formats'):
            QMessageBox.warning(self, "Inga format", "Kunde inte hitta några spelbara format för denna länk.")
            return
        dialog = FormatSelectorDialog(info['formats'], self)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_format:
            selected = dialog.selected_format
            info.update({'src': selected['url'], 'media_type': selected['media_type'],
                         'title': info['title'], 'original_url': info['original_url']})
            info['rotation'] = 0
            self.videos.append(info)
            self.add_item_to_playlist(info)

    def on_info_ready(self, info):
        if not info.get('is_error'):
            info['rotation'] = 0
            self.videos.append(info)
            self.add_item_to_playlist(info)

    def add_item_to_playlist(self, v):
        display_text = f"{v.get('title', 'Okänd Titel')}\n({v.get('length_str', '--:--')})"
        item = QListWidgetItem(display_text)
        if v.get('thumbnail_path') and Path(v['thumbnail_path']).exists():
            item.setIcon(QIcon(v['thumbnail_path']))
        self.playlist.addItem(item)
        # Apply current filter to new item
        self.on_search_changed(self.search_input.text())
        self.update_status_label() # ÄNDRING: Uppdatera räknaren


    def on_worker_error(self, error_tuple):
        print("Fel i bakgrundstråd:", error_tuple[2])
        QMessageBox.critical(self, "Fel i bakgrunden", f"Ett fel inträffade: {error_tuple[1]}")

    def execute_in_background(self, fn, *args, on_result, **kwargs):
        worker = Worker(fn, *args, **kwargs)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(self.on_worker_error)
        self.threadpool.start(worker)

    def on_scan(self):
        self.btn_scan.setText("Söker..."), self.btn_scan.setEnabled(False)
        worker = Worker(lambda: pychromecast.get_chromecasts(tries=1))
        worker.signals.result.connect(self.on_scan_finished)
        worker.signals.error.connect(self.on_worker_error)
        self.threadpool.start(worker)
        
    def on_scan_finished(self, result):
        casts, self.browser = result
        self.found_casts = sorted([c for c in casts if c.cast_type != 'group'], key=lambda c: c.name)
        self.update_device_list()
        self.btn_scan.setText("Uppdatera"), self.btn_scan.setEnabled(True)

    def update_device_list(self):
        self.device_combo.blockSignals(True)
        current_text = self.device_combo.currentText()
        self.device_combo.clear()
        
        if not self.found_casts:
             self.device_combo.blockSignals(False)
             self.on_device_changed(-1)
             return

        last_uuid = self.settings.get('last_used_device_uuid')
        last_idx = -1

        for i, cast in enumerate(self.found_casts):
            self.device_combo.addItem(cast.name, userData=str(cast.uuid))
            if str(cast.uuid) == last_uuid:
                last_idx = i
        
        if last_idx != -1:
            self.device_combo.setCurrentIndex(last_idx)
        elif self.device_combo.findText(current_text) != -1:
             self.device_combo.setCurrentText(current_text)
        elif self.found_casts:
            self.device_combo.setCurrentIndex(0)

        self.device_combo.blockSignals(False)
        self.on_device_changed(self.device_combo.currentIndex())

    def on_device_changed(self, idx):
        if not (0 <= idx < len(self.found_casts)):
            if self.cast_device:
                threading.Thread(target=self.cast_device.disconnect, daemon=True).start()
            self.cast_device = None
            self.media_controller = None
            return

        selected_device = self.found_casts[idx]

        if self.cast_device and self.cast_device.uuid == selected_device.uuid:
            return

        if self.cast_device:
            threading.Thread(target=self.cast_device.disconnect, daemon=True).start()

        self.cast_device = selected_device
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.cast_device.wait()
            self.media_controller = self.cast_device.media_controller
            
            if not self.status_listener:
                self.status_listener = StatusListener(self)
            
            self.media_controller.register_status_listener(self.status_listener)
            self.settings['last_used_device_uuid'] = str(self.cast_device.uuid)
        except Exception as e:
            QMessageBox.critical(self, "Anslutningsfel", f"Kunde inte ansluta: {e}")
            self.cast_device = None
            self.media_controller = None
        finally:
            QApplication.restoreOverrideCursor()

    def cast_video(self, index, start_time=0):
        if not self.cast_device or not self.cast_device.socket_client.is_connected:
            self.show_error_message("Ingen Chromecast", "Välj en Chromecast först.")
            return
        if not (0 <= index < len(self.videos)): return
        
        self.cancel_image_timer()
        if self.server_proc: 
            try:
                self.server_proc.shutdown()
                self.server_proc.server_close()
            except Exception: pass
            self.server_proc = None
        
        self.current_index = index
        v = self.videos[index]
        self.total_secs = v.get('length', 0)

        media_url = self.start_local_stream(v, start_time)
        
        media_type = 'video/mp4'
        if v.get('media_type') == 'image':
            img_path = Path(v['src'])
            media_type, _ = mimetypes.guess_type(img_path.name)
            if not media_type: media_type = 'image/jpeg'
            
            self.slider.setEnabled(False)
            self.slider.setValue(0)
            self.lbl_time.setText("Bildvisning")
        elif v.get('media_type') == 'audio':
            media_type = 'audio/aac'
            self.slider.setEnabled(True)
            self.slider.setRange(0, int(self.total_secs))
        else: # video
            self.slider.setEnabled(True)
            self.slider.setRange(0, int(self.total_secs))

        self.media_controller.play_media(media_url, media_type, title=v.get('title'), current_time=start_time)
        self.is_playing = True
        self.playlist.setCurrentRow(index)
        self.slider.setValue(int(start_time))


        if v.get('media_type') == 'image' and self.autoplay_checkbox.isChecked():
            duration_ms = self.settings.get('image_autoplay_duration', 10) * 1000
            self.image_autoplay_timer = QTimer()
            self.image_autoplay_timer.setSingleShot(True)
            self.image_autoplay_timer.timeout.connect(self.on_next)
            self.image_autoplay_timer.start(duration_ms)

    def start_local_stream(self, media_data, start_time=0):
        if self.server_proc: 
            try:
                self.server_proc.shutdown()
                self.server_proc.server_close()
            except Exception as e:
                print(f"Fel vid nedstängning av server: {e}")
        
        handler = self.create_handler(media_data, start_time)
        self.server_proc = ThreadedTCPServer(("", 0), handler)
        port = self.server_proc.server_address[1]
        
        server_thread = threading.Thread(target=self.server_proc.serve_forever, daemon=True)
        server_thread.start()
        
        return f"http://{self.detect_local_ip()}:{port}/stream"

    def update_media_status(self, status: MediaStatus):
        if not status: return

        current_item_is_image = False
        if 0 <= self.current_index < len(self.videos):
            current_item = self.videos[self.current_index]
            current_item_is_image = current_item.get('media_type') == 'image'
        
        if self.seek_lock and status.player_state == "PLAYING":
             self.seek_lock = False

        if not self.slider_is_pressed and not self.seek_lock and not current_item_is_image:
            self.slider.setValue(int(status.current_time))
            if self.total_secs > 0:
                time_format = '%H:%M:%S' if self.total_secs >= 3600 else '%M:%S'
                current_time_str = time.strftime(time_format, time.gmtime(status.current_time))
                total_time_str = time.strftime(time_format, time.gmtime(self.total_secs))
                self.lbl_time.setText(f"{current_time_str} / {total_time_str}")
        
        new_player_state = status.player_state
        if self.is_playing and self.last_player_state in ['PLAYING', 'BUFFERING'] and new_player_state == 'IDLE':
            if status.idle_reason == 'FINISHED':
                 if not current_item_is_image and self.autoplay_checkbox.isChecked():
                     QTimer.singleShot(1000, self.on_next)
                 else:
                     self.is_playing = False
        
        self.last_player_state = new_player_state

    def on_play(self):
        if self.current_index < 0 and self.videos: self.cast_video(0)
        elif self.media_controller: self.media_controller.play()

    def on_pause(self):
        self.cancel_image_timer()
        if self.media_controller: self.media_controller.pause()
            
    def on_stop(self, clear_ui=True):
        self.cancel_image_timer()
        if self.server_proc: 
            try:
                self.server_proc.shutdown()
                self.server_proc.server_close()
            except Exception: pass
            self.server_proc = None

        if self.media_controller and self.media_controller.is_active: self.media_controller.stop()
        self.is_playing = False
        if clear_ui:
            self.slider.setEnabled(True)
            self.slider.setValue(0)
            self.lbl_time.setText("--:-- / --:--")
            self.current_index = -1
            self.playlist.setCurrentRow(-1)
            
    def on_next(self):
        if self.current_index < len(self.videos) - 1: self.cast_video(self.current_index + 1)
        else: self.on_stop()

    def on_prev(self):
        if self.current_index > 0: self.cast_video(self.current_index - 1)
            
    def seek_to(self, seconds):
        if self.is_playing and self.media_controller and self.total_secs > 0:
            seconds = max(0, min(int(self.total_secs), seconds))
            self.seek_lock = True
            self.cast_video(self.current_index, start_time=seconds)
        
    def on_slider_pressed(self): 
        self.slider_is_pressed = True

    def on_slider_released(self):
        self.slider_is_pressed = False
        self.seek_to(self.slider.value())
    
    def on_jump_to_time(self):
        if not self.is_playing or self.total_secs <= 0:
            QMessageBox.information(self, "Information", "Spela upp media för att kunna hoppa i tiden.")
            return

        text, ok = QInputDialog.getText(self, 'Hoppa till tid', 'Ange tid (t.ex. 1:23 eller 45 sekunder):')
        if ok and text:
            parts = str(text).strip().split(':')
            seconds = 0
            try:
                if len(parts) == 1:
                    seconds = int(parts[0])
                elif len(parts) == 2:
                    seconds = int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                else:
                    raise ValueError("Ogiltigt tidsformat")

                if 0 <= seconds <= self.total_secs:
                    self.seek_to(seconds)
                else:
                    raise ValueError("Tiden är utanför mediats längd")

            except (ValueError, IndexError):
                QMessageBox.warning(self, 'Felaktigt format', 'Ange tiden i ett giltigt format (HH:MM:SS, MM:SS, eller sekunder) och inom videons längd.')
        
    def set_volume(self, value):
        if self.cast_device and self.cast_device.socket_client.is_connected:
            self.cast_device.set_volume(value / 100.0)
        self.settings['volume'] = value

    def repopulate_playlist(self):
        current_sel = self.playlist.currentRow()
        try:
            self.playlist.model().rowsMoved.disconnect(self.on_playlist_reordered)
        except TypeError:
            pass
        self.playlist.clear()
        for v in self.videos:
            self.add_item_to_playlist(v)
        if 0 <= current_sel < self.playlist.count(): self.playlist.setCurrentRow(current_sel)
        self.playlist.model().rowsMoved.connect(self.on_playlist_reordered)
        self.on_search_changed(self.search_input.text())


    def on_playlist_reordered(self, parent, start, end, dest, row):
        if start == row: return
        moved_item = self.videos.pop(start)
        self.videos.insert(row, moved_item)
        if self.current_index == start: self.current_index = row
        elif start < self.current_index and row >= self.current_index: self.current_index -= 1
        elif start > self.current_index and row <= self.current_index: self.current_index += 1

    def ensure_config_dirs(self):
        for d in [CONFIG_DIR, THUMBNAIL_DIR, SUBTITLE_DIR]: d.mkdir(exist_ok=True)

    def save_json(self, fp, data):
        try:
            with open(fp, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
        except Exception as e: print(f"Kunde inte spara JSON: {e}")

    def load_json(self, fp, default):
        try:
            with open(fp, 'r', encoding='utf-8') as f: return json.load(f)
        except (IOError, json.JSONDecodeError): return default

    def apply_theme(self):
        theme_name = self.theme_combo.currentText()
        self.setStyleSheet(THEMES.get(theme_name, ""))
        self.btn_play.setStyleSheet("background-color: #4CAF50; color: white;")
        self.btn_stop.setStyleSheet("background-color: #f44336; color: white;")
        self.settings['theme'] = theme_name

    def detect_local_ip(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception: return "127.0.0.1"

    def create_handler(self, media_data, start_time=0):
        main_window_ref = self

        class MediaStreamHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if media_data.get('media_type') == 'image':
                    self.serve_image()
                else:
                    self.serve_transcoded_media()

            def serve_image(self):
                try:
                    filepath = media_data['src']
                    rotation = media_data.get('rotation', 0)
                    
                    with Image.open(filepath) as img:
                        if rotation != 0:
                            img = img.rotate(-rotation, expand=True)

                        buffer = io.BytesIO()
                        img_format_str = Path(filepath).suffix.lower()
                        pil_format = Image.registered_extensions().get(img_format_str, 'JPEG').upper()
                        
                        if (pil_format in ['PNG', 'WEBP']) or (img.mode in ('RGBA', 'P')):
                             pil_format = 'PNG'

                        img.save(buffer, format=pil_format)
                        buffer.seek(0)
                        img_bytes = buffer.read()

                    content_type, _ = mimetypes.guess_type(f"dummy.{pil_format.lower()}")
                    self.send_response(200)
                    self.send_header('Content-Type', content_type or 'application/octet-stream')
                    self.send_header('Content-Length', len(img_bytes))
                    self.end_headers()
                    self.wfile.write(img_bytes)

                except FileNotFoundError:
                    self.send_error(404, "File Not Found")
                except Exception as e:
                    print(f"Fel vid servering av roterad bild: {e}")
                    traceback.print_exc()
                    self.send_error(500, "Server Error")

            def serve_transcoded_media(self):
                self.send_response(200)
                media_type = 'audio/aac' if media_data.get('media_type') == 'audio' else 'video/mp4'
                self.send_header('Content-Type', media_type)
                self.end_headers()
                
                args = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
                if start_time > 0.5:
                    args.extend(["-ss", str(start_time)])
                
                args.extend(["-i", media_data['src']])

                vf, af = [], []

                rotation = media_data.get('rotation', 0)
                if media_data.get('media_type') != 'audio' and rotation != 0:
                    if rotation == 90:
                        vf.append("transpose=1")
                    elif rotation == 180:
                        vf.append("transpose=2,transpose=2")
                    elif rotation == 270:
                        vf.append("transpose=2")

                if media_data.get('subtitle_path'):
                    subtitle_path = media_data['subtitle_path'].replace('\\', '/')
                    if sys.platform == "win32":
                         subtitle_path = re.sub(r'([A-Za-z]):\\', r'/mnt/\1/', subtitle_path).replace('\\', '/')
                    subtitle_path = subtitle_path.replace(':', '\\:')
                    vf.append(f"subtitles='{subtitle_path}'")

                eq_bands = [f"equalizer=f={f}:width_type=h:width={w}:g={main_window_ref.settings.get(f'eq_{b}', 0)}"
                            for f, w, b in [(64, 50, 'bas'), (1000, 200, 'mellan'), (10000, 2000, 'diskant')]]
                if any(v != 0 for v in [main_window_ref.settings.get(f'eq_{b}', 0) for b in ['bas', 'mellan', 'diskant']]):
                    af.append(','.join(eq_bands))

                if vf: args.extend(["-vf", ",".join(vf)])
                if af: args.extend(["-af", ",".join(af)])

                if media_data.get('media_type') == 'audio':
                    if media_data.get('audio_codec') in ['aac', 'mp3'] and not af:
                        args.extend(["-c:a", "copy"])
                    else:
                        args.extend(["-c:a", "aac", "-ac", "2"])
                    args.extend(["-f", "adts"])
                else: # video
                    args.extend(["-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency", 
                                 "-c:a", "aac", "-ac", "2", "-f", "mp4", 
                                 "-movflags", "frag_keyframe+empty_moov"])
                args.append("pipe:1")
                
                proc = None
                try:
                    proc = subprocess.Popen(args, stdout=self.wfile, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                    _, stderr_data = proc.communicate()
                    
                    if proc.returncode != 0:
                        err_text = stderr_data.decode('utf-8', 'ignore')
                        if 'Connection reset by peer' not in err_text and 'Broken pipe' not in err_text:
                            print(f"FFmpeg-fel:\n{err_text}")

                except BrokenPipeError:
                    print("Anslutningen stängdes av klienten (förväntat beteende).")
                except Exception as e:
                    print(f"Oväntat fel i mediastream-hanteraren: {e}")
                finally:
                    if proc and proc.poll() is None:
                        proc.kill()
                        proc.wait()

            def log_message(self, format, *args): return
        
        return MediaStreamHandler
        
    def closeEvent(self, e):
        self.save_json(SETTINGS_FILE, self.settings)
        self.save_json(RESUME_FILE, self.resume_points)
        self.on_stop(clear_ui=False)
        if self.browser:
            try: stop_discovery(self.browser)
            except Exception as ex: print(f"Fel vid stopp av discovery: {ex}")
        if self.cast_device: self.cast_device.disconnect()
        self.toggle_remote(force_off=True)
        e.accept()

    def on_remove_selected(self):
        items_to_remove = self.playlist.selectedItems()
        if not items_to_remove:
            row = self.playlist.currentRow()
            if row >= 0:
                items_to_remove = [self.playlist.item(row)]
            else:
                return

        rows_to_remove = sorted([self.playlist.row(item) for item in items_to_remove], reverse=True)

        for row in rows_to_remove:
            if row < 0: continue
            if row == self.current_index: self.on_stop()
            
            self.playlist.takeItem(row) 
            self.videos.pop(row)

            if self.current_index > row: self.current_index -= 1
            elif self.current_index == row: self.current_index = -1
        
        self.on_playlist_selection_changed()
        self.update_status_label() # ÄNDRING: Uppdatera räknaren

    def on_shuffle(self):
        if not self.videos: return
        current_item = self.videos[self.current_index] if self.current_index >= 0 else None
        random.shuffle(self.videos)
        if current_item:
            try: self.current_index = self.videos.index(current_item)
            except ValueError: self.current_index = -1
        self.repopulate_playlist()

    def on_clear_list(self):
        self.on_stop()
        self.videos.clear()
        self.playlist.clear()
        self.on_playlist_selection_changed()
        self.update_status_label() # ÄNDRING: Uppdatera räknaren

    def on_add_file(self):
        file_filter = f"Alla mediafiler ({' '.join(['*'+e for e in ALL_SUPPORTED_EXT])});;Alla filer (*.*)"
        fns, _ = QFileDialog.getOpenFileNames(self, "Välj filer", "", file_filter)
        if fns: self.add_files(fns)

    def on_add_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Välj mapp")
        if path:
            all_files = [str(f) for ext in ALL_SUPPORTED_EXT for f in Path(path).rglob(f"*{ext}")]
            self.add_files(all_files)

    def on_save_list(self):
        path, _ = QFileDialog.getSaveFileName(self, "Spara spellista", "", "JSON-filer (*.json)")
        if not path: return
        
        save_data = []
        for v in self.videos:
            item_data = {}
            if v.get('type') == 'local':
                item_data = {'type': 'local', 'src': v['src']}
            elif v.get('type') == 'web':
                item_data = {'type': 'web', 'src': v['original_url']}
            
            if 'rotation' in v:
                item_data['rotation'] = v['rotation']
            save_data.append(item_data)
        
        self.save_json(path, save_data)
        QMessageBox.information(self, "Sparat", "Spellistan har sparats.")

    def on_load_list(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ladda spellista", "", "JSON-filer (*.json)")
        if not path: return
        
        self.on_clear_list()
        loaded_data = self.load_json(path, [])
        for item in loaded_data:
            if item.get('type') == 'local':
                self.add_files([item['src']]) 
            elif item.get('type') == 'web':
                self.on_add_url(url=item['src'])

    def on_restart_cast(self):
        if self.current_index >= 0: self.cast_video(self.current_index)

    def handle_remote_command(self, command, value):
        if command == "play": self.on_play()
        elif command == "pause": self.on_pause()
        elif command == "next": self.on_next()
        elif command == "prev": self.on_prev()
        elif command == "volume": self.volume_slider.setValue(int(value))

    def toggle_remote(self, force_off=False):
        if self.remote_proc and (force_off or (hasattr(self.remote_proc, 'is_running') and self.remote_proc.is_running)):
            try:
                self.remote_proc.shutdown()
                self.remote_proc.server_close()
            except Exception: pass
            self.remote_proc = None
            self.btn_remote.setText("Fjärrkontroll")
            print("Webb-fjärrkontroll stoppad.")
            return
        
        if force_off: return

        port = 8080
        ip = self.detect_local_ip()
        handler_class = self.create_remote_handler()
        
        try:
            self.remote_proc = ThreadedTCPServer(("", port), handler_class)
            self.remote_proc.is_running = True
            threading.Thread(target=self.remote_proc.serve_forever, daemon=True).start()
            self.btn_remote.setText(f"Stoppa Fjärr")
            QMessageBox.information(self, "Fjärrkontroll Aktiv", f"Öppna följande adress i din webbläsare:\n\nhttp://{ip}:{port}")
            print(f"Webb-fjärrkontroll startad på http://{ip}:{port}")
        except OSError as e:
            QMessageBox.critical(self, "Fel", f"Kunde inte starta fjärrkontrollen på port {port}.\nPorten kan vara upptagen.\nFel: {e}")
            self.remote_proc = None

    def create_remote_handler(self):
        main_window_ref = self
        class RemoteControlHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/": self.send_html()
                else: self.send_command()
            
            def send_html(self):
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                html = """
                <!DOCTYPE html><html><head><title>PyCast Fjärrkontroll</title>
                <meta charset="UTF-8"><meta name=viewport content="width=device-width, initial-scale=1">
                <style>
                    body { font-family: sans-serif; background: #2b2b2b; color: white; text-align: center; }
                    .container { max-width: 400px; margin: auto; padding: 20px; }
                    button { font-size: 2em; width: 100px; height: 100px; margin: 10px; border-radius: 50%; border: 2px solid #555; background: #3c3c3c; color: white; }
                    #vol-slider { width: 80%; }
                </style></head><body><div class=container>
                    <h1>PyCast Fjärrkontroll</h1>
                    <div>
                        <button onclick="cmd('prev')">⏮</button>
                        <button onclick="cmd('play')">▶</button>
                        <button onclick="cmd('pause')">⏸</button>
                        <button onclick="cmd('next')">⏭</button>
                    </div>
                    <h2>Volym</h2>
                    <input type=range min=0 max=100 value=50 id=vol-slider onchange="cmd('volume', this.value)">
                </div><script>
                    function cmd(c, v) { fetch(`/${c}?val=${v||''}`); }
                </script></body></html>
                """
                self.wfile.write(html.encode('utf-8'))

            def send_command(self):
                parsed_path = urlparse(self.path)
                command = parsed_path.path.strip('/')
                params = parse_qs(parsed_path.query)
                value = params.get('val', [None])[0]
                if command in ["play", "pause", "next", "prev", "volume"]:
                    main_window_ref.signals.remote_command.emit(command, value)
                    self.send_response(200)
                else:
                    self.send_response(404)
                self.end_headers()
        return RemoteControlHandler

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == '__main__':
    if sys.platform == 'win32':
         QApplication.setAttribute(Qt.AA_EnableHighDpiScaling), QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    font = QFont()
    font.setPointSize(9)
    app.setFont(font)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
