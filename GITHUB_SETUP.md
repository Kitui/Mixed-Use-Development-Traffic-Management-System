# GitHub Sharing Guide

Use this guide to publish the prototype so anyone with the GitHub link can clone it and run it locally.

## What To Upload

Upload the project files, but do not upload local/private files such as:

- `.venv/`
- `.env`
- `db.sqlite3`
- `staticfiles/`
- `media/`
- `.agents/`

These are already listed in `.gitignore`.

## Option A: GitHub Desktop

1. Install GitHub Desktop from https://desktop.github.com/.
2. Open GitHub Desktop.
3. Choose `File > Add local repository`.
4. Select:

```text
C:\Users\user\Documents\Estate traffic Management System
```

5. If prompted, create a repository from the folder.
6. Commit the files with a message such as:

```text
Initial Tilisi estate traffic management prototype
```

7. Click `Publish repository`.
8. Choose `Public` if anyone with the link should access it.
9. Copy the GitHub repository URL and share it.

## Option B: Git Command Line

Install Git first if `git --version` does not work.

```bash
git init
git add .
git commit -m "Initial Tilisi estate traffic management prototype"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

## How Someone Else Runs It

```bash
git clone https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
cd YOUR-REPOSITORY
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_tilisi
python manage.py runserver
```

macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_tilisi
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Demo accounts:

```text
admin / admin12345
guard / guard12345
unitguard / unitguard12345
resident / resident12345
reception / reception12345
```

## Important Note

GitHub makes the code accessible. It does not automatically host the running web app. If you want people to open a live URL in their browser without installing anything, deploy it to a service such as Render, Railway, Azure, or AWS using `DEPLOYMENT.md`.
