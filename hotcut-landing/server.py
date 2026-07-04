"""
Hotcut Landing — Backend
/api/early-access : reçoit un email, génère un code, envoie via Brevo SMTP
"""
import os, sqlite3, secrets, smtplib, string
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path

app = Flask(__name__, static_folder=".")

# ── Config (variables d'environnement sur le VPS) ──────────────────────────
BREVO_SMTP_HOST   = "smtp-relay.brevo.com"
BREVO_SMTP_PORT   = 587
BREVO_SMTP_USER   = os.environ.get("BREVO_SMTP_USER", "")   # ton login Brevo
BREVO_SMTP_PASS   = os.environ.get("BREVO_SMTP_PASS", "")   # clé SMTP Brevo
FROM_EMAIL        = os.environ.get("FROM_EMAIL", "hello@hotcut.xyz")
FROM_NAME         = "Hotcut"

# ── Base de données ─────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "early_access.db"

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS early_access (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            email     TEXT UNIQUE NOT NULL,
            code      TEXT UNIQUE NOT NULL,
            created   TEXT NOT NULL,
            used      INTEGER DEFAULT 0
        )
    """)
    con.commit()
    con.close()

init_db()

# ── Génération de code ───────────────────────────────────────────────────────
def generate_code() -> str:
    """Génère un code unique style HOTCUT-A3X7-K2P9"""
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(secrets.choice(chars) for _ in range(4))
    part2 = ''.join(secrets.choice(chars) for _ in range(4))
    return f"HOTCUT-{part1}-{part2}"

def unique_code() -> str:
    con = sqlite3.connect(DB_PATH)
    while True:
        code = generate_code()
        exists = con.execute("SELECT 1 FROM early_access WHERE code=?", (code,)).fetchone()
        if not exists:
            con.close()
            return code

# ── Email HTML ───────────────────────────────────────────────────────────────
def build_email(email: str, code: str) -> tuple[str, str]:
    subject = f"Your Hotcut early access code — {code}"
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#080808;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:48px 16px">
      <table width="520" cellpadding="0" cellspacing="0"
             style="background:#111;border:1px solid #222;border-radius:16px;overflow:hidden">

        <!-- Header -->
        <tr><td style="padding:40px 40px 32px;border-bottom:1px solid #1a1a1a">
          <img src="https://hotcut.xyz/brand-assets/hotcut-mark.png?v=hotcut-mark-20260527"
               height="28" alt="Hotcut" style="display:block;margin-bottom:12px">
          <span style="color:#fff;font-size:1.1rem;font-weight:700;letter-spacing:-.02em">Hotcut</span>
        </td></tr>

        <!-- Body -->
        <tr><td style="padding:40px">
          <p style="color:#888;font-size:.85rem;margin:0 0 8px">Welcome to the beta,</p>
          <h1 style="color:#fff;font-size:1.6rem;font-weight:800;letter-spacing:-.03em;margin:0 0 20px;line-height:1.2">
            Your early access<br>code is ready.
          </h1>
          <p style="color:#666;font-size:.9rem;line-height:1.7;margin:0 0 32px">
            You're one of the first to join Hotcut — the platform for pro rider cards and equipment showcases. Use the code below to activate your instance.
          </p>

          <!-- Code block -->
          <div style="background:#0d0d0d;border:1px solid #2a2a2a;border-radius:12px;padding:28px;text-align:center;margin-bottom:32px">
            <p style="color:#555;font-size:.72rem;text-transform:uppercase;letter-spacing:.1em;margin:0 0 12px">Your early access code</p>
            <p style="color:#fff;font-size:1.8rem;font-weight:800;letter-spacing:.08em;margin:0;font-family:monospace">{code}</p>
          </div>

          <p style="color:#555;font-size:.82rem;line-height:1.65;margin:0">
            We'll reach out soon with instructions to set up your Hotcut instance. In the meantime, reply to this email if you have any questions.
          </p>
        </td></tr>

        <!-- Footer -->
        <tr><td style="padding:24px 40px;border-top:1px solid #1a1a1a">
          <p style="color:#333;font-size:.75rem;margin:0">
            © 2026 Hotcut &nbsp;·&nbsp;
            <a href="https://hotcut.xyz" style="color:#444;text-decoration:none">hotcut.xyz</a>
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return subject, html

# ── Routes ──────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/api/early-access", methods=["POST"])
def early_access():
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "Invalid email"}), 400

    con = sqlite3.connect(DB_PATH)
    try:
        # Email déjà inscrit ?
        row = con.execute("SELECT code FROM early_access WHERE email=?", (email,)).fetchone()
        if row:
            code = row[0]
        else:
            code = unique_code()
            con.execute(
                "INSERT INTO early_access (email, code, created) VALUES (?,?,?)",
                (email, code, datetime.utcnow().isoformat())
            )
            con.commit()

        # Envoi email via Brevo SMTP
        subject, html = build_email(email, code)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"]      = email
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(BREVO_SMTP_HOST, BREVO_SMTP_PORT) as s:
            s.starttls()
            s.login(BREVO_SMTP_USER, BREVO_SMTP_PASS)
            s.sendmail(FROM_EMAIL, email, msg.as_string())

        return jsonify({"ok": True, "code": code})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        con.close()

@app.route("/admin/early-access")
def admin_list():
    """Liste tous les inscrits (protéger avec auth plus tard)"""
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT email, code, created FROM early_access ORDER BY created DESC").fetchall()
    con.close()
    html = "<style>body{font-family:monospace;background:#0d0d0d;color:#eee;padding:32px}table{border-collapse:collapse;width:100%}td,th{padding:8px 16px;border-bottom:1px solid #222;text-align:left}th{color:#E8612C}</style>"
    html += f"<h2 style='color:#E8612C;margin-bottom:20px'>Early Access — {len(rows)} inscrits</h2><table><tr><th>Email</th><th>Code</th><th>Date</th></tr>"
    for r in rows:
        html += f"<tr><td>{r[0]}</td><td style='letter-spacing:.06em'>{r[1]}</td><td style='color:#555'>{r[2][:10]}</td></tr>"
    html += "</table>"
    return html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=False)
