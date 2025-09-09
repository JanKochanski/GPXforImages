# logic/exif_handler.py

import pyexiv2
from datetime import datetime

def get_datetime_from_exif(img_path):
    """Liest das Aufnahmedatum aus der EXIF aus."""
    try:
        metadata = pyexiv2.ImageMetadata(img_path)
        metadata.read()
        date_tag = None
        if "Exif.Photo.DateTimeOriginal" in metadata:
            date_tag = metadata["Exif.Photo.DateTimeOriginal"].value
        elif "Exif.Image.DateTime" in metadata:
            date_tag = metadata["Exif.Image.DateTime"].value
        if date_tag:
            return datetime.strptime(str(date_tag), "%Y:%m:%d %H:%M:%S")
        return None
    except Exception:
        return None

def extract_camera_model(img_path):
    """Liest das Kameramodell aus der EXIF aus."""
    try:
        metadata = pyexiv2.ImageMetadata(img_path)
        metadata.read()
        if "Exif.Image.Model" in metadata:
            return str(metadata["Exif.Image.Model"].value)
        return None
    except Exception:
        return None

def has_gps_data(img_path):
    """Prüft, ob GPS-Daten vorhanden sind."""
    try:
        metadata = pyexiv2.ImageMetadata(img_path)
        metadata.read()
        return ("Exif.GPSInfo.GPSLatitude" in metadata) and ("Exif.GPSInfo.GPSLongitude" in metadata)
    except Exception:
        return False

def deg_to_dms_rational(deg):
    """
    Wandelt Dezimalgrad in DMS-Rational-Format um:
    z. B. 48.858222 → [(48,1),(51,1),(29,100)]
    """
    d = int(deg)
    m = int((deg - d) * 60)
    s = round((deg - d - m / 60) * 3600 * 100)
    return [(d, 1), (m, 1), (s, 100)]

def write_gps_to_image(img_path, lat, lon):
    """Schreibt GPS-Koordinaten in die EXIF eines Bildes."""
    try:
        metadata = pyexiv2.ImageMetadata(img_path)
        metadata.read()

        # GPS-Referenzen setzen
        metadata["Exif.GPSInfo.GPSLatitudeRef"] = 'N' if lat >= 0 else 'S'
        metadata["Exif.GPSInfo.GPSLatitude"] = deg_to_dms_rational(abs(lat))
        metadata["Exif.GPSInfo.GPSLongitudeRef"] = 'E' if lon >= 0 else 'W'
        metadata["Exif.GPSInfo.GPSLongitude"] = deg_to_dms_rational(abs(lon))

        metadata.write()
        return True
    except Exception as e:
        print(f"[Fehler] GPS schreiben in {img_path}: {e}")
        return False
