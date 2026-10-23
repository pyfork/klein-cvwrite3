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
    secret_key: str         # signs CSRF tokens
    access_team: str        # Cloudflare Access team domain, e.g. "example.cloudflareaccess.com"
    access_aud: str         # the Access application's AUD tag
    access_certs_url: str   # the team's signing keys; a file:// URL is allowed in dev only
    app_origin: str         # e.g. "https://cvwrite3.puascari.com"; POSTs must come from here
    wave2_cap: int = 50
    data_dir: str = str(Path(__file__).resolve().parent.parent / "data")  # PDFs live under data/pdfs/
    claude: str = "real"    # "fake" (dev and tests only) answers without calling Claude
    qr_path: str = str(Path(__file__).resolve().parent.parent / "config" / "qr" / "duitnow.png")  # outside git

    @property
    def access_issuer(self):
        return "https://" + self.access_team


def load(environ=os.environ):
    def need(key):
        value = environ.get(key, "").strip()
        if not value:
            raise ConfigError(f"{key} is not set")
        return value

    env = environ.get("CVWRITE_ENV", "prod").strip()
    if env not in ("prod", "dev"):
        raise ConfigError("CVWRITE_ENV must be prod or dev")
    team = need("CVWRITE_ACCESS_TEAM")
    certs = environ.get("CVWRITE_ACCESS_CERTS_URL", "").strip() or f"https://{team}/cdn-cgi/access/certs"
    if env == "prod" and not certs.startswith("https://"):
        raise ConfigError("CVWRITE_ACCESS_CERTS_URL must be https in prod")
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
        access_team=team,
        access_aud=need("CVWRITE_ACCESS_AUD"),
        access_certs_url=certs,
        app_origin=need("CVWRITE_APP_ORIGIN").rstrip("/"),
        data_dir=environ.get("CVWRITE_DATA_DIR", "").strip() or Settings.data_dir,
        claude=claude,
        qr_path=environ.get("CVWRITE_QR_PATH", "").strip() or Settings.qr_path,
    )
