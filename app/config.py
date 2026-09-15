import os
import secrets
from datetime import timedelta

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Load a .env file if present (local secrets, never shipped/committed).
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(basedir, '.env'))
except ImportError:
    pass


def _get_or_create_secret_key():
    """Use SECRET_KEY from the environment if set. Otherwise, generate one
    and persist it locally so it stays stable across restarts (a random key
    that changes on every restart would silently log everyone out and
    invalidate all CSRF tokens). Never hardcode a shared secret in source
    control — that would let anyone who ever saw this code forge sessions.
    """
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key

    instance_dir = os.path.join(basedir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    key_path = os.path.join(instance_dir, 'secret_key.txt')
    if os.path.exists(key_path):
        with open(key_path, 'r') as f:
            return f.read().strip()

    new_key = secrets.token_hex(32)
    with open(key_path, 'w') as f:
        f.write(new_key)
    return new_key


class Config:
    """Base configuration shared by all environments."""
    SECRET_KEY = _get_or_create_secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', f'sqlite:///{os.path.join(basedir, "clinic.db")}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}
    SLOT_DURATION_MINUTES = 20  # Default slot duration
    WORKING_DAYS = [0, 1, 2, 3, 4, 5, 6]  # Mon=0 to Sun=6; clinic is open every day
    WORKING_HOURS_START = '09:00'
    WORKING_HOURS_END = '17:00'
    CLINIC_NAME_AR = 'مركز الفايدي'
    CLINIC_NAME_EN = 'ALFAIDY CENTER'
    DOCTOR_NAME = 'Dr. Hisham'
    DOCTOR_TITLE = 'General Surgeon'

    # --- Session / cookie security ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # SESSION_COOKIE_SECURE is enabled in ProductionConfig (requires HTTPS to work at all).
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = False

    # --- Official prescription letterhead (matches the printed paper form) ---
    CLINIC_NAME_AR_FULL = 'مركز الفايدي للجراحات العامة'
    CLINIC_NAME_EN_LINE1 = 'ALFAIDY CENTER'
    CLINIC_NAME_EN_LINE2 = 'for General Surgery'

    # WhatsApp number the "fully booked" box links to (international format, no + or spaces, e.g. 201012345678).
    # Leave empty to hide the WhatsApp button.
    ASSISTANT_WHATSAPP_NUMBER = os.environ.get('ASSISTANT_WHATSAPP_NUMBER', '')

    # --- Branches (shown in the booking form so patients pick a center) ---
    BRANCHES = [
        {'key': 'fayoum', 'name_ar': 'الفيوم', 'name_en': 'Fayoum'},
        {'key': 'abshway', 'name_ar': 'ابشواي', 'name_en': 'Abshway'},
    ]
    CLINIC_BRANCHES = [
        {
            'address': 'الفيوم - أمام سيتي بلازا - برج كيان - الدور الأول - أعلى توكيل LG',
            'phone_label': 'للتواصل والاستعلام',
            'phone': '0842035105 - 01040014047',
        },
        {
            'address': 'ابشواي - المحطة - بجوار مسجد الشيخ عبدالعليم - برج العمدة حسين العلواني الدور الأرضي',
            'phone_label': 'للتواصل والاستعلام',
            'phone': '01013660813',
        },
    ]


class DevelopmentConfig(Config):
    """Used for local development only. Never deploy with this."""
    DEBUG = True


class ProductionConfig(Config):
    """Used for the real deployment the doctor/clinic actually runs."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True   # Cookies only sent over HTTPS
    REMEMBER_COOKIE_SECURE = True


def get_config():
    """Pick the config class based on FLASK_ENV. Defaults to production
    (the safe choice) unless explicitly told this is development.
    """
    env = os.environ.get('FLASK_ENV', 'production').lower()
    return DevelopmentConfig if env == 'development' else ProductionConfig
