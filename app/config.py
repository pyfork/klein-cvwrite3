"""Settings from the environment. Secrets come from .env (0600) on sk24, never from git."""
import os
from pathlib import Path
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    env: str                # "prod" or "dev"
    database_url: str
    owner_email: str
    secret_key: str         # signs CSRF tokens; keys the HMACs of sign-in codes and session tokens
    app_origin: str         # e.g. "https://betterjobs.puascari.com"; POSTs must come from here
    wave2_cap: int = 30   # open sign-ups stop here; the rest join the waitlist (owner, 2026-10-25)
    data_dir: str = str(Path(__file__).resolve().parent.parent / "data")  # PDFs live under data/pdfs/
    claude: str = "real"    # "fake" (dev and tests only) answers without calling Claude
    qr_path: str = str(Path(__file__).resolve().parent.parent / "config" / "qr" / "duitnow.png")  # outside git
    # The sign-in code's mail (prod only; dev and tests keep codes in an outbox).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = ""     # e.g. "cvwrite3 <signin@puascari.com>"


def load(environ=os.environ):
    def need(key):
        value = environ.get(key, "").strip()
        if not value:
            raise ConfigError(f"{key} is not set")
        return value

    env = environ.get("CVWRITE_ENV", "prod").strip()
    if env not in ("prod", "dev"):
        raise ConfigError("CVWRITE_ENV must be prod or dev")
    mail = {}
    if env == "prod":
        mail = dict(smtp_host=need("CVWRITE_SMTP_HOST"), smtp_user=need("CVWRITE_SMTP_USER"),
                    smtp_password=need("CVWRITE_SMTP_PASSWORD"), mail_from=need("CVWRITE_MAIL_FROM"))
        port = environ.get("CVWRITE_SMTP_PORT", "587").strip() or "587"
        if not port.isdigit():
            raise ConfigError("CVWRITE_SMTP_PORT must be a number")
        mail["smtp_port"] = int(port)
    secret = need("CVWRITE_SECRET_KEY")
    if len(secret) < 32:
        raise ConfigError("CVWRITE_SECRET_KEY must be at least 32 characters")
    claude = environ.get("CVWRITE_CLAUDE", "real").strip()
    if claude not in ("real", "fake") or (claude == "fake" and env == "prod"):
        raise ConfigError("CVWRITE_CLAUDE must be real in prod (fake is for dev only)")
    return Settings(
        env=env,
        database_url=need("CVWRITE_DATABASE_URL"),
        owner_email=need("CVWRITE_OWNER_EMAIL").lower(),
        secret_key=secret,
        app_origin=need("CVWRITE_APP_ORIGIN").rstrip("/"),
        data_dir=environ.get("CVWRITE_DATA_DIR", "").strip() or Settings.data_dir,
        claude=claude,
        qr_path=environ.get("CVWRITE_QR_PATH", "").strip() or Settings.qr_path,
        **mail,
    )
