from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from datetime import datetime, date
from flask_login import login_required, current_user
from app import db
from app.models import Appointment, Patient, InventoryItem
from app.services import book_appointment, get_available_slots, assign_waitlisted_appointment
from functools import wraps


assistant_bp = Blueprint('assistant', __name__)


def assistant_required(f):
    """Decorator: require assistant role."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'assistant':
            flash('ليس لديك صلاحية الوصول', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@assistant_bp.route('/book', methods=['GET', 'POST'])
@assistant_required
def book_appointment_page():
    """Assistant can book an appointment manually for a patient (e.g. phone booking)."""
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
            flash('يرجى ملء جميع الحقول المطلوبة.', 'danger')
            return redirect(url_for('assistant.book_appointment_page'))

        try:
            target_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
            appt, patient = book_appointment(
                full_name=full_name, phone=phone, age=int(age), gender=gender,
                appointment_date=target_date, time_slot=time_slot, branch=branch, complaint=complaint
            )
            appt.created_by = current_user.id
            appt.status = 'confirmed'
            db.session.commit()
            flash('تم حجز الموعد وتأكيده بنجاح.', 'success')
            return redirect(url_for('assistant.appointments'))
        except ValueError as e:
            flash(str(e), 'danger')

    return render_template('assistant/book_appointment.html')


@assistant_bp.route('/waitlist/<int:appointment_id>/assign', methods=['GET', 'POST'])
@assistant_required
def assign_waitlist_page(appointment_id):
    """Give a waitlisted patient a real slot once one becomes available."""
    appointment = Appointment.query.get_or_404(appointment_id)
    if not appointment.is_waitlisted:
        flash('هذا الموعد ليس في قائمة الانتظار.', 'danger')
        return redirect(url_for('assistant.appointments'))

    if request.method == 'POST':
        appointment_date = request.form.get('appointment_date', '').strip()
        time_slot = request.form.get('time_slot', '').strip()
        if not appointment_date or not time_slot:
            flash('يرجى اختيار اليوم والموعد.', 'danger')
            return redirect(url_for('assistant.assign_waitlist_page', appointment_id=appointment_id))
        try:
            target_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
            assign_waitlisted_appointment(appointment_id, time_slot, appointment_date=target_date)
            flash('تم تعيين الموعد للمريض وتحويله من قائمة الانتظار.', 'success')
            return redirect(url_for('assistant.appointments'))
        except ValueError as e:
            flash(str(e), 'danger')

    return render_template('assistant/assign_waitlist.html', appointment=appointment)


@assistant_bp.route('/')
@assistant_bp.route('/dashboard')
@assistant_required
def dashboard():
    """Main assistant dashboard with today's schedule."""
    today = date.today()
    today_appointments = Appointment.query.filter(
        Appointment.appointment_date == today,
        Appointment.is_deleted == False
    ).order_by(Appointment.time_slot).all()

    # Stats
    total_today = len(today_appointments)
    pending_count = sum(1 for a in today_appointments if a.status == 'pending')
    confirmed_count = sum(1 for a in today_appointments if a.status == 'confirmed')
    completed_count = sum(1 for a in today_appointments if a.status == 'completed')

    return render_template('assistant/dashboard.html',
                           appointments=today_appointments,
                           total_today=total_today,
                           pending_count=pending_count,
                           confirmed_count=confirmed_count,
                           completed_count=completed_count,
                           today=today)


@assistant_bp.route('/appointments')
@assistant_required
def appointments():
    """View all appointments with filters."""
    status_filter = request.args.get('status', 'all')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search = request.args.get('search', '').strip()

    query = Appointment.query.filter(Appointment.is_deleted == False)

    if status_filter and status_filter != 'all':
        query = query.filter(Appointment.status == status_filter)

    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(Appointment.appointment_date >= df)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(Appointment.appointment_date <= dt)
        except ValueError:
            pass

    if search:
        query = query.join(Patient).filter(
            db.or_(
                Patient.full_name.ilike(f'%{search}%'),
                Patient.phone.ilike(f'%{search}%')
            )
        )

    appointments = query.order_by(Appointment.appointment_date.desc(),
                                   Appointment.time_slot).all()

    return render_template('assistant/appointments.html',
                           appointments=appointments,
                           status_filter=status_filter,
                           date_from=date_from,
                           date_to=date_to,
                           search=search)


@assistant_bp.route('/appointment/<int:appointment_id>/update-status', methods=['POST'])
@assistant_required
def update_status(appointment_id):
    """Update appointment status."""
    appointment = Appointment.query.get_or_404(appointment_id)
    new_status = request.form.get('status')

    valid_statuses = ['pending', 'confirmed', 'completed', 'cancelled', 'no_show']
    if new_status not in valid_statuses:
        flash('حالة غير صالحة', 'danger')
        return redirect(request.referrer or url_for('assistant.appointments'))

    appointment.status = new_status
    appointment.updated_at = datetime.utcnow()

    # Add note if provided
    note = request.form.get('note', '').strip()
    if note:
        if appointment.notes:
            appointment.notes += f'\n[{datetime.utcnow().strftime("%Y-%m-%d %H:%M")}] {note}'
        else:
            appointment.notes = f'[{datetime.utcnow().strftime("%Y-%m-%d %H:%M")}] {note}'

    db.session.commit()
    flash('تم تحديث حالة الموعد', 'success')
    return redirect(request.referrer or url_for('assistant.appointments'))


@assistant_bp.route('/search-patients')
@assistant_required
def search_patients():
    """Search patients by name or phone."""
    query = request.args.get('q', '').strip()
    patients = []
    if query and len(query) >= 2:
        patients = Patient.query.filter(
            Patient.is_deleted == False,
            db.or_(
                Patient.full_name.ilike(f'%{query}%'),
                Patient.phone.ilike(f'%{query}%')
            )
        ).order_by(Patient.created_at.desc()).limit(50).all()
    return render_template('assistant/search_patients.html', patients=patients, query=query)


@assistant_bp.route('/patient/<int:patient_id>')
@assistant_required
def patient_detail(patient_id):
    """View patient details and their appointments."""
    patient = Patient.query.get_or_404(patient_id)
    appointments = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.is_deleted == False
    ).order_by(Appointment.appointment_date.desc()).all()
    return render_template('assistant/patient_detail.html',
                           patient=patient, appointments=appointments)


# ==================== INVENTORY (view + quick stock adjust only) ====================

@assistant_bp.route('/inventory')
@assistant_required
def inventory():
    """View inventory. Assistants can adjust quantities but not add/edit/delete items —
    that stays with the doctor to avoid accidental changes to the item list itself."""
    branch = request.args.get('branch', '')
    category = request.args.get('category', '')
    show = request.args.get('show', '')

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

    all_items = InventoryItem.query.filter_by(is_deleted=False).all()
    low_stock_count = len([i for i in all_items if i.is_low_stock])
    expiring_count = len([i for i in all_items if i.is_expiring_soon])

    return render_template('assistant/inventory.html', items=items, categories=InventoryItem.CATEGORIES,
                           branch=branch, category=category, show=show,
                           low_stock_count=low_stock_count, expiring_count=expiring_count)


@assistant_bp.route('/inventory/<int:item_id>/adjust', methods=['POST'])
@assistant_required
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
    return redirect(url_for('assistant.inventory', branch=request.form.get('branch', ''), category=request.form.get('category', '')))
