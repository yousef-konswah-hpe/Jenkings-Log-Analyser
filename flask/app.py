"""
Jenkins Log Analyzer — Flask API
=================================
Provides REST endpoints consumed by the Next.js frontend for:
  • Jenkins job CRUD
  • Log analysis (job-based & raw upload)
  • Scheduled / immediate email reports
  • Support chatbot
"""

# Imports

# stdlib
import os
import random
import smtplib
import sys
import threading
import time
from datetime import datetime
from email.mime.text import MIMEText
from urllib.parse import quote_plus

# third-party
import jenkins
import pymongo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from bson.objectid import ObjectId
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request
from flask_cors import CORS
from pymongo import MongoClient

# local
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.llm_client import LLMClient, LLMClientConfig, LLMClientError, env_bool
from send_email import EmailReport


# Environment

if os.path.exists(".env.local"):
    load_dotenv(".env.local")
    print("[CONFIG] Using .env.local for localhost MongoDB configuration")
else:
    load_dotenv()
    print("[CONFIG] Using .env for configuration")


# MongoDB

MONGO_USER = os.getenv("MONGO_USER", "sample")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "sample123")
MONGO_HOST = os.getenv("MONGO_HOST", "172.20.141.3")
MONGO_PORT = os.getenv("MONGO_PORT", "27018")
MONGO_DB = os.getenv("MONGO_DB", "jenkins")
MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB", "admin")


def _connect_mongo() -> tuple:
    """
    Try the configured remote MongoDB first, then fall back to localhost.

    Returns:
        (client, db, jobs_collection)
    """
    connection_string = (
        f"mongodb://{quote_plus(MONGO_USER)}:{quote_plus(MONGO_PASSWORD)}"
        f"@{MONGO_HOST}:{MONGO_PORT}/{MONGO_AUTH_DB}"
    )
    print(f"Connecting to MongoDB at: {MONGO_HOST}:{MONGO_PORT}")
    print(f"Using database: {MONGO_DB}")
    print(f"Authentication database: {MONGO_AUTH_DB}")

    timeout_opts = dict(
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=5000,
    )

    # Attempt remote connection
    try:
        cli = MongoClient(connection_string, **timeout_opts)
        cli.server_info()
        print("Connected to MongoDB successfully.")
        _db = cli[MONGO_DB]
        _db["jobs"].find_one()
        print("Database access verified.")
        return cli, _db, _db["jobs"]

    except Exception as exc:
        print(f"Error connecting to MongoDB: {exc}")

    # Fallback to local
    try:
        print("Attempting fallback to local MongoDB...")
        cli = MongoClient("mongodb://localhost:27017/")
        cli.server_info()
        print("Connected to local MongoDB as fallback.")
        _db = cli["jenkins"]
        return cli, _db, _db["jobs"]

    except Exception as exc:
        print(f"Error connecting to local MongoDB: {exc}")
        raise RuntimeError("Failed to connect to both remote and local MongoDB")


client, db, jobs_collection = _connect_mongo()


# LLM

LLM_API_URL = os.getenv("LLM_API_URL", "")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "meta/llama-3.1-70b-instruct")
LLM_AUTH_TOKEN = os.getenv("LLM_AUTH_TOKEN", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
LLM_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_VERIFY_TLS = env_bool("LLM_VERIFY_TLS", True)

llm_client = LLMClient(
    LLMClientConfig(
        api_url=LLM_API_URL,
        auth_token=LLM_AUTH_TOKEN,
        default_model=LLM_MODEL_NAME,
        provider=LLM_PROVIDER,
        timeout_seconds=LLM_TIMEOUT,
        verify_tls=LLM_VERIFY_TLS,
        max_retries=LLM_RETRIES,
    )
)

if llm_client.is_configured():
    print(f"[CONFIG] LLM configured (provider={LLM_PROVIDER}, model={LLM_MODEL_NAME}, TLS={LLM_VERIFY_TLS})")
else:
    print("[CONFIG] LLM is not fully configured. For Ollama set LLM_PROVIDER=ollama, LLM_API_URL, LLM_MODEL_NAME.")


# Prompts and constants

SUMMARY_PROMPT = (
    "Analyze the following Jenkins build log, with a focus on the pytest execution output. "
    "Identify and summarize:\n\n"
    "**Failed test cases** along with their names and file locations.\n\n"
    "**Selectors or locators** that caused the failures (e.g., CSS/XPath), and specify "
    "where in the code (file/function) they are defined or referenced, if visible.\n\n"
    "**Any tracebacks or error messages** related to element not found, timeout, or assertion errors.\n\n"
    "**Group the findings** to help testers quickly backtrack in the browser and debug.\n\n"
    "Format your response in a structured way that makes it easy for testers to understand "
    "what failed and where to look for fixes.\n\n"
    "Jenkins build log to analyze:\n\n"
)

SUPPORT_CHAT_SYSTEM_PROMPT = (
    "You are a concise support assistant for Jenkins Log Analyzer. "
    "Help users with Jenkins job analysis, scheduling email reports, troubleshooting errors, and usage steps. "
    "IMPORTANT FORMATTING RULES:\n"
    "- Always respond in short, numbered steps or bullet points.\n"
    "- Never write long paragraphs. Keep each point to 1-2 sentences max.\n"
    "- Use numbered lists (1. 2. 3.) for sequential steps.\n"
    "- Use bullet points (• ) for non-sequential tips or options.\n"
    "- Start with a brief one-line summary if helpful, then list the steps.\n"
    "- If user asks for secrets or harmful actions, refuse and suggest safe alternatives."
)

# Chunking parameters
TOKENS_PER_CHUNK = 60_000          # stays within 131k context window
CHARS_PER_TOKEN = 4                # conservative estimate
CHUNK_SIZE = TOKENS_PER_CHUNK * CHARS_PER_TOKEN   # 240 000 chars
CHUNK_OVERLAP = 1_000              # overlap between chunks (chars)

FREQUENCY_MAP = {
    "daily": "0 9 * * *",
    "weekly": "0 9 * * 1",
    "monthly": "0 9 1 * *",
    "hourly": "0 * * * *",
}


# Flask app and scheduler

app = Flask(__name__)
CORS(app)

scheduler = BackgroundScheduler()
scheduler.start()


# AI / analysis helpers

def frequency_to_cron(frequency: str) -> str | None:
    """Convert a human frequency label to a cron expression."""
    return FREQUENCY_MAP.get(frequency.lower())


def split_by_chars(text: str, chunk_size: int) -> list[str]:
    """Split *text* into fixed-size character chunks."""
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def summarize_chunk(chunk: str) -> str:
    """Send a single chunk to the LLM for analysis."""
    max_chars = TOKENS_PER_CHUNK * CHARS_PER_TOKEN
    if len(chunk) > max_chars:
        print(f"[AI] Chunk too large ({len(chunk)} chars), truncating to {max_chars}")
        chunk = chunk[-max_chars:]

    if not llm_client.is_configured():
        return "[ERROR] LLM not configured. For Ollama set LLM_PROVIDER=ollama, LLM_API_URL, LLM_MODEL_NAME."

    try:
        print("[AI] Calling LLM for chunk summary …")
        content, usage = llm_client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a Jenkins build log analysis expert. Provide detailed, structured analysis of build logs."},
                {"role": "user", "content": SUMMARY_PROMPT + chunk},
            ],
            max_tokens=1024,
            temperature=0,
            frequency_penalty=0,
            presence_penalty=0.5,
        )
        print(f"[AI] ✅ Chunk processed ({usage.get('total_tokens', '?')} tokens)")
        return content
    except LLMClientError as exc:
        return f"[ERROR] {exc}"
    except Exception as exc:
        return f"[ERROR] Failed to summarize chunk: {exc}"


def iterative_summarize(text: str, chunk_size: int = CHUNK_SIZE) -> str:
    """
    Recursively split → summarise → merge until the text fits one chunk,
    then return the final summary.
    """
    print(f"[AI] Starting iterative summarisation of {len(text)} chars")

    for iteration in range(1, 11):
        if len(text) <= chunk_size:
            break

        print(f"[AI] Iteration {iteration}: {len(text)} chars")
        chunks = split_by_chars(text, chunk_size)
        summaries = []

        for idx, chunk in enumerate(chunks, 1):
            print(f"[AI] Chunk {idx}/{len(chunks)} ({len(chunk)} chars) …")
            result = summarize_chunk(chunk)
            if result and not result.startswith("[ERROR]"):
                summaries.append(result)
            else:
                print(f"[AI] ⚠ Chunk {idx} failed — skipping")

        if not summaries:
            return "[ERROR] All chunks failed to summarize"

        text = "\n\n".join(summaries)
        print(f"[AI] Iteration {iteration} done → {len(text)} chars")

    print("[AI] Generating final summary …")
    return summarize_chunk(text)


def analyze_jenkins_log(log_content: str) -> str:
    """Top-level entry point: analyse a raw log string."""
    try:
        print(f"[AI] Starting analysis ({len(log_content)} chars)")
        result = iterative_summarize(log_content)
        return result if result and result.strip() else "[AI ANALYSIS ERROR]: Empty response from AI model"
    except (LLMClientError, Exception) as exc:
        return f"[AI ANALYSIS ERROR]: {exc}"


def safe_ai_request_with_retry(log_content: str, max_retries: int = 3) -> str:
    """Wrap *analyze_jenkins_log* with top-level retry & back-off."""
    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                delay = 2 ** attempt + random.uniform(1, 3)
                print(f"[AI] Waiting {delay:.1f}s before retry …")
                time.sleep(delay)

            print(f"[AI] Attempt {attempt}/{max_retries} ({len(log_content)} chars)")
            result = analyze_jenkins_log(log_content)

            if result and not result.startswith(("[AI ANALYSIS ERROR]", "[ERROR]")):
                print(f"[AI] completed on attempt {attempt}")
                return result

            print(f"[AI] ⚠ Attempt {attempt} returned: {result[:100]}…")

        except Exception as exc:
            print(f"[AI] Attempt {attempt} error: {exc}")

    return f"[AI ANALYSIS ERROR]: Failed after {max_retries} attempts"


# Email helper

def send_email_report(analysis_data: dict, email_address, job_id) -> bool:
    """Save analysis to disk and email it."""
    try:
        job_name = analysis_data.get("job_name", "Unknown Job")
        analysis_text = analysis_data.get("analysis", "No analysis result")

        summary_path = f"./logs/{job_name}_latest.txt"
        os.makedirs(os.path.dirname(summary_path), exist_ok=True)

        with open(summary_path, "w") as fh:
            fh.write(analysis_text)

        recipients = [email_address] if isinstance(email_address, str) else email_address
        EmailReport().send_email(
            filename=summary_path,
            subject=f"AI Log Analysis Report for Jenkins job: {job_name}",
            to_email=recipients,
        )
        print(f"[EMAIL] Report sent to {email_address} for job '{job_name}'")
        return True

    except Exception as exc:
        print(f"[EMAIL] Error sending report: {exc}")
        return False


# Jenkins log processing

def process_jenkins_log(job_id, jenkins_url=None, username=None, password=None):
    """
    Fetch the latest console log for a stored Jenkins job and analyse it.

    Returns:
        (result_dict | None, error_message | None)
    """
    try:
        job = jobs_collection.find_one({"_id": ObjectId(job_id)})
        if not job:
            return None, f"Job with ID {job_id} not found"

        jenkins_url = jenkins_url or job.get("url")
        username = username or job.get("username")
        password = password or job.get("password")
        job_name = job.get("name")

        if not all([jenkins_url, username, password]):
            return None, "Missing Jenkins credentials or URL"

        print(f"Analysing job: {job_name}")

        server = jenkins.Jenkins(jenkins_url, username=username, password=password)
        job_info = server.get_job_info(job_name)

        if not job_info:
            return None, f'Jenkins job "{job_name}" not found'

        last_build = job_info.get("lastCompletedBuild")
        if not last_build:
            return None, f'No completed builds for job "{job_name}"'

        build_number = last_build["number"]
        print(f"Analysing build #{build_number}")

        log_text = server.get_build_console_output(job_name, build_number)
        if not log_text or len(log_text.strip()) < 100:
            return None, f"No meaningful log content for build #{build_number}"

        print(f"Log fetched ({len(log_text)} chars)")

        analysis = safe_ai_request_with_retry(log_text)
        if analysis.startswith("[AI ANALYSIS ERROR]"):
            return None, f"AI analysis failed: {analysis}"

        return {
            "analysis": analysis,
            "job_name": job_name,
            "build_number": build_number,
            "job_details": job,
        }, None

    except jenkins.NotFoundException:
        return None, "Jenkins job or build not found"
    except Exception as exc:
        print(f"Error analysing job: {exc}")
        return None, str(exc)


# Routes

# root redirect

@app.route("/")
def index():
    return redirect("http://localhost:3000")


# health

@app.route("/api/health")
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "mode": "chunks",
        "description": "Direct API mode with chunking support for large logs",
    })


# jobs CRUD

@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    if not client:
        return jsonify({"success": False, "error": "Database connection not available. Make sure MongoDB is running"}), 500

    try:
        jobs = list(jobs_collection.find({}, {"name": 1}))
        print(f"Found {len(jobs)} jobs")

        formatted = [
            {
                "id": str(j["_id"]),
                "display_name": j["name"],
                "description": j.get("description", ""),
            }
            for j in jobs
        ]
        return jsonify({"success": True, "jobs": formatted})

    except Exception as exc:
        print(f"Error getting jobs: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/jobs", methods=["POST"])
def add_job():
    if not client:
        return jsonify({"success": False, "error": "Database connection not available. Make sure MongoDB is running"}), 500

    try:
        data = request.get_json()

        for field in ("name", "url", "username", "password"):
            if not data.get(field):
                return jsonify({"success": False, "error": f"Field {field} is required"}), 400

        if jobs_collection.find_one({"name": data["name"]}):
            return jsonify({"success": False, "error": "Job with this name already exists"}), 400

        job_data = {
            "name": data["name"],
            "url": data["url"],
            "username": data["username"],
            "password": data["password"],
            "email": data.get("email", ""),
            "description": data.get("description", ""),
        }
        result = jobs_collection.insert_one(job_data)
        return jsonify({"success": True, "job_name": data["name"], "job_id": str(result.inserted_id)})

    except Exception as exc:
        print(f"Error adding job: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500


# analysis

@app.route("/api/analyze", methods=["POST"])
def analyze_log():
    try:
        data = request.get_json()
        if "job_id" not in data:
            return jsonify({"success": False, "error": "Missing job_id"}), 400

        print(f"Starting analysis for job_id: {data['job_id']}")
        result, error = process_jenkins_log(
            data["job_id"],
            data.get("jenkins_url"),
            data.get("username"),
            data.get("password"),
        )
        if error:
            return jsonify({"success": False, "error": error}), 400

        print("Analysis completed successfully")
        return jsonify({
            "success": True,
            "response": result["analysis"],
            "job_name": result["job_name"],
            "build_number": result["build_number"],
        })

    except Exception as exc:
        print(f"Error analysing job: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/analyze-log", methods=["POST"])
def analyze_log_text():
    """Analyse raw log text (drag-and-drop / paste)."""
    try:
        log_content = None
        filename = "uploaded_log"

        if request.content_type and "multipart/form-data" in request.content_type:
            file = request.files.get("file")
            if not file:
                return jsonify({"success": False, "error": "No file provided"}), 400
            log_content = file.read().decode("utf-8", errors="replace")
            filename = file.filename or filename
        else:
            data = request.get_json(silent=True) or {}
            log_content = data.get("log_text", "").strip()
            filename = data.get("filename", filename)

        if not log_content or len(log_content.strip()) < 50:
            return jsonify({"success": False, "error": "Log content is too short or empty. Please provide a meaningful Jenkins log."}), 400

        print(f"[UPLOAD] Analysing: {filename} ({len(log_content)} chars)")
        analysis = safe_ai_request_with_retry(log_content)

        if analysis.startswith("[AI ANALYSIS ERROR]"):
            return jsonify({"success": False, "error": f"AI analysis failed: {analysis}"}), 500

        return jsonify({
            "success": True,
            "response": analysis,
            "job_name": filename,
            "build_number": "uploaded",
        })

    except Exception as exc:
        print(f"Error analysing uploaded log: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500


# email reports

@app.route("/api/email-log-report", methods=["POST"])
def email_log_report():
    """Analyse uploaded log text and email the report."""
    try:
        data = request.get_json(silent=True) or {}
        log_content = (data.get("log_text") or "").strip()
        email = (data.get("email") or "").strip()
        filename = data.get("filename", "uploaded_log")

        if not email:
            return jsonify({"success": False, "error": "Email address is required"}), 400
        if not log_content or len(log_content) < 50:
            return jsonify({"success": False, "error": "Log content is too short or empty."}), 400

        print(f"[EMAIL-LOG] Analysing: {filename} ({len(log_content)} chars) → {email}")
        analysis = safe_ai_request_with_retry(log_content)

        if analysis.startswith("[AI ANALYSIS ERROR]"):
            return jsonify({"success": False, "error": f"AI analysis failed: {analysis}"}), 500

        success = send_email_report({"analysis": analysis, "job_name": filename}, email, "uploaded")

        return jsonify({
            "success": True,
            "message": f"Analysis report emailed to {email}" if success else "Analysis complete but email delivery may be delayed.",
            "response": analysis,
            "job_name": filename,
            "build_number": "uploaded",
        })

    except Exception as exc:
        print(f"Error in email-log-report: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500


# support chatbot

@app.route("/api/chat/support", methods=["POST"])
def support_chat():
    try:
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        context = data.get("context") or {}

        if not message:
            return jsonify({"success": False, "error": "Missing message"}), 400

        if not llm_client.is_configured():
            return jsonify({
                "success": False,
                "error": "LLM not configured. For Ollama set LLM_PROVIDER=ollama, LLM_API_URL, and LLM_MODEL_NAME.",
            }), 500

        context_text = ""
        if isinstance(context, dict) and context:
            context_text = "\n\nContext:\n" + "\n".join(f"{k}: {v}" for k, v in context.items())

        content, usage = llm_client.chat_completion(
            messages=[
                {"role": "system", "content": SUPPORT_CHAT_SYSTEM_PROMPT},
                {"role": "user", "content": f"User request:\n{message}{context_text}"},
            ],
            max_tokens=512,
            temperature=0.2,
            frequency_penalty=0,
            presence_penalty=0.1,
        )
        return jsonify({"success": True, "response": content, "usage": usage}), 200

    except LLMClientError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# scheduling

@app.route("/schedule-email/<job_id>", methods=["POST"])
def schedule_or_send_email(job_id):
    try:
        data = request.get_json()
        frequency = data.get("frequency")
        email = data.get("email")

        if not email:
            return jsonify({"error": "Email is required"}), 400

        if not client:
            return jsonify({"error": "Database connection not available. Make sure MongoDB is running"}), 500

        # Try to find existing job
        job = None
        try:
            job = jobs_collection.find_one({"_id": ObjectId(job_id)})
        except Exception:
            pass

        jenkins_url = data.get("jenkins_url")
        username = data.get("username")
        password = data.get("password")
        job_name = data.get("job_name", "")

        # Auto-register if all credentials supplied but no stored job
        if not job and all([jenkins_url, username, password, job_name]):
            job_data = {
                "name": job_name,
                "url": jenkins_url,
                "username": username,
                "password": password,
                "email": email,
            }
            result = jobs_collection.insert_one(job_data)
            job_id = str(result.inserted_id)
            job = {**job_data, "_id": result.inserted_id}
            print(f"[SCHEDULE] Auto-registered job: {job_name} (ID: {job_id})")
        elif not job:
            return jsonify({"error": "Job not found. Please provide Jenkins URL, username, password, and job name to register it."}), 404

        job_name = job.get("name")
        jenkins_url = jenkins_url or job.get("url")
        username = username or job.get("username")
        password = password or job.get("password")

        def generate_and_send_summary():
            """Fetch latest log, analyse, and email."""
            try:
                print(f"Generating summary for job: {job_name}")
                result, error = process_jenkins_log(job_id, jenkins_url, username, password)

                if error:
                    print(f"Error processing log for {job_name}: {error}")
                    send_email_report({"analysis": f"[ERROR] {error}", "job_name": job_name}, email, job_id)
                    return

                ok = send_email_report(result, email, job_id)
                print(f"{'Sent' if ok else 'Failed to send'} summary to {email} for {job_name}")

            except Exception as exc:
                print(f"Error in generate_and_send_summary for {job_name}: {exc}")
                try:
                    send_email_report(
                        {"analysis": f"[CRITICAL ERROR] {exc}", "job_name": job_name},
                        email, job_id,
                    )
                except Exception:
                    print(f"Failed to send error-notification email for {job_name}")

        if frequency:
            cron_expr = frequency_to_cron(frequency)
            if not cron_expr:
                return jsonify({"error": "Invalid frequency. Use: daily, weekly, monthly, hourly"}), 400

            if frequency.lower() == "daily":
                cron_expr = f"{random.randint(0, 59)} 9 * * *"

            try:
                scheduler.add_job(
                    func=generate_and_send_summary,
                    trigger=CronTrigger.from_crontab(cron_expr),
                    id=f"email_{job_id}_{email}",
                    replace_existing=True,
                    max_instances=1,
                )
                print(f"Scheduled {frequency} email for {job_name} → {email} (cron: {cron_expr})")
                return jsonify({"message": "Email scheduled successfully"}), 200

            except Exception as exc:
                return jsonify({"error": f"Failed to schedule email: {exc}"}), 500
        else:
            threading.Thread(target=generate_and_send_summary, daemon=True).start()
            return jsonify({"message": f"Email sent to {email} for job {job_name}"}), 200

    except Exception as exc:
        print(f"Error in schedule_or_send_email: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/schedule-email/<job_id>", methods=["DELETE"])
def cancel_scheduled_email(job_id):
    """Cancel a previously scheduled email job."""
    try:
        data = request.get_json()
        email = data.get("email")

        if not email:
            return jsonify({"error": "Email is required to cancel scheduled job"}), 400

        sched_id = f"email_{job_id}_{email}"
        if scheduler.get_job(sched_id):
            scheduler.remove_job(sched_id)
            return jsonify({"success": True, "message": f"Scheduled email cancelled for job {job_id} to {email}"}), 200

        return jsonify({"error": "No scheduled email found for this job and email"}), 404

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/scheduled-emails", methods=["GET"])
def list_scheduled_emails():
    """List every active scheduled-email job."""
    try:
        scheduled = []
        for sched_job in scheduler.get_jobs():
            if not sched_job.id.startswith("email_"):
                continue

            parts = sched_job.id.split("_", 2)
            if len(parts) < 3:
                continue

            stored_job_id, sched_email = parts[1], parts[2]
            details = jobs_collection.find_one({"_id": ObjectId(stored_job_id)})

            scheduled.append({
                "job_id": stored_job_id,
                "job_name": details.get("name", "Unknown") if details else "Unknown",
                "email": sched_email,
                "next_run": sched_job.next_run_time.isoformat() if sched_job.next_run_time else None,
                "trigger": str(sched_job.trigger),
            })

        return jsonify({"success": True, "scheduled_emails": scheduled, "total": len(scheduled)}), 200

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# SMTP test

@app.route("/api/email-test", methods=["POST"])
def email_test():
    """Quick SMTP connectivity test — sends a tiny probe email."""
    try:
        data = request.get_json(silent=True) or {}
        to_email = (data.get("email") or "").strip()
        if not to_email:
            return jsonify({"success": False, "error": 'Provide "email" in JSON body'}), 400

        smtp_server = os.getenv("SMTP_SERVER", "mxdns01.hpelabs.net")
        smtp_port = int(os.getenv("SMTP_PORT", "0"))
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes")
        use_tls = os.getenv("SMTP_USE_TLS", "false").lower() in ("1", "true", "yes")

        msg = MIMEText("This is a test email from Jenkins Log Analyzer.\nIf you received this, SMTP is working!", "plain")
        msg["Subject"] = "Jenkins Log Analyzer — SMTP Test"
        msg["From"] = "projects@hpelabs.net"
        msg["To"] = to_email

        ports_to_try = [smtp_port] if smtp_port else [25, 587, 465]
        errors = []

        for port in ports_to_try:
            try:
                if use_ssl or port == 465:
                    smtp = smtplib.SMTP_SSL(smtp_server, port, timeout=15)
                else:
                    smtp = smtplib.SMTP(smtp_server, port, timeout=15)

                smtp.ehlo()
                if use_tls and port != 465:
                    smtp.starttls()
                    smtp.ehlo()
                if smtp_username and smtp_password:
                    smtp.login(smtp_username, smtp_password)

                smtp.sendmail(msg["From"], [to_email], msg.as_string())
                smtp.quit()
                return jsonify({"success": True, "message": f"Test email sent to {to_email} via {smtp_server}:{port}"}), 200

            except Exception as exc:
                errors.append(f"{smtp_server}:{port} — {exc}")

        return jsonify({
            "success": False,
            "error": "All SMTP attempts failed",
            "details": errors,
            "config": {
                "SMTP_SERVER": smtp_server,
                "SMTP_PORT": smtp_port or "auto",
                "SMTP_USE_TLS": use_tls,
                "SMTP_USE_SSL": use_ssl,
                "SMTP_USERNAME": smtp_username or "(none)",
            },
        }), 502

    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    

if __name__ == "__main__":
    import atexit

    atexit.register(lambda: (print("Shutting down scheduler…"), scheduler.shutdown()))

    print("Starting Jenkins Log Analyzer with Chunking Support…")
    print("Chunking mode enabled for large logs")

    app.run(debug=True, port=5005, host="0.0.0.0")
