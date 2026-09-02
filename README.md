# Pet Adoption Management System (PAMS)

A complete pet adoption management platform with role-based access control for Adopters, Staff, and Administrators.

## Architecture

```
adopter-portal/    → React + TypeScript + Vite + Tailwind CSS
staff-portal/      → React + TypeScript + Vite + Tailwind CSS
backend/           → Django + Django REST Framework + PostgreSQL
```

## Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env
# Edit .env with your PostgreSQL credentials
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Adopter Portal

```bash
cd adopter-portal
npm install
npm run dev
```

### Staff Portal

```bash
cd staff-portal
npm install
npm run dev
```

## Features

- Role-based access control (Adopter, Staff, Administrator)
- Pet management with images and health records
- Adoption application workflow with status tracking
- Document uploads with security validation
- Staff review system with internal/visible notes
- Optional adoption packages and payment tracking
- In-app notifications
- Report generation with CSV export
- Audit logging for all important actions
