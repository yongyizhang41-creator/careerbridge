import getpass
from io import StringIO
import os
from pathlib import Path
import runpy
from smtplib import SMTPAuthenticationError
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, override_settings


class EmailSetupTests(SimpleTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        overrides = override_settings(
            BASE_DIR=self.directory, EMAIL_HOST="smtp.gmail.com",
            EMAIL_HOST_USER="careerbridgemessage@gmail.com",
        )
        overrides.enable()
        self.addCleanup(overrides.disable)
        environment = {key: value for key, value in os.environ.items() if key != "EMAIL_HOST_PASSWORD"}
        patcher = patch.dict(os.environ, environment, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_setup_checks_sign_in_and_saves_private_password_without_sending(self):
        output = StringIO()
        password_file = self.directory / ".smtp-password"
        with (
            patch("communications.management.commands.configure_email.getpass.getpass", return_value="abcd efgh ijkl mnop"),
            patch("communications.management.commands.configure_email.get_connection") as connection,
        ):
            call_command("configure_email", stdout=output)
            connection.assert_called_once_with(
                backend="django.core.mail.backends.smtp.EmailBackend", password="abcdefghijklmnop",
            )
            connection.return_value.__enter__.assert_called_once()
            connection.return_value.send_messages.assert_not_called()
        self.assertEqual(password_file.read_text(), "abcdefghijklmnop\n")
        self.assertEqual(password_file.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("abcdefghijklmnop", output.getvalue())
        self.assertIn("sign-in verified", output.getvalue())

    def test_failed_sign_in_keeps_existing_password_and_redacts_server_error(self):
        password_file = self.directory / ".smtp-password"
        password_file.write_text("old-password")
        with (
            patch("communications.management.commands.configure_email.getpass.getpass", return_value="new-password"),
            patch("communications.management.commands.configure_email.get_connection") as connection,
        ):
            connection.return_value.__enter__.side_effect = SMTPAuthenticationError(535, b"private server detail")
            with self.assertRaisesMessage(CommandError, "SMTP sign-in failed") as error:
                call_command("configure_email", stdout=StringIO())
        self.assertNotIn("private server detail", str(error.exception))
        self.assertEqual(password_file.read_text(), "old-password")

    def test_empty_password_is_not_saved_or_sent_to_smtp(self):
        with (
            patch("communications.management.commands.configure_email.getpass.getpass", return_value="   "),
            patch("communications.management.commands.configure_email.get_connection") as connection,
        ):
            with self.assertRaisesMessage(CommandError, "No password entered"):
                call_command("configure_email", stdout=StringIO())
            connection.assert_not_called()
        self.assertFalse((self.directory / ".smtp-password").exists())

    def test_environment_override_is_not_silently_ignored(self):
        with patch.dict(os.environ, {"EMAIL_HOST_PASSWORD": "environment-password"}):
            with self.assertRaisesMessage(CommandError, "Update it there"):
                call_command("configure_email", stdout=StringIO())
        self.assertFalse((self.directory / ".smtp-password").exists())

    def test_settings_load_saved_password_and_respect_environment_override(self):
        settings_path = self.directory / "config" / "settings.py"
        settings_path.parent.mkdir()
        source = Path(__file__).resolve().parent.parent / "config" / "settings.py"
        settings_path.write_text(source.read_text())
        (self.directory / ".smtp-password").write_text("saved-password\n")
        self.assertEqual(runpy.run_path(str(settings_path))["EMAIL_HOST_PASSWORD"], "saved-password")
        for password in ("environment-password", ""):
            with self.subTest(password=password), patch.dict(os.environ, {"EMAIL_HOST_PASSWORD": password}):
                self.assertEqual(runpy.run_path(str(settings_path))["EMAIL_HOST_PASSWORD"], password)

    def test_noninteractive_input_is_rejected_before_password_is_read(self):
        with patch("communications.management.commands.configure_email.getpass.getpass", side_effect=getpass.GetPassWarning):
            with self.assertRaisesMessage(CommandError, "interactive terminal"):
                call_command("configure_email", stdout=StringIO())
        self.assertFalse((self.directory / ".smtp-password").exists())
