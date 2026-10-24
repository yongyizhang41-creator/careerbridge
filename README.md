# CareerBridge

CareerBridge is a Django web application that connects early-career job seekers with recruiters.

## Tech Stack

| Layer | Technologies |
| --- | --- |
| Backend | Python 3; Django 5.2.17; Django ORM, forms, session authentication, and role-based authorization |
| Frontend | Server-rendered Django templates, HTML, CSS, and vanilla JavaScript |
| Database | SQLite by default locally; Neon PostgreSQL through `DATABASE_URL` in production, using psycopg and dj-database-url |
| Maps | MapLibre GL JS 5, OpenFreeMap tiles, OpenStreetMap Nominatim address search, and browser geolocation |
| Deployment | Render, Gunicorn, and WhiteNoise for compressed, versioned static files |

## Architecture

CareerBridge is a server-rendered Django monolith. The browser requests pages and submits forms; Django routes requests to views, checks authentication and permissions, reads or writes records through the ORM, and renders templates. JavaScript adds map interactions and email-client handoff.

```text
Browser (HTML / CSS / JavaScript)
  | HTTP requests and form submissions
  v
Django (config/ URLs, settings, middleware)
  |-- accounts/        Users, roles, profiles, candidate search, saved searches, CSV exports
  |-- jobs/            Job postings, applications, cart, pipeline, maps, recommendations
  |-- communications/  Private conversations and candidate email composition
  |-- reports/         User/job reports and administrator review
  |-- templates/       Shared layout and reusable components
  |-- static/          CSS, JavaScript, and map interactions
  v
Django ORM --> SQLite (local) / Neon PostgreSQL (production)

Browser --> MapLibre + OpenFreeMap / Nominatim
Browser --> Recruiter's email client (mailto)
```

A custom `User` model holds the role. Job seekers have a profile with education, work experience, projects, and professional links. Recruiters own jobs; applications connect job seekers to jobs and store hiring status. Conversations connect a recruiter and candidate and contain their private messages. Views enforce ownership, role access, and profile visibility.

## Features

CareerBridge supports three roles: Job Seeker, Recruiter, and Administrator. The original user-story IDs and capabilities are retained below.

### Job Seeker

| ID | Capability |
| --- | --- |
| US1 | Create a professional profile with headline, skills, education, work experience, and links |
| US2 | Search for jobs using title, skills, location, salary, work arrangement, and visa filters |
| US3 | Apply to a job and include a tailored note |
| US4 | Track application status from Applied through Closed |
| US5 | Control profile privacy |
| US6 | Receive skill-based job recommendations |
| US7 | View job postings on an interactive map |
| US8 | Filter mapped jobs by distance |
| US9 | Set a preferred commute radius |
| US10 | Save jobs in a comparison cart |

### Recruiter

| ID | Capability |
| --- | --- |
| US11 | Post and edit job roles |
| US12 | Search candidates by skills, location, and projects |
| US13 | Organize applicants in a hiring pipeline |
| US14 | Message candidates inside the platform |
| US15 | Email candidates through the platform |
| US16 | Save candidate searches and receive match notifications |
| US17 | Receive candidate recommendations for job postings |
| US18 | Pin a job's office location on a map |
| US19 | View applicant-location clusters on a map |
| US20 | Review a candidate profile and application together |

### Administrator

| ID | Capability |
| --- | --- |
| US21 | Manage users and roles |
| US22 | Moderate or remove job posts |
| US23 | Export platform data as CSV |
| US24 | Review reports about users or job postings |

US15 opens a prefilled message in the recruiter's configured email client using `mailto:`. The recruiter selects the sending account and sends the email there; CareerBridge does not deliver it through a server-side email service. US16 displays new-match counts and highlights new candidates when saved searches are viewed; it does not send background email or push notifications. Recommendations use deterministic skill matching.

## Setup Instructions

### 1. Clone the repository

Use an account with access to the private repository:

```bash
git clone https://github.com/yongyizhang41-creator/careerbridge-private.git
cd careerbridge-private
```

### 2. Create and activate a virtual environment

Python 3.12 matches the deployment configuration.

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies and initialize the database

With the virtual environment active:

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py check
```

Local development uses SQLite automatically when `DATABASE_URL` is unset. No external database or email credentials are needed for local startup.

### 4. Start the application

```bash
python manage.py runserver
```

Open [registration](http://127.0.0.1:8000/accounts/register/) to create a Job Seeker or Recruiter account, or [sign in](http://127.0.0.1:8000/accounts/login/). Stop the server with `Ctrl+C`.

Maps and address search require internet access. Distance filtering requires location permission or a location selected on the map. Email composition requires a configured email client for `mailto:` links.

### 5. Create an administrator (optional)

```bash
python manage.py createsuperuser
```

Sign in at [Django Admin](http://127.0.0.1:8000/admin/), open the user record, and set its CareerBridge role to **Administrator**. Django's staff/superuser flags control Django Admin access; the application role controls administrator workspaces, moderation, and reports.

### 6. Production deployment

The repository includes `render.yaml` for Render and `build.sh` to install dependencies, collect static assets, and apply migrations. Gunicorn runs `config.wsgi:application`; WhiteNoise serves static files.

Configure these values in the hosting environment:

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Production secret key; generated by the Render Blueprint |
| `DJANGO_DEBUG` | Set to `False` in production |
| `DATABASE_URL` | Neon PostgreSQL connection string; the application requires TLS |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames when needed; Render's external hostname is added automatically |

The production database is separate from local SQLite and starts without local accounts or records. Keep credentials in environment variables. Candidate email composition uses the recruiter's email client and requires no SMTP setup.
