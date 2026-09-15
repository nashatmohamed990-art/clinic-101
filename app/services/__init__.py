"""Business logic services for the clinic management system."""

from datetime import datetime, date, timedelta, time
from flask import current_app
from app import db
from app.models import (Appointment, Patient, MedicalRecord, Surgery,
                         PatientFile, Prescription, ClinicSetting, User)
from werkzeug.security import generate_password_hash


def is_working_day(target_date):
    """Whether the clinic is open at all on this date (config-driven)."""
    working_days = current_app.config.get('WORKING_DAYS', [0, 1, 2, 3, 4, 5, 6])
    return target_date.weekday() in working_days


def get_available_slots(target_date, branch='fayoum'):
    """Get available time slots for a given date at a given branch.
    Each branch has its own independent set of slots.
    Returns list of available 'HH:MM' strings. Returns [] both when the
    clinic is closed that day AND when the day is fully booked — callers
    that need to tell those apart should check is_working_day() too.
    """
    if not is_working_day(target_date):
        return []

    slot_duration = current_app.config.get('SLOT_DURATION_MINUTES', 20)
    start_h, start_m = map(int, current_app.config.get('WORKING_HOURS_START', '09:00').split(':'))
    end_h, end_m = map(int, current_app.config.get('WORKING_HOURS_END', '17:00').split(':'))

    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m

    # Generate all possible slots
    all_slots = []
    current = start_minutes
    while current + slot_duration <= end_minutes:
        h = current // 60
        m = current % 60
        all_slots.append(f'{h:02d}:{m:02d}')
        current += slot_duration

    # Get booked slots for this date and branch (non-cancelled, non-deleted, non-waitlisted)
    booked = Appointment.query.filter(
        Appointment.appointment_date == target_date,
        Appointment.branch == branch,
        Appointment.is_deleted == False,
        Appointment.is_waitlisted == False,
        Appointment.status.in_(['pending', 'confirmed'])
    ).with_entities(Appointment.time_slot).all()

    booked_slots = {slot[0] for slot in booked}

    # Return available slots
    available = [s for s in all_slots if s not in booked_slots]
    return available


def get_waitlist_count(target_date, branch='fayoum'):
    """How many patients are currently waiting for a slot on this date/branch."""
    return Appointment.query.filter(
        Appointment.appointment_date == target_date,
        Appointment.branch == branch,
        Appointment.is_deleted == False,
        Appointment.is_waitlisted == True,
        Appointment.status == 'pending'
    ).count()


def get_waitlist(target_date=None, branch=None):
    """List waitlisted patients, oldest request first (their booking order)."""
    query = Appointment.query.filter(
        Appointment.is_deleted == False,
        Appointment.is_waitlisted == True,
        Appointment.status == 'pending'
    )
    if target_date:
        query = query.filter(Appointment.appointment_date == target_date)
    if branch:
        query = query.filter(Appointment.branch == branch)
    return query.order_by(Appointment.created_at).all()


def waitlist_position(appointment):
    """1-based position of this appointment in its date/branch waitlist queue."""
    if not appointment.is_waitlisted:
        return None
    return Appointment.query.filter(
        Appointment.appointment_date == appointment.appointment_date,
        Appointment.branch == appointment.branch,
        Appointment.is_deleted == False,
        Appointment.is_waitlisted == True,
        Appointment.status == 'pending',
        Appointment.created_at <= appointment.created_at
    ).count()


def book_appointment(full_name, phone, age, gender, appointment_date, time_slot, branch='fayoum', complaint=None):
    """Book a new appointment, or add to the waitlist if the day is full.

    If time_slot is falsy, or the day has no open slots left at this branch,
    the patient is placed on that date/branch's waitlist (in order) instead
    of being turned away, so they can be booked into the next opening.
    Returns (appointment, patient).
    """
    # Check for existing patient or create new one
    patient = Patient.query.filter_by(phone=phone, is_deleted=False).first()
    if not patient:
        patient = Patient(full_name=full_name, phone=phone, age=age, gender=gender)
        db.session.add(patient)
        db.session.flush()  # Get the ID

    available_today = get_available_slots(appointment_date, branch=branch)

    if not time_slot:
        # No slot was picked because none were available -> join the waitlist,
        # but re-check in case a slot just freed up.
        if available_today:
            raise ValueError('يوجد مواعيد متاحة الآن، برجاء اختيار ميعاد.')
        appointment = Appointment(
            patient_id=patient.id,
            appointment_date=appointment_date,
            time_slot=None,
            branch=branch,
            is_waitlisted=True,
            complaint=complaint,
            status='pending'
        )
        db.session.add(appointment)
        db.session.commit()
        return appointment, patient

    # A specific slot was requested: check for conflict at this branch
    conflict = Appointment.query.filter(
        Appointment.appointment_date == appointment_date,
        Appointment.time_slot == time_slot,
        Appointment.branch == branch,
        Appointment.is_deleted == False,
        Appointment.is_waitlisted == False,
        Appointment.status.in_(['pending', 'confirmed'])
    ).first()

    if conflict:
        raise ValueError('This time slot is already booked.')

    appointment = Appointment(
        patient_id=patient.id,
        appointment_date=appointment_date,
        time_slot=time_slot,
        branch=branch,
        complaint=complaint,
        status='pending'
    )
    db.session.add(appointment)
    db.session.commit()

    return appointment, patient


def assign_waitlisted_appointment(appointment_id, time_slot, appointment_date=None):
    """Staff action: pull a waitlisted patient off the queue and give them a
    real slot (used once the day's booked appointments are done, or a slot
    opens up). Returns the updated Appointment.
    """
    appointment = Appointment.query.get_or_404(appointment_id)
    if not appointment.is_waitlisted:
        raise ValueError('This appointment is not on the waitlist.')

    target_date = appointment_date or appointment.appointment_date

    conflict = Appointment.query.filter(
        Appointment.appointment_date == target_date,
        Appointment.time_slot == time_slot,
        Appointment.branch == appointment.branch,
        Appointment.is_deleted == False,
        Appointment.is_waitlisted == False,
        Appointment.status.in_(['pending', 'confirmed']),
        Appointment.id != appointment.id
    ).first()
    if conflict:
        raise ValueError('This time slot is already booked.')

    appointment.appointment_date = target_date
    appointment.time_slot = time_slot
    appointment.is_waitlisted = False
    appointment.status = 'confirmed'
    appointment.updated_at = datetime.utcnow()
    db.session.commit()
    return appointment


def get_or_create_patient(full_name, phone, age=None, gender=None):
    """Get existing patient by phone or create new one."""
    patient = Patient.query.filter_by(phone=phone, is_deleted=False).first()
    if not patient:
        patient = Patient(full_name=full_name, phone=phone, age=age, gender=gender)
        db.session.add(patient)
        db.session.commit()
    return patient


def search_patients(query):
    """Search patients by name or phone."""
    return Patient.query.filter(
        Patient.is_deleted == False,
        db.or_(
            Patient.full_name.ilike(f'%{query}%'),
            Patient.phone.ilike(f'%{query}%')
        )
    ).order_by(Patient.created_at.desc()).all()


def generate_prescription_pdf(prescription_id):
    """Generate a PDF prescription that matches the clinic's official
    'Al Faidy Center for General Surgery' paper letterhead: blue header
    banner with the bilingual clinic name, a Name/Diagnosis/Age/Date info
    row, a large blank area for the treatment (Rx), and a footer banner
    with both branch addresses, phone numbers, and an emergency line.
    Returns the file path.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import arabic_reshaper
    from bidi.algorithm import get_display
    import os
    import re

    # --- Fonts (bundled with the app, so this works on any deployment) ---
    fonts_dir = os.path.join(current_app.root_path, 'static', 'fonts')
    pdfmetrics.registerFont(TTFont('Arabic', os.path.join(fonts_dir, 'Arabic-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('ArabicBold', os.path.join(fonts_dir, 'Arabic-Bold.ttf')))
    body_font = 'Helvetica'
    bold_font = 'Helvetica-Bold'
    logo_path = os.path.join(current_app.root_path, 'static', 'images', 'logo.png')

    # The bundled Arabic font only has Arabic-script glyphs (no digits, Latin
    # letters, or punctuation), so any mixed text ("الفيوم - ... LG",
    # "0842035105", "Name: دينا محمد") must be drawn run-by-run, switching
    # fonts per run, or the non-Arabic characters render as blank tofu boxes.
    _AR_RANGE = re.compile('[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')

    def _visual(text):
        return get_display(arabic_reshaper.reshape(text)) if text else ''

    def _split_runs(visual_text):
        runs = []
        cur, cur_is_ar = '', None
        for ch in visual_text:
            is_ar = bool(_AR_RANGE.match(ch))
            if cur_is_ar is None or is_ar == cur_is_ar:
                cur += ch
            else:
                runs.append((cur, cur_is_ar))
                cur = ch
            cur_is_ar = is_ar
        if cur:
            runs.append((cur, cur_is_ar))
        return runs

    def draw_mixed(text, x, y, ar_size=11, lat_size=11, ar_bold=False, lat_bold=False,
                    color=black, align='left'):
        """Draw text that may mix Arabic with digits/Latin/punctuation, picking
        the right font per run so nothing renders as a missing-glyph box."""
        ar_f = 'ArabicBold' if ar_bold else 'Arabic'
        lat_f = bold_font if lat_bold else body_font
        runs = _split_runs(_visual(text))
        total = sum(c.stringWidth(r, ar_f if a else lat_f, ar_size if a else lat_size) for r, a in runs)
        if align == 'right':
            cur_x = x - total
        elif align == 'center':
            cur_x = x - total / 2
        else:
            cur_x = x
        c.setFillColor(color)
        for run, is_ar in runs:
            f, sz = (ar_f, ar_size) if is_ar else (lat_f, lat_size)
            c.setFont(f, sz)
            c.drawString(cur_x, y, run)
            cur_x += c.stringWidth(run, f, sz)
        return total

    prescription = Prescription.query.get_or_404(prescription_id)
    patient = prescription.patient
    cfg = current_app.config

    # Output path
    output_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'prescriptions')
    os.makedirs(output_dir, exist_ok=True)
    filename = f'prescription_{prescription_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    filepath = os.path.join(output_dir, filename)

    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    margin = 15 * mm

    navy = HexColor('#1c3f6e')
    teal = HexColor('#2a9d9d')
    text_dark = HexColor('#1f2933')
    grey = HexColor('#6b7280')
    red = HexColor('#c0392b')

    # ================= HEADER BANNER =================
    header_h = 26 * mm
    header_top = height - 12 * mm
    c.setFillColor(navy)
    c.rect(0, header_top - header_h, width, header_h, fill=1, stroke=0)

    # English clinic name (left)
    c.setFillColor(white)
    c.setFont(bold_font, 13)
    c.drawString(margin, header_top - 10 * mm, cfg['CLINIC_NAME_EN_LINE1'])
    c.setFont(body_font, 10)
    c.drawString(margin, header_top - 16 * mm, cfg['CLINIC_NAME_EN_LINE2'])

    # Arabic clinic name (right)
    draw_mixed('مركز الفايدي', width - margin, header_top - 10 * mm,
               ar_size=15, ar_bold=True, color=white, align='right')
    draw_mixed('للجراحات العامة', width - margin, header_top - 17 * mm,
               ar_size=11, color=white, align='right')

    # Center logo (real clinic logo, falls back to a drawn roundel if missing)
    cx, cy = width / 2, header_top - header_h / 2
    logo_r = 11 * mm
    if os.path.exists(logo_path):
        c.drawImage(logo_path, cx - logo_r, cy - logo_r, width=2 * logo_r, height=2 * logo_r,
                    mask='auto', preserveAspectRatio=True)
    else:
        c.setFillColor(white)
        c.circle(cx, cy, logo_r, fill=1, stroke=0)
        c.setStrokeColor(teal)
        c.setLineWidth(1.6)
        c.circle(cx, cy, logo_r, fill=0, stroke=1)
        c.setFillColor(teal)
        c.setFont(bold_font, 20)
        c.drawCentredString(cx, cy - 3.2 * mm, 'H')

    # ================= PATIENT INFO ROW =================
    info_y = header_top - header_h - 14 * mm
    draw_mixed(f"Name: {patient.full_name}", margin, info_y, ar_size=11, lat_size=11,
               ar_bold=True, lat_bold=True, color=text_dark, align='left')
    draw_mixed(f"Age: {patient.age or '—'}", width - margin, info_y, ar_size=11, lat_size=11,
               ar_bold=True, lat_bold=True, color=text_dark, align='right')

    info_y2 = info_y - 8 * mm
    diagnosis_text = prescription.diagnosis or '—'
    draw_mixed(f"Diagnosis: {diagnosis_text}", margin, info_y2, ar_size=11, lat_size=11,
               ar_bold=True, lat_bold=True, color=text_dark, align='left')
    draw_mixed(f"Date: {prescription.created_at.strftime('%d/%m/%Y')}", width - margin, info_y2,
               ar_size=11, lat_size=11, ar_bold=True, lat_bold=True, color=text_dark, align='right')

    # Divider under the info row
    divider_y = info_y2 - 6 * mm
    c.setStrokeColor(navy)
    c.setLineWidth(1)
    c.line(margin, divider_y, width - margin, divider_y)

    # ================= BLANK TREATMENT AREA =================
    footer_h = 34 * mm
    footer_top = footer_h
    content_top = divider_y - 8 * mm
    content_bottom = footer_top + 16 * mm

    # Left accent line, like the ruled margin on the paper form
    c.setStrokeColor(teal)
    c.setLineWidth(1.2)
    c.line(margin, content_top, margin, content_bottom)

    # Rx mark
    c.setFillColor(teal)
    c.setFont(bold_font, 16)
    c.drawString(margin + 4 * mm, content_top - 8 * mm, 'Rx')

    # Faint ruled lines to keep the "prescription pad" feel
    c.setStrokeColor(HexColor('#e5e7eb'))
    c.setLineWidth(0.5)
    line_gap = 9 * mm
    y = content_top - 16 * mm
    while y > content_bottom:
        c.line(margin + 4 * mm, y, width - margin, y)
        y -= line_gap

    # Prescription content text, wrapped onto those lines.
    # Each line may itself mix Arabic and Latin/digits, so wrap+draw with draw_mixed.
    max_width = width - margin - (margin + 6 * mm)
    y = content_top - 14 * mm
    for line in prescription.content.split('\n'):
        if line.strip() == '':
            y -= line_gap
            continue
        words = line.split(' ')
        current_line = ''
        for word in words:
            test_line = current_line + (' ' if current_line else '') + word
            runs = _split_runs(_visual(test_line))
            test_width = sum(c.stringWidth(r, 'Arabic' if a else body_font, 11) for r, a in runs)
            if test_width < max_width:
                current_line = test_line
            else:
                if current_line:
                    draw_mixed(current_line, margin + 6 * mm, y, ar_size=11, lat_size=11, color=black)
                    y -= line_gap
                current_line = word
        if current_line:
            draw_mixed(current_line, margin + 6 * mm, y, ar_size=11, lat_size=11, color=black)
            y -= line_gap

    # Follow-up appointment field, just above the footer (matches "موعد الاستشارة" on the paper)
    draw_mixed('موعد الاستشارة: ..... / ..... / 20.....', width - margin, footer_top + 8 * mm,
               ar_size=9, lat_size=9, color=grey, align='right')

    # ================= FOOTER BANNER =================
    c.setFillColor(navy)
    c.rect(0, 0, width, footer_h, fill=1, stroke=0)

    branches = cfg['CLINIC_BRANCHES']
    by = footer_h - 7 * mm
    for branch in branches:
        draw_mixed(branch['address'], width - margin, by, ar_size=8.5, lat_size=8.5,
                   ar_bold=True, color=white, align='right')
        by -= 4.6 * mm
        draw_mixed(f"{branch['phone_label']}: {branch['phone']}", width - margin, by,
                   ar_size=8, lat_size=8, color=white, align='right')
        by -= 6.2 * mm

    # Emergency roundel (bottom-left, mirroring the paper's "24hr" icon)
    ex, ey = margin + 11 * mm, footer_h - 12 * mm
    c.setFillColor(red)
    c.circle(ex, ey, 7 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(bold_font, 12)
    c.drawCentredString(ex, ey - 1.5 * mm, '24')
    draw_mixed('ساعة طوارئ', ex, ey - 7 * mm - 3.5 * mm, ar_size=7, color=white, align='center')

    c.save()
    return filepath


def allowed_file(filename):
    """Check if file extension is allowed."""
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {
        'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'
    })
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def save_patient_file(patient_id, file, category='patients'):
    """Save an uploaded file linked to a patient. Returns PatientFile object."""
    import uuid

    if not file or not file.filename:
        raise ValueError('No file provided')

    if not allowed_file(file.filename):
        raise ValueError('File type not allowed')

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f'{uuid.uuid4().hex}.{ext}'
    subdir = os.path.join(current_app.config['UPLOAD_FOLDER'], category)
    os.makedirs(subdir, exist_ok=True)
    filepath = os.path.join(subdir, unique_name)

    file.save(filepath)

    patient_file = PatientFile(
        patient_id=patient_id,
        filename=unique_name,
        original_filename=file.filename,
        file_path=filepath,
        file_type=file.content_type,
        file_size=os.path.getsize(filepath) if os.path.exists(filepath) else 0
    )
    db.session.add(patient_file)
    db.session.commit()

    return patient_file


# Need os import
import os
