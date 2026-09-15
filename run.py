import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_ENV', 'production').lower() == 'development'
    if debug_mode:
        print("Running in DEVELOPMENT mode (debug on). Do not use this for the real clinic.")
    else:
        print("Running in PRODUCTION mode.")
        print("NOTE: for real use, run behind gunicorn instead of 'python run.py':")
        print("      gunicorn -w 4 -b 0.0.0.0:8000 run:app")
    app.run(host='127.0.0.1', port=5000, debug=debug_mode)
