"""Sends the only two emails cvwrite3 ever sends: the sign-in code (Addendum 5), and one "there's room" email
to a waitlisted person who asked for it (Addendum 6, sent only when the owner presses the button).

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


OPEN_BODY = """There's room at cvwrite3 now.

Sign in at {origin} to join. Places go to whoever signs in first.

You asked us to email you once when there was room. This is that email: we won't send another.
"""


class MailError(Exception):
    pass


def message(sender, to, code):
    return _message(sender, to, f"{code} is your cvwrite3 code", BODY.format(code=code))


def open_message(sender, to, origin):
    return _message(sender, to, "There's room at cvwrite3 now", OPEN_BODY.format(origin=origin))


def _message(sender, to, subject, body):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = sender, to, subject
    m["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1].strip("> "))
    m.set_content(body)
    return m


class SMTPMailer:
    def __init__(self, settings):
        self.s = settings

    def send_code(self, to, code):
        self._send(message(self.s.mail_from, to, code))

    def send_open(self, to, origin):
        self._send(open_message(self.s.mail_from, to, origin))

    def _send(self, msg):
        s, ctx = self.s, ssl.create_default_context()
        try:
            if s.smtp_port == 465:
                smtp = smtplib.SMTP_SSL(s.smtp_host, 465, timeout=15, context=ctx)
            else:
                smtp = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15)
                smtp.starttls(context=ctx)
            with smtp:
                smtp.login(s.smtp_user, s.smtp_password)
                smtp.send_message(msg)
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

    def send_open(self, to, origin):
        self.sent.append((to, "open"))
        if self.echo:
            print(f"[dev mail] there's room, to {to}", flush=True)
