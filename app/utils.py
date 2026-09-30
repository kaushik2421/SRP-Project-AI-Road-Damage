from functools import wraps
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from uuid import uuid4
from flask import abort, current_app
from flask_login import current_user
from PIL import Image


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated: abort(401)
            if current_user.role not in roles: abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def valid_coordinates(latitude, longitude):
    try: return -90 <= float(latitude) <= 90 and -180 <= float(longitude) <= 180
    except (TypeError, ValueError): return False


def haversine_meters(lat1, lon1, lat2, lon2):
    d_lat, d_lon = radians(lat2-lat1), radians(lon2-lon1)
    a = sin(d_lat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(d_lon/2)**2
    return 6371000 * 2 * asin(sqrt(a))


def save_image(file_storage, group):
    if not file_storage or not file_storage.filename: raise ValueError("An image is required.")
    extension = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if extension not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]: raise ValueError("Use JPG, PNG, or WebP images only.")
    try:
        image = Image.open(file_storage.stream); image.verify(); file_storage.stream.seek(0)
    except Exception as exc: raise ValueError("The uploaded file is not a valid image.") from exc
    name = f"{uuid4().hex}.{extension}"
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / group
    folder.mkdir(parents=True, exist_ok=True)
    file_storage.save(folder / name)
    return f"{group}/{name}"
