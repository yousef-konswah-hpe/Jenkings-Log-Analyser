"""Business-logic services: Jenkins log processing, email, analysis persistence."""

import os
import threading
from datetime import datetime

import jenkins
from bson.objectid import ObjectId

from analysis import safe_analyze_with_retry
from config import jobs_collection, analyses_collection
from send_email import EmailReport
from rag import store_embedding


def process_jenkins_log(job_id, jenkins_url=None, username=None, password=None):
    """Fetch the latest console log for a stored Jenkins job and analyse it."""
    try:
        try:
            oid = ObjectId(job_id)
        except Exception:
            return None, f"Invalid job ID format: {job_id}"

        job = jobs_collection.find_one({"_id": oid})
        if not job:
            return None, f"Job with ID {job_id} not found"

        jenkins_url = jenkins_url or job.get("url")
        username = username or job.get("username")
        password = password or job.get("password")
        job_name = job.get("name")

        if not all([jenkins_url, username, password]):
            return None, "Missing Jenkins credentials or URL"

        server = jenkins.Jenkins(jenkins_url, username=username, password=password)
        job_info = server.get_job_info(job_name)
        if not job_info:
            return None, f'Jenkins job "{job_name}" not found'

        last_build = job_info.get("lastCompletedBuild")
        if not last_build:
            return None, f'No completed builds for job "{job_name}"'

        build_number = last_build["number"]
        log_text = server.get_build_console_output(job_name, build_number)
        if not log_text or len(log_text.strip()) < 100:
            return None, f"No meaningful log content for build #{build_number}"

        print(f"[SVC] Analysing {job_name} #{build_number} ({len(log_text)} chars)")

        result = safe_analyze_with_retry(log_text, job_name=job_name)
        analysis = result.get("report", "")
        if analysis.startswith("[AI ANALYSIS ERROR]"):
            return None, f"AI analysis failed: {analysis}"

        return {
            "analysis": analysis,
            "job_name": job_name,
            "build_number": build_number,
            "job_details": job,
            "log_text": log_text,
            "similar_analyses": result.get("similar_analyses", []),
            "react_trace": result.get("react_trace", []),
        }, None

    except jenkins.NotFoundException:
        return None, "Jenkins job or build not found"
    except Exception as exc:
        print(f"[SVC] Error analysing job: {exc}")
        return None, str(exc)


def send_email_report(analysis_data: dict, email_address, job_id) -> bool:
    """Save analysis to disk and email it."""
    try:
        job_name = analysis_data.get("job_name", "Unknown Job")
        analysis_text = analysis_data.get("analysis", "No analysis result")

        path = f"./logs/{job_name}_latest.txt"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(analysis_text)

        recipients = [email_address] if isinstance(email_address, str) else email_address
        EmailReport().send_email(
            filename=path,
            subject=f"AI Log Analysis Report for Jenkins job: {job_name}",
            to_email=recipients,
        )
        print(f"[SVC] Report sent to {email_address} for '{job_name}'")
        return True

    except Exception as exc:
        print(f"[SVC] Email error: {exc}")
        return False


def save_analysis(job_name: str, build_number, analysis_text: str, log_content: str = "", user_id: str = "") -> str | None:
    """Persist an analysis result in MongoDB, then generate its RAG embedding."""
    try:
        doc = {
            "job_name": job_name,
            "build_number": str(build_number),
            "analysis": analysis_text,
            "log_content": log_content,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
        }
        result = analyses_collection.insert_one(doc)
        analysis_id = str(result.inserted_id)
        print(f"[SVC] Saved analysis {analysis_id}")

        # Generate and store RAG embedding in background
        threading.Thread(
            target=store_embedding,
            args=(analysis_id, job_name, analysis_text),
            daemon=True,
        ).start()

        return analysis_id
    except Exception as exc:
        print(f"[SVC] Save failed: {exc}")
        return None
