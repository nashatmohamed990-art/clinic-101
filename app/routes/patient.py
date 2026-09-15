from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from datetime import datetime, date, timedelta
from app import db
from app.models import Appointment, Patient
from app.services import get_available_slots, book_appointment, get_waitlist_count, waitlist_position, is_working_day


patient_bp = Blueprint('patient', __name__)

VALID_BRANCHES = ('fayoum', 'abshway')


@patient_bp.route('/')
def booking_page():
    """Main patient booking page."""
    return render_template('patient/booking.html')


@patient_bp.route('/slots', methods=['POST'])
def get_slots():
    """AJAX endpoint: get available slots for a date at a branch."""
    date_str = request.json.get('date')
    branch = request.json.get('branch', 'fayoum')
    if branch not in VALID_BRANCHES:
        branch = 'fayoum'
    if not date_str:
        return jsonify({'slots': [], 'error': 'Date required'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'slots': [], 'error': 'Invalid date format'}), 400

    # Don't allow booking past dates
    if target_date < date.today():
        return jsonify({'slots': [], 'error': 'Cannot book past dates'})

    slots = get_available_slots(target_date, branch=branch)
    open_day = is_working_day(target_date)
    waitlist_count = get_waitlist_count(target_date, branch=branch) if (not slots and open_day) else 0
    return jsonify({
        'slots': slots,
        'date': date_str,
        'branch': branch,
        'day_name': _arabic_day(target_date),
        'is_working_day': open_day,
        'waitlist_count': waitlist_count,
        'whatsapp_number': current_app.config.get('ASSISTANT_WHATSAPP_NUMBER', '')
    })


def _arabic_day(d):
    """Return Arabic day name."""
    days = {
        0: 'الإثنين', 1: 'الثلاثاء', 2: 'الأربعاء',
        3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'
    }
    return days.get(d.weekday(), '')


@patient_bp.route('/book', methods=['POST'])
def book():
    """Handle appointment booking submission."""
    full_name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    age = request.form.get('age', '').strip()
    gender = request.form.get('gender', '').strip()
    branch = request.form.get('branch', '').strip()
    appointment_date = request.form.get('appointment_date', '').strip()
    time_slot = request.form.get('time_slot', '').strip()
    join_waitlist = request.form.get('join_waitlist', '').strip() == '1'
    complaint = request.form.get('complaint', '').strip()

    # Validation
    errors = []
    if not full_name or len(full_name) < 3:
        errors.append('يرجى إدخال الاسم الكامل (3 أحرف على الأقل)')
    if not phone or len(phone) < 10:
        errors.append('يرجى إدخال رقم موبايل صحيح')
    if not age or not age.isdigit() or int(age) < 1 or int(age) > 150:
        errors.append('يرجى إدخال سن صحيح')
    if gender not in ('ذكر', 'أنثى'):
        errors.append('يرجى اختيار النوع')
    if branch not in VALID_BRANCHES:
        errors.append('يرجى اختيار الفرع')
    if not appointment_date:
        errors.append('يرجى اختيار اليوم')
    if not time_slot and not join_waitlist:
        errors.append('يرجى اختيار الموعد')

    if errors:
        for e in errors:
            flash(e, 'danger')
        return redirect(url_for('patient.booking_page'))

    try:
        target_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
        appointment, patient = book_appointment(
            full_name=full_name,
            phone=phone,
            age=int(age),
            gender=gender,
            appointment_date=target_date,
            time_slot=time_slot if time_slot else None,
            branch=branch,
            complaint=complaint if complaint else None
        )
        if appointment.is_waitlisted:
            flash('المواعيد ممتلئة، وتم إضافتك لقائمة الانتظار!', 'success')
        else:
            flash('تم حجز الموعد بنجاح!', 'success')
        return redirect(url_for('patient.confirmation', appointment_id=appointment.id))
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('patient.booking_page'))


@patient_bp.route('/confirmation/<int:appointment_id>')
def confirmation(appointment_id):
    """Show appointment confirmation."""
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.is_deleted:
        flash('هذا الموعد غير موجود', 'danger')
        return redirect(url_for('patient.booking_page'))
    position = waitlist_position(appointment) if appointment.is_waitlisted else None
    return render_template('patient/confirmation.html', appointment=appointment, waitlist_position=position)
