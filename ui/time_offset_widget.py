# ui/time_offset_widget.py

from PyQt5.QtWidgets import (
    QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QSizePolicy, QFrame, QSplitter, QDialog, 
    QTableWidget, QTableWidgetItem, QScrollArea

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
        self.resize(1900, 1000)

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

        # 📋 Kameratabelle
        self.camera_table = QTableWidget()
        self.camera_table.setColumnCount(2)
        self.camera_table.setHorizontalHeaderLabels(["Zeitversatz", "Kamera"])
        self.camera_table.verticalHeader().setVisible(False)
        self.camera_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.camera_table.setSelectionMode(QTableWidget.NoSelection)
        self.camera_table.setMaximumHeight(5 * 30 + 30)  # max 5 Zeilen + Header
        self.camera_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


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
        # 📐 Steuerleisten
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.minus_btn)
        controls_layout.addWidget(self.plus_btn)
        controls_layout.addWidget(self.change_img_btn)
        controls_layout.addStretch()
        controls_layout.addWidget(self.confirm_btn)

        # 📐 Splitter in eigenen Container verpacken (nur dieser darf vertikal wachsen)
        splitter_container = QFrame()
        splitter_container_layout = QVBoxLayout()
        splitter_container_layout.setContentsMargins(0, 0, 0, 0)
        splitter_container_layout.addWidget(splitter)
        splitter_container.setLayout(splitter_container_layout)

        # 📐 Hauptlayout
        main_layout = QVBoxLayout()
        main_layout.addWidget(QLabel(f"Kamera: {camera_model}"))
        main_layout.addWidget(splitter_container)  # Das ist der einzige stretchebare Bereich
        main_layout.setStretch(main_layout.count() - 1, 1)  # splitter_container stretcht vertikal

        main_layout.addWidget(self.camera_table)
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

    def set_camera_overview(self, camera_image_map, time_offset_dict):
        self.camera_table.setRowCount(len(camera_image_map))
        for row, (model, _) in enumerate(camera_image_map.items()):
            offset = time_offset_dict.get(model, "Nicht gesetzt")
            self.camera_table.setItem(row, 0, QTableWidgetItem(str(offset)))
            self.camera_table.setItem(row, 1, QTableWidgetItem(model))

    def update_map(self, lat, lon):
        if lat is None or lon is None:
            js = "if (typeof clearMarker === 'function') { clearMarker(); }"
            self.map_view.page().runJavaScript(js)
            return

        corrected_time = self.exif_time + self.offset
        ten_minutes = timedelta(minutes=10)

        # Finde alle GPX-Punkte in +/-10 Minuten
        relevant_points = [
            p for p in self.gpx_points
            if abs(p['time'] - corrected_time) <= ten_minutes
        ]

        # Füge den aktuellen Punkt explizit hinzu
        relevant_points.append({'lat': lat, 'lon': lon})

        # Berechne Bounding Box
        lats = [p['lat'] for p in relevant_points]
        lons = [p['lon'] for p in relevant_points]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        js = f"""
            if (typeof updateMarker === 'function' && typeof map !== 'undefined') {{
                updateMarker({lat}, {lon});
                var bounds = L.latLngBounds(
                    L.latLng({min_lat}, {min_lon}),
                    L.latLng({max_lat}, {max_lon})
                );
                map.fitBounds(bounds, {{ padding: [20, 20] }});
            }}
        """
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
