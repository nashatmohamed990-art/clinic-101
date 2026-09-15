from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app
from datetime import datetime, date
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import (Appointment, Patient, MedicalRecord, Surgery,
                         PatientFile, Prescription, InventoryItem)
from app.services import (search_patients, get_available_slots, generate_prescription_pdf,
                          save_patient_file, book_appointment)
from functools import wraps


doctor_bp = Blueprint('doctor', __name__)


def doctor_required(f):
    """Decorator: require doctor role."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'doctor':
            flash('Access denied. Doctor only.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ==================== DASHBOARD ====================

@doctor_bp.route('/')
@doctor_bp.route('/dashboard')
@doctor_required
def dashboard():
    """Doctor's main dashboard."""
    today = date.today()
    today_apps = Appointment.query.filter(
        Appointment.appointment_date == today,
        Appointment.is_deleted == False,
        Appointment.status.in_(['pending', 'confirmed'])
    ).order_by(Appointment.time_slot).all()

    upcoming_apps = Appointment.query.filter(
        Appointment.appointment_date > today,
        Appointment.is_deleted == False,
        Appointment.status.in_(['pending', 'confirmed'])
    ).order_by(Appointment.appointment_date, Appointment.time_slot).limit(10).all()

    total_patients = Patient.query.filter(Patient.is_deleted == False).count()
    total_surgeries = Surgery.query.filter(Surgery.is_deleted == False,
                                           Surgery.status == 'scheduled').count()

    return render_template('doctor/dashboard.html',
                           today_apps=today_apps,
                           upcoming_apps=upcoming_apps,
                           total_patients=total_patients,
                           total_surgeries=total_surgeries,
                           today=today)


# ==================== PATIENTS ====================

@doctor_bp.route('/patients')
@doctor_required
def patients():
    """View all patients."""
    query = request.args.get('q', '').strip()
    if query:
        patient_list = search_patients(query)
    else:
        patient_list = Patient.query.filter(Patient.is_deleted == False)\
            .order_by(Patient.created_at.desc()).limit(100).all()
    return render_template('doctor/patients.html', patients=patient_list, query=query)


@doctor_bp.route('/patient/<int:patient_id>')
@doctor_required
def patient_detail(patient_id):
    """Patient detail with all related data."""
    patient = Patient.query.get_or_404(patient_id)
    appointments = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.is_deleted == False
    ).order_by(Appointment.appointment_date.desc()).all()
    medical_record = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(
        MedicalRecord.updated_at.desc()).first()
    surgeries = Surgery.query.filter(
        Surgery.patient_id == patient_id,
        Surgery.is_deleted == False
    ).order_by(Surgery.planned_date.desc()).all()
    files = PatientFile.query.filter(
        PatientFile.patient_id == patient_id,
        PatientFile.is_deleted == False
    ).order_by(PatientFile.uploaded_at.desc()).all()
    prescriptions = Prescription.query.filter_by(patient_id=patient_id).order_by(
        Prescription.created_at.desc()).all()

    return render_template('doctor/patient_detail.html',
                           patient=patient,
                           appointments=appointments,
                           medical_record=medical_record,
                           surgeries=surgeries,
                           files=files,
                           prescriptions=prescriptions)


# ==================== MEDICAL RECORD ====================

@doctor_bp.route('/patient/<int:patient_id>/medical-record', methods=['GET', 'POST'])
@doctor_required
def medical_record(patient_id):
    """Create or edit medical record."""
    patient = Patient.query.get_or_404(patient_id)
    record = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(
        MedicalRecord.updated_at.desc()).first()

    if request.method == 'POST':
        if record:
            # Update existing
            record.personal_info = request.form.get('personal_info', '')
            record.medical_history = request.form.get('medical_history', '')
            record.current_complaint = request.form.get('current_complaint', '')
            record.clinical_examination = request.form.get('clinical_examination', '')
            record.diagnosis = request.form.get('diagnosis', '')
            record.investigations = request.form.get('investigations', '')
            record.treatment_plan = request.form.get('treatment_plan', '')
            record.follow_up_notes = request.form.get('follow_up_notes', '')
            record.additional_notes = request.form.get('additional_notes', '')
            record.updated_at = datetime.utcnow()
            flash('Medical record updated successfully.', 'success')
        else:
            # Create new
            record = MedicalRecord(
                patient_id=patient_id,
                personal_info=request.form.get('personal_info', ''),
                medical_history=request.form.get('medical_history', ''),
                current_complaint=request.form.get('current_complaint', ''),
                clinical_examination=request.form.get('clinical_examination', ''),
                diagnosis=request.form.get('diagnosis', ''),
                investigations=request.form.get('investigations', ''),
                treatment_plan=request.form.get('treatment_plan', ''),
                follow_up_notes=request.form.get('follow_up_notes', ''),
                additional_notes=request.form.get('additional_notes', '')
            )
            db.session.add(record)
            flash('Medical record created successfully.', 'success')

        db.session.commit()
        return redirect(url_for('doctor.patient_detail', patient_id=patient_id))

    return render_template('doctor/medical_record.html', patient=patient, record=record)


# ==================== APPOINTMENTS ====================

@doctor_bp.route('/appointments')
@doctor_required
def appointments():
    """View all appointments."""
    status_filter = request.args.get('status', 'all')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    query = Appointment.query.filter(Appointment.is_deleted == False)

    if status_filter and status_filter != 'all':
        query = query.filter(Appointment.status == status_filter)
    if date_from:
        try:
            query = query.filter(Appointment.appointment_date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Appointment.appointment_date <= datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass

    appointments = query.order_by(Appointment.appointment_date.desc(), Appointment.time_slot).all()
    return render_template('doctor/appointments.html', appointments=appointments,
                           status_filter=status_filter, date_from=date_from, date_to=date_to)


@doctor_bp.route('/appointment/<int:appointment_id>/status', methods=['POST'])
@doctor_required
def update_appointment_status(appointment_id):
    """Update appointment status."""
    appointment = Appointment.query.get_or_404(appointment_id)
    new_status = request.form.get('status')
    valid = ['pending', 'confirmed', 'completed', 'cancelled', 'no_show']
    if new_status in valid:
        appointment.status = new_status
        appointment.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Appointment status updated.', 'success')
    return redirect(request.referrer or url_for('doctor.appointments'))


@doctor_bp.route('/book-appointment', methods=['GET', 'POST'])
@doctor_required
def book_appointment_page():
    """Doctor can book appointment manually."""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        age = request.form.get('age', '').strip()
        gender = request.form.get('gender', '').strip()
        branch = request.form.get('branch', 'fayoum').strip()
        appointment_date = request.form.get('appointment_date', '').strip()
        time_slot = request.form.get('time_slot', '').strip()
        complaint = request.form.get('complaint', '').strip()

        if not all([full_name, phone, age, gender, branch, appointment_date, time_slot]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('doctor.book_appointment_page'))

        try:
            target_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
            appt, patient = book_appointment(
                full_name=full_name, phone=phone, age=int(age), gender=gender,
                appointment_date=target_date, time_slot=time_slot, branch=branch, complaint=complaint
            )
            appt.created_by = current_user.id
            appt.status = 'confirmed'
            db.session.commit()
            flash('Appointment booked and confirmed.', 'success')
            return redirect(url_for('doctor.appointments'))
        except ValueError as e:
            flash(str(e), 'danger')
    
    return render_template('doctor/book_appointment.html')


# ==================== SURGERIES ====================

@doctor_bp.route('/surgeries')
@doctor_required
def surgeries():
    """View all surgeries."""
    status_filter = request.args.get('status', 'all')
    query = Surgery.query.filter(Surgery.is_deleted == False)
    if status_filter and status_filter != 'all':
        query = query.filter(Surgery.status == status_filter)
    surgeries = query.order_by(Surgery.planned_date.desc()).all()
    return render_template('doctor/surgeries.html', surgeries=surgeries, status_filter=status_filter)


@doctor_bp.route('/patient/<int:patient_id>/surgery/add', methods=['GET', 'POST'])
@doctor_required
def add_surgery(patient_id):
    """Add a new surgery."""
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        surgery = Surgery(
            patient_id=patient_id,
            surgery_type=request.form.get('surgery_type', ''),
            planned_date=datetime.strptime(request.form.get('planned_date', ''), '%Y-%m-%d').date(),
            planned_time=request.form.get('planned_time', ''),
            pre_op_notes=request.form.get('pre_op_notes', ''),
            status=request.form.get('status', 'scheduled')
        )
        db.session.add(surgery)
        db.session.commit()
        flash('Surgery scheduled successfully.', 'success')
        return redirect(url_for('doctor.patient_detail', patient_id=patient_id))
    return render_template('doctor/surgery_form.html', patient=patient, surgery=None)


@doctor_bp.route('/surgery/<int:surgery_id>/edit', methods=['GET', 'POST'])
@doctor_required
def edit_surgery(surgery_id):
    """Edit a surgery."""
    surgery = Surgery.query.get_or_404(surgery_id)
    patient = surgery.patient
    if request.method == 'POST':
        surgery.surgery_type = request.form.get('surgery_type', '')
        surgery.planned_date = datetime.strptime(request.form.get('planned_date', ''), '%Y-%m-%d').date()
        surgery.planned_time = request.form.get('planned_time', '')
        surgery.pre_op_notes = request.form.get('pre_op_notes', '')
        surgery.post_op_notes = request.form.get('post_op_notes', '')
        surgery.status = request.form.get('status', 'scheduled')
        surgery.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Surgery updated successfully.', 'success')
        return redirect(url_for('doctor.patient_detail', patient_id=patient.id))
    return render_template('doctor/surgery_form.html', patient=patient, surgery=surgery)


# ==================== FILES ====================

@doctor_bp.route('/patient/<int:patient_id>/files/upload', methods=['POST'])
@doctor_required
def upload_file(patient_id):
    """Upload a file for a patient."""
    patient = Patient.query.get_or_404(patient_id)
    files = request.files.getlist('files')
    
    if not files:
        flash('No files selected.', 'danger')
        return redirect(url_for('doctor.patient_detail', patient_id=patient_id))

    uploaded_count = 0
    for f in files:
        if f and f.filename:
            try:
                save_patient_file(patient_id, f)
                uploaded_count += 1
            except ValueError as e:
                flash(f'Error uploading {f.filename}: {e}', 'danger')

    if uploaded_count > 0:
        flash(f'{uploaded_count} file(s) uploaded successfully.', 'success')
    return redirect(url_for('doctor.patient_detail', patient_id=patient_id))


@doctor_bp.route('/file/<int:file_id>/download')
@doctor_required
def download_file(file_id):
    """Download a patient file."""
    pf = PatientFile.query.get_or_404(file_id)
    return send_file(pf.file_path, download_name=pf.original_filename, as_attachment=True)


@doctor_bp.route('/file/<int:file_id>/delete', methods=['POST'])
@doctor_required
def delete_file(file_id):
    """Soft-delete a patient file."""
    pf = PatientFile.query.get_or_404(file_id)
    pf.is_deleted = True
    db.session.commit()
    flash('File removed.', 'success')
    return redirect(request.referrer or url_for('doctor.dashboard'))


# ==================== PRESCRIPTIONS ====================

@doctor_bp.route('/patient/<int:patient_id>/prescription', methods=['GET', 'POST'])
@doctor_required
def create_prescription(patient_id):
    """Create electronic prescription."""
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        diagnosis = request.form.get('diagnosis', '').strip()
        content = request.form.get('content', '').strip()
        if not content:
            flash('Prescription content is required.', 'danger')
            return render_template('doctor/prescription_form.html', patient=patient, content=content, diagnosis=diagnosis)

        prescription = Prescription(patient_id=patient_id, diagnosis=diagnosis, content=content)
        db.session.add(prescription)
        db.session.commit()

        # Generate PDF
        try:
            pdf_path = generate_prescription_pdf(prescription.id)
            flash('Prescription created. PDF generated successfully.', 'success')
            return send_file(pdf_path, download_name=f'prescription_{patient_id}.pdf', as_attachment=True)
        except Exception as e:
            flash(f'Prescription saved but PDF generation failed: {e}', 'warning')
            return redirect(url_for('doctor.patient_detail', patient_id=patient_id))

    return render_template('doctor/prescription_form.html', patient=patient, content='', diagnosis='')


@doctor_bp.route('/prescription/<int:prescription_id>/pdf')
@doctor_required
def prescription_pdf(prescription_id):
    """Download/generate prescription PDF."""
    prescription = Prescription.query.get_or_404(prescription_id)
    try:
        pdf_path = generate_prescription_pdf(prescription.id)
        return send_file(pdf_path, download_name=f'prescription_{prescription.patient_id}.pdf', as_attachment=True)
    except Exception as e:
        flash(f'PDF generation failed: {e}', 'danger')
        return redirect(url_for('doctor.patient_detail', patient_id=prescription.patient_id))


# ==================== INVENTORY ====================

@doctor_bp.route('/inventory')
@doctor_required
def inventory():
    """List inventory items (OR tools, medicines, injections, supplies)."""
    branch = request.args.get('branch', '')
    category = request.args.get('category', '')
    show = request.args.get('show', '')  # 'low' or 'expiring'

    query = InventoryItem.query.filter_by(is_deleted=False)
    if branch:
        query = query.filter_by(branch=branch)
    if category:
        query = query.filter_by(category=category)

    items = query.order_by(InventoryItem.category, InventoryItem.name).all()

    if show == 'low':
        items = [i for i in items if i.is_low_stock]
    elif show == 'expiring':
        items = [i for i in items if i.is_expiring_soon]

    low_stock_count = len([i for i in InventoryItem.query.filter_by(is_deleted=False).all() if i.is_low_stock])
    expiring_count = len([i for i in InventoryItem.query.filter_by(is_deleted=False).all() if i.is_expiring_soon])

    return render_template('doctor/inventory.html', items=items, categories=InventoryItem.CATEGORIES,
                           branch=branch, category=category, show=show,
                           low_stock_count=low_stock_count, expiring_count=expiring_count)


@doctor_bp.route('/inventory/add', methods=['GET', 'POST'])
@doctor_required
def add_inventory_item():
    """Add a new inventory item."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', 'other')
        branch = request.form.get('branch', 'fayoum')
        quantity = request.form.get('quantity', '0').strip()
        unit = request.form.get('unit', '').strip()
        minimum_quantity = request.form.get('minimum_quantity', '0').strip()
        expiry_date = request.form.get('expiry_date', '').strip()
        notes = request.form.get('notes', '').strip()

        if not name:
            flash('Item name is required.', 'danger')
            return redirect(url_for('doctor.add_inventory_item'))

        item = InventoryItem(
            name=name,
            category=category if category in InventoryItem.CATEGORIES else 'other',
            branch=branch,
            quantity=int(quantity) if quantity.isdigit() else 0,
            unit=unit or None,
            minimum_quantity=int(minimum_quantity) if minimum_quantity.isdigit() else 0,
            expiry_date=datetime.strptime(expiry_date, '%Y-%m-%d').date() if expiry_date else None,
            notes=notes or None
        )
        db.session.add(item)
        db.session.commit()
        flash('Item added to inventory.', 'success')
        return redirect(url_for('doctor.inventory'))

    return render_template('doctor/inventory_form.html', item=None, categories=InventoryItem.CATEGORIES)


@doctor_bp.route('/inventory/<int:item_id>/edit', methods=['GET', 'POST'])
@doctor_required
def edit_inventory_item(item_id):
    """Edit an inventory item."""
    item = InventoryItem.query.get_or_404(item_id)

    if request.method == 'POST':
        item.name = request.form.get('name', '').strip() or item.name
        item.category = request.form.get('category', item.category)
        item.branch = request.form.get('branch', item.branch)
        quantity = request.form.get('quantity', '').strip()
        minimum_quantity = request.form.get('minimum_quantity', '').strip()
        item.quantity = int(quantity) if quantity.isdigit() else item.quantity
        item.minimum_quantity = int(minimum_quantity) if minimum_quantity.isdigit() else item.minimum_quantity
        item.unit = request.form.get('unit', '').strip() or None
        expiry_date = request.form.get('expiry_date', '').strip()
        item.expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date() if expiry_date else None
        item.notes = request.form.get('notes', '').strip() or None
        item.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Item updated.', 'success')
        return redirect(url_for('doctor.inventory'))

    return render_template('doctor/inventory_form.html', item=item, categories=InventoryItem.CATEGORIES)


@doctor_bp.route('/inventory/<int:item_id>/adjust', methods=['POST'])
@doctor_required
def adjust_inventory_item(item_id):
    """Quickly increase/decrease the quantity of an item (+/- buttons)."""
    item = InventoryItem.query.get_or_404(item_id)
    delta = request.form.get('delta', '0')
    try:
        delta = int(delta)
    except ValueError:
        delta = 0
    item.quantity = max(0, item.quantity + delta)
    item.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for('doctor.inventory', branch=request.form.get('branch', ''), category=request.form.get('category', '')))


@doctor_bp.route('/inventory/<int:item_id>/delete', methods=['POST'])
@doctor_required
def delete_inventory_item(item_id):
    """Soft-delete an inventory item."""
    item = InventoryItem.query.get_or_404(item_id)
    item.is_deleted = True
    db.session.commit()
    flash('Item removed from inventory.', 'success')
    return redirect(url_for('doctor.inventory'))
