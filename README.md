# مركز الفايدي - Clinic Management System

A complete, production-ready multi-role Clinic Management System for **Al-Faydi Center** by Dr. Hisham (General Surgeon), Egypt.

## Features

- **Patient Booking** (Arabic RTL, mobile-first, no login required)
- **Assistant Dashboard** (Arabic RTL - manage appointments, search patients)
- **Doctor Dashboard** (English - medical records, surgeries, file archive, e-prescriptions)
- **Appointment System** with configurable time slots, double-booking prevention, and status tracking
- **Medical Records** (full medical sheet per patient)
- **Surgery Management** (schedule, track, pre/post-op notes)
- **File Archive** (upload images, X-rays, PDFs, lab reports per patient)
- **Electronic Prescription** (free-text, generates professional PDF on A4)

## Tech Stack

- **Backend:** Python 3.10+ / Flask 3.0
- **Database:** SQLite (easily migratable to PostgreSQL)
- **ORM:** SQLAlchemy
- **Auth:** Flask-Login + Werkzeug password hashing
- **CSRF:** Flask-WTF
- **PDF:** ReportLab
- **Frontend:** Tailwind CSS (CDN), vanilla JavaScript

## Quick Start (Local Development)

```bash
# 1. Clone and navigate
mkdir al-faydi-clinic && cd al-faydi-clinic

# 2. Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize database and create default accounts
python seed.py

# 5. Run the development server
python run.py

# 6. Open in browser
# Patient booking:  http://localhost:5000/
# Staff login:     http://localhost:5000/auth/login
# Doctor login:    http://localhost:5000/auth/login
```

## Default Accounts

| Role      | Username   | Password  |
|-----------|-----------|----------|
| Doctor    | doctor    | doctor123 |
| Assistant | assistant1| assist123 |
| Assistant | assistant2| assist123 |

**⚠️ Change all passwords before going to production!**

## Deployment on VPS (Ubuntu/Debian)

```bash
# 1. Install system dependencies
sudo apt update
sudo apt install python3 python3-pip python3-venv nginx

# 2. Upload project to /var/www/clinic/
# Example: git clone your-repo /var/www/clinic/

# 3. Set up virtual environment
cd /var/www/clinic
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python seed.py

# 4. Configure Gunicorn systemd service
sudo cat > /etc/systemd/system/clinic.service << 'EOF'
[Unit]
Description=Al-Faydi Clinic Management System
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/clinic
Environment="PATH=/var/www/clinic/venv/bin"
ExecStart=/var/www/clinic/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 "run:app"

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl start clinic
sudo systemctl enable clinic

# 5. Configure Nginx
sudo cat > /etc/nginx/sites-available/clinic << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # Change this

    client_max_body_size 16M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/clinic/app/static/;
        expires 30d;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/clinic /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 6. (Optional) Add SSL with Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Configuration

Edit `app/config.py` to customize:

- `SLOT_DURATION_MINUTES`: Default is 20 minutes
- `WORKING_DAYS`: Default is Mon-Fri `[0, 1, 2, 3, 4]`
- `WORKING_HOURS_START`: Default `'09:00'`
- `WORKING_HOURS_END`: Default `'17:00'`
- `SECRET_KEY`: **Must be changed for production!**
- `MAX_CONTENT_LENGTH`: File upload limit (default 16MB)
- `CLINIC_NAME_AR` / `CLINIC_NAME_EN`: Clinic name
- `DOCTOR_NAME` / `DOCTOR_TITLE`: Doctor info shown on prescriptions

## Database Schema

| Table           | Description                                        |
|----------------|----------------------------------------------------|
| users          | System accounts (doctor + assistants)               |
| patients        | Patient records (auto-created on first booking)     |
| appointments    | Appointment scheduling with status tracking        |
| medical_records  | Full medical sheets per patient                    |
| surgeries       | Surgery scheduling and tracking                    |
| patient_files   | Uploaded files linked to patients                  |
| prescriptions   | Electronic prescriptions with PDF generation      |
| clinic_settings | Key-value configuration store                      |

## Migrating to PostgreSQL

1. Install: `pip install psycopg2-binary`
2. Change in `config.py`:
   ```python
   SQLALCHEMY_DATABASE_URI = 'postgresql://user:pass@localhost/clinic_db'
   ```
3. The SQLAlchemy ORM handles the rest - no code changes needed.

## Project Structure

```
clinic-management-system/
├── app/
│   ├── __init__.py          # App factory
│   ├── config.py            # Configuration
│   ├── models/
│   │   └── __init__.py      # All SQLAlchemy models
│   ├── routes/
│   │   ├── auth.py          # Login/logout
│   │   ├── patient.py       # Public booking
│   │   ├── assistant.py     # Assistant dashboard
│   │   └── doctor.py        # Doctor dashboard
│   ├── services/
│   │   └── __init__.py      # Business logic
│   ├── templates/           # Jinja2 HTML templates
│   │   ├── base_ar.html     # Arabic RTL base
│   │   ├── base_en.html     # English base
│   │   ├── auth/
│   │   ├── patient/
│   │   ├── assistant/
│   │   └── doctor/
│   └── static/
│       └── uploads/         # Uploaded files
├── run.py                   # Entry point
├── seed.py                  # Database seeder
├── requirements.txt
└── README.md
```

## Security Notes

- Passwords are hashed with Werkzeug's PBKDF2
- Role-based access control (doctor/assistant/public)
- CSRF protection on all forms
- Soft deletes for medical data (no hard deletes)
- File upload type validation and size limits
- **Change `SECRET_KEY` and all default passwords before production!**
