"""Service de notification par email.

Pipeline unique : les événements de l'app appellent queue_email() qui écrit
dans email_outbox. Le transport est appliqué selon email_configs.transport_mode :

  eml      → generate_eml() écrit un fichier .eml téléchargeable
  smtp     → send_via_smtp() envoie immédiatement (BackgroundTasks côté routes)
  external → export JSON pour la CLI standalone email_sender.py
  mailbox  → réservé (mode 4, non implémenté)

Le serveur ne voit JAMAIS le clair des PV : l'envoi vers la direction passe
par MinuteShareLink (enveloppe DEK chiffrée sous un code de lecture).
"""
from __future__ import annotations

import os
import re
import secrets
from datetime import datetime, timedelta
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.models.email import EmailConfig, EmailOutbox, EmailEventType, EmailStatus, TransportMode
from app.models.organization import Organization

EMAIL_DIR = Path(os.environ.get("SD_EMAIL_DIR", "/app/data/emails"))

# ── Templates multilingues ──────────────────────────────────────────────
# {base_url} = racine de l'app ; {share_url} = lien de lecture sécurisé ;
# les autres clés sont fournies par le contexte de l'événement.

_T = {
    "fr": {
        "meeting_invite": {
            "subject": "Convocation — {meeting_title} ({org_name})",
            "body": """<p>Bonjour {recipient_name},</p>
<p>Vous êtes convié(e) à la réunion de la délégation du personnel :</p>
<p><strong>{meeting_title}</strong><br>
📅 {meeting_date} — 📍 {meeting_location}<br>
🏢 {org_name}</p>
<p>Ordre du jour : {agenda}</p>
<p>Merci de confirmer votre présence ou votre absence depuis l'application&nbsp;: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "meeting_reminder": {
            "subject": "Rappel — {meeting_title} dans {days} jour(s) ({org_name})",
            "body": """<p>Bonjour {recipient_name},</p>
<p>Rappel : la réunion <strong>{meeting_title}</strong> a lieu dans <strong>{days} jour(s)</strong> — le {meeting_date} à {meeting_location}.</p>
<p>Ordre du jour : {agenda}</p>
<p>Confirmez votre présence depuis l'application&nbsp;: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "minutes_direction": {
            "subject": "PV de la réunion {meeting_title} — {org_name}",
            "body": """<p>Bonjour,</p>
<p>Veuillez trouver ci-dessous le lien de consultation du procès-verbal de la réunion <strong>{meeting_title}</strong> du {meeting_date}.</p>
<p>🔗 <a href="{share_url}">{share_url}</a></p>
<p>Le code de lecture vous est communiqué séparément. Le lien expire le {expires_at}.</p>
<p>Cordialement,<br>{org_name}</p>""",
        },
        "minutes_dp": {
            "subject": "PV validé — {meeting_title} ({org_name})",
            "body": """<p>Bonjour {recipient_name},</p>
<p>Le procès-verbal de la réunion <strong>{meeting_title}</strong> du {meeting_date} a été validé.</p>
<p>Connectez-vous pour le consulter&nbsp;: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "member_invite": {
            "subject": "Invitation à rejoindre {org_name}",
            "body": """<p>Bonjour {recipient_name},</p>
<p>Vous avez été invité(e) à rejoindre la délégation du personnel <strong>{org_name}</strong>.</p>
<p>Votre code d'invitation : <code><strong>{invite_code}</strong></code></p>
<p>Créez votre compte ici&nbsp;: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "test": {
            "subject": "Test des notifications — {org_name}",
            "body": """<p>Ceci est un email de test de configuration.</p>
<p>Si vous le recevez, les notifications de <strong>{org_name}</strong> sont opérationnelles.</p>
<p>{signature}</p>""",
        },
        "consultation_created": {
            "subject": "Consultation — {title} ({org_name})",
            "body": """<p>Bonjour,</p>
<p>La délégation du personnel de <strong>{org_name}</strong> vous soumet une consultation (art. L.414-3 du Code du travail) :</p>
<p><strong>{title}</strong><br>
Domaine : {category}<br>
{description_block}</p>
<p>Merci de fournir une réponse motivée dans les meilleurs délais{response_due_block}.</p>
<p>{signature}</p>""",
        },
        "consultation_reminder": {
            "subject": "Rappel : réponse attendue — {title} ({org_name})",
            "body": """<p>Bonjour,</p>
<p>La consultation suivante, soumise par la délégation du personnel de <strong>{org_name}</strong> (art. L.414-3), attend toujours votre réponse motivée :</p>
<p><strong>{title}</strong>{response_due_block}</p>
<p>{signature}</p>""",
        },
    },
    "en": {
        "meeting_invite": {
            "subject": "Invitation — {meeting_title} ({org_name})",
            "body": """<p>Hello {recipient_name},</p>
<p>You are invited to the staff delegation meeting:</p>
<p><strong>{meeting_title}</strong><br>
📅 {meeting_date} — 📍 {meeting_location}<br>
🏢 {org_name}</p>
<p>Agenda: {agenda}</p>
<p>Please confirm your attendance from the app: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "meeting_reminder": {
            "subject": "Reminder — {meeting_title} in {days} day(s) ({org_name})",
            "body": """<p>Hello {recipient_name},</p>
<p>Reminder: the meeting <strong>{meeting_title}</strong> takes place in <strong>{days} day(s)</strong> — on {meeting_date} at {meeting_location}.</p>
<p>Agenda: {agenda}</p>
<p>Confirm your attendance from the app: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "minutes_direction": {
            "subject": "Minutes of meeting {meeting_title} — {org_name}",
            "body": """<p>Hello,</p>
<p>Please find below the link to consult the minutes of the meeting <strong>{meeting_title}</strong> held on {meeting_date}.</p>
<p>🔗 <a href="{share_url}">{share_url}</a></p>
<p>The reading code is communicated separately. The link expires on {expires_at}.</p>
<p>Best regards,<br>{org_name}</p>""",
        },
        "minutes_dp": {
            "subject": "Validated minutes — {meeting_title} ({org_name})",
            "body": """<p>Hello {recipient_name},</p>
<p>The minutes of the meeting <strong>{meeting_title}</strong> of {meeting_date} have been validated.</p>
<p>Log in to read them: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "member_invite": {
            "subject": "Invitation to join {org_name}",
            "body": """<p>Hello {recipient_name},</p>
<p>You have been invited to join the staff delegation <strong>{org_name}</strong>.</p>
<p>Your invitation code: <code><strong>{invite_code}</strong></code></p>
<p>Create your account here: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "test": {
            "subject": "Notification test — {org_name}",
            "body": """<p>This is a configuration test email.</p>
<p>If you receive it, notifications for <strong>{org_name}</strong> are operational.</p>
<p>{signature}</p>""",
        },
        "consultation_created": {
            "subject": "Consultation — {title} ({org_name})",
            "body": """<p>Dear Sir/Madam,</p>
<p>The staff delegation of <strong>{org_name}</strong> submits the following consultation to you (Art. L.414-3 of the Labour Code):</p>
<p><strong>{title}</strong><br>
Topic: {category}<br>
{description_block}</p>
<p>Please provide a reasoned answer as soon as possible{response_due_block}.</p>
<p>{signature}</p>""",
        },
        "consultation_reminder": {
            "subject": "Reminder: answer expected — {title} ({org_name})",
            "body": """<p>Dear Sir/Madam,</p>
<p>The following consultation, submitted by the staff delegation of <strong>{org_name}</strong> (Art. L.414-3), still awaits your reasoned answer:</p>
<p><strong>{title}</strong>{response_due_block}</p>
<p>{signature}</p>""",
        },
    },
    "de": {
        "meeting_invite": {
            "subject": "Einladung — {meeting_title} ({org_name})",
            "body": """<p>Guten Tag {recipient_name},</p>
<p>Sie sind zur Sitzung der Personaldelegation eingeladen:</p>
<p><strong>{meeting_title}</strong><br>
📅 {meeting_date} — 📍 {meeting_location}<br>
🏢 {org_name}</p>
<p>Tagesordnung: {agenda}</p>
<p>Bitte bestätigen Sie Ihre Teilnahme in der App: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "meeting_reminder": {
            "subject": "Erinnerung — {meeting_title} in {days} Tag(en) ({org_name})",
            "body": """<p>Guten Tag {recipient_name},</p>
<p>Erinnerung: Die Sitzung <strong>{meeting_title}</strong> findet in <strong>{days} Tag(en)</strong> statt — am {meeting_date} um {meeting_location}.</p>
<p>Tagesordnung: {agenda}</p>
<p>Bestätigen Sie Ihre Teilnahme in der App: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "minutes_direction": {
            "subject": "Protokoll der Sitzung {meeting_title} — {org_name}",
            "body": """<p>Guten Tag,</p>
<p>Bitte finden Sie unten den Link zum Protokoll der Sitzung <strong>{meeting_title}</strong> vom {meeting_date}.</p>
<p>🔗 <a href="{share_url}">{share_url}</a></p>
<p>Der Lesecode wird Ihnen separat mitgeteilt. Der Link läuft am {expires_at} ab.</p>
<p>Mit freundlichen Grüßen,<br>{org_name}</p>""",
        },
        "minutes_dp": {
            "subject": "Genehmigtes Protokoll — {meeting_title} ({org_name})",
            "body": """<p>Guten Tag {recipient_name},</p>
<p>Das Protokoll der Sitzung <strong>{meeting_title}</strong> vom {meeting_date} wurde genehmigt.</p>
<p>Melden Sie sich an, um es zu lesen: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "member_invite": {
            "subject": "Einladung zu {org_name}",
            "body": """<p>Guten Tag {recipient_name},</p>
<p>Sie wurden eingeladen, der Personaldelegation <strong>{org_name}</strong> beizutreten.</p>
<p>Ihr Einladungscode: <code><strong>{invite_code}</strong></code></p>
<p>Erstellen Sie Ihr Konto hier: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "test": {
            "subject": "Test-Benachrichtigung — {org_name}",
            "body": """<p>Dies ist eine Test-E-Mail der Konfiguration.</p>
<p>Wenn Sie diese erhalten, sind die Benachrichtigungen von <strong>{org_name}</strong> betriebsbereit.</p>
<p>{signature}</p>""",
        },
        "consultation_created": {
            "subject": "Konsultation — {title} ({org_name})",
            "body": """<p>Sehr geehrte Damen und Herren,</p>
<p>Die Personaldelegation von <strong>{org_name}</strong> legt Ihnen folgende Konsultation vor (Art. L.414-3 des Arbeitsgesetzbuchs):</p>
<p><strong>{title}</strong><br>
Bereich: {category}<br>
{description_block}</p>
<p>Bitte antworten Sie so bald wie möglich{response_due_block}.</p>
<p>{signature}</p>""",
        },
        "consultation_reminder": {
            "subject": "Erinnerung: Antwort erwartet — {title} ({org_name})",
            "body": """<p>Sehr geehrte Damen und Herren,</p>
<p>Die folgende Konsultation der Personaldelegation von <strong>{org_name}</strong> (Art. L.414-3) wartet weiterhin auf Ihre begründete Antwort:</p>
<p><strong>{title}</strong>{response_due_block}</p>
<p>{signature}</p>""",
        },
    },
    "pt": {
        "meeting_invite": {
            "subject": "Convocação — {meeting_title} ({org_name})",
            "body": """<p>Olá {recipient_name},</p>
<p>Você está convidado(a) para a reunião da delegação do pessoal:</p>
<p><strong>{meeting_title}</strong><br>
📅 {meeting_date} — 📍 {meeting_location}<br>
🏢 {org_name}</p>
<p>Ordem do dia: {agenda}</p>
<p>Confirme a sua presença na aplicação: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "meeting_reminder": {
            "subject": "Lembrete — {meeting_title} em {days} dia(s) ({org_name})",
            "body": """<p>Olá {recipient_name},</p>
<p>Lembrete: a reunião <strong>{meeting_title}</strong> realiza-se em <strong>{days} dia(s)</strong> — em {meeting_date} às {meeting_location}.</p>
<p>Ordem do dia: {agenda}</p>
<p>Confirme a sua presença na aplicação: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "minutes_direction": {
            "subject": "Ata da reunião {meeting_title} — {org_name}",
            "body": """<p>Olá,</p>
<p>Encontre abaixo o link para consultar a ata da reunião <strong>{meeting_title}</strong> de {meeting_date}.</p>
<p>🔗 <a href="{share_url}">{share_url}</a></p>
<p>O código de leitura é comunicado separadamente. O link expira em {expires_at}.</p>
<p>Cumprimentos,<br>{org_name}</p>""",
        },
        "minutes_dp": {
            "subject": "Ata validada — {meeting_title} ({org_name})",
            "body": """<p>Olá {recipient_name},</p>
<p>A ata da reunião <strong>{meeting_title}</strong> de {meeting_date} foi validada.</p>
<p>Inicie sessão para a consultar: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "member_invite": {
            "subject": "Convite para {org_name}",
            "body": """<p>Olá {recipient_name},</p>
<p>Foi convidado(a) a aderir à delegação do pessoal <strong>{org_name}</strong>.</p>
<p>O seu código de convite: <code><strong>{invite_code}</strong></code></p>
<p>Crie a sua conta aqui: <a href="{base_url}">{base_url}</a></p>
<p>{signature}</p>""",
        },
        "test": {
            "subject": "Teste de notificação — {org_name}",
            "body": """<p>Este é um e-mail de teste de configuração.</p>
<p>Se o receber, as notificações de <strong>{org_name}</strong> estão operacionais.</p>
<p>{signature}</p>""",
        },
        "consultation_created": {
            "subject": "Consulta — {title} ({org_name})",
            "body": """<p>Caro(a) senhor(a),</p>
<p>A delegação do pessoal de <strong>{org_name}</strong> submete-lhe a seguinte consulta (art. L.414-3 do Código do Trabalho):</p>
<p><strong>{title}</strong><br>
Domínio: {category}<br>
{description_block}</p>
<p>Queira fornecer uma resposta fundamentada o mais rapidamente possível{response_due_block}.</p>
<p>{signature}</p>""",
        },
        "consultation_reminder": {
            "subject": "Lembrete: resposta aguardada — {title} ({org_name})",
            "body": """<p>Caro(a) senhor(a),</p>
<p>A seguinte consulta, apresentada pela delegação do pessoal de <strong>{org_name}</strong> (art. L.414-3), aguarda ainda a sua resposta fundamentada:</p>
<p><strong>{title}</strong>{response_due_block}</p>
<p>{signature}</p>""",
        },
    },
}


def _fmt_date(dt: datetime, lang: str) -> str:
    months = {
        "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
        "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
        "pt": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
    }
    m = months.get(lang, months["fr"])[dt.month - 1]
    return f"{dt.day} {m} {dt.year}"


def _strip_html(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"</p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def render_email(config: EmailConfig, org: Organization, event_type: str, ctx: dict, lang: str) -> tuple[str, str, str]:
    """Rend (subject, body_html, body_text) pour un événement et une langue."""
    tpl = _T.get(lang, _T["fr"]).get(event_type)
    if tpl is None:
        tpl = _T["fr"][event_type]

    values = dict(ctx)
    values.setdefault("org_name", org.name)
    values.setdefault("signature", config.signature or "")
    values.setdefault("base_url", ctx.get("base_url", ""))
    # Blocs localisés : description de la consultation + échéance de réponse
    lang_code = lang if lang in _T else "fr"
    if "description_block" not in values:
        desc = values.get("description")
        safe = (str(desc).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if desc else "")
        values["description_block"] = f"<br>{safe}" if safe else ""
    if "response_due_block" not in values:
        due = values.get("response_due")
        if due:
            prefix = {
                "fr": " avant le ",
                "en": " before ",
                "de": " vor dem ",
                "pt": " antes de ",
            }.get(lang_code, " avant le ")
            values["response_due_block"] = f"{prefix}{due}"
        else:
            values["response_due_block"] = ""
    # Échapper les valeurs utilisateur dans le HTML (les blocs construits
    # ci-dessus sont déjà échappés/sûrs — ne pas les ré-échapper)
    esc = {k: str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
           for k, v in values.items() if k not in ("description_block", "response_due_block")}
    esc.update({k: values[k] for k in ("description_block", "response_due_block") if k in values})
    subject = tpl["subject"].format(**values)
    body_html = tpl["body"].format(**esc)
    return subject, body_html, _strip_html(body_html)


def queue_email(db: Session, org_id: int, event_type: str, recipient_name: str, recipient_email: str, lang: str, ctx: dict) -> Optional[EmailOutbox]:
    """Alimente l'outbox. Retourne None si les notifications sont désactivées
    ou si un message identique est déjà en file (idempotence)."""
    config = db.query(EmailConfig).filter(EmailConfig.organization_id == org_id).first()
    if config is None or not config.enabled:
        return None
    org = db.query(Organization).get(org_id)
    subject, body_html, body_text = render_email(config, org, event_type, ctx, lang)

    existing = db.query(EmailOutbox).filter(
        EmailOutbox.organization_id == org_id,
        EmailOutbox.event_type == event_type,
        EmailOutbox.recipient_email == recipient_email,
        EmailOutbox.status.in_([EmailStatus.ready, EmailStatus.sent]),
        EmailOutbox.payload == ctx,
    ).first()
    if existing:
        return existing

    msg = EmailOutbox(
        organization_id=org_id,
        event_type=event_type,
        transport=config.transport_mode,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        lang=lang,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        payload=ctx,
        status=EmailStatus.ready,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Mode eml : générer immédiatement le fichier (l'admin le télécharge ensuite)
    if config.transport_mode == TransportMode.eml:
        msg.eml_path = generate_eml(config, org, msg)
        db.commit()
    return msg


def _mime_message(config: EmailConfig, org: Organization, msg: EmailOutbox) -> MIMEMultipart:
    from_name = config.from_name or org.name
    from_email = config.from_email or f"noreply@{org.name.lower().replace(' ', '')}.invalid"
    m = MIMEMultipart("alternative")
    m["From"] = formataddr((str(Header(from_name, "utf-8")), from_email))
    m["To"] = formataddr((str(Header(msg.recipient_name or "", "utf-8")), msg.recipient_email))
    m["Subject"] = str(Header(msg.subject, "utf-8"))
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain=from_email.split("@")[-1])
    if config.reply_to:
        m["Reply-To"] = config.reply_to
    m.attach(MIMEText(msg.body_text, "plain", "utf-8"))
    m.attach(MIMEText(msg.body_html, "html", "utf-8"))
    return m


def generate_eml(config: EmailConfig, org: Organization, msg: EmailOutbox) -> str:
    """Écrit le fichier .eml (RFC 5322) sur disque et retourne son chemin."""
    EMAIL_DIR.mkdir(parents=True, exist_ok=True)
    m = _mime_message(config, org, msg)
    filename = f"{msg.created_at:%Y%m%d-%H%M%S}-{msg.id}-{msg.event_type}.eml"
    path = EMAIL_DIR / filename
    path.write_bytes(m.as_bytes())
    return str(path)


def send_via_smtp(config: EmailConfig, org: Organization, msg: EmailOutbox) -> None:
    """Envoie via smtplib (STARTTLS ou SSL direct, auth optionnelle)."""
    import smtplib

    m = _mime_message(config, org, msg)
    if config.smtp_use_ssl:
        server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=15)
    else:
        server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
        if config.smtp_use_tls:
            server.starttls()
    try:
        if config.smtp_user:
            server.login(config.smtp_user, config.smtp_password or "")
        server.sendmail(
            m["From"],
            [msg.recipient_email],
            m.as_string(),
        )
    finally:
        server.quit()


def send_ready_smtp(db: Session, org_id: Optional[int] = None) -> tuple[int, int]:
    """Envoie les messages prêts en mode smtp (retry simple, 1 tentative/tick).
    Retourne (envoyés, échoués). Appelé en BackgroundTasks depuis les routes."""
    q = db.query(EmailOutbox).filter(
        EmailOutbox.status == EmailStatus.ready,
        EmailOutbox.transport == TransportMode.smtp,
    )
    if org_id is not None:
        q = q.filter(EmailOutbox.organization_id == org_id)

    sent = failed = 0
    for msg in q.limit(50).all():
        config = db.query(EmailConfig).filter(EmailConfig.organization_id == msg.organization_id).first()
        org = db.query(Organization).get(msg.organization_id)
        if not config or not config.enabled or not config.smtp_host:
            continue
        try:
            send_via_smtp(config, org, msg)
            msg.status = EmailStatus.sent
            msg.sent_at = datetime.utcnow()
            sent += 1
        except Exception as e:  # noqa: BLE001
            msg.attempts += 1
            msg.last_error = str(e)[:500]
            if msg.attempts >= 5:
                msg.status = EmailStatus.failed
            failed += 1
        db.add(msg)
    db.commit()
    return sent, failed


def scan_due_reminders(db: Session, base_url: str = "") -> int:
    """File les rappels de réunion dus (J - remind_days_before, par org).

    Idempotent : un rappel déjà en file (ready/sent) pour la même réunion +
    le même destinataire n'est pas dupliqué. Appelé au démarrage du backend.
    Retourne le nombre de rappels nouvellement mis en file.
    """
    from app.models.meeting import Meeting, MeetingInvitee

    today = datetime.utcnow().date()
    queued = 0
    configs = db.query(EmailConfig).filter(EmailConfig.enabled == True).all()  # noqa: E712
    for config in configs:
        due_at = today + timedelta(days=config.remind_days_before)
        meetings = db.query(Meeting).filter(
            Meeting.organization_id == config.organization_id,
            Meeting.status == "planned",
        ).all()
        for meeting in meetings:
            if meeting.date is None:
                continue
            meeting_date = meeting.date
            if meeting_date.tzinfo:
                meeting_date = meeting_date.replace(tzinfo=None)
            if meeting_date.date() != due_at:
                continue
            ctx_base = {
                "base_url": base_url,
                "meeting_title": meeting.title,
                "meeting_date": f"{meeting_date:%d/%m/%Y}",
                "meeting_location": meeting.location or "",
                "days": config.remind_days_before,
                "agenda": ", ".join(p.description for p in (meeting.points or [])[:5]),
            }
            for inv in meeting.invitees or []:
                user = inv.user
                if not user or not user.email:
                    continue
                ctx = dict(ctx_base, recipient_name=user.full_name or user.email,
                           **{"meeting_id": meeting.id, "remind_days": config.remind_days_before})
                if queue_email(db, config.organization_id, EmailEventType.meeting_reminder.value,
                               user.full_name, user.email, user.language or "fr", ctx):
                    queued += 1
    db.commit()
    return queued


# Libellés lisibles des catégories de consultation (email direction, FR par défaut)
CATEGORY_LABELS_FR: dict[str, str] = {
    "conditions_travail": "Conditions de travail",
    "reglement_interieur": "Règlement intérieur",
    "temps_travail": "Temps de travail",
    "pension": "Régime de pension",
    "formation": "Plan de formation continue",
    "reclassement": "Reclassement interne",
    "licenciements_collectifs": "Licenciements collectifs",
    "transfert": "Transfert d'entreprise",
    "interimaire": "Recours à l'intérim",
    "oeuvres_sociales": "Œuvres sociales",
    "statistiques_sexe": "Statistiques ventilées par sexe",
    "teletravail": "Télétravail / droit à la déconnexion",
    "autre": "Autre",
}


def scan_consultation_reminders(db: Session, base_url: str = "") -> int:
    """File un rappel à la direction pour chaque consultation en attente dont
    l'échéance de réponse est dépassée (art. L.414-3).

    Idempotent : au plus 1 rappel par consultation par jour (last_reminded_at).
    Appelé au démarrage du backend, comme scan_due_reminders.
    """
    from app.models.consultation import Consultation, ConsultationStatus

    now = datetime.utcnow()
    queued = 0
    rows = db.query(Consultation).filter(
        Consultation.status == ConsultationStatus.requested,
        Consultation.response_due.isnot(None),
        Consultation.response_due < now,
    ).all()
    for c in rows:
        org = c.organization
        if org is None:
            continue
        config = db.query(EmailConfig).filter(
            EmailConfig.organization_id == c.organization_id, EmailConfig.enabled == True  # noqa: E712
        ).first()
        if config is None or not config.direction_email:
            continue
        # Au plus un rappel par jour
        if c.last_reminded_at is not None and (now - c.last_reminded_at).total_seconds() < 86400:
            continue
        queued_msg = queue_email(
            db, c.organization_id, "consultation_reminder",
            "Direction", config.direction_email, "fr",
            {
                "base_url": base_url,
                "consultation_id": c.id,
                "title": c.title,
                "category": CATEGORY_LABELS_FR.get(c.category.value, c.category.value),
                "response_due": c.response_due.isoformat() if c.response_due else None,
            },
        )
        if queued_msg:
            c.last_reminded_at = now
            queued += 1
    db.commit()
    return queued
