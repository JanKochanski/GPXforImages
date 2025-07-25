# main.py

import sys
import os
from collections import defaultdict
from datetime import timedelta

from PyQt5.QtWidgets import (
    QApplication, QWidget, QFileDialog, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QListWidget, QDialog, QMessageBox, QProgressDialog
)
from PyQt5.QtCore import Qt, QStandardPaths


from logic.exif_handler import (
    get_datetime_from_exif,
    extract_camera_model,
    has_gps_data,
    write_gps_to_image
)
from logic.gpx_matcher import load_gpx_points, find_closest_point
from ui.time_offset_widget import TimeOffsetWidget


class GeoTaggerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GeoTagger mit GPX")
        self.setMinimumSize(600, 400)

        self.image_folder = ""
        self.gpx_file = ""
        self.time_offsets = {}
        self.pending_models = set()

        # UI-Elemente
        self.folder_label = QLabel("📁 Kein Bildordner ausgewählt")
        self.gpx_label = QLabel("🛰️ Keine GPX-Datei ausgewählt")
        self.select_folder_btn = QPushButton("Bildordner auswählen")
        self.select_gpx_btn = QPushButton("GPX-Datei auswählen")
        self.load_btn = QPushButton("Bilder & GPX laden")
        self.load_btn.setEnabled(False)

        self.select_folder_btn.clicked.connect(self.select_folder)
        self.select_gpx_btn.clicked.connect(self.select_gpx)
        self.load_btn.clicked.connect(self.load_data)

        layout = QVBoxLayout()
        layout.addWidget(self.folder_label)
        layout.addWidget(self.select_folder_btn)
        layout.addWidget(self.gpx_label)
        layout.addWidget(self.select_gpx_btn)
        layout.addWidget(self.load_btn)

        self.setLayout(layout)

    def select_folder(self):        
        pictures_dir = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)

        folder = QFileDialog.getExistingDirectory(
            None,
            "Bilderordner auswählen",
            pictures_dir,  # 👉 Startverzeichnis
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )

        if folder:
            self.image_folder = folder
            self.folder_label.setText(f"📁 Ordner: {os.path.basename(folder)}")
            self.update_load_btn_state()

    def select_gpx(self):
        file, _ = QFileDialog.getOpenFileName(self, "GPX-Datei wählen", filter="GPX Dateien (*.gpx)")
        if file:
            self.gpx_file = file
            self.gpx_label.setText(f"🛰️ GPX: {os.path.basename(file)}")
            self.update_load_btn_state()

    def update_load_btn_state(self):
        self.load_btn.setEnabled(bool(self.image_folder and self.gpx_file))

    def load_data(self):
        print("🔄 Lade GPX-Punkte und analysiere Bilder...")
        gpx_points = load_gpx_points(self.gpx_file)
        if not gpx_points:
            QMessageBox.critical(self, "Fehler", "Keine GPX-Punkte gefunden.")
            return

        # Kamera → Liste aller zugehörigen Bilder
        camera_image_map = {}
        for filename in os.listdir(self.image_folder):
            if not filename.lower().endswith(('.jpg', '.jpeg')):
                continue
            full_path = os.path.join(self.image_folder, filename)
            if has_gps_data(full_path):
                continue
            model = extract_camera_model(full_path) or "Unbekannte Kamera"
            camera_image_map.setdefault(model, []).append(full_path)

        if not camera_image_map:
            QMessageBox.information(self, "Hinweis", "Keine Bilder ohne GPS-Daten gefunden.")
            return

        # Zeige erkannte Kameras im Hinweisdialog
        camera_list_str = "\n".join(
            f"{model} ({len(paths)} Bilder)" for model, paths in camera_image_map.items()
        )
        print("📷 Gefundene Kameras:")
        print(camera_list_str)
        QMessageBox.information(self, "Kameras erkannt", f"Folgende Kameramodelle wurden erkannt:\n\n{camera_list_str}")

        self.time_offsets = {}

        # Zeige Zeitversatz-Dialog für jede Kamera
        for model, image_paths in camera_image_map.items():
            first_image = image_paths[0]
            exif_time = get_datetime_from_exif(first_image)
            if not exif_time:
                print(f"⚠️ Kein EXIF-Zeitstempel für {first_image}")
                continue

            widget = TimeOffsetWidget(
                camera_model=model,
                image_path=first_image,
                exif_time=exif_time,
                gpx_points=gpx_points,
                find_closest_point_callback=find_closest_point
            )

            if widget.exec_() == QDialog.Accepted:
                offset = widget.get_time_offset()
                print(f"✅ Zeitversatz bestätigt für {model}: {offset}")
                self.time_offsets[model] = offset
            else:
                print(f"⛔ Zeitversatz für {model} abgebrochen.")
                return  # Vorgang abbrechen, wenn abgelehnt
        if len(self.time_offsets) == len(camera_image_map):
            self.process_all_images_with_offsets()


        # Wenn alle offsets gesetzt sind, starte Bildverarbeitung
        self.process_all_images_with_offsets()


    def process_all_images_with_offsets(self):
        gpx_points = load_gpx_points(self.gpx_file)

        # Bilder nach Kameramodell gruppieren
        camera_images = defaultdict(list)
        for filename in os.listdir(self.image_folder):
            if not filename.lower().endswith(('.jpg', '.jpeg')):
                continue
            full_path = os.path.join(self.image_folder, filename)
            if has_gps_data(full_path):
                continue
            model = extract_camera_model(full_path)
            if not model:
                continue
            camera_images[model].append(full_path)

        total = sum(len(imgs) for imgs in camera_images.values())
        progress = QProgressDialog("Schreibe GPS-Daten in Bilder...", "Abbrechen", 0, total, self)
        progress.setWindowTitle("Verarbeitung läuft")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        count_success = 0
        count_failed = 0
        current = 0

        for model, image_list in camera_images.items():
            offset = self.time_offsets.get(model, timedelta())
            for img_path in image_list:
                current += 1
                progress.setValue(current)
                if progress.wasCanceled():
                    QMessageBox.warning(self, "Abgebrochen", "Die Verarbeitung wurde abgebrochen.")
                    return
                timestamp = get_datetime_from_exif(img_path)
                if not timestamp:
                    count_failed += 1
                    continue
                corrected_time = timestamp + offset
                match = find_closest_point(gpx_points, corrected_time)
                if match:
                    success = write_gps_to_image(img_path, match['lat'], match['lon'])
                    count_success += int(success)
                    count_failed += int(not success)
                else:
                    count_failed += 1

        progress.close()
        QMessageBox.information(
            self,
            "Fertig",
            f"✅ Erfolgreich bearbeitet: {count_success}\n❌ Fehlgeschlagen: {count_failed}"
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeoTaggerApp()
    window.show()
    sys.exit(app.exec_())
