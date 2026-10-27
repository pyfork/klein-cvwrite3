"""The user's profile: one master CV (as text), contact fields and standing edits."""
CONTACT = ("name", "location", "phone", "email", "links")
LIMITS = {"name": 120, "location": 120, "phone": 60, "email": 200, "links": 300, "standing_edits": 2000}


def get(conn, account_id):
    row = conn.execute("select * from profiles where account_id = %s", (account_id,)).fetchone()
    return row or {"account_id": account_id, "master_text": "", "master_name": "", "standing_edits": "",
                   **{k: "" for k in CONTACT}}


def contact(p):
    """The dict render/contact.py takes."""
    return {k: p[k] for k in CONTACT if p.get(k)}


def clean(fields):
    return {k: " ".join(str(fields.get(k, "")).split())[: LIMITS[k]] if k != "standing_edits"
            else str(fields.get(k, "")).strip()[: LIMITS[k]] for k in LIMITS}


def save(conn, account_id, master_text, master_name, fields):
    f = clean(fields)
    conn.execute(
        """insert into profiles (account_id, master_text, master_name, name, location, phone, email, links, standing_edits)
           values (%(a)s, %(mt)s, %(mn)s, %(name)s, %(location)s, %(phone)s, %(email)s, %(links)s, %(standing_edits)s)
           on conflict (account_id) do update set master_text = excluded.master_text, master_name = excluded.master_name,
             name = excluded.name, location = excluded.location, phone = excluded.phone, email = excluded.email,
             links = excluded.links, standing_edits = excluded.standing_edits, updated_at = now()""",
        {"a": account_id, "mt": master_text, "mn": master_name[:200], **f},
    )


def ready(p):
    """What's missing before a first generation, as a user message, or None."""
    if not p["master_text"].strip():
        return "Upload your master CV first."
    if not p.get("name"):
        return "Add your name in Profile first. It goes at the top of every CV."
    return None


PHRASES = {"master": "upload your master CV", "name": "add your full name"}


def missing(p):
    """What's still to do before a first CV, as keys of PHRASES, in the order a person would do them."""
    return [k for k, gap in (("master", not p["master_text"].strip()), ("name", not p.get("name"))) if gap]


def todo_text(keys):
    return " and ".join(PHRASES[k] for k in keys)
