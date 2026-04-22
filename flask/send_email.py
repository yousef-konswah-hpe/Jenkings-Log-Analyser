"""Email report sender for Jenkins Log Analyzer."""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailReport:
    """Sends analysis reports via SMTP using environment-configured server."""

    def __init__(self):
        self.from_email = os.getenv("SMTP_FROM_EMAIL")

        # SMTP configuration from environment variables
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.office365.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes")
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")

        # Default email recipients (override via SMTP_DEFAULT_RECIPIENT env var)
        self.default_recipients = [os.getenv("SMTP_DEFAULT_RECIPIENT", "")]
        self.default_recipients = [r for r in self.default_recipients if r]
        self.to_email = self.default_recipients[0] if self.default_recipients else ""

    # Public API

    def send_email(self, filename=None, html_content=None, subject=None, to_email=None):
        """
        Send a report via SMTP.

        Args:
            filename:     Path to a text file to attach.
            html_content: Raw HTML to send as the email body.
            subject:      Email subject line.
            to_email:     Additional recipient(s) — str or list[str].

        Returns:
            True if the email was sent successfully, False otherwise.
        """
        all_recipients = self._resolve_recipients(to_email)

        msg = self._build_message(
            recipients=all_recipients,
            subject=subject,
            filename=filename,
            html_content=html_content,
        )

        return self._send_with_retries(msg, all_recipients, max_retries=3)

    # Internals

    def _resolve_recipients(self, extra):
        """Merge default recipients with any extras, de-duplicate."""
        recipients = set(self.default_recipients)

        if isinstance(extra, str):
            recipients.add(extra)
        elif isinstance(extra, list):
            recipients.update(extra)

        return [r.strip() for r in recipients if r.strip()]

    def _build_message(self, recipients, subject, filename, html_content):
        """Construct a MIMEMultipart email message."""
        msg = MIMEMultipart("alternative")
        msg["From"] = self.from_email
        msg["To"] = ", ".join(recipients)

        if subject:
            msg["Subject"] = subject

        if filename is None and html_content:
            msg.attach(MIMEText(html_content, "html"))
        elif filename is not None:
            msg.set_charset("utf-8")
            with open(filename, "r") as fh:
                body = fh.read().rstrip("\n")
            attachment = MIMEText(body, "plain", "utf-8")
            attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=os.path.basename(filename),
            )
            msg.attach(attachment)

        return msg

    def _send_with_retries(self, msg, recipients, max_retries=3):
        """Try to deliver *msg* up to *max_retries* times."""
        print(f"[EMAIL] Sending to: {recipients}")

        for attempt in range(1, max_retries + 1):
            smtp = None
            try:
                print(f"[EMAIL] Attempt {attempt}/{max_retries} → {self.smtp_server}:{self.smtp_port}")
                smtp = self._connect_smtp()
                smtp.sendmail(self.from_email, recipients, msg.as_string())
                smtp.quit()
                print(f"[EMAIL] Sent to {len(recipients)} recipient(s)")
                return True

            except Exception as exc:
                print(f"[EMAIL] Attempt {attempt} failed: {exc}")
                self._safe_quit(smtp)

        print("[EMAIL] All retry attempts exhausted")
        return False

    def _connect_smtp(self):
        """Open and authenticate an SMTP connection."""
        if self.use_ssl or self.smtp_port == 465:
            conn = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=15)
        else:
            conn = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15)

        conn.ehlo()

        if self.use_tls and self.smtp_port != 465:
            conn.starttls()
            conn.ehlo()

        if self.smtp_username and self.smtp_password:
            conn.login(self.smtp_username, self.smtp_password)

        return conn

    @staticmethod
    def _safe_quit(smtp):
        """Silently close an SMTP connection if it exists."""
        if smtp:
            try:
                smtp.quit()
            except Exception:
                pass