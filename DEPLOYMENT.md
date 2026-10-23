# Render + Neon deployment

Use the Free plan for both services. Create a Neon PostgreSQL project near Render Virginia and supply its TLS connection string as DATABASE_URL in Render. Never commit database credentials or .smtp-password.

Create a Render Blueprint from this repository and main branch using render.yaml. The build installs dependencies, collects static assets, and applies migrations. Gunicorn serves Django; WhiteNoise serves versioned static assets. Render supplies the hostname; HTTPS and secure cookies are enabled on Render. Local development continues to use SQLite unless DATABASE_URL is set.

The online database starts empty. Local SQLite data is not uploaded automatically. Register new users online. Create an administrator from a trusted local shell connected to Neon: set DATABASE_URL and DJANGO_SECRET_KEY securely in the environment, then run python manage.py createsuperuser. Do not put passwords in command arguments or commit them.

Render Free sleeps after inactivity and has no persistent local storage. Keep database records in Neon, keep backups, and use external object storage if file uploads are introduced. Do not use Render Free PostgreSQL for long-term storage because it expires after 30 days.

## Email limitation

The current Gmail SMTP configuration uses port 587, which Render Free blocks. Email outreach will not work until an HTTPS mail-provider integration and verified sender are configured. In-platform messages are independent of SMTP. Do not claim that outbound email is live until it has been verified with an authorized recipient.

## Verification

Run python manage.py check, collectstatic --noinput, and git diff --check before deployment. After deployment verify HTTPS, login/registration, CSS and JS delivery, and database persistence across redeploys. No automated tests are required by this project.
