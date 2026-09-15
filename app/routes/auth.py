from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from app import db, limiter
from app.models import User


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute, 50 per hour')  # Slow down password-guessing attempts
def login():
    """Login page for staff and doctor."""
    if current_user.is_authenticated:
        if current_user.role == 'doctor':
            return redirect(url_for('doctor.dashboard'))
        else:
            return redirect(url_for('assistant.dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username, active=True).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            session.permanent = True
            next_page = request.args.get('next')
            if user.role == 'doctor':
                return redirect(next_page or url_for('doctor.dashboard'))
            else:
                return redirect(next_page or url_for('assistant.dashboard'))
        else:
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة'

    return render_template('auth/login.html', error=error)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Let a logged-in doctor/assistant set their own password."""
    error = None
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not check_password_hash(current_user.password_hash, current_password):
            error = 'كلمة المرور الحالية غير صحيحة'
        elif len(new_password) < 8:
            error = 'كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل'
        elif new_password != confirm_password:
            error = 'كلمة المرور الجديدة وتأكيدها غير متطابقين'
        else:
            current_user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('تم تغيير كلمة المرور بنجاح', 'success')
            if current_user.role == 'doctor':
                return redirect(url_for('doctor.dashboard'))
            return redirect(url_for('assistant.dashboard'))

    return render_template('auth/change_password.html', error=error)


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout."""
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'info')
    return redirect(url_for('patient.booking_page'))
