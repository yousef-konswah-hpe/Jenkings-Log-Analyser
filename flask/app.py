"""
Jenkins Log Analyzer — Flask API
Routes for: job CRUD, log analysis, email reports, support chatbot, scheduling.
"""

import os
import random
import smtplib
import threading
import time
from datetime import datetime
from email.mime.text import MIMEText

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from bson.objectid import ObjectId
from flask import Flask, jsonify, redirect, request
from flask_cors import CORS

from config import (
    client, jobs_collection, analyses_collection,
    llm_client, FREQUENCY_MAP,
)  # must be first (sets sys.path)
from analysis import safe_analyze_with_retry, compute_confidence
from prompts import SUPPORT_CHAT_PROMPT
from services import process_jenkins_log, send_email_report, save_analysis

# App & scheduler

app = Flask(__name__)
CORS(app)

scheduler = BackgroundScheduler()
scheduler.start()

# Shared state for the support chatbot
_latest_analysis: dict = {
    "result": None,
    "job_name": None,
    "build_number": None,
    "timestamp": None,
}


def _update_latest(analysis: str, job_name: str, build_number):
    """Update the latest analysis context for the chatbot."""
    _latest_analysis.update({
        "result": analysis,
        "job_name": job_name,
        "build_number": build_number,
        "timestamp": datetime.now().isoformat(),
    })


def _user_id() -> str:
    """Extract per-user identity from request header."""
    return request.headers.get("X-User-Id", "")


# Routes

@app.route("/")
def index():
    return redirect("http://localhost:3000")


@app.route("/api/health")
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()})


# Jobs CRUD

@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    if not client:
        return jsonify({"success": False, "error": "Database not available"}), 500
    try:
        jobs = list(jobs_collection.find({}, {"name": 1}))
        formatted = [
            {"id": str(j["_id"]), "display_name": j["name"], "description": j.get("description", "")}
            for j in jobs
        ]
        return jsonify({"success": True, "jobs": formatted})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/jobs", methods=["POST"])
def add_job():
    if not client:
        return jsonify({"success": False, "error": "Database not available"}), 500
    try:
        data = request.get_json()
        for field in ("name", "url", "username", "password"):
            if not data.get(field):
                return jsonify({"success": False, "error": f"Field {field} is required"}), 400

        if jobs_collection.find_one({"name": data["name"]}):
            return jsonify({"success": False, "error": "Job with this name already exists"}), 400

        result = jobs_collection.insert_one({
            "name": data["name"], "url": data["url"],
            "username": data["username"], "password": data["password"],
            "email": data.get("email", ""), "description": data.get("description", ""),
        })
        return jsonify({"success": True, "job_name": data["name"], "job_id": str(result.inserted_id)})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# Analysis

@app.route("/api/analyze", methods=["POST"])
def analyze_log():
    try:
        data = request.get_json()
        if "job_id" not in data:
            return jsonify({"success": False, "error": "Missing job_id"}), 400

        result, error = process_jenkins_log(
            data["job_id"], data.get("jenkins_url"), data.get("username"), data.get("password"),
        )
        if error:
            return jsonify({"success": False, "error": error}), 400

        _update_latest(result["analysis"], result["job_name"], result["build_number"])
        save_analysis(result["job_name"], result["build_number"], result["analysis"], result.get("log_text", ""), _user_id())

        confidence = compute_confidence(result["analysis"], result.get("log_text", ""))
        return jsonify({
            "success": True, "response": result["analysis"],
            "job_name": result["job_name"], "build_number": result["build_number"],
            "confidence": confidence,
        })
    except Exception as exc:
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
            return jsonify({"success": False, "error": "Log content is too short or empty."}), 400

        analysis = safe_analyze_with_retry(log_content)
        if analysis.startswith("[AI ANALYSIS ERROR]"):
            return jsonify({"success": False, "error": f"AI analysis failed: {analysis}"}), 500

        _update_latest(analysis, filename, "uploaded")
        save_analysis(filename, "uploaded", analysis, log_content, _user_id())

        confidence = compute_confidence(analysis, log_content)
        return jsonify({
            "success": True, "response": analysis,
            "job_name": filename, "build_number": "uploaded",
            "confidence": confidence,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# Email reports

@app.route("/api/email-log-report", methods=["POST"])
def email_log_report():
    """Analyse uploaded log and email the report."""
    try:
        data = request.get_json(silent=True) or {}
        log_content = (data.get("log_text") or "").strip()
        email = (data.get("email") or "").strip()
        filename = data.get("filename", "uploaded_log")

        if not email:
            return jsonify({"success": False, "error": "Email address is required"}), 400
        if not log_content or len(log_content) < 50:
            return jsonify({"success": False, "error": "Log content is too short or empty."}), 400

        analysis = safe_analyze_with_retry(log_content)
        if analysis.startswith(("[AI ANALYSIS ERROR]", "[ERROR]")):
            return jsonify({"success": False, "error": f"AI analysis failed: {analysis}"}), 500

        _update_latest(analysis, filename, "uploaded")
        save_analysis(filename, "uploaded", analysis, log_content, _user_id())
        success = send_email_report({"analysis": analysis, "job_name": filename}, email, "uploaded")

        return jsonify({
            "success": True,
            "message": f"Analysis report emailed to {email}" if success else "Analysis complete but email may be delayed.",
            "response": analysis, "job_name": filename, "build_number": "uploaded",
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# Support chatbot

@app.route("/api/chat/support", methods=["POST"])
def support_chat():
    try:
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        context = data.get("context") or {}
        history = data.get("history") or []

        if not message:
            return jsonify({"success": False, "error": "Missing message"}), 400
        if not llm_client.is_configured():
            return jsonify({"success": False, "error": "LLM not configured."}), 500

        # Build system prompt with latest analysis context
        system = SUPPORT_CHAT_PROMPT
        if _latest_analysis["result"]:
            ctx = _latest_analysis
            system += (
                f"\n\n--- LATEST ANALYSIS CONTEXT ---\n"
                f"Job: {ctx['job_name']}\nBuild: {ctx['build_number']}\nAnalyzed: {ctx['timestamp']}\n\n"
                f"{ctx['result'][:6000]}\n--- END ANALYSIS CONTEXT ---\n\n"
                "Use this analysis data to answer questions about the latest build."
            )

        # System → conversation history → current message
        messages = [{"role": "system", "content": system}]
        for turn in history[-10:]:
            if turn.get("role") in ("user", "assistant") and turn.get("content", "").strip():
                messages.append({"role": turn["role"], "content": turn["content"]})

        ctx_text = ""
        if isinstance(context, dict) and context:
            ctx_text = "\n\nContext:\n" + "\n".join(f"{k}: {v}" for k, v in context.items())
        messages.append({"role": "user", "content": f"{message}{ctx_text}"})

        content, usage = llm_client.chat_completion(
            messages=messages, max_tokens=768, temperature=0.1,
            frequency_penalty=0, presence_penalty=0.1,
        )
        return jsonify({"success": True, "response": content, "usage": usage})

    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# Scheduling

@app.route("/schedule-email/<job_id>", methods=["POST"])
def schedule_or_send_email(job_id):
    try:
        data = request.get_json()
        frequency = data.get("frequency")
        email = data.get("email")

        if not email:
            return jsonify({"error": "Email is required"}), 400
        if not client:
            return jsonify({"error": "Database not available"}), 500

        # Find or auto-register the job
        job = None
        try:
            job = jobs_collection.find_one({"_id": ObjectId(job_id)})
        except Exception:
            pass

        jenkins_url = data.get("jenkins_url")
        username = data.get("username")
        password = data.get("password")
        job_name = data.get("job_name", "")

        if not job and all([jenkins_url, username, password, job_name]):
            result = jobs_collection.insert_one({
                "name": job_name, "url": jenkins_url,
                "username": username, "password": password, "email": email,
            })
            job_id = str(result.inserted_id)
            job = {**{"name": job_name, "url": jenkins_url, "username": username, "password": password}, "_id": result.inserted_id}
        elif not job:
            return jsonify({"error": "Job not found. Provide credentials to register it."}), 404

        job_name = job.get("name")
        jenkins_url = jenkins_url or job.get("url")
        username = username or job.get("username")
        password = password or job.get("password")

        def _generate_and_send():
            try:
                result, error = process_jenkins_log(job_id, jenkins_url, username, password)
                if error:
                    send_email_report({"analysis": f"[ERROR] {error}", "job_name": job_name}, email, job_id)
                    return
                send_email_report(result, email, job_id)
            except Exception as exc:
                print(f"[SCHED] Error for {job_name}: {exc}")
                try:
                    send_email_report({"analysis": f"[CRITICAL] {exc}", "job_name": job_name}, email, job_id)
                except Exception:
                    pass

        if frequency:
            cron_expr = FREQUENCY_MAP.get(frequency.lower())
            if not cron_expr:
                return jsonify({"error": "Invalid frequency. Use: daily, weekly, monthly, hourly"}), 400
            if frequency.lower() == "daily":
                cron_expr = f"{random.randint(0, 59)} 9 * * *"

            scheduler.add_job(
                func=_generate_and_send,
                trigger=CronTrigger.from_crontab(cron_expr),
                id=f"email_{job_id}_{email}",
                replace_existing=True, max_instances=1,
            )
            return jsonify({"message": "Email scheduled successfully"}), 200
        else:
            threading.Thread(target=_generate_and_send, daemon=True).start()
            return jsonify({"message": f"Email being generated for {job_name} → {email}"}), 202

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/schedule-email/<job_id>", methods=["DELETE"])
def cancel_scheduled_email(job_id):
    try:
        data = request.get_json(silent=True) or {}
        email = data.get("email")
        if not email:
            return jsonify({"error": "Email is required"}), 400

        sched_id = f"email_{job_id}_{email}"
        if scheduler.get_job(sched_id):
            scheduler.remove_job(sched_id)
            return jsonify({"success": True, "message": "Scheduled email cancelled"}), 200
        return jsonify({"error": "No scheduled email found"}), 404
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/scheduled-emails", methods=["GET"])
def list_scheduled_emails():
    try:
        scheduled = []
        for sj in scheduler.get_jobs():
            if not sj.id.startswith("email_"):
                continue
            parts = sj.id.split("_", 2)
            if len(parts) < 3:
                continue
            stored_id, sched_email = parts[1], parts[2]
            try:
                det = jobs_collection.find_one({"_id": ObjectId(stored_id)})
            except Exception:
                det = None
            scheduled.append({
                "job_id": stored_id,
                "job_name": det.get("name", "Unknown") if det else "Unknown (deleted)",
                "email": sched_email,
                "next_run": sj.next_run_time.isoformat() if sj.next_run_time else None,
                "trigger": str(sj.trigger),
            })
        return jsonify({"success": True, "scheduled_emails": scheduled, "total": len(scheduled)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# Analysis history

@app.route("/api/analyses", methods=["GET"])
def get_analyses():
    try:
        uid = _user_id()
        query = {"user_id": uid} if uid else {}
        docs = list(analyses_collection.find(query).sort("timestamp", -1).limit(50))
        results = [
            {
                "id": str(d["_id"]),
                "job_name": d.get("job_name", "Unknown"),
                "build_number": d.get("build_number", ""),
                "timestamp": d.get("timestamp", ""),
                "preview": (d.get("analysis", "")[:150] + "…") if len(d.get("analysis", "")) > 150 else d.get("analysis", ""),
            }
            for d in docs
        ]
        return jsonify({"success": True, "analyses": results})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/analyses/<analysis_id>", methods=["GET"])
def get_analysis(analysis_id):
    try:
        uid = _user_id()
        query = {"_id": ObjectId(analysis_id)}
        if uid:
            query["user_id"] = uid
        doc = analyses_collection.find_one(query)
        if not doc:
            return jsonify({"success": False, "error": "Analysis not found"}), 404
        return jsonify({
            "success": True, "id": str(doc["_id"]),
            "job_name": doc.get("job_name", "Unknown"),
            "build_number": doc.get("build_number", ""),
            "timestamp": doc.get("timestamp", ""),
            "analysis": doc.get("analysis", ""),
            "log_content": doc.get("log_content", ""),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/analyses/<analysis_id>", methods=["DELETE"])
def delete_analysis(analysis_id):
    try:
        uid = _user_id()
        query = {"_id": ObjectId(analysis_id)}
        if uid:
            query["user_id"] = uid
        result = analyses_collection.delete_one(query)
        if result.deleted_count == 0:
            return jsonify({"success": False, "error": "Analysis not found"}), 404
        return jsonify({"success": True, "message": "Analysis deleted"})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# SMTP test

@app.route("/api/email-test", methods=["POST"])
def email_test():
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

        msg = MIMEText("Test email from Jenkins Log Analyzer.\nSMTP is working!", "plain")
        msg["Subject"] = "Jenkins Log Analyzer — SMTP Test"
        msg["From"] = "projects@hpelabs.net"
        msg["To"] = to_email

        ports = [smtp_port] if smtp_port else [25, 587, 465]
        errors = []

        for port in ports:
            try:
                smtp = smtplib.SMTP_SSL(smtp_server, port, timeout=15) if (use_ssl or port == 465) else smtplib.SMTP(smtp_server, port, timeout=15)
                smtp.ehlo()
                if use_tls and port != 465:
                    smtp.starttls()
                    smtp.ehlo()
                if smtp_username and smtp_password:
                    smtp.login(smtp_username, smtp_password)
                smtp.sendmail(msg["From"], [to_email], msg.as_string())
                smtp.quit()
                return jsonify({"success": True, "message": f"Test email sent to {to_email} via {smtp_server}:{port}"})
            except Exception as exc:
                errors.append(f"{smtp_server}:{port} — {exc}")

        return jsonify({"success": False, "error": "All SMTP attempts failed", "details": errors}), 502
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# Entry point

if __name__ == "__main__":
    import atexit
    atexit.register(lambda: scheduler.shutdown())
    print("Starting Jenkins Log Analyzer …")
    app.run(debug=True, port=5005, host="0.0.0.0")
