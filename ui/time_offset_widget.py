# ui/time_offset_widget.py

from PyQt5.QtWidgets import (
    QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QSizePolicy, QFrame, QSplitter, QDialog
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QUrl, QTimer
from PyQt5.QtWebEngineWidgets import QWebEngineView

from PIL import Image
import io
from datetime import timedelta
import os


class TimeOffsetWidget(QDialog):
    def __init__(self, camera_model, image_path, exif_time, gpx_points, find_closest_point_callback, parent=None):
        super().__init__(parent)
        self.camera_model = camera_model
        self.original_image_path = image_path
        self.image_path = image_path
        self.exif_time = exif_time
        self.gpx_points = gpx_points
        self.offset = timedelta()
        self.find_closest_point = find_closest_point_callback

        self.setWindowTitle(f"Zeitversatz für: {camera_model}")
        self.resize(1200, 700)

        # 📷 Bildvorschau
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFrameShape(QFrame.Box)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 🌍 Karte
        self.map_view = QWebEngineView()
        self.map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "map_template.html"))
        self.map_view.load(QUrl.fromLocalFile(html_path))

        # 📷 + 🌍 nebeneinander
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.image_label)
        splitter.addWidget(self.map_view)
        splitter.setSizes([600, 600])  # Startverteilung

        # 📅 Zeit/Koord Anzeige
        self.time_label = QLabel()
        self.gps_label = QLabel()
        self.gps_label.setStyleSheet("font-weight: bold; color: green;")

        # 🕐 Steuerbuttons
        self.minus_btn = QPushButton("−1h")
        self.plus_btn = QPushButton("+1h")
        self.change_img_btn = QPushButton("Anderes Bild wählen")
        self.confirm_btn = QPushButton("Bestätigen")

        self.minus_btn.clicked.connect(self.decrease_offset)
        self.plus_btn.clicked.connect(self.increase_offset)
        self.change_img_btn.clicked.connect(self.select_new_image)
        self.confirm_btn.clicked.connect(self.accept)  # ersetzt confirm_callback

        # 📐 Layouts
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.minus_btn)
        controls_layout.addWidget(self.plus_btn)
        controls_layout.addWidget(self.change_img_btn)
        controls_layout.addStretch()
        controls_layout.addWidget(self.confirm_btn)

        main_layout = QVBoxLayout()
        main_layout.addWidget(QLabel(f"Kamera: {camera_model}"))
        main_layout.addWidget(splitter)
        main_layout.addWidget(self.time_label)
        main_layout.addWidget(self.gps_label)
        main_layout.addLayout(controls_layout)

        self.setLayout(main_layout)

        self.update_ui()

    def load_image_preview(self, path):
        try:
            img = Image.open(path)
            img.thumbnail((800, 800))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG")
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.getvalue())
            self.image_label.setPixmap(pixmap)
        except Exception as e:
            self.image_label.setText(f"Fehler beim Laden des Bildes: {e}")

    def update_ui(self):
        self.load_image_preview(self.image_path)
        corrected_time = self.exif_time + self.offset
        self.time_label.setText(f"📷 EXIF-Zeit (korrigiert): {corrected_time.strftime('%Y-%m-%d %H:%M:%S')}")

        match = self.find_closest_point(self.gpx_points, corrected_time)
        if match:
            self.gps_label.setText(f"📍 Koordinaten: {match['lat']:.5f}, {match['lon']:.5f}")
            QTimer.singleShot(1000, lambda: self.update_map(match['lat'], match['lon']))
        else:
            self.gps_label.setText("⚠️ Keine passenden GPX-Daten gefunden.")
            QTimer.singleShot(1000, lambda: self.update_map(None, None))

    def update_map(self, lat, lon):
        if lat is not None and lon is not None:
            js = f"""
                if (typeof updateMarker === 'function') {{
                    updateMarker({lat}, {lon});
                }}
            """
        else:
            js = "if (typeof clearMarker === 'function') { clearMarker(); }"
        self.map_view.page().runJavaScript(js)

    def increase_offset(self):
        self.offset += timedelta(hours=1)
        self.update_ui()

    def decrease_offset(self):
        self.offset -= timedelta(hours=1)
        self.update_ui()

    def select_new_image(self):
        file, _ = QFileDialog.getOpenFileName(self, "Anderes Bild wählen", filter="Bilder (*.jpg *.jpeg)")
        if file:
            from logic.exif_handler import get_datetime_from_exif
            new_time = get_datetime_from_exif(file)
            if new_time:
                self.image_path = file
                self.exif_time = new_time
                self.offset = timedelta()
                self.update_ui()
            else:
                self.gps_label.setText("⚠️ Keine gültige EXIF-Zeit in diesem Bild.")

    def get_time_offset(self):
        return self.offset
