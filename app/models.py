from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from .extensions import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30))
    role = db.Column(db.String(20), nullable=False, default="CITIZEN", index=True)
    profile_image = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    complaints = db.relationship("Complaint", foreign_keys="Complaint.citizen_id", back_populates="citizen")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)


class Worker(TimestampMixin, db.Model):
    __tablename__ = "workers"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    specialization = db.Column(db.String(120), default="Road repair")
    availability = db.Column(db.Boolean, default=True, nullable=False)
    status = db.Column(db.String(30), default="AVAILABLE", nullable=False)
    user = db.relationship("User")
    assignments = db.relationship("Assignment", back_populates="worker")


class Road(TimestampMixin, db.Model):
    __tablename__ = "roads"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    category = db.Column(db.String(40), nullable=False)
    traffic_density = db.Column(db.Float, default=0.5)
    emergency_route = db.Column(db.Boolean, default=False)


class Complaint(TimestampMixin, db.Model):
    __tablename__ = "complaints"
    id = db.Column(db.Integer, primary_key=True)
    complaint_code = db.Column(db.String(24), nullable=False, unique=True, index=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=False, index=True)
    longitude = db.Column(db.Float, nullable=False, index=True)
    road_name = db.Column(db.String(160), nullable=False)
    road_category = db.Column(db.String(40), nullable=False, index=True)
    original_image = db.Column(db.String(255), nullable=False)
    detected_image = db.Column(db.String(255))
    image_hash = db.Column(db.String(64))
    damage_type = db.Column(db.String(60), nullable=False, default="Unclassified")
    severity_score = db.Column(db.Float, nullable=False, default=0)
    severity_level = db.Column(db.String(20), nullable=False, default="LOW", index=True)
    priority_score = db.Column(db.Float, nullable=False, default=0)
    priority_level = db.Column(db.String(20), nullable=False, default="LOW", index=True)
    status = db.Column(db.String(30), nullable=False, default="SUBMITTED", index=True)
    master_complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), index=True)
    citizen = db.relationship("User", foreign_keys=[citizen_id], back_populates="complaints")
    master_complaint = db.relationship("Complaint", remote_side=[id], backref="related_complaints")
    detections = db.relationship("Detection", back_populates="complaint", cascade="all, delete-orphan")
    assignments = db.relationship("Assignment", back_populates="complaint", cascade="all, delete-orphan")
    repairs = db.relationship("RepairUpdate", back_populates="complaint", cascade="all, delete-orphan")

    @property
    def duplicate_count(self): return len(self.related_complaints) if self.master_complaint_id is None else 0


class Detection(TimestampMixin, db.Model):
    __tablename__ = "detections"
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False, index=True)
    class_name = db.Column(db.String(60), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    x1 = db.Column(db.Float, nullable=False); y1 = db.Column(db.Float, nullable=False)
    x2 = db.Column(db.Float, nullable=False); y2 = db.Column(db.Float, nullable=False)
    area = db.Column(db.Float, nullable=False)
    complaint = db.relationship("Complaint", back_populates="detections")


class DuplicateComplaint(TimestampMixin, db.Model):
    __tablename__ = "duplicate_complaints"
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False, index=True)
    master_complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False, index=True)
    distance_meters = db.Column(db.Float, nullable=False)
    image_similarity_score = db.Column(db.Float, nullable=False)


class Assignment(TimestampMixin, db.Model):
    __tablename__ = "assignments"
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False, index=True)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False, index=True)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    complaint = db.relationship("Complaint", back_populates="assignments")
    worker = db.relationship("Worker", back_populates="assignments")


class RepairUpdate(TimestampMixin, db.Model):
    __tablename__ = "repair_updates"
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False, index=True)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"))
    status = db.Column(db.String(30), nullable=False)
    notes = db.Column(db.Text)
    before_image = db.Column(db.String(255))
    after_image = db.Column(db.String(255))
    complaint = db.relationship("Complaint", back_populates="repairs")


class Notification(TimestampMixin, db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    user = db.relationship("User", back_populates="notifications")


class AuditLog(TimestampMixin, db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
