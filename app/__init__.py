import logging
from pathlib import Path
from flask import Flask, jsonify, render_template, request
from config import DevelopmentConfig
from .extensions import db, login_manager, migrate
from .models import User


def create_app(config_object=DevelopmentConfig):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(config_object)
    if hasattr(config_object, "validate"): config_object.validate()
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    db.init_app(app); login_manager.init_app(app); migrate.init_app(app, db)
    with app.app_context():
        db.create_all()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from .routes import auth_bp, citizen_bp, admin_bp, municipal_bp, worker_bp, api_bp
    for blueprint in (auth_bp, citizen_bp, admin_bp, municipal_bp, worker_bp, api_bp): app.register_blueprint(blueprint)
    @app.get("/")
    def landing(): return render_template("landing.html")
    @app.errorhandler(400)
    def bad_request(_):
        if request.path.startswith('/api/'):
            return jsonify(error="Bad request."), 400
        return render_template("error.html", code=400, message="The request could not be processed."), 400
    @app.errorhandler(401)
    def unauthorized(_):
        if request.path.startswith('/api/'):
            return jsonify(error="Authentication required."), 401
        return render_template("error.html", code=401, message="Please log in to continue."), 401
    @app.errorhandler(403)
    def forbidden(_):
        if request.path.startswith('/api/'):
            return jsonify(error="You do not have permission to access this resource."), 403
        return render_template("error.html", code=403, message="You do not have permission to access this resource."), 403
    @app.errorhandler(404)
    def not_found(_):
        if request.path.startswith('/api/'):
            return jsonify(error="Not found."), 404
        return render_template("error.html", code=404, message="The page you requested does not exist."), 404
    @app.errorhandler(413)
    def too_large(_): return jsonify(error="Image exceeds the 10 MB limit."),413
    @app.errorhandler(500)
    def server_error(_):
        app.logger.exception("Unhandled server error")
        if request.path.startswith('/api/'):
            return jsonify(error="An internal server error occurred."), 500
        return render_template("error.html", code=500, message="Something went wrong while processing your request."), 500
    @login_manager.user_loader
    def load_user(user_id): return db.session.get(User, int(user_id))
    return app
