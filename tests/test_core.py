import io
from PIL import Image
from app import create_app
from app.extensions import db
from app.models import User, Worker
from config import TestingConfig


def app():
    instance=create_app(TestingConfig)
    with instance.app_context(): db.create_all()
    return instance


def test_register_and_protected_dashboard():
    client=app().test_client(); response=client.post('/auth/register',data={'full_name':'A Citizen','email':'a@example.test','phone':'','password':'Password123'},follow_redirects=True)
    assert response.status_code==200 and b'Welcome back, A.' in response.data and b'Recent reports' in response.data


def test_citizen_cannot_access_admin():
    client=app().test_client();client.post('/auth/register',data={'full_name':'A Citizen','email':'a@example.test','phone':'','password':'Password123'})
    assert client.get('/admin/dashboard').status_code==403


def test_register_works_without_manual_table_creation():
    client=create_app(TestingConfig).test_client()
    response=client.post('/auth/register',data={'full_name':'Fresh User','email':'fresh@example.test','phone':'','password':'Password123'},follow_redirects=True)
    assert response.status_code==200 and b'Welcome back, Fresh.' in response.data and b'Your road safety impact' in response.data


def test_municipal_login_and_protected_access():
    app_instance = create_app(TestingConfig)
    with app_instance.app_context():
        from app.models import User
        user = User(full_name='Municipal Officer', email='municipal@example.test', phone='000', role='MUNICIPAL_ADMIN')
        user.set_password('Password123')
        from app.extensions import db
        db.session.add(user); db.session.commit()
    client = app_instance.test_client()
    response = client.post('/municipal/login', data={'email':'municipal@example.test','password':'Password123'}, follow_redirects=True)
    assert response.status_code==200 and b'City road intelligence' in response.data and b'Priority queue' in response.data
    assert client.get('/citizen/dashboard').status_code==403
    for path in ['/municipal/priority','/municipal/severity','/municipal/analytics','/municipal/map']:
        page=client.get(path)
        assert page.status_code==200


def test_municipal_admin_can_view_and_manage_submitted_complaints():
    app_instance=create_app(TestingConfig)
    with app_instance.app_context():
        municipal=User(full_name='Municipal Officer',email='officer@example.test',phone='',role='MUNICIPAL_ADMIN')
        municipal.set_password('Password123')
        worker_user=User(full_name='Field Worker',email='worker@example.test',phone='',role='WORKER')
        worker_user.set_password('Password123')
        db.session.add(worker_user)
        db.session.flush()
        worker=Worker(user_id=worker_user.id)
        db.session.add(municipal)
        db.session.add(worker)
        db.session.flush()
        worker_id=worker.id
        db.session.commit()

    citizen_client=app_instance.test_client()
    citizen_client.post('/auth/register',data={'full_name':'Reporting Citizen','email':'reporter@example.test','phone':'','password':'Password123'})
    image=io.BytesIO()
    Image.new('RGB',(32,32),'gray').save(image,format='JPEG')
    image.seek(0)
    submitted=citizen_client.post('/api/complaints',data={'latitude':'37.5','longitude':'-122.2','road_category':'Local','road_name':'Main Street','description':'Large pothole near the crossing','image':(image,'road.jpg')},content_type='multipart/form-data')
    assert submitted.status_code==201

    municipal_client=app_instance.test_client()
    municipal_client.post('/municipal/login',data={'email':'officer@example.test','password':'Password123'})
    response=municipal_client.get('/api/complaints')
    assert response.status_code==200
    assert any(item['code']==submitted.json['code'] for item in response.json['items'])
    complaint_id=submitted.json['id']
    assigned=municipal_client.post(f'/api/complaints/{complaint_id}/assign',json={'worker_id':worker_id})
    assert assigned.status_code==200
    changed=municipal_client.post(f'/api/complaints/{complaint_id}/status',json={'status':'UNDER_REVIEW'})
    assert changed.status_code==200
    report=municipal_client.get(f'/api/complaints/{complaint_id}/report.pdf')
    assert report.status_code==200 and report.mimetype=='application/pdf'


def test_municipal_admin_can_view_worker_availability():
    app_instance=create_app(TestingConfig)
    with app_instance.app_context():
        municipal=User(full_name='Municipal Officer',email='officer@example.test',phone='',role='MUNICIPAL_ADMIN')
        municipal.set_password('Password123')
        worker_user=User(full_name='Field Worker',email='worker@example.test',phone='',role='WORKER')
        worker_user.set_password('Password123')
        db.session.add_all([municipal,worker_user])
        db.session.flush()
        db.session.add(Worker(user_id=worker_user.id,availability=False))
        db.session.commit()

    client=app_instance.test_client()
    client.post('/municipal/login',data={'email':'officer@example.test','password':'Password123'})
    response=client.get('/api/workers')
    assert response.status_code==200
    assert response.json['items'][0]['name']=='Field Worker'
    assert response.json['items'][0]['availability'] is False


def test_invalid_coordinates_rejected():
    client=app().test_client();client.post('/auth/register',data={'full_name':'A Citizen','email':'a@example.test','phone':'','password':'Password123'})
    response=client.post('/api/complaints',data={'latitude':'400','longitude':'90','road_category':'Local','road_name':'Main','description':'Large pothole near crossing'})
    assert response.status_code==400 and b'location' in response.data


def test_citizen_can_submit_report_without_configured_ai_model():
    client=app().test_client()
    client.post('/auth/register',data={'full_name':'A Citizen','email':'reporter@example.test','phone':'','password':'Password123'})
    image=io.BytesIO()
    Image.new('RGB',(32,32),'gray').save(image,format='JPEG')
    image.seek(0)
    response=client.post('/api/complaints',data={'latitude':'37.5','longitude':'-122.2','road_category':'Local','road_name':'Main Street','description':'Large pothole near the crossing','image':(image,'road.jpg')},content_type='multipart/form-data')
    assert response.status_code==201
    assert response.json['ai_warning']
    assert response.json['latitude']==37.5


def test_forbidden_api_request_returns_json_error():
    client=app().test_client()
    client.post('/auth/register',data={'full_name':'A Citizen','email':'citizen@example.test','phone':'','password':'Password123'})
    response=client.get('/api/workers')
    assert response.status_code==403
    assert response.is_json
    assert 'permission' in response.json['error']
