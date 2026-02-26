# # """
# # Email report
# # """
# # import os
# # import smtplib
# # from email.mime.multipart import MIMEMultipart
# # from email.mime.text import MIMEText
# # # from automation.logger import log
# # from bs4 import BeautifulSoup
# # # from automation.tests.utils import log_generation


# # class EmailReport:
# #     def __init__(self, **kwargs):
# #         # self.from_email = kwargs.get("from_email", "pcbe_load_bringup@hpe.com")
# #         # self.to_email = kwargs.get("to_email", "prasanna2@hpe.com")
# #         self.from_email =  "prasanna2@hpe.com"
# #         self.to_email = "prasanna2@hpe.com"


# #     def send_email(self, filename=None, html_content=None, subject=None, to_email=None):
# #         """
# #         To send the html report of test results.
# #         params: filename: name of the file which needs to be sent
# #         params: subject: subject name
# #         """
# #         msg = MIMEMultipart("alternative")
# #         # msg["Subject"] = "PCBE Load Simulation Report"
# #         msg["From"] = self.from_email

# #         if to_email:
# #             msg["To"] = ", ".join(to_email)
# #         else:
# #             msg["To"] = self.to_email
# #         if filename is None:
# #             # print(os.getenv("html_file"))
# #             # msg_html = open(os.getenv("html_file"), "r+")
# #             # msg_html = msg_html.read()
# #             # soup = BeautifulSoup(msg_html)
# #             # msg_html = soup.prettify()

# #             part2 = MIMEText(html_content, "html")
# #             msg.attach(part2)
# #         elif subject is not None:
# #             msg["Subject"] = subject
# #             msg.set_charset("utf-8")
# #             f = open(filename, "r+")
# #             attachment = MIMEText(f.read().rstrip("\n"), "plain", "utf-8")
# #             attachment.add_header("Content-Disposition", "attachment", filename=filename)
# #             msg.attach(attachment)
# #         retry = 3
# #         smtp = None
# #         sent_mail = False
# #         while retry > 0 and not sent_mail:
# #             try:
# #                 retry = retry - 1
# #                 smtp = smtplib.SMTP("smtp3.hpe.com")
# #                 smtp.sendmail(self.from_email, to_email, msg.as_string())
# #                 smtp.close()
# #                 sent_mail = True
# #             except Exception:
# #                 print("Failed to connect to SMTP Server")
# #         else:
# #             if not smtp:
# #                 print("Not able to send the report")






# """
# Email report
# """
# import os
# import smtplib
# from email.mime.multipart import MIMEMultipart
# from email.mime.text import MIMEText
# # from automation.logger import log
# from bs4 import BeautifulSoup
# # from automation.tests.utils import log_generation


# class EmailReport:
#     def __init__(self, **kwargs):
#         # self.from_email = kwargs.get("from_email", "pcbe_load_bringup@hpe.com")
#         # self.to_email = kwargs.get("to_email", "prasanna2@hpe.com")
#         self.from_email =  "prasanna2@hpe.com"
        
#         # Default email recipients - you can add multiple emails here
#         self.default_recipients = [
#             "prasanna2@hpe.com",
#             "varshith-r@hpe.com",
#             "pushpalatha.pulicherla@hpe.com",
#             "sarada.a@hpe.com"

#             # "admin@company.com",
#             # "jenkins-alerts@company.com",
#             # "team-lead@company.com"
#         ]
        
#         # For backward compatibility
#         self.to_email = self.default_recipients[0]


#     def send_email(self, filename=None, html_content=None, subject=None, to_email=None):
#         """
#         To send the html report of test results.
#         params: filename: name of the file which needs to be sent
#         params: subject: subject name
#         params: to_email: list of email addresses or single email address from UI
#         """
#         # Combine default recipients with UI-provided emails
#         all_recipients = self.default_recipients.copy()
        
#         if to_email:
#             if isinstance(to_email, str):
#                 # Single email from UI
#                 if to_email not in all_recipients:
#                     all_recipients.append(to_email)
#             elif isinstance(to_email, list):
#                 # Multiple emails from UI
#                 for email in to_email:
#                     if email not in all_recipients:
#                         all_recipients.append(email)
        
#         # Remove duplicates and empty strings
#         all_recipients = list(set([email.strip() for email in all_recipients if email.strip()]))
        
#         print(f"[EMAIL] Sending to recipients: {all_recipients}")
        
#         msg = MIMEMultipart("alternative")
#         # msg["Subject"] = "PCBE Load Simulation Report"
#         msg["From"] = self.from_email
#         msg["To"] = ", ".join(all_recipients)
#         if filename is None:
#             # print(os.getenv("html_file"))
#             # msg_html = open(os.getenv("html_file"), "r+")
#             # msg_html = msg_html.read()
#             # soup = BeautifulSoup(msg_html)
#             # msg_html = soup.prettify()

#             part2 = MIMEText(html_content, "html")
#             msg.attach(part2)
#         elif subject is not None:
#             msg["Subject"] = subject
#             msg.set_charset("utf-8")
#             f = open(filename, "r+")
#             attachment = MIMEText(f.read().rstrip("\n"), "plain", "utf-8")
#             attachment.add_header("Content-Disposition", "attachment", filename=filename)
#             msg.attach(attachment)
#         retry = 3
#         smtp = None
#         sent_mail = False
#         while retry > 0 and not sent_mail:
#             try:
#                 retry = retry - 1
#                 smtp = smtplib.SMTP("smtp3.hpe.com")
#                 smtp.sendmail(self.from_email, all_recipients, msg.as_string())
#                 smtp.close()
#                 sent_mail = True
#                 print(f"[EMAIL] ✅ Successfully sent email to {len(all_recipients)} recipients")
#             except Exception as e:
#                 print(f"[EMAIL] ❌ Failed to connect to SMTP Server: {e}")
#                 if retry == 0:
#                     print(f"[EMAIL] ❌ Failed to send email after 3 attempts")
#                 print("Failed to connect to SMTP Server")
#         else:
#             if not sent_mail:
#                 print("[EMAIL] ❌ Not able to send the report to any recipients")
            
#         return sent_mail



"""
Email report
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
# from automation.logger import log
from bs4 import BeautifulSoup
# from automation.tests.utils import log_generation


class EmailReport:
    def __init__(self, **kwargs):
        self.from_email = "projects@hpelabs.net"

        # SMTP config from environment variables (same as /api/email-test)
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp3.hpe.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "25"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes")
        self.use_tls = os.getenv("SMTP_USE_TLS", "false").lower() in ("1", "true", "yes")

        # Default email recipients
        self.default_recipients = [
            "prasanna2@hpe.com",
            "varshith-r@hpe.com",
            "pushpalatha.pulicherla@hpe.com",
            "sarada.a@hpe.com"
        ]

        # For backward compatibility
        self.to_email = self.default_recipients[0]

    def send_email(self, filename=None, html_content=None, subject=None, to_email=None):
        """
        Send the report via SMTP using env-configured server.
        """
        # Combine default recipients with UI-provided emails
        all_recipients = self.default_recipients.copy()

        if to_email:
            if isinstance(to_email, str):
                if to_email not in all_recipients:
                    all_recipients.append(to_email)
            elif isinstance(to_email, list):
                for email in to_email:
                    if email not in all_recipients:
                        all_recipients.append(email)

        # Remove duplicates and empty strings
        all_recipients = list(set([e.strip() for e in all_recipients if e.strip()]))

        print(f"[EMAIL] Sending to recipients: {all_recipients}")

        msg = MIMEMultipart("alternative")
        msg["From"] = self.from_email
        msg["To"] = ", ".join(all_recipients)

        if filename is None and html_content:
            part2 = MIMEText(html_content, "html")
            msg.attach(part2)
        elif subject is not None and filename is not None:
            msg["Subject"] = subject
            msg.set_charset("utf-8")
            with open(filename, "r") as f:
                attachment = MIMEText(f.read().rstrip("\n"), "plain", "utf-8")
            attachment.add_header("Content-Disposition", "attachment", filename=os.path.basename(filename))
            msg.attach(attachment)

        if subject and "Subject" not in msg:
            msg["Subject"] = subject

        sent_mail = False
        smtp = None
        retry = 3

        while retry > 0 and not sent_mail:
            try:
                retry -= 1
                print(f"[EMAIL] Connecting to {self.smtp_server}:{self.smtp_port}")

                if self.use_ssl or self.smtp_port == 465:
                    smtp = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=15)
                else:
                    smtp = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15)

                smtp.ehlo()

                if self.use_tls and self.smtp_port != 465:
                    smtp.starttls()
                    smtp.ehlo()

                if self.smtp_username and self.smtp_password:
                    smtp.login(self.smtp_username, self.smtp_password)

                smtp.sendmail(self.from_email, all_recipients, msg.as_string())
                smtp.quit()
                sent_mail = True
                print(f"[EMAIL] ✅ Sent to {len(all_recipients)} recipients via {self.smtp_server}:{self.smtp_port}")

            except Exception as e:
                print(f"[EMAIL] ❌ Attempt failed: {e}")
                if smtp:
                    try:
                        smtp.quit()
                    except:
                        pass
                    smtp = None

        if not sent_mail:
            print(f"[EMAIL] ❌ Failed to send email after all retries")

        return sent_mail
            
        
    