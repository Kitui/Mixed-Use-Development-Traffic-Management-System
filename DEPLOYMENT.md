# Prototype Deployment Guide

This guide is for a demo/prototype deployment, not a hardened production system.

## Environment Variables

Create environment variables on your hosting service using `.env.example` as a guide.

Minimum required for a public demo:

```text
DEBUG=False
SECRET_KEY=<long random value>
ALLOWED_HOSTS=<your-demo-hostname>
CSRF_TRUSTED_ORIGINS=https://<your-demo-hostname>
```

For a quick prototype, SQLite can work on a single VM or persistent disk. For platforms with ephemeral disks, use PostgreSQL and set:

```text
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME
```

## Deploy Steps

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py createsuperuser
gunicorn estate_traffic.wsgi:application
```

On platforms like Render or Railway:

- Build command: `bash build.sh`
- Start command: `gunicorn estate_traffic.wsgi:application`

## Before Sharing The Demo

- Change/remove demo users and weak passwords.
- Set `DEBUG=False`.
- Use a real `SECRET_KEY`.
- Set `ALLOWED_HOSTS` to your actual demo domain.
- If using HTTPS, set:

```text
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

Only enable HSTS when the demo domain is permanently HTTPS-only:

```text
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=False
```

## Not Yet Production-Hardened

Before real estate use, add stronger audit logging, backups, monitoring, password reset, email/SMS notifications, and a proper privacy/security review.
