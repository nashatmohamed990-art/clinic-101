from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[])


def create_app(config_class=None):
    """Application factory."""
    from app.config import get_config

    app = Flask(__name__,
                template_folder='templates',
                static_folder='static',
                static_url_path='/static')

    app.config.from_object(config_class or get_config())

    # Ensure upload directories exist
    upload_base = app.config['UPLOAD_FOLDER']
    for subdir in ['patients', 'surgeries']:
        os.makedirs(os.path.join(upload_base, subdir), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'يرجى تسجيل الدخول أولاً'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.patient import patient_bp
    from app.routes.assistant import assistant_bp
    from app.routes.doctor import doctor_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(patient_bp)
    app.register_blueprint(assistant_bp, url_prefix='/assistant')
    app.register_blueprint(doctor_bp, url_prefix='/doctor')

    # Exempt public API endpoints from CSRF
    from app.routes.patient import get_slots
    csrf.exempt(get_slots)

    # Basic security headers on every response. A reverse proxy (nginx) should
    # additionally terminate HTTPS and add HSTS in front of this app.
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    # Context processors
    @app.context_processor
    def inject_clinic_info():
        return {
            'clinic_name_ar': app.config.get('CLINIC_NAME_AR', 'مركز الفايدي'),
            'clinic_name_en': app.config.get('CLINIC_NAME_EN', 'ALFAIDY CENTER'),
            'doctor_name': app.config.get('DOCTOR_NAME', 'Dr. Hisham'),
            'doctor_title': app.config.get('DOCTOR_TITLE', 'General Surgeon'),
            'branches': app.config.get('BRANCHES', []),
        }

    # Create tables
    with app.app_context():
        db.create_all()

    return app
