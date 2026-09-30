"""Development-only demo seed. Run manually: python seed.py"""
import os
from app import create_app
from app.extensions import db
from app.models import User, Worker

app=create_app()
with app.app_context():
    db.create_all(); password=os.getenv("DEMO_PASSWORD","ChangeMe123!")
    for name,email,role in [("Municipal Admin","admin@example.test","MUNICIPAL_ADMIN"),("City Engineer","engineer@example.test","ENGINEER"),("Repair Worker","worker@example.test","WORKER"),("Demo Citizen","citizen@example.test","CITIZEN")]:
        user=User.query.filter_by(email=email).first()
        if not user:
            user=User(full_name=name,email=email,role=role,phone="0000000000");user.set_password(password);db.session.add(user);db.session.flush()
            if role in {"WORKER","ENGINEER"}:db.session.add(Worker(user_id=user.id,specialization="Road repair"))
    db.session.commit();print("Development accounts created. No sample complaints are generated automatically.")
