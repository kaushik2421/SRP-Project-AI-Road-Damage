# RoadWatch — AI-Based Road Damage Detection and Intelligent Repair Prioritization

RoadWatch is a Flask municipal workflow application: citizens report geolocated damage, municipal staff prioritize and assign it, repair workers attach evidence, and operators track the status to closure. Dashboard statistics, maps, filtering, notifications, assignments, and PDF reports are database-backed.

## Quick start (Windows / VS Code)

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
python seed.py              # optional, development accounts only
python app.py
```

Open `http://127.0.0.1:5000`. Demo accounts from `seed.py` use the email names `admin@example.test`, `engineer@example.test`, `worker@example.test`, and `citizen@example.test`; their password comes from `DEMO_PASSWORD` (default `ChangeMe123!`).

## Database and migrations

Development intentionally uses SQLite through `DEV_DATABASE_URL`. Production requires a MySQL SQLAlchemy URL and fails clearly if one is not configured:

```sql
CREATE DATABASE road_damage_db CHARACTER SET utf8mb4;
```

Set `DATABASE_URL=mysql+pymysql://USER:PASSWORD@HOST:3306/road_damage_db` and `FLASK_ENV=production`. After installing dependencies, use migrations:

```powershell
flask --app app.py db init
flask --app app.py db migrate -m "initial schema"
flask --app app.py db upgrade
```

## AI model setup

Set `MODEL_PATH=models/road_damage/best.pt` to verified road-damage weights compatible with the installed Ultralytics runtime. The detector loads weights once, uses the runtime's actual `YOLO` API, filters supported classes, saves annotated images, and stores real boxes/confidence values. No fabricated prediction is produced: if weights or Ultralytics are unavailable, reports are still stored with an explicit “model not configured” notice and no detection claim.

Supported configured labels are `Pothole`, `Longitudinal Crack`, `Transverse Crack`, and `Alligator Crack`.

## Test

```powershell
pytest -q
```

## API highlights

- `POST /api/complaints` — multipart citizen report
- `GET /api/complaints` — authenticated, server-side search/filter/pagination
- `GET /api/dashboard` — role-scoped live statistics
- `POST /api/complaints/<id>/assign` — admin assignment
- `POST /api/complaints/<id>/repair` — worker update and repair evidence
- `GET /api/complaints/<id>/report.pdf` — admin PDF export

The severity and priority formulas are configurable engineering heuristics, not claims of scientific or machine-learning validation. Model confidence is shown only as an inference confidence, never as model accuracy.
