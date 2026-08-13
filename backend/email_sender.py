#!/usr/bin/env python3
"""email_sender.py — CLI standalone d'envoi des notifications StaffDPapp.

Mode 3 (transport « external ») : l'administrateur exporte les messages
prêts depuis l'application (JSON), puis lance ce script sur n'importe quelle
machine disposant d'un accès SMTP — y compris sans rapport avec le serveur
de l'app. Aucune dépendance : Python 3.9+ standard library only.

Usage:
    python3 email_sender.py --input messages.json \
        --host smtp.example.com --port 587 --user bob --password secret [--tls]
    python3 email_sender.py --input messages.json \
        --host smtp.example.com --port 465 --ssl --user bob --password secret

Format de messages.json :
    [
      {
        "to": "dest@example.com",
        "subject": "Convocation ...",
        "body_text": "...",
        "body_html": "<p>...</p>",
        "from_name": "Délégation Demo",
        "from_email": "delegation@example.invalid",
        "reply_to": null
      }
    ]

Le script écrit sent.json (liste des envoyés) et failed.json en cas d'erreur.
"""
import argparse
import json
import smtplib
import sys
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path


def build_message(item: dict) -> MIMEMultipart:
    from_name = item.get("from_name") or item.get("from_email", "noreply@invalid")
    from_email = item.get("from_email", "noreply@invalid")
    m = MIMEMultipart("alternative")
    m["From"] = formataddr((str(Header(from_name, "utf-8")), from_email))
    m["To"] = formataddr((str(Header(item.get("to_name", ""), "utf-8")), item["to"]))
    m["Subject"] = str(Header(item["subject"], "utf-8"))
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain=from_email.split("@")[-1])
    if item.get("reply_to"):
        m["Reply-To"] = item["reply_to"]
    m.attach(MIMEText(item.get("body_text", ""), "plain", "utf-8"))
    m.attach(MIMEText(item.get("body_html", item.get("body_text", "")), "html", "utf-8"))
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description="Envoyer les notifications StaffDPapp exportées")
    ap.add_argument("--input", required=True, help="messages.json exporté depuis l'app")
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=587)
    ap.add_argument("--user", default=None)
    ap.add_argument("--password", default=None)
    ap.add_argument("--tls", action="store_true", help="STARTTLS (défaut si port 587)")
    ap.add_argument("--ssl", action="store_true", help="SSL direct (port 465)")
    ap.add_argument("--dry-run", action="store_true", help="affiche seulement, n'envoie pas")
    args = ap.parse_args()

    items = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not items:
        print("Aucun message à envoyer.")
        return 0

    sent, failed = [], []
    server = None
    if not args.dry_run:
        if args.ssl:
            server = smtplib.SMTP_SSL(args.host, args.port, timeout=20)
        else:
            server = smtplib.SMTP(args.host, args.port, timeout=20)
            if args.tls or args.port == 587:
                server.starttls()
        if args.user:
            server.login(args.user, args.password or "")

    try:
        for item in items:
            msg = build_message(item)
            if args.dry_run:
                print(f"[dry-run] → {item['to']} : {item['subject']}")
                sent.append(item["to"])
                continue
            server.sendmail(msg["From"], [item["to"]], msg.as_string())
            sent.append(item["to"])
            print(f"✓ {item['to']} : {item['subject']}")
    except Exception as e:  # noqa: BLE001
        print(f"✗ échec : {e}", file=sys.stderr)
        failed.append(str(e))
    finally:
        if server:
            server.quit()

    Path("sent.json").write_text(json.dumps(sent, ensure_ascii=False, indent=2), encoding="utf-8")
    if failed:
        Path("failed.json").write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1
    print(f"{len(sent)} envoyé(s), 0 échec.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
