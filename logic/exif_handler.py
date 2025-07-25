# logic/exif_handler.py

import piexif
from PIL import Image
from datetime import datetime

def get_datetime_from_exif(img_path):
    try:
        img = Image.open(img_path)
        exif_data = img._getexif()
        if not exif_data:
            return None
        date_str = exif_data.get(36867) or exif_data.get(306)  # DateTimeOriginal oder DateTime
        if not date_str:
            return None
        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except:
        return None

def extract_camera_model(img_path):
    try:
        img = Image.open(img_path)
        exif_data = img._getexif()
        return exif_data.get(272) if exif_data else None  # Tag 272 = Camera Model
    except:
        return None

def has_gps_data(img_path):
    try:
        exif_dict = piexif.load(img_path)
        return bool(exif_dict.get("GPS", {}).get(piexif.GPSIFD.GPSLatitude))
    except:
        return False

def deg_to_dms_rational(deg):
    d = int(deg)
    m = int((deg - d) * 60)
    s = int(((deg - d) * 60 - m) * 60 * 10000)
    return [(d, 1), (m, 1), (s, 10000)]

def write_gps_to_image(img_path, lat, lon):
    try:
        exif_dict = piexif.load(img_path)
        gps_ifd = {
            piexif.GPSIFD.GPSLatitudeRef: 'N' if lat >= 0 else 'S',
            piexif.GPSIFD.GPSLatitude: deg_to_dms_rational(abs(lat)),
            piexif.GPSIFD.GPSLongitudeRef: 'E' if lon >= 0 else 'W',
            piexif.GPSIFD.GPSLongitude: deg_to_dms_rational(abs(lon)),
        }
        exif_dict['GPS'] = gps_ifd
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, img_path)
        return True
    except Exception as e:
        print(f"[Fehler] GPS schreiben in {img_path}: {e}")
        return False
