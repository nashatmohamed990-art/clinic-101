from datetime import datetime, date
from flask_login import UserMixin
from app import db


class User(UserMixin, db.Model):
    """System users: assistants and doctor."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'doctor' or 'assistant'
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    appointments_created = db.relationship('Appointment', backref='created_by_user', lazy='dynamic')

    def is_doctor(self):
        return self.role == 'doctor'

    def is_assistant(self):
        return self.role == 'assistant'


class Patient(db.Model):
    """Patient records."""
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False, index=True)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10), nullable=True)  # ذكر / أنثى
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)

    # Relationships
    appointments = db.relationship('Appointment', backref='patient', lazy='dynamic',
                                    primaryjoin='and_(Patient.id == Appointment.patient_id, Appointment.is_deleted == False)')
    medical_records = db.relationship('MedicalRecord', backref='patient', lazy='dynamic')
    surgeries = db.relationship('Surgery', backref='patient', lazy='dynamic',
                                 primaryjoin='and_(Patient.id == Surgery.patient_id, Surgery.is_deleted == False)')
    files = db.relationship('PatientFile', backref='patient', lazy='dynamic',
                             primaryjoin='and_(Patient.id == PatientFile.patient_id, PatientFile.is_deleted == False)')
    prescriptions = db.relationship('Prescription', backref='patient', lazy='dynamic')

    @property
    def display_gender(self):
        return 'Male' if self.gender == 'ذكر' else ('Female' if self.gender == 'أنثى' else 'N/A')


class Appointment(db.Model):
    """Appointments booked by patients or assistants."""
    __tablename__ = 'appointments'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    appointment_date = db.Column(db.Date, nullable=False, index=True)
    time_slot = db.Column(db.String(5), nullable=True)  # 'HH:MM' format; null while on the waitlist
    branch = db.Column(db.String(20), nullable=False, default='fayoum', index=True)  # 'fayoum' or 'abshway'
    is_waitlisted = db.Column(db.Boolean, default=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    # Statuses: pending, confirmed, completed, cancelled, no_show
    notes = db.Column(db.Text, nullable=True)
    complaint = db.Column(db.Text, nullable=True)  # Patient's initial complaint
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)

    @property
    def branch_display_ar(self):
        return {'fayoum': 'الفيوم', 'abshway': 'ابشواي'}.get(self.branch, self.branch)

    @property
    def branch_display_en(self):
        return {'fayoum': 'Fayoum', 'abshway': 'Abshway'}.get(self.branch, self.branch)

    @property
    def status_display_ar(self):
        mapping = {
            'pending': 'في الانتظار',
            'confirmed': 'مؤكد',
            'completed': 'مكتمل',
            'cancelled': 'ملغي',
            'no_show': 'لم يحضر',
        }
        return mapping.get(self.status, self.status)

    @property
    def status_color(self):
        mapping = {
            'pending': 'yellow',
            'confirmed': 'blue',
            'completed': 'green',
            'cancelled': 'red',
            'no_show': 'gray',
        }
        return mapping.get(self.status, 'gray')


class MedicalRecord(db.Model):
    """Full medical sheet for a patient."""
    __tablename__ = 'medical_records'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    personal_info = db.Column(db.Text, nullable=True)
    medical_history = db.Column(db.Text, nullable=True)
    current_complaint = db.Column(db.Text, nullable=True)
    clinical_examination = db.Column(db.Text, nullable=True)
    diagnosis = db.Column(db.Text, nullable=True)
    investigations = db.Column(db.Text, nullable=True)
    treatment_plan = db.Column(db.Text, nullable=True)
    follow_up_notes = db.Column(db.Text, nullable=True)
    additional_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Surgery(db.Model):
    """Surgery scheduling and records."""
    __tablename__ = 'surgeries'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    surgery_type = db.Column(db.String(255), nullable=False)
    planned_date = db.Column(db.Date, nullable=False)
    planned_time = db.Column(db.String(5), nullable=True)  # 'HH:MM'
    pre_op_notes = db.Column(db.Text, nullable=True)
    post_op_notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='scheduled')
    # Statuses: scheduled, done, cancelled, postponed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)

    @property
    def status_display(self):
        mapping = {
            'scheduled': 'Scheduled',
            'done': 'Done',
            'cancelled': 'Cancelled',
            'postponed': 'Postponed',
        }
        return mapping.get(self.status, self.status)

    @property
    def status_display_ar(self):
        mapping = {
            'scheduled': 'مجدول',
            'done': 'تم',
            'cancelled': 'ملغي',
            'postponed': 'مؤجل',
        }
        return mapping.get(self.status, self.status)


class PatientFile(db.Model):
    """Uploaded files linked to patients."""
    __tablename__ = 'patient_files'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)  # Stored filename
    original_filename = db.Column(db.String(255), nullable=False)  # Original upload name
    file_path = db.Column(db.String(500), nullable=False)  # Full path
    file_type = db.Column(db.String(50), nullable=True)  # MIME type
    file_size = db.Column(db.Integer, nullable=True)  # Size in bytes
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)


class Prescription(db.Model):
    """Electronic prescriptions."""
    __tablename__ = 'prescriptions'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, index=True)
    diagnosis = db.Column(db.String(255), nullable=True)  # Shown in the "Diagnosis" field on the printed form
    content = db.Column(db.Text, nullable=False)  # Free-text prescription content (the blank Rx area)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships


class ClinicSetting(db.Model):
    """Clinic configuration settings."""
    __tablename__ = 'clinic_settings'

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=True)

    @staticmethod
    def get(key, default=None):
        setting = ClinicSetting.query.filter_by(setting_key=key).first()
        return setting.setting_value if setting else default

    @staticmethod
    def set(key, value):
        setting = ClinicSetting.query.filter_by(setting_key=key).first()
        if setting:
            setting.setting_value = value
        else:
            setting = ClinicSetting(setting_key=key, setting_value=value)
            db.session.add(setting)
        db.session.commit()
        return setting


class InventoryItem(db.Model):
    """Operating-room tools, medicines, injections, and other clinic supplies."""
    __tablename__ = 'inventory_items'

    CATEGORIES = {
        'instrument': 'أدوات غرفة العمليات',
        'medicine': 'أدوية',
        'injection': 'حقن',
        'supply': 'مستلزمات طبية',
        'other': 'أخرى',
    }

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(20), nullable=False, default='other')  # key from CATEGORIES
    branch = db.Column(db.String(20), nullable=False, default='fayoum', index=True)  # 'fayoum' or 'abshway'
    quantity = db.Column(db.Integer, nullable=False, default=0)
    unit = db.Column(db.String(30), nullable=True)  # e.g. 'قطعة', 'أمبولة', 'عبوة', 'شريط'
    minimum_quantity = db.Column(db.Integer, nullable=False, default=0)  # alert threshold
    expiry_date = db.Column(db.Date, nullable=True)  # relevant for medicines/injections
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)

    @property
    def category_display_ar(self):
        return self.CATEGORIES.get(self.category, self.category)

    @property
    def branch_display_ar(self):
        return {'fayoum': 'الفيوم', 'abshway': 'ابشواي'}.get(self.branch, self.branch)

    @property
    def branch_display_en(self):
        return {'fayoum': 'Fayoum', 'abshway': 'Abshway'}.get(self.branch, self.branch)

    @property
    def is_low_stock(self):
        return self.quantity <= self.minimum_quantity

    @property
    def is_expiring_soon(self):
        """True if the item expires within 60 days (or has already expired)."""
        if not self.expiry_date:
            return False
        return (self.expiry_date - date.today()).days <= 60

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        return self.expiry_date < date.today()
