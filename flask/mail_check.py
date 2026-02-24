import smtplib
from email.mime.text import MIMEText
import uuid
import traceback

FROM = "projects@hpelabs.net"
TO = "varshith-r@hpe.com"
SUBJECT = "Test Email - " + str(uuid.uuid4())

msg = MIMEText("This is a test email from Python script.")
msg["Subject"] = SUBJECT
msg["From"] = FROM
msg["To"] = TO
msg["Disposition-Notification-To"] = FROM

try:
    server = smtplib.SMTP("mxdns01.hpelabs.net", 25, timeout=20)
    print("Server connection successful")
    #server.ehlo()
    server.ehlo("jenkins-analyzer.hpelabs.net")
    server.sendmail(FROM, [TO], msg.as_string())
    #server.sendmail(FROM, TO, msg.as_string())
    print("Email should be sent")
    server.quit()
    print(f"✅ Email sent to {TO} with subject: {SUBJECT}")
except Exception as e:
    print("❌ Error sending email")
    traceback.print_exc()
