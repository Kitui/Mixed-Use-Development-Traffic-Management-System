# Smart Estate Traffic Management System

A Django MVP for managing human and vehicle movement in the Tilisi community setup.

## MVP Features

- Resident registration
- Visitor registration
- Visitor approval and denial
- Tilisi community units such as Maisha Makao and Coast Cables
- Three main gates: Chunga Mali - Ngecha Road, Nairobi-Nakuru Highway, and Limuru Road
- Visitor, delivery, and service provider requests
- Role-based access for Admin, Main Gate Guard, Estate/Company Guard, Resident, and Receptionist users
- Vehicle registration
- Human and vehicle entry/exit logging
- Dashboards with totals, pending approvals, and recent activity
- Search and filtering for residents, visitors, vehicles, and logs
- Edit screens for residents, visitors, and vehicles
- Admin-only deactivation/deletion controls for operational cleanup
- Reports for date-filtered movement, visitor status, vehicle types, and gate activity
- CSV exports for traffic logs, visitors, and vehicles
- Django admin for data management

## Local Setup

Clone the project:

```bash
git clone https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
cd YOUR-REPOSITORY
```

Create and activate a virtual environment.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

On macOS/Linux:

```bash
cp .env.example .env
```

Prepare the database and demo data:

```powershell
python manage.py migrate
python manage.py seed_tilisi
```

Run the server:

```powershell
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Default local admin:

```text
Username: admin
Password: admin12345
```

Demo local users created during verification:

```text
Main gate guard: guard / guard12345
Estate/company guard: unitguard / unitguard12345
Resident: resident / resident12345
Company receptionist: reception / reception12345
```

## Sharing On GitHub

See `GITHUB_SETUP.md` for step-by-step instructions to publish this repository publicly and for clone-and-run instructions for other users.

Do not commit these local/private files:

- `.env`
- `.venv/`
- `db.sqlite3`
- `staticfiles/`
- `media/`

## Useful Commands

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py seed_tilisi
```

## Prototype Deployment

Deployment helper files are included:

- `.env.example`: environment variable template
- `Procfile`: process command for simple cloud hosts
- `build.sh`: collect static files and run migrations
- `runtime.txt`: Python version hint
- `DEPLOYMENT.md`: prototype deployment guide

For a public demo, copy `.env.example` values into your host settings and set at least:

```text
DEBUG=False
SECRET_KEY=<long random value>
ALLOWED_HOSTS=<your-demo-domain>
CSRF_TRUSTED_ORIGINS=https://<your-demo-domain>
```

## Apps

- `accounts`: user role profiles
- `residents`: resident records
- `visitors`: visitor, delivery, and service provider records and approval status
- `vehicles`: resident and visitor vehicles
- `traffic_logs`: gate entry and exit records
- `dashboard`: security dashboard

## Tilisi Prototype Flow

1. Resident or company receptionist pre-lists an expected visitor, delivery, or service provider. This booking is automatically approved for main-gate arrival.
2. Main gate guard sees the pre-booked entry and checks the visitor in at the main gate.
3. Estate/company guard confirms the visitor has arrived at the correct internal destination.
4. Resident or company receptionist confirms final check-in.
5. Resident or company receptionist initiates checkout.
6. Main gate guard confirms final exit.
7. If a visitor was created at the main gate and the destination was unclear, the estate/company guard can redirect the visitor to the correct destination queue.

## Implemented Role Functions

Main gate guards can:

- Add visitors, deliveries, and service providers.
- Capture visitor vehicle plate, model, and color.
- Check pre-listed or pre-approved requests.
- Alert the host estate/company by marking the request as alerted.
- Check approved guests in at the main gate.
- Confirm final checkout at the main gate after the host requests checkout.

Estate/company guards can:

- View approved and redirected queues.
- Correct visitor and vehicle details.
- Redirect guests who arrive at the wrong estate/company.
- Confirm the visitor arrived at the estate/company.

Residents and company receptionists can:

- Pre-list expected visitors, deliveries, and service providers.
- Add car details for their own expected guests.
- Approve or deny requests raised by main gate guards.
- Confirm final check-in after the estate/company guard confirms arrival.
- Initiate checkout for their own guests.

Estate admin/management can:

- Maintain residents and employees.
- Maintain community units and companies through Django admin.
- Maintain resident/employee vehicle records.
- View reports and export CSV data.

## Next Enhancements

- QR code generation and scanning
- Printable PDF reports
- PostgreSQL production database
- Number plate recognition with OpenCV/OCR
