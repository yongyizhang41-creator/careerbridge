import getpass
import os
from pathlib import Path
from smtplib import SMTPException
from tempfile import NamedTemporaryFile
import warnings

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.mail import get_connection


class Command(BaseCommand):
    help = "Verify the platform SMTP sign-in and privately save its password on this machine."
    requires_system_checks = []

    def handle(self, *args, **options):
        if "EMAIL_HOST_PASSWORD" in os.environ:
            raise CommandError(
                "EMAIL_HOST_PASSWORD is set in the server environment. "
                "Update it there, or unset it before using this command."
            )
        self.stdout.write(f"Configuring email for {settings.EMAIL_HOST_USER} at {settings.EMAIL_HOST}.")
        self.stdout.write("Enter the Google app password, not the account's normal password. Input is hidden.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                password = getpass.getpass("App password: ")
        except (getpass.GetPassWarning, EOFError, KeyboardInterrupt):
            raise CommandError("No password saved. Run this command in an interactive terminal.") from None
        password = "".join(password.split())
        if not password:
            raise CommandError("No password entered. Nothing was saved.")
        self.stdout.write("Checking the SMTP sign-in; no email will be sent...")
        try:
            with get_connection(
                backend="django.core.mail.backends.smtp.EmailBackend",
                password=password,
            ):
                pass
        except (SMTPException, OSError):
            raise CommandError(
                "SMTP sign-in failed. Nothing was saved. Check the app password, "
                "2-Step Verification, and outbound SMTP access."
            ) from None

        password_file = Path(settings.BASE_DIR) / ".smtp-password"
        temp_path = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=settings.BASE_DIR,
                prefix=".smtp-password-", delete=False,
            ) as temporary:
                temp_path = Path(temporary.name)
                temporary.write(password + "\n")
            temp_path.replace(password_file)
        except OSError:
            raise CommandError("Sign-in succeeded, but the private password file could not be saved. Check directory permissions.") from None
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS(
            "SMTP sign-in verified. Password saved privately in .smtp-password (ignored by Git). "
            "Restart or reload the app to enable sending."
        ))
