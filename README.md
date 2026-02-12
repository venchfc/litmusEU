# LITMUS Event Scoring System

A Flask-based event scoring and tabulation system for LITMUS of Manuel S. Enverga University Foundation - Catanauan Inc.

## Features
- Role-based authentication (Admin, Tabulator)
- Competition portals for Choir, Vocal Solo, Vocal Duet, Hiphop Dance, Folkdance
- Manage competitions, judges, contestants, criteria, and accounts
- Score input with Save and irreversible Lock
- Admin results view with PDF export
- Event history tracking

## Setup
1. Create a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   python run.py
   ```

## Default Admin
- Username: admin
- Password: admin123

Update these immediately in production. You can override defaults with environment variables:
- `DEFAULT_ADMIN_USERNAME`
- `DEFAULT_ADMIN_PASSWORD`
- `SECRET_KEY`
- `DATABASE_URL`
