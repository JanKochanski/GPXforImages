# logic/gpx_matcher.py

import gpxpy
from datetime import timedelta

def load_gpx_points(gpx_file):
    with open(gpx_file, 'r', encoding='utf-8') as f:
        gpx = gpxpy.parse(f)
    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for p in segment.points:
                if p.time:
                    points.append({
                        'time': p.time.replace(tzinfo=None),
                        'lat': p.latitude,
                        'lon': p.longitude
                    })
    return points

def find_closest_point(gpx_points, target_time):
    closest = None
    min_diff = float('inf')
    for point in gpx_points:
        diff = abs((point['time'] - target_time).total_seconds())
        if diff < min_diff:
            min_diff = diff
            closest = point
    return closest if min_diff <= 300 else None  # max 5 Min Toleranz
