# Great Irish Hotels (GIH) Management System

A Django-based web application built for the Great Irish Hotels group, developed for the ATU Donegal coursework.

## Table of Contents

- [Great Irish Hotels (GIH) Management System](#great-irish-hotels-gih-management-system)
  - [Table of Contents](#table-of-contents)
  - [Project Overview](#project-overview)
  - [Amiresponsive](#amiresponsive)
  - [User Experience (UX)](#user-experience-ux)
    - [User Goals](#user-goals)
    - [Business Goals](#business-goals)
    - [User Stories](#user-stories)
  - [Design](#design)
    - [Wireframes](#wireframes)
    - [Information Architecture](#information-architecture)
    - [Accessibility](#accessibility)
  - [Features](#features)
  - [Data Model](#data-model)
  - [Technologies Used](#technologies-used)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Local Setup](#local-setup)
    - [Running Tests](#running-tests)
    - [Cloudinary Setup](#cloudinary-setup)
    - [Stripe Setup](#stripe-setup)
    - [Activating the Python Virtual Environment](#activating-the-python-virtual-environment)
  - [Deployment](#deployment)
    - [Deploying to Render.com](#deploying-to-rendercom)
  - [Project Structure](#project-structure)
  - [Testing and QA](#testing-and-qa)
  - [Unittest](#unittest)
  - [User Manual](#user-manual)
    - [Guests](#guests)
    - [Staff (custom staff accounts)](#staff-custom-staff-accounts)
    - [Admin (Django staff users)](#admin-django-staff-users)
    - [General Navigation \& Tips](#general-navigation--tips)
  - [Future Enhancements](#future-enhancements)
  - [Credits and Acknowledgements](#credits-and-acknowledgements)

## Project Overview

Great Irish Hotels (GIH) is a full-stack Django application for hotel operations, including guest profiles, room reservations, housekeeping workflows, maintenance requests, loyalty programmes, and service charges. The solution targets small-to-medium hotel groups and is aligned with ATU Donegal coursework expectations.

[Back to Table of Contents](#table-of-contents)

## Amiresponsive

- Confirm responsive layout via https://ui.dev/amiresponsive or https://amiresponsive.co.uk using the deployed site URL.
- Capture a screenshot of the composite view (desktop/tablet/phone) for submission or documentation.
- Re-check after major layout changes (CSS, templates) before release.

[Back to Table of Contents](#table-of-contents)

## User Experience (UX)

### User Goals

- Book rooms, manage stays, and view loyalty status.
- Hotel staff manage reservations, housekeeping tasks, and maintenance.
- Admins generate reports and oversee service requests.

[Back to Table of Contents](#table-of-contents)

### Business Goals

- Centralise hotel operations into one interface.
- Reduce manual overhead for staff scheduling and maintenance tracking.
- Improve guest retention through loyalty and personalised services.

[Back to Table of Contents](#table-of-contents)

### User Stories

- Guests can register, log in, and manage reservations and profiles.
- Housekeeping staff can view and update room cleaning status.
- Maintenance teams can log and resolve maintenance requests with timestamps.
- Admins can manage rooms, staff, and service pricing.

[Back to Table of Contents](#table-of-contents)

## Design

### Wireframes

- High-level wireframes are planned for core flows (home, reservation booking, housekeeping board). Update this section with exported images or links when available.

[Back to Table of Contents](#table-of-contents)

### Information Architecture

- Core navigation: Home → Rooms → Reservations → Loyalty → Services → Login/Admin.
- Role-based dashboards: Admin, Housekeeper, Guest views.

[Back to Table of Contents](#table-of-contents)

### Accessibility

- Semantic HTML in templates where possible.
- Colour contrast checked against WCAG AA; further audits recommended during UI polish.
- Forms provide labels and error feedback for validation issues.

[Back to Table of Contents](#table-of-contents)

## Features

- Guest management: personal details, contact info, preferences, loyalty status.
- Room reservations: multi-night stays, group bookings, status tracking.
- Housekeeping: daily assignments, cleaning status, deep cleaning schedules.
- Maintenance: request logging, task assignment, cost tracking.
- Loyalty programme: points, status, discounts.
- Service requests: link charges to reservations, track fulfilment.

[Back to Table of Contents](#table-of-contents)

## Data Model

- Django models cover guests, rooms, reservations, services, loyalty status, housekeeping, and maintenance records.
- Migrations in `core/migrations/` define schema evolution, including room images (local or Cloudinary) and role management.

[Back to Table of Contents](#table-of-contents)

## Technologies Used

- Django 5.2.10, Python 3.12.
- SQLite for local development; Postgres via `dj-database-url` for production.
- Cloudinary and `django-cloudinary-storage` for media.
- WhiteNoise for static files in production.
- Gunicorn for WSGI hosting; Render.com deployment ready.

[Back to Table of Contents](#table-of-contents)

## Getting Started

### Prerequisites

- Python 3.12+
- pip
- Virtual environment (venv recommended)

[Back to Table of Contents](#table-of-contents)

### Local Setup

1. Clone the repository.
2. Create a virtual environment (recommended):
   ```bash
   python -m venv .venv
   ```
3. Activate the virtual environment (pick your shell):
   - PowerShell: `./.venv/Scripts/Activate.ps1`
   - Command Prompt: `.venv\Scripts\activate.bat`
   - Git Bash: `source .venv/Scripts/activate`
   If PowerShell blocks activation, allow local scripts once: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force` (then re-run the activate command).
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   This pulls the full stack with pinned versions:
   - `asgiref==3.11.0`
   - `Django==5.2.10`
   - `pillow==12.1.0`
   - `sqlparse==0.5.5`
   - `tzdata==2025.3`
   - `cloudinary==1.41.0`
   - `django-cloudinary-storage==0.3.0`
   - `python-dotenv==1.0.1`
   - `stripe>=7.0.0`
   - `django-jazzmin==3.0.1`
   - `gunicorn==23.0.0`
   - `dj-database-url==2.1.0`
   - `psycopg[binary]==3.2.3`
   - `whitenoise==6.7.0`

5. Create a Django superuser (for Django admin access):
   ```bash
   python manage.py createsuperuser
   ```
   Follow the prompts to set username, email, and password.

6. (Optional) To enable a modern admin interface, install Jazzmin:
   ```bash
   pip install django-jazzmin
   ```
7. Add `jazzmin` to your `INSTALLED_APPS` in `gih/settings.py` (before `django.contrib.admin`).
8. Run migrations:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```
9. Start the development server:
   ```bash
   python manage.py runserver
   ```
10. Access the app at http://127.0.0.1:8000/

[Back to Table of Contents](#table-of-contents)

### Running Tests

Run all tests:
```bash
python manage.py test
```

[Back to Table of Contents](#table-of-contents)

### Cloudinary Setup

1. Create a hidden `.env` directory in the project root (already ignored by `.gitignore`).
2. Inside it, create `.env.local` with your Cloudinary credentials:
   ```dotenv
   CLOUDINARY_API_KEY=your_key
   CLOUDINARY_API_SECRET=your_secret
   CLOUDINARY_CLOUD_NAME=your_cloud_name
   # Optional if you want to supply the full URL yourself
   # CLOUDINARY_URL=cloudinary://your_key:your_secret@your_cloud_name
   ```
3. Install the media-storage helpers if you are not using `requirements.txt`:
   ```bash
   pip install cloudinary==1.41.0 django-cloudinary-storage==0.3.0 python-dotenv==1.0.1
   ```
4. Never commit `.env/.env.local` to source control; the folder is already ignored but double-check before pushing.
5. Restart the Django server. When the environment variables are present, uploaded room images automatically store in your Cloudinary account via `django-cloudinary-storage`; without them, the app falls back to local storage in `room_images/`.
6. Verify the integration by adding/editing a room in the Django admin and confirming the image appears in your Cloudinary dashboard (folder `rooms`).

[Back to Table of Contents](#table-of-contents)

### Stripe Setup

Store Stripe keys in `.env/.env.local` (never commit them). Example block:

```dotenv
# Stripe API keys - do not commit this file, hidden `.env` directory in the project root (already ignored by `.gitignore`)
STRIPE_PUBLIC_KEY=pk_test_************************************
STRIPE_SECRET_KEY=sk_test_************************************
```

These variables are read by `gih/settings.py` for payment flows.

[Back to Table of Contents](#table-of-contents)

### Activating the Python Virtual Environment

Create once, activate per session, deactivate when done:

1) Create (if not already):
```bash
python -m venv .venv
```

2) Activate (choose your shell):
- PowerShell: `./.venv/Scripts/Activate.ps1`
- Command Prompt: `.venv\Scripts\activate.bat`
- Git Bash: `source .venv/Scripts/activate`

If PowerShell blocks activation, run once: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force`, then activate again.

3) Deactivate when finished:
```bash
deactivate
```

Tip: After activation, your shell prompt should show `(.venv)`; if it does not, activation did not succeed.

[Back to Table of Contents](#table-of-contents)

## Deployment

### Deploying to Render.com

Follow these steps to deploy the app to Render:

1) Prepare code (already configured in this repo)
- Requirements include `gunicorn`, `dj-database-url`, `psycopg2-binary`, and `whitenoise` for production.
- `gih/settings.py` reads `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `DATABASE_URL` from environment variables, uses `dj_database_url` for Postgres, and serves static files with WhiteNoise (`STATIC_ROOT` is set). Cloudinary and Stripe keys are read from env if present.
- A `Procfile` is present with `web: gunicorn gih.wsgi:application`.
- A `render.yaml` is included with build/start commands and env-var stubs.

2) Push your changes to the main branch on GitHub.

3) Create a Postgres instance on Render and copy its `DATABASE_URL`.

4) Create a new Web Service on Render
- Connect your GitHub repo and choose the main branch.
- Environment: Python.
- Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- Start command: `gunicorn gih.wsgi:application`

5) Set environment variables in Render
- `DJANGO_SETTINGS_MODULE=gih.settings`
- `SECRET_KEY` (generate a strong value)
- `DEBUG=false`
- `ALLOWED_HOSTS=yourapp.onrender.com`
- `CSRF_TRUSTED_ORIGINS=https://yourapp.onrender.com`
- `DATABASE_URL` (from Render Postgres)
- `STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY` (if using payments)
- `CLOUDINARY_URL` (if using Cloudinary media storage)

6) Deploy
- Render will build and start using the commands above.
- After the first deploy, open the Render Shell and run `python manage.py migrate` to apply database migrations.

7) Verify
- Hit the app URL, ensure static files load, and confirm media works (Cloudinary if configured).
- Test a page like `/profile` to confirm the app runs correctly.

[Back to Table of Contents](#table-of-contents)

## Project Structure

- `core/` - Main app with models, views, templates, static files.
- `gih/` - Project settings and URLs.
- `db.sqlite3` - Default SQLite database.
- `manage.py` - Django management script.

[Back to Table of Contents](#table-of-contents)

## Testing and QA

- Automated: `python manage.py test` covers forms, models, and integration paths (see `core/tests/`).
- Manual: smoke test key user journeys (register, login, book room, update housekeeping, raise maintenance, complete payment flows).
- Accessibility: run browser-based audits (Lighthouse) and screen-reader spot checks; address contrast and focus states.

[Back to Table of Contents](#table-of-contents)

## Unittest

- Command executed: `python manage.py test core.tests.test_guest_login`
- Result: 3 tests, all passed.
- Coverage (overall): ~29% statements (forms ~32%, views ~14%).

Screenshots:

![Guest login tests](assets/test_guest_login.png)
![Coverage report](assets/Unittest_coverage.png)

[Back to Table of Contents](#table-of-contents)

## User Manual

### Guests

- Sign up / Sign in: Use Register to create an account (first/last name, email, phone, ID, password). Return users sign in via Login; repeated failures may be rate-limited.
- Profile: Visit Profile to edit personal details and change password.
- Browse rooms: View rooms, images, rates, and date availability; logged-in guests see loyalty points and redemption eligibility.
- Book a room: From Rooms or Reservations, select room and dates, then start payment. Optionally redeem 35 points for a 10% discount if eligible. Successful Stripe payment auto-creates a confirmed reservation, deducts redeemed points, and awards points at checkout.
- Loyalty: Check points and redemption rules on the Loyalty page; earn 5 points when a stay is checked out, redeem with ≥35 points.
- Service/Maintenance requests: If enabled, submit requests tied to your reservation and track status (Requested → In Progress → Completed).
- Newsletter: Subscribe via the Newsletter page.
- Logout: Use Logout when finished.


### Staff (custom staff accounts)

- Login: Use Housekeeper/Staff Login with staff email/password. Role-based landing (Maintenance → Maintenance list; Housekeeper/Reception → Housekeeping list).
- Guests: Manage guest records (list/create/edit/delete/view) via Management → Guests.
- Reservations: Management → Reservations to create, edit, cancel/delete, and view bookings. Overlaps are blocked for confirmed/checked-in stays.
- Rooms: Staff with elevated rights can add/edit/delete rooms (Admin Add Room; Rooms list).
- Housekeeping: Management → Housekeeping to assign staff, set status (scheduled/in-progress/completed/inspected), track deep cleaning and time spent.
- Maintenance: Management → Maintenance to log requests, assign staff, update status, and add internal comments.
- Service Requests: Management → Services to track guest service requests, fulfillment time, and charges.
- Loyalty assistance: Reception staff can book on behalf of guests from Rooms and update guest ID docs during booking.
- Reporting: Staff with Django staff privileges can access admin reports if permitted.


### Admin (Django staff users)

- Login: Use Admin Frontend Login with a Django staff account (rate-limited). Django admin remains at /admin/.
- Dashboard: Admin Dashboard for overview links.
- Reports: Admin Reports to run date-range reports (occupancy, reservations, services, housekeeping, maintenance) and export CSV.
- Rooms: Add rooms at Admin Add Room; edit/delete via Rooms list.
- Media/Payments Config: Ensure Stripe keys and Cloudinary are set in .env/.env.local to enable payments and media uploads.


### General Navigation & Tips

- Payments require Stripe keys; without them the payment page shows a configuration error.
- Loyalty: redeem (35 pts → 10% discount) during booking; earn (5 pts) on checkout.
- Access control: Django staff bypass most role checks; custom staff sessions rely on role names. Guests must be logged in to book.
- Errors: Access denied pages show for insufficient permissions; form errors surface inline.
- Newsletter and marketing pages are public.

[Back to Table of Contents](#table-of-contents)

## Future Enhancements

- Payment integration with Stripe checkout flows.
- Advanced analytics dashboards for occupancy and revenue.
- Staff rostering with shift preferences and conflict detection.
- Public API for partner bookings.

[Back to Table of Contents](#table-of-contents)

## Credits and Acknowledgements

- Built by ATU Donegal students.
- Cloudinary integration guidance from official docs.
- Render deployment steps adapted from project scaffolding included in this repository.

[Back to Table of Contents](#table-of-contents)
