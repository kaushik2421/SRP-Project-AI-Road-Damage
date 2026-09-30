from datetime import datetime
from io import BytesIO
from flask import Blueprint, Response, abort, current_app, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required, login_user, logout_user
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import false, func
from .extensions import db
from .models import Assignment, Complaint, Detection, DuplicateComplaint, Notification, RepairUpdate, User, Worker
from .services import AIUnavailableError, ai_detector, audit, calculate_priority, calculate_severity, find_duplicate, image_fingerprint, notify
from .utils import roles_required, save_image, valid_coordinates

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
citizen_bp = Blueprint("citizen", __name__, url_prefix="/citizen")
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
municipal_bp = Blueprint("municipal", __name__, url_prefix="/municipal")
worker_bp = Blueprint("worker", __name__, url_prefix="/worker")
api_bp = Blueprint("api", __name__, url_prefix="/api")

STATUSES = ["SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS", "REPAIR_COMPLETED", "VERIFIED", "CLOSED"]


def complaint_data(item, detailed=False):
    data = {"id":item.id,"code":item.complaint_code,"damage_type":item.damage_type,"severity_score":item.severity_score,"severity_level":item.severity_level,"priority_score":item.priority_score,"priority_level":item.priority_level,"status":item.status,"road_name":item.road_name,"road_category":item.road_category,"latitude":item.latitude,"longitude":item.longitude,"created_at":item.created_at.isoformat(),"duplicate_count":item.duplicate_count,"master_code":item.master_complaint.complaint_code if item.master_complaint else None}
    if detailed:
        data.update(description=item.description,original_image=item.original_image,detected_image=item.detected_image,citizen={"name":item.citizen.full_name,"email":item.citizen.email,"phone":item.citizen.phone},detections=[{"class_name":d.class_name,"confidence":d.confidence,"bbox":{"x1":d.x1,"y1":d.y1,"x2":d.x2,"y2":d.y2},"area":d.area} for d in item.detections])
    return data


def page_for_role(user):
    return {
        "CITIZEN": "citizen.dashboard",
        "ADMIN": "admin.dashboard",
        "MUNICIPAL_ADMIN": "municipal.dashboard",
        "ENGINEER": "worker.dashboard",
        "WORKER": "worker.dashboard",
    }.get(user.role, "landing")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated: return redirect(url_for(page_for_role(current_user)))
    error = None
    if request.method == "POST":
        name, email, phone, password = (request.form.get(k, "").strip() for k in ("full_name","email","phone","password"))
        if len(name) < 2 or "@" not in email or len(password) < 8: error = "Enter a name, valid email, and a password of at least 8 characters."
        elif User.query.filter_by(email=email.lower()).first(): error = "An account with that email already exists."
        else:
            user = User(full_name=name,email=email.lower(),phone=phone,role="CITIZEN"); user.set_password(password); db.session.add(user); db.session.commit(); login_user(user)
            return redirect(url_for("citizen.dashboard"))
    return render_template("auth/register.html", error=error)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated: return redirect(url_for(page_for_role(current_user)))
    error = None
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "").lower().strip()).first()
        if not user or not user.is_active or not user.check_password(request.form.get("password", "")): error = "Invalid email or password."
        else: login_user(user); return redirect(request.args.get("next") or url_for(page_for_role(user)))
    return render_template("auth/login.html", error=error)


@municipal_bp.route("/login", methods=["GET", "POST"])
def municipal_login():
    if current_user.is_authenticated: return redirect(url_for(page_for_role(current_user)))
    error = None
    if request.method == "POST":
        username = request.form.get("email", "").lower().strip() or request.form.get("username", "").lower().strip()
        user = User.query.filter_by(email=username).first()
        if not user or user.role not in {"ADMIN", "MUNICIPAL_ADMIN"} or not user.is_active or not user.check_password(request.form.get("password", "")):
            error = "Invalid municipal credentials."
        else:
            login_user(user)
            return redirect(request.args.get("next") or url_for("municipal.dashboard"))
    return render_template("municipal/login.html", error=error)


@auth_bp.post("/logout")
@login_required
def logout(): logout_user(); return redirect(url_for("landing"))


@citizen_bp.get("/dashboard")
@roles_required("CITIZEN")
def dashboard(): return render_template("citizen/dashboard.html")

@citizen_bp.get("/report")
@roles_required("CITIZEN")
def report(): return render_template("citizen/report_wizard.html")

@citizen_bp.get("/complaints/<int:complaint_id>")
@roles_required("CITIZEN")
def complaint_detail(complaint_id):
    item = db.get_or_404(Complaint, complaint_id)
    if item.citizen_id != current_user.id: abort(403)
    return render_template("citizen/complaint_detail.html", complaint=item, statuses=STATUSES)


@admin_bp.get("/dashboard")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def dashboard(): return render_template("admin/dashboard.html")

@admin_bp.get("/complaints")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def complaints(): return render_template("admin/complaints.html")

@admin_bp.get("/complaints/<int:complaint_id>")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def complaint_detail(complaint_id): return render_template("admin/complaint_detail.html", complaint=db.get_or_404(Complaint, complaint_id), statuses=STATUSES)

@admin_bp.get("/map")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def complaint_map(): return render_template("admin/map.html")

@admin_bp.get("/workers")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def workers(): return render_template("admin/workers.html")


@municipal_bp.get("/dashboard")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def dashboard(): return render_template("municipal/dashboard.html")

@municipal_bp.get("/complaints")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def complaints(): return render_template("municipal/complaints.html")

@municipal_bp.get("/map")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def map(): return render_template("municipal/map.html")

@municipal_bp.get("/workers")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def workers(): return render_template("municipal/workers.html")

@municipal_bp.get("/priority")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def priority(): return render_template("municipal/priority.html")

@municipal_bp.get("/severity")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def severity(): return render_template("municipal/severity.html")

@municipal_bp.get("/analytics")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def analytics(): return render_template("municipal/analytics.html")


@worker_bp.get("/dashboard")
@roles_required("WORKER", "ENGINEER")
def dashboard(): return render_template("worker/dashboard.html")


@api_bp.get("/uploads/<path:filename>")
@login_required
def uploaded_image(filename): return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)

@api_bp.post("/auth/register")
def api_register():
    payload = request.get_json(silent=True) or request.form
    if request.get_json(silent=True) is not None:
        if not payload.get("full_name") or not payload.get("email") or not payload.get("password"):
            return jsonify(error="Full name, email, and password are required."), 400
        name, email, phone, password = payload.get("full_name", "").strip(), payload.get("email", "").strip().lower(), payload.get("phone", "").strip(), payload.get("password", "")
        if len(name) < 2 or "@" not in email or len(password) < 8:
            return jsonify(error="Enter a name, valid email, and a password of at least 8 characters."), 400
        if User.query.filter_by(email=email).first():
            return jsonify(error="An account with that email already exists."), 409
        user = User(full_name=name, email=email, phone=phone, role="CITIZEN")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return jsonify(ok=True, user={"id": user.id, "email": user.email, "role": user.role})
    return register()

@api_bp.post("/auth/login")
def api_login():
    payload = request.get_json(silent=True) or request.form
    email = (payload.get("email", "") or "").lower().strip()
    password = payload.get("password", "") or ""
    user = User.query.filter_by(email=email).first()
    if not user or not user.is_active or not user.check_password(password):
        return jsonify(error="Invalid email or password."), 401
    login_user(user)
    return jsonify(ok=True, role=user.role, redirect=url_for(page_for_role(user)))

@api_bp.post("/auth/logout")
@login_required
def api_logout():
    logout_user(); return jsonify(ok=True)

@api_bp.post("/auth/municipal/login")
def api_municipal_login():
    payload = request.get_json(silent=True) or request.form
    email = (payload.get("email") or payload.get("username") or "").lower().strip()
    password = payload.get("password") or ""
    user = User.query.filter_by(email=email).first()
    if not user or user.role not in {"ADMIN", "MUNICIPAL_ADMIN"} or not user.is_active or not user.check_password(password):
        return jsonify(error="Invalid municipal credentials."), 401
    login_user(user)
    return jsonify(ok=True, role=user.role, redirect=url_for("municipal.dashboard"))

@api_bp.get("/municipal/dashboard")
@login_required
def municipal_dashboard_api():
    if current_user.role not in {"ADMIN", "MUNICIPAL_ADMIN"}:
        abort(403)
    return dashboard_metrics()

@api_bp.get("/dashboard")
@login_required
def dashboard_metrics():
    query = Complaint.query
    if current_user.role == "CITIZEN": query = query.filter_by(citizen_id=current_user.id)
    elif current_user.role in {"WORKER", "ENGINEER"}:
        worker = Worker.query.filter_by(user_id=current_user.id).first()
        query = query.join(Assignment).filter(Assignment.worker_id == worker.id, Assignment.active.is_(True)) if worker else query.filter(false())
    rows = query.all(); count = len(rows)
    by = lambda field: {key: value for key,value in db.session.query(field, func.count(Complaint.id)).filter(Complaint.id.in_([x.id for x in rows]) if rows else false()).group_by(field).all()}
    return jsonify(total=count, statuses=by(Complaint.status), damage=by(Complaint.damage_type), severity=by(Complaint.severity_level), priority=by(Complaint.priority_level), recent=[complaint_data(x) for x in sorted(rows,key=lambda c:c.created_at,reverse=True)[:6]])

@api_bp.get("/dashboard/stats")
@login_required
def dashboard_metrics_alias():
    return dashboard_metrics()

@api_bp.get("/complaints")
@login_required
def list_complaints():
    query = Complaint.query
    if current_user.role == "CITIZEN": query = query.filter_by(citizen_id=current_user.id)
    elif current_user.role not in {"ADMIN","MUNICIPAL_ADMIN","WORKER","ENGINEER"}: abort(403)
    if current_user.role in {"WORKER","ENGINEER"}:
        worker = Worker.query.filter_by(user_id=current_user.id).first()
        query = query.join(Assignment).filter(Assignment.worker_id == worker.id, Assignment.active.is_(True)) if worker else query.filter(false())
    for key,column in {"status":Complaint.status,"priority":Complaint.priority_level,"severity":Complaint.severity_level,"damage_type":Complaint.damage_type,"road_category":Complaint.road_category}.items():
        if request.args.get(key): query=query.filter(column==request.args[key].upper() if key != "damage_type" and key != "road_category" else request.args[key])
    if request.args.get("search"):
        term=f"%{request.args['search']}%"
        query=query.filter(db.or_(Complaint.complaint_code.ilike(term),Complaint.road_name.ilike(term),Complaint.damage_type.ilike(term)))
    sort = request.args.get("sort","created_at"); column = getattr(Complaint, sort, Complaint.created_at); query=query.order_by(column.desc())
    page = max(1, request.args.get("page",1,type=int)); per_page=min(100,max(1,request.args.get("per_page",10,type=int))); pagination=query.paginate(page=page,per_page=per_page,error_out=False)
    return jsonify(items=[complaint_data(x) for x in pagination.items], page=page, pages=pagination.pages, total=pagination.total)

@api_bp.post("/complaints")
@roles_required("CITIZEN")
def create_complaint():
    try:
        form = request.form; latitude, longitude = form.get("latitude"),form.get("longitude")
        if not valid_coordinates(latitude,longitude): raise ValueError("Choose a valid map location.")
        road_category = form.get("road_category",""); description=form.get("description","").strip(); road_name=form.get("road_name","").strip()
        if road_category not in {"Highway","Arterial","Collector","Local"}: raise ValueError("Choose a road category.")
        if len(road_name)<2 or len(description)<8: raise ValueError("Road name and a description of at least 8 characters are required.")
        original = save_image(request.files.get("image"), "original"); fingerprint=image_fingerprint(original)
        ai_warning=None; analysis={"detections":[],"detected_image":None}
        try: analysis=ai_detector.detect(original)
        except AIUnavailableError as exc: ai_warning=str(exc)
        severity, severity_level=calculate_severity(analysis["detections"], road_category)
        duplicate=find_duplicate(Complaint,float(latitude),float(longitude),fingerprint)
        count=(duplicate[0].duplicate_count+1) if duplicate else 1
        priority, priority_level=calculate_priority(severity,road_category,count)
        item=Complaint(complaint_code=f"RD-{datetime.utcnow():%Y%m%d}-{Complaint.query.count()+1:04d}",citizen_id=current_user.id,description=description,latitude=float(latitude),longitude=float(longitude),road_name=road_name,road_category=road_category,original_image=original,detected_image=analysis["detected_image"],image_hash=fingerprint,damage_type=analysis["detections"][0]["class_name"] if analysis["detections"] else "Unclassified",severity_score=severity,severity_level=severity_level,priority_score=priority,priority_level=priority_level,master_complaint_id=duplicate[0].id if duplicate else None)
        db.session.add(item); db.session.flush()
        for d in analysis["detections"]: db.session.add(Detection(complaint_id=item.id,class_name=d["class_name"],confidence=d["confidence"],x1=d["bbox"]["x1"],y1=d["bbox"]["y1"],x2=d["bbox"]["x2"],y2=d["bbox"]["y2"],area=d["area"]))
        if duplicate: db.session.add(DuplicateComplaint(complaint_id=item.id,master_complaint_id=duplicate[0].id,distance_meters=duplicate[1],image_similarity_score=duplicate[2]))
        audit(item.id,current_user.id,"CREATED","Citizen submitted report"); notify(current_user.id,"Report submitted",f"{item.complaint_code} was submitted.",f"/citizen/complaints/{item.id}")
        for admin in User.query.filter_by(role="ADMIN",is_active=True): notify(admin.id,"New road report",f"{item.complaint_code} needs review.",f"/admin/complaints/{item.id}")
        db.session.commit(); result=complaint_data(item,True); result["ai_warning"]=ai_warning
        if duplicate: result["duplicate"]={"code":duplicate[0].complaint_code,"distance_meters":round(duplicate[1],1),"image_similarity":round(duplicate[2],3)}
        return jsonify(result),201
    except ValueError as exc: return jsonify(error=str(exc)),400

@api_bp.get("/complaints/<int:complaint_id>")
@login_required
def get_complaint(complaint_id):
    item=db.get_or_404(Complaint,complaint_id)
    if current_user.role=="CITIZEN" and item.citizen_id != current_user.id: abort(403)
    return jsonify(complaint_data(item,True))

@api_bp.post("/complaints/<int:complaint_id>/assign")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def assign(complaint_id):
    payload=request.get_json(silent=True)
    try:
        worker_id=int(payload.get("worker_id")) if isinstance(payload,dict) else 0
    except (TypeError,ValueError):
        worker_id=0
    if worker_id < 1: return jsonify(error="Choose a valid worker."),400
    item=db.get_or_404(Complaint,complaint_id); worker=db.get_or_404(Worker,worker_id); Assignment.query.filter_by(complaint_id=item.id,active=True).update({"active":False})
    db.session.add(Assignment(complaint_id=item.id,worker_id=worker.id,assigned_by_id=current_user.id)); item.status="ASSIGNED"; audit(item.id,current_user.id,"ASSIGNED",f"Assigned to {worker.user.full_name}"); notify(worker.user_id,"New assignment",f"{item.complaint_code} is assigned to you.","/worker/dashboard"); notify(item.citizen_id,"Repair team assigned",f"A repair team was assigned to {item.complaint_code}."); db.session.commit(); return jsonify(ok=True)

@api_bp.post("/complaints/<int:complaint_id>/status")
@roles_required("ADMIN", "MUNICIPAL_ADMIN", "ENGINEER", "WORKER")
def update_status(complaint_id):
    item=db.get_or_404(Complaint,complaint_id); status=request.json.get("status")
    if status not in STATUSES: return jsonify(error="Invalid status."),400
    if current_user.role=="WORKER":
        worker=Worker.query.filter_by(user_id=current_user.id).first()
        if not worker or not Assignment.query.filter_by(complaint_id=item.id,worker_id=worker.id,active=True).first(): abort(403)
        if status not in {"IN_PROGRESS","REPAIR_COMPLETED"}: abort(403)
    item.status=status; audit(item.id,current_user.id,"STATUS_CHANGED",status); notify(item.citizen_id,"Report update",f"{item.complaint_code} is now {status.replace('_',' ').title()}."); db.session.commit(); return jsonify(ok=True,status=status)

@api_bp.post("/complaints/<int:complaint_id>/repair")
@roles_required("WORKER","ENGINEER")
def repair_update(complaint_id):
    item=db.get_or_404(Complaint,complaint_id); worker=Worker.query.filter_by(user_id=current_user.id).first()
    if not worker or not Assignment.query.filter_by(complaint_id=item.id,worker_id=worker.id,active=True).first(): abort(403)
    try:
        before=save_image(request.files.get("before_image"),"repair/before") if request.files.get("before_image") else None; after=save_image(request.files.get("after_image"),"repair/after") if request.files.get("after_image") else None
        status=request.form.get("status","IN_PROGRESS")
        if status not in {"IN_PROGRESS","REPAIR_COMPLETED"}: raise ValueError("Worker can only submit repair progress or completion.")
        item.status=status; db.session.add(RepairUpdate(complaint_id=item.id,worker_id=worker.id,status=status,notes=request.form.get("notes",""),before_image=before,after_image=after)); audit(item.id,current_user.id,"REPAIR_UPDATE",status); notify(item.citizen_id,"Repair update",f"{item.complaint_code}: {status.replace('_',' ').title()}."); db.session.commit(); return jsonify(ok=True)
    except ValueError as exc: return jsonify(error=str(exc)),400

@api_bp.get("/workers")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def list_workers(): return jsonify(items=[{"id":w.id,"name":w.user.full_name,"email":w.user.email,"phone":w.user.phone,"specialization":w.specialization,"availability":w.availability,"workload":sum(1 for a in w.assignments if a.active)} for w in Worker.query.all()])

@api_bp.post("/workers")
@roles_required("ADMIN")
def create_worker():
    data=request.json or {}; email=data.get("email","").lower().strip()
    if not data.get("name") or "@" not in email or len(data.get("password",""))<8: return jsonify(error="Name, valid email, and 8-character password required."),400
    if User.query.filter_by(email=email).first(): return jsonify(error="Email already exists."),409
    user=User(full_name=data["name"],email=email,phone=data.get("phone",""),role="WORKER"); user.set_password(data["password"]); db.session.add(user); db.session.flush(); db.session.add(Worker(user_id=user.id,specialization=data.get("specialization","Road repair"))); db.session.commit(); return jsonify(ok=True),201

@api_bp.get("/notifications")
@login_required
def notifications():
    items=Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(10).all()
    return jsonify(unread=Notification.query.filter_by(user_id=current_user.id,is_read=False).count(),items=[{"id":n.id,"title":n.title,"message":n.message,"link":n.link,"is_read":n.is_read,"created_at":n.created_at.isoformat()} for n in items])

@api_bp.post("/notifications/<int:notification_id>/read")
@login_required
def read_notification(notification_id):
    item=db.get_or_404(Notification,notification_id)
    if item.user_id != current_user.id: abort(403)
    item.is_read=True; db.session.commit(); return jsonify(ok=True)

@api_bp.get("/complaints/<int:complaint_id>/report.pdf")
@roles_required("ADMIN", "MUNICIPAL_ADMIN")
def pdf_report(complaint_id):
    item=db.get_or_404(Complaint,complaint_id); stream=BytesIO(); pdf=canvas.Canvas(stream,pagesize=letter); pdf.setTitle(f"Complaint {item.complaint_code}"); text=pdf.beginText(48,740)
    for row in [f"Road Damage Report: {item.complaint_code}",f"Citizen: {item.citizen.full_name}",f"Created: {item.created_at:%Y-%m-%d %H:%M UTC}",f"Road: {item.road_name} ({item.road_category})",f"Location: {item.latitude:.6f}, {item.longitude:.6f}",f"Damage: {item.damage_type}",f"Severity: {item.severity_score}/100 {item.severity_level}",f"Priority: {item.priority_score}/100 {item.priority_level}",f"Status: {item.status}",f"Duplicate reports: {item.duplicate_count}","",f"Description: {item.description}"]:
        text.textLine(row)
    pdf.drawText(text); pdf.showPage(); pdf.save(); stream.seek(0); return Response(stream.read(),mimetype="application/pdf",headers={"Content-Disposition":f"attachment; filename={item.complaint_code}.pdf"})
