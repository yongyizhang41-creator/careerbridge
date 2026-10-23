# CareerBridge

CareerBridge is a Django web application that connects early-career job seekers with recruiters. It gives job seekers a place to present their experience and find relevant opportunities, helps recruiters publish roles, and provides administrators with tools for platform oversight and reporting.

This repository is being developed by a five-person team for Georgia Tech CS 2340 Project 2.

## Project vision

Early-career candidates often struggle to find roles that match their skills, interests, location preferences, and practical constraints. Recruiters face the complementary problem of finding and evaluating suitable applicants across large candidate pools.

CareerBridge is designed around three roles:

- **Job Seekers** create professional profiles, discover jobs, apply, and track their progress.
- **Recruiters** publish openings, find candidates, and manage applicants.
- **Administrators** manage users, moderate content, investigate reports, and export platform data.

The platform combines professional profiles, job search and applications, hiring pipelines, communication, recommendations, administration, and map-based discovery.

## Features

CareerBridge provides a complete role-based recruitment workflow built around the following capabilities.

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

## Core workflows

The application connects the three roles through these end-to-end workflows:

```text
Job Seeker:    Register → Create Profile → Search Jobs → Apply → Track Application
Recruiter:     Post Job → Set Office Location → View Applicants
Administrator: Manage Users → Moderate Jobs → Export Data
```

These workflows share a common account foundation with registration, authentication, role-based authorization, and dedicated workspaces for each user type.

## Domain model

The core data relationships are:

```text
User
├── role
├── JobSeekerProfile (one-to-one, for job seekers)
│   ├── Education (one-to-many)
│   ├── WorkExperience (one-to-many)
│   └── ProfessionalLink (one-to-many)
├── Job (one-to-many, for recruiters)
├── Application (one-to-many, for job seekers)
└── Conversation (one-to-many, as recruiter or candidate)

Job
└── Application (one-to-many)

Conversation
└── Message (one-to-many, private to its recruiter and candidate)
```

Each `(job, applicant)` pair is unique, so a job seeker cannot create duplicate applications for the same job.

## Technology stack

- Python 3
- Django 5.2.17
- SQLite for local development
- Django templates
- HTML and CSS
- MapLibre GL JS 5 (loaded from jsDelivr) with OpenFreeMap map tiles for the job maps; no API key needed
- OpenStreetMap Nominatim for turning a job's address into a map pin, called from the browser

## Local setup

### 1. Clone and enter the repository

```bash
git clone <repository-url>
cd ProjectTwo
```

Replace `<repository-url>` with the team's Git repository URL.

### 2. Create and activate a virtual environment

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

On Windows, use `py -m pip` if `python3` is unavailable.

### 4. Apply database migrations

```bash
python3 manage.py migrate
```

### 5. Run the development server

```bash
python3 manage.py runserver
```

Open <http://127.0.0.1:8000/accounts/register/> to create a job seeker or recruiter account. Stop the server with `Ctrl+C`.

## Administrator setup

Create a Django superuser:

```bash
python3 manage.py createsuperuser
```

Then:

1. Open <http://127.0.0.1:8000/admin/>.
2. Sign in with the superuser account.
3. Open that user record and set its CareerBridge role to **Administrator**.

Django's `is_staff`/`is_superuser` flags control access to Django Admin, while the CareerBridge `role` field controls access to the application's administrator reports and moderation pages.

## Main application routes

| Route | Purpose | Access |
| --- | --- | --- |
| `/accounts/register/` | Create a job seeker or recruiter account | Public |
| `/accounts/login/` | Sign in | Public |
| `/accounts/dashboard/` | Shared account dashboard | Authenticated users |
| `/accounts/job-seeker/` | View and build a job seeker profile | Job seeker |
| `/accounts/recruiter/` | Recruiter workspace | Recruiter |
| `/jobs/` | Search active jobs with List/Map views | Authenticated users |
| `/jobs/map/` | Redirect to the Find jobs map view | Authenticated users |
| `/jobs/new/` | Create a job posting | Recruiter |
| `/jobs/mine/` | View owned job postings | Recruiter |
| `/jobs/moderation/` | Remove or restore job postings | Administrator |
| `/messages/` | View private recruiter-candidate conversations | Job seeker or recruiter |
| `/messages/candidates/<id>/email/` | Compose and send an email to a candidate | Recruiter |
| `/accounts/reports/` | View metrics and download CSV reports | Administrator |
| `/admin/` | Manage users and Django data | Staff users |

## Project structure

```text
ProjectTwo/
├── accounts/               # Users, authentication, profiles, reports, and role access
│   ├── migrations/         # Account and profile schema history
│   └── templates/accounts/ # Account and profile pages
├── jobs/                   # Jobs, applications, search, and moderation
│   ├── migrations/         # Job and application schema history
│   └── templates/jobs/     # Job-related pages
├── communications/         # Private recruiter-candidate conversations and messages
├── config/                 # Django settings and root URL configuration
├── static/css/app.css      # Shared visual design
├── templates/              # Shared base template and components
├── manage.py               # Django command-line entry point
└── requirements.txt        # Python dependencies
```

## Authorization and data-safety notes

- Anonymous users are redirected to the login page when authentication is required.
- Role-protected views return HTTP 403 when the signed-in user has the wrong role.
- Recruiters can edit only jobs they own.
- Only a conversation's recruiter and candidate can read or send its messages.
- Message senders and recipients are derived on the server rather than trusted from form data.
- Recruiters may contact discoverable candidates, their own applicants, or candidates with an existing conversation.
- Candidate email outreach uses a configured platform SMTP account, with the recruiter's account email as Reply-To. See [messaging and email setup](docs/us14-us15.md).
- The default sender is `careerbridgemessage@gmail.com`. Run `python manage.py configure_email` once on the demo machine or hosted server to privately enter and verify its Google app password, then restart/reload the app.
- Removed jobs are hidden from ordinary users but remain visible to their recruiter and administrators.
- State-changing actions such as logout, job applications, removal, and restoration use POST requests.
- CSV exports omit application notes and escape formula-like text to reduce spreadsheet-injection risk.
- Other Django models must reference users with `settings.AUTH_USER_MODEL` or `get_user_model()`, not Django's default `User` class.

## Development workflow

The team currently works directly on `main` unless a feature branch is explicitly requested:

```bash
git switch main
git pull --ff-only
python3 manage.py check
git status
```

Pull the latest changes before development, make one coherent change at a time, and inspect the working tree before committing. Do not commit local databases, virtual environments, secrets, or local session-planning files.

## Production note

The current settings are intended for local development. Before deployment, move the secret key to an environment variable, disable debug mode, configure allowed hosts, use a production database and static-file strategy, and run Django's deployment checks.
