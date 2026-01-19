"""Alert notification routing for email and other channels."""

from __future__ import annotations

import json
import os
import smtplib
from email.message import EmailMessage
from typing import Iterable

from sqlalchemy import create_engine, text

from eap.logging import configure_logging

DB = os.environ["DATABASE_URL"]
engine = create_engine(DB, pool_pre_ping=True)
logger = configure_logging(os.getenv("LOG_LEVEL", "INFO"))


def _parse_recipients(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [address.strip() for address in raw.split(",") if address.strip()]


def _build_email_body(alert: dict) -> str:
    return (
        "Alert details:\n"
        f"Metric: {alert['metric_name']}\n"
        f"Severity: {alert['severity']}\n"
        f"Risk score: {alert['risk_score']}\n"
        f"Message: {alert['message']}\n"
        f"Timestamp: {alert['ts']}\n"
        f"Context: {alert['context']}\n"
    )


def _send_email(
    recipients: Iterable[str],
    subject: str,
    body: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str | None,
    smtp_password: str | None,
    smtp_use_tls: bool,
    sender: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        if smtp_use_tls:
            smtp.starttls()
        if smtp_user and smtp_password:
            smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)


def _fetch_pending_email_alerts(conn, target: str, limit: int) -> list[dict]:
    return (
        conn.execute(
            text(
                """
            SELECT a.alert_id,
                   a.metric_name,
                   a.metric_date::text,
                   a.severity,
                   a.risk_score,
                   a.message,
                   a.context,
                   a.ts::text
            FROM alerts a
            LEFT JOIN alert_notifications n
              ON n.alert_id = a.alert_id
             AND n.channel = 'email'
             AND n.target = :target
             AND n.status = 'sent'
            WHERE n.notification_id IS NULL
            ORDER BY a.ts ASC
            LIMIT :limit
            """
            ),
            {"target": target, "limit": limit},
        )
        .mappings()
        .all()
    )


def _record_notification(
    conn,
    alert_id: int,
    channel: str,
    target: str,
    status: str,
    payload: dict,
    error: str | None = None,
) -> None:
    conn.execute(
        text(
            """
        INSERT INTO alert_notifications(
          alert_id,
          channel,
          target,
          status,
          payload,
          last_error,
          sent_at
        )
        VALUES (
          :alert_id,
          :channel,
          :target,
          :status,
          CAST(:payload AS jsonb),
          :last_error,
          CASE WHEN :status = 'sent' THEN NOW() ELSE NULL END
        )
        ON CONFLICT (alert_id, channel, target)
        DO UPDATE SET
          status = EXCLUDED.status,
          payload = EXCLUDED.payload,
          last_error = EXCLUDED.last_error,
          sent_at = EXCLUDED.sent_at
        """
        ),
        {
            "alert_id": alert_id,
            "channel": channel,
            "target": target,
            "status": status,
            "payload": json.dumps(payload),
            "last_error": error,
        },
    )


def send_email_notifications(limit: int = 50) -> int:
    recipients = _parse_recipients(os.getenv("ALERT_EMAIL_TO"))
    if not recipients:
        logger.info("email_notifications_skipped", reason="missing_recipients")
        return 0

    sender = os.getenv("ALERT_EMAIL_FROM", "alerts@eap.local")
    smtp_host = os.getenv("SMTP_HOST", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "25"))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "false").lower() == "true"
    target = ",".join(recipients)

    sent = 0
    with engine.begin() as conn:
        alerts = _fetch_pending_email_alerts(conn, target, limit)
        for alert in alerts:
            subject = (
                f"[EAP] {alert['severity']} {alert['metric_name']} "
                f"{alert['metric_date'] or ''}".strip()
            )
            body = _build_email_body(alert)
            payload = {
                "subject": subject,
                "recipients": recipients,
                "alert_id": alert["alert_id"],
            }
            try:
                _send_email(
                    recipients=recipients,
                    subject=subject,
                    body=body,
                    smtp_host=smtp_host,
                    smtp_port=smtp_port,
                    smtp_user=smtp_user,
                    smtp_password=smtp_password,
                    smtp_use_tls=smtp_use_tls,
                    sender=sender,
                )
                _record_notification(
                    conn,
                    alert_id=alert["alert_id"],
                    channel="email",
                    target=target,
                    status="sent",
                    payload=payload,
                )
                sent += 1
            except Exception as error:
                logger.error("email_notification_failed", error=str(error))
                _record_notification(
                    conn,
                    alert_id=alert["alert_id"],
                    channel="email",
                    target=target,
                    status="failed",
                    payload=payload,
                    error=str(error),
                )
    logger.info("email_notifications_complete", sent=sent)
    return sent


def run() -> None:
    send_email_notifications()
