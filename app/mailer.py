"""Sends the sign-in code: the only email cvwrite3 ever sends (Addendum 5).

SMTP from the standard library, so any provider works and there's no new dependency. Port 465 is TLS from
the start; any other port must offer STARTTLS, or nothing is sent. Nothing about the message is logged.
"""
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid

BODY = """Your cvwrite3 sign-in code is {code}

It works for 10 minutes. Type it on the page where you asked for it.

If you didn't ask for a code, ignore this email: nobody can sign in without it.
"""


class MailError(Exception):
    pass


def message(sender, to, code):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = sender, to, f"{code} is your cvwrite3 code"
    m["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1].strip("> "))
    m.set_content(BODY.format(code=code))
    return m


class SMTPMailer:
    def __init__(self, settings):
        self.s = settings

    def send_code(self, to, code):
        s, ctx = self.s, ssl.create_default_context()
        try:
            if s.smtp_port == 465:
                smtp = smtplib.SMTP_SSL(s.smtp_host, 465, timeout=15, context=ctx)
            else:
                smtp = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15)
                smtp.starttls(context=ctx)
            with smtp:
                smtp.login(s.smtp_user, s.smtp_password)
                smtp.send_message(message(s.mail_from, to, code))
        except (OSError, smtplib.SMTPException) as e:
            raise MailError(type(e).__name__) from None


class Outbox:
    """Dev and tests: keeps what would have been sent. In dev the code is also printed (made-up emails only)."""

    def __init__(self, echo=False):
        self.sent, self.echo = [], echo

    def send_code(self, to, code):
        self.sent.append((to, code))
        if self.echo:
            print(f"[dev mail] code for {to}: {code}", flush=True)
