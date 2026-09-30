from datetime import datetime
from pathlib import Path
import logging
import cv2
import numpy as np
from flask import current_app
from PIL import Image, ImageDraw
from .extensions import db
from .models import AuditLog, Notification
from .utils import haversine_meters

logger = logging.getLogger(__name__)
DAMAGE_CLASSES = {"Pothole", "Longitudinal Crack", "Transverse Crack", "Alligator Crack"}


class AIUnavailableError(RuntimeError): pass


class AIDetector:
    """Lazy, verified adapter for actual Ultralytics/YOLO-compatible weights."""
    _model = None; _model_path = None
    def _load(self):
        path = Path(current_app.config["MODEL_PATH"])
        if not path.is_file(): raise AIUnavailableError("Road-damage AI model is not configured. Add verified weights at MODEL_PATH.")
        if self._model is not None and self._model_path == str(path): return self._model
        try:
            from ultralytics import YOLO
            self._model = YOLO(str(path)); self._model_path = str(path)
            return self._model
        except ImportError as exc: raise AIUnavailableError("Ultralytics is not installed; cannot run configured model.") from exc
        except Exception as exc: raise AIUnavailableError(f"Configured model could not be loaded: {exc}") from exc

    def detect(self, relative_image):
        model = self._load(); source = Path(current_app.config["UPLOAD_FOLDER"]) / relative_image
        try: result = model(str(source), conf=current_app.config["AI_CONFIDENCE_THRESHOLD"], verbose=False)[0]
        except Exception as exc: raise AIUnavailableError(f"Model inference failed: {exc}") from exc
        original = Image.open(source).convert("RGB"); draw = ImageDraw.Draw(original); detections = []
        names = result.names
        for box in result.boxes:
            cls = int(box.cls[0]); class_name = str(names[cls])
            if class_name not in DAMAGE_CLASSES: continue
            x1,y1,x2,y2 = [float(v) for v in box.xyxy[0].tolist()]; confidence = float(box.conf[0])
            item = {"class_name": class_name, "confidence": round(confidence, 4), "bbox": {"x1":x1,"y1":y1,"x2":x2,"y2":y2}, "area": round((x2-x1)*(y2-y1), 2)}
            detections.append(item); draw.rectangle((x1,y1,x2,y2), outline="#dc3545", width=4); draw.text((x1, max(0,y1-18)), f"{class_name} {confidence:.0%}", fill="#dc3545")
        filename = f"detected/{source.stem}_detected.jpg"; original.save(Path(current_app.config["UPLOAD_FOLDER"]) / filename, quality=92)
        return {"detections": detections, "detected_image": filename}


ai_detector = AIDetector()


def image_fingerprint(relative_image):
    image = cv2.imread(str(Path(current_app.config["UPLOAD_FOLDER"]) / relative_image), cv2.IMREAD_GRAYSCALE)
    if image is None: return None
    reduced = cv2.resize(image, (9, 8)); bits = reduced[:, 1:] > reduced[:, :-1]
    return "".join("1" if bit else "0" for bit in bits.flatten())


def similarity(first, second):
    if not first or not second or len(first) != len(second): return 0.0
    return 1 - sum(a != b for a,b in zip(first,second)) / len(first)


def find_duplicate(complaint_cls, latitude, longitude, fingerprint):
    radius = current_app.config["DUPLICATE_RADIUS_METERS"]; candidate = None
    for existing in complaint_cls.query.filter(complaint_cls.status != "CLOSED").all():
        distance = haversine_meters(latitude, longitude, existing.latitude, existing.longitude)
        score = similarity(fingerprint, existing.image_hash)
        if distance <= radius and score >= current_app.config["IMAGE_SIMILARITY_THRESHOLD"]:
            candidate = (existing.master_complaint or existing, distance, score); break
    return candidate


def calculate_severity(detections, road_category):
    if not detections: return 0.0, "LOW"
    area = min(1.0, sum(d["area"] for d in detections) / 250000)
    confidence = sum(d["confidence"] for d in detections) / len(detections)
    type_factor = max({"Pothole":.75,"Longitudinal Crack":.55,"Transverse Crack":.6,"Alligator Crack":.9}.get(d["class_name"], .4) for d in detections)
    road_factor = {"Highway":1,"Arterial":.85,"Collector":.65,"Local":.45}.get(road_category,.5)
    score = round(min(100, 100*(.35*area+.25*confidence+.25*type_factor+.15*road_factor)), 1)
    return score, "CRITICAL" if score > 75 else "HIGH" if score > 50 else "MODERATE" if score > 25 else "LOW"


def calculate_priority(severity, road_category, report_count=1, pending_days=0):
    road = {"Highway":1,"Arterial":.8,"Collector":.6,"Local":.4}.get(road_category,.5)
    score = min(100, .55*severity + .18*road*100 + .15*min(report_count/5,1)*100 + .12*min(pending_days/30,1)*100)
    score = round(score, 1)
    return score, "CRITICAL" if score > 75 else "HIGH" if score > 50 else "MEDIUM" if score > 25 else "LOW"


def audit(complaint_id, actor_id, action, details=""):
    db.session.add(AuditLog(complaint_id=complaint_id, actor_id=actor_id, action=action, details=details))


def notify(user_id, title, message, link=None): db.session.add(Notification(user_id=user_id,title=title,message=message,link=link))
