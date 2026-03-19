import smtplib
import csv
import os
import time
import logging
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from dotenv import load_dotenv


#  STEP 1: Load secrets from .env file
load_dotenv()

SENDER_EMAIL    = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")   # Gmail App Password (not real password)
SMTP_HOST       = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", 587))

#  STEP 2: Setup Logging (file + console)
os.makedirs("logs", exist_ok=True)
timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"logs/email_log_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("EmailBot")

#  STEP 3: Read Recipients from CSV
def read_recipients(csv_path: str) -> list[dict]:
    """
    Reads recipient data from a CSV file.

    CSV must have at minimum:
        name, email

    Any extra columns (e.g. company, role) can be used
    as personalisation placeholders in subject/body.

    Returns:
        List of dicts, one per valid recipient row.
    """
    recipients = []

    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: '{csv_path}'")
        return recipients

    with open(csv_path, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for idx, row in enumerate(reader, start=2):          # row 1 = header
            name  = row.get("name",  "").strip()
            email = row.get("email", "").strip()

            if not name or not email:
                logger.warning(f"Row {idx}: missing name/email — skipped: {dict(row)}")
                continue

            if "@" not in email or "." not in email.split("@")[-1]:
                logger.warning(f"Row {idx}: invalid email '{email}' — skipped")
                continue

            recipients.append(dict(row))

    logger.info(f"Loaded {len(recipients)} valid recipient(s) from '{csv_path}'")
    return recipients

#  STEP 4: Personalise Subject / Body
def personalise(template: str, data: dict) -> str:
    """
    Replaces {placeholders} in the template with recipient data.

    Example:
        template  = "Hello {name}, welcome to {company}!"
        data      = {"name": "Rahul", "company": "Syntecxhub"}
        result    = "Hello Rahul, welcome to Syntecxhub!"
    """
    try:
        return template.format(**data)
    except KeyError as missing_key:
        logger.warning(
            f"Placeholder {missing_key} not found for '{data.get('email')}' "
            f"— sending template as-is."
        )
        return template

#  STEP 5: Build the Email (MIME format)
def build_email(
    sender:      str,
    recipient:   dict,
    subject:     str,
    body_html:   str,
    attachments: list[str] = []
) -> MIMEMultipart:
    """
    Constructs a complete MIME email message.

    Args:
        sender:      Sender's email address.
        recipient:   Dict with at least 'name' and 'email'.
        subject:     Email subject (supports {placeholders}).
        body_html:   HTML body (supports {placeholders}).
        attachments: List of local file paths to attach.

    Returns:
        A MIMEMultipart email object ready to send.
    """
    msg = MIMEMultipart("alternative")
    msg["From"]    = sender
    msg["To"]      = recipient["email"]
    msg["Subject"] = personalise(subject, recipient)

    # ── Personalised HTML body ──
    html_content = personalise(body_html, recipient)
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    # ── Attach files ──
    for filepath in attachments:
        if not os.path.isfile(filepath):
            logger.warning(f"Attachment not found, skipping: '{filepath}'")
            continue

        filename = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            payload = f.read()

        part = MIMEBase("application", "octet-stream")
        part.set_payload(payload)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)
        logger.info(f"  📎 Attached: {filename}")

    return msg

#  STEP 6: Send with Retry Logic
def send_with_retry(
    server:      smtplib.SMTP,
    sender:      str,
    recipient:   dict,
    msg:         MIMEMultipart,
    max_retries: int = 3,
    retry_delay: int = 5
) -> dict:
    """
    Attempts to send an email, retrying on transient failures.

    Args:
        server:      An authenticated smtplib.SMTP connection.
        sender:      Sender email address.
        recipient:   Dict with 'name' and 'email'.
        msg:         The built MIMEMultipart email object.
        max_retries: How many times to attempt sending (default 3).
        retry_delay: Seconds to wait between retries (default 5).

    Returns:
        A status dict: { name, email, status, attempts, timestamp, error }
    """
    result = {
        "name":      recipient.get("name"),
        "email":     recipient.get("email"),
        "status":    "FAILED",
        "attempts":  0,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "error":     None
    }

    for attempt in range(1, max_retries + 1):
        result["attempts"] = attempt
        try:
            server.sendmail(sender, recipient["email"], msg.as_string())
            result["status"] = "SUCCESS"
            logger.info(
                f"  ✅ Sent → {recipient['email']}  "
                f"(attempt {attempt}/{max_retries})"
            )
            return result

        except smtplib.SMTPRecipientsRefused as e:
            # Hard failure — no point retrying
            result["error"] = f"Recipient refused: {e}"
            logger.error(f"  ❌ Refused: {recipient['email']} — {e}")
            return result

        except smtplib.SMTPServerDisconnected as e:
            result["error"] = str(e)
            logger.warning(f"  ⚠️  Server disconnected (attempt {attempt}): {e}")

        except smtplib.SMTPException as e:
            result["error"] = str(e)
            logger.warning(
                f"  ⚠️  SMTP error on attempt {attempt}/{max_retries} "
                f"for {recipient['email']}: {e}"
            )

        if attempt < max_retries:
            logger.info(f"  🔁 Retrying in {retry_delay}s...")
            time.sleep(retry_delay)

    logger.error(
        f"  ❌ All {max_retries} attempts failed for {recipient['email']}"
    )
    return result

#  STEP 7: Save JSON Send Report
def save_report(results: list[dict], report_path: str) -> None:
    """
    Saves the complete send report to a JSON file.

    Structure:
        {
          "generated_at": "...",
          "total": N,
          "success": N,
          "failed": N,
          "results": [ { name, email, status, attempts, timestamp, error }, ... ]
        }
    """
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total":         len(results),
        "success":       success_count,
        "failed":        len(results) - success_count,
        "results":       results
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info(f"📄 Report saved → '{report_path}'")

#  MAIN — Orchestrates Everything
def main():
    logger.info("━" * 60)
    logger.info("   📧  Email Sender Bot  |  Syntecxhub Project-3")
    logger.info("━" * 60)

    #  ★ CONFIGURE YOUR EMAIL CAMPAIGN HERE
    CSV_FILE    = "recipients.csv"        # Path to your recipients list
    ATTACHMENTS = []                      # e.g. ["report.pdf", "data.xlsx"]
    MAX_RETRIES = 3                       # Retry attempts per recipient
    SEND_DELAY  = 1.5                     # Seconds between emails (avoid spam filters)

    SUBJECT = "Hello {name} 👋 — Important Message for You"

    BODY_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    body       {{ font-family: 'Segoe UI', sans-serif; background:#f4f6f9;
                  margin:0; padding:30px; color:#333; }}
    .card      {{ background:#ffffff; border-radius:12px; max-width:560px;
                  margin:auto; padding:36px 40px;
                  box-shadow:0 4px 20px rgba(0,0,0,0.08); }}
    .header    {{ font-size:22px; font-weight:700; color:#1a1a2e; margin-bottom:8px; }}
    .divider   {{ border:none; border-top:2px solid #e8ecf0; margin:20px 0; }}
    .body-text {{ font-size:15px; line-height:1.7; color:#444; }}
    .highlight {{ background:#eef4ff; border-left:4px solid #3b82f6;
                  padding:12px 16px; border-radius:6px; margin:20px 0;
                  font-size:14px; color:#1e40af; }}
    .footer    {{ font-size:12px; color:#9ca3af; margin-top:28px;
                  border-top:1px solid #f0f0f0; padding-top:16px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">Hello, {name}! 👋</div>
    <hr class="divider">
    <p class="body-text">
      We hope this message finds you well. This is a personalised notification
      sent to you via our automated Email Sender Bot.
    </p>
    <div class="highlight">
      📌 Your registered email: <strong>{email}</strong>
    </div>
    <p class="body-text">
      If you have any questions or need assistance, please do not hesitate
      to reach out to our team. We are happy to help.
    </p>
    <p class="body-text">
      Warm regards,<br>
      <strong>The Syntecxhub Team</strong>
    </p>
    <div class="footer">
      This is an automated email sent by Email Sender Bot.<br>
      Please do not reply directly to this message.
    </div>
  </div>
</body>
</html>
"""

    # ── Validate credentials 
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logger.error(
            "SENDER_EMAIL or SENDER_PASSWORD not set in .env file.\n"
            "  → Copy '.env.example' to '.env' and fill in your credentials."
        )
        return

    # ── Load recipients 
    recipients = read_recipients(CSV_FILE)
    if not recipients:
        logger.error("No valid recipients found. Exiting.")
        return

    logger.info(f"Recipients  : {len(recipients)}")
    logger.info(f"Sender      : {SENDER_EMAIL}")
    logger.info(f"Attachments : {len(ATTACHMENTS)} file(s)")
    logger.info(f"Max retries : {MAX_RETRIES}")
    logger.info("━" * 60)

    # ── Connect & authenticate 
    results = []
    try:
        logger.info(f"Connecting to {SMTP_HOST}:{SMTP_PORT} ...")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()          # Upgrade to TLS encryption
            server.ehlo()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            logger.info("✅ Authenticated successfully")
            logger.info("━" * 60)

            # ── Send loop 
            for idx, recipient in enumerate(recipients, start=1):
                logger.info(
                    f"[{idx}/{len(recipients)}]  "
                    f"Sending to: {recipient['name']} <{recipient['email']}>"
                )
                email_msg = build_email(
                    sender=SENDER_EMAIL,
                    recipient=recipient,
                    subject=SUBJECT,
                    body_html=BODY_HTML,
                    attachments=ATTACHMENTS
                )
                result = send_with_retry(
                    server=server,
                    sender=SENDER_EMAIL,
                    recipient=recipient,
                    msg=email_msg,
                    max_retries=MAX_RETRIES
                )
                results.append(result)
                time.sleep(SEND_DELAY)   # Polite delay between sends

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "❌ Authentication failed!\n"
            "  Common fixes:\n"
            "    1. Enable 2-Step Verification on your Google account\n"
            "    2. Generate a Gmail App Password (not your real password)\n"
            "    3. Paste it into SENDER_PASSWORD in your .env file"
        )
        return
    except TimeoutError:
        logger.error("❌ Connection timed out. Check your internet or SMTP settings.")
        return
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return

    # ── Summary 
    success = sum(1 for r in results if r["status"] == "SUCCESS")
    failed  = len(results) - success

    logger.info("━" * 60)
    logger.info(f"  ✅ Success  : {success}")
    logger.info(f"  ❌ Failed   : {failed}")
    logger.info(f"  📦 Total    : {len(results)}")
    logger.info("━" * 60)

    # ── Save report 
    report_path = f"logs/send_report_{timestamp}.json"
    save_report(results, report_path)
    logger.info(f"📋 Log saved → '{log_filename}'")
    logger.info("   Email Sender Bot — Done! 🎉")
    logger.info("━" * 60)


# Entry point 
if __name__ == "__main__":
    main()
