from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import uuid
import json
import time
import sys
import os
import jenkins
import threading
import requests
from dotenv import load_dotenv
from threading import Lock
from datetime import datetime
from send_email import EmailReport
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from bson import ObjectId
from urllib.parse import quote_plus

# Load environment variables (prioritize .env.local for localhost)
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
    print("[CONFIG] Using .env.local for localhost MongoDB configuration")
else:
    load_dotenv()
    print("[CONFIG] Using .env for configuration")

# MongoDB Configuration
class MongoDBManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.jobs_collection = None
        self.initialize_db()
    
    def initialize_db(self):
        """Initialize MongoDB connection to localhost"""
        try:
            # Use localhost MongoDB configuration
            mongo_host = os.getenv('MONGO_HOST', 'localhost')
            mongo_port = os.getenv('MONGO_PORT', '27017')
            mongo_user = os.getenv('MONGO_USER', '')
            mongo_password = os.getenv('MONGO_PASSWORD', '')
            db_name = os.getenv('MONGO_DB_NAME', 'jenkins')
            
            # Construct MongoDB URI for localhost
            if mongo_user and mongo_password:
                encoded_password = quote_plus(mongo_password)
                mongo_uri = f"mongodb://{mongo_user}:{encoded_password}@{mongo_host}:{mongo_port}/"
            else:
                mongo_uri = f"mongodb://{mongo_host}:{mongo_port}/"
            
            # Create MongoDB client
            self.client = MongoClient(mongo_uri)
            
            # Test connection
            self.client.admin.command('ping')
            
            # Get database and collection (same names as original)
            self.db = self.client[db_name]
            self.jobs_collection = self.db.jobs
            
            # Create indexes for better performance
            self.jobs_collection.create_index([("name", 1)])
            
            print(f"[DB] Connected to MongoDB at {mongo_host}:{mongo_port}")
            print(f"[DB] Using database: {db_name}, collection: jobs")
            
            # Test if we can query the collection
            job_count = self.jobs_collection.count_documents({})
            print(f"[DB] Found {job_count} jobs in the collection")
            
        except ConnectionFailure as e:
            print(f"[DB] ❌ Error connecting to MongoDB: {e}")
            print(f"[DB] Make sure MongoDB is running on {mongo_host}:{mongo_port}")
            self.client = None
        except Exception as e:
            print(f"[DB] ❌ Error initializing database: {e}")
            self.client = None
    
    def get_active_jobs(self):
        """Get all Jenkins jobs from MongoDB"""
        if not self.client:
            return []
        try:
            jobs_cursor = self.jobs_collection.find({}).sort("name", 1)
            
            job_list = []
            for job in jobs_cursor:
                job_list.append({
                    'id': str(job['_id']),
                    'job_name': job.get('name', ''),
                    'display_name': job.get('name', ''),
                    'description': job.get('description', '') or '',
                    'jenkins_url': job.get('url', ''),
                    'username': job.get('username', ''),
                    'password': job.get('password', ''),
                    'email': job.get('email', '')
                })
            
            return job_list
            
        except Exception as e:
            print(f"[DB] Error fetching jobs: {e}")
            return []
    
    def get_job_by_id(self, job_id):
        """Get specific job details by ID"""
        if not self.client:
            return None
        try:
            if isinstance(job_id, str):
                job_id = ObjectId(job_id)
            
            job = self.jobs_collection.find_one({"_id": job_id})
            
            if job:
                return {
                    'id': str(job['_id']),
                    'job_name': job.get('name', ''),
                    'display_name': job.get('name', ''),
                    'description': job.get('description', '') or '',
                    'jenkins_url': job.get('url', ''),
                    'username': job.get('username', ''),
                    'password': job.get('password', ''),
                    'email': job.get('email', '')
                }
            return None
            
        except Exception as e:
            print(f"[DB] Error fetching job {job_id}: {e}")
            return None
    
    def insert_job(self, job_data):
        """Insert new job into MongoDB"""
        if not self.client:
            return None
        try:
            # Map the input data to MongoDB document format
            document = {
                'name': job_data['name'],
                'url': job_data['url'],
                'username': job_data['username'],
                'password': job_data['password'],
                'email': job_data.get('email', ''),
                'description': job_data.get('description', ''),
                'created_at': datetime.utcnow()
            }
            
            result = self.jobs_collection.insert_one(document)
            return str(result.inserted_id)
            
        except Exception as e:
            print(f"[DB] Error inserting job: {e}")
            return None

# Initialize MongoDB manager
db_manager = MongoDBManager()

app = Flask(__name__)
CORS(app)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Model configuration - same as ai_log_agent.py
MODEL_ENDPOINT = "https://llama70b-deploy-predictor-pankaj-rawat-hp-c8660003.pcai.si18.vcfmr.local"
API_PATH = "/v1/chat/completions"
AUTH_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IkhQeXNRVVBjeUZ5RmNMWU9VSGNiYk5TUGlRT0xxNWJxb3R6MHBwZ3JMVlEifQ.eyJhdWQiOlsiYXBpIiwiaXN0aW8tY2EiXSwiZXhwIjoxNzc0NDUzNzU2LCJpYXQiOjE3NDg1MzM3NTYsImlzcyI6Imh0dHBzOi8va3ViZXJuZXRlcy5kZWZhdWx0LnN2Yy5jbHVzdGVyLmxvY2FsIiwianRpIjoiNTBkMTU2ZWEtMzkyYi00NjBkLThiY2QtNTE0MGM5MDMwY2Y0Iiwia3ViZXJuZXRlcy5pbyI6eyJuYW1lc3BhY2UiOiJ1aSIsInNlcnZpY2VhY2NvdW50Ijp7Im5hbWUiOiJpc3ZjLWVwLTE3NDg1MzM3NTY4ODAiLCJ1aWQiOiIzOTE1ZmFjOS01ZjI2LTRjYzUtOTBjMS05NDZmN2U5MTk0NTYifX0sIm5iZiI6MTc0ODUzMzc1Niwic3ViIjoic3lzdGVtOnNlcnZpY2VhY2NvdW50OnVpOmlzdmMtZXAtMTc0ODUzMzc1Njg4MCJ9.WMXxihq-1Wia_DajqhShbNQ0J_titbGAECR2nFfPFm4xckQ2ALV6nHsdOnaTIxZj-8pZUiMnkK_7WXFrL4_y2EYzqhmkpZ6h6t994dmdCIIhWbYobzE91w7IhABp9dQSiezyP3g4Ei-3dbFAJvXULXFT9MR-HrihzudYOkhBCANG3J4gEK3eTpoozBVeAijMnPMlWWpAiucRsYjW8JDoFJtxAnoL0jIKxUg1x9bnMHe1h77otDoXXvtpkMmr9Ih-k60XZm5FkilM4Q2kWhxOScKpR8Gtkn5CZuyXBCCyYz_v5C0HpCLGJrE7l0gk1LtrMbrfiDaknRZQu50Q1GDFNw"

SUMMARY_PROMPT = (
    "Analyze the following Jenkins build log, with a focus on the pytest execution output. Identify and summarize:\n\n"
    "**Failed test cases** along with their names and file locations.\n\n"
    "**Selectors or locators** that caused the failures (e.g., CSS/XPath), and specify where in the code (file/function) they are defined or referenced, if visible.\n\n"
    "**Any tracebacks or error messages** related to element not found, timeout, or assertion errors.\n\n"
    "**Group the findings** to help testers quickly backtrack in the browser and debug.\n\n"
    "Format your response in a structured way that makes it easy for testers to understand what failed and where to look for fixes.\n\n"
    "If there is no information regarding the pytest execution analyze and summarize the provided logs"
    "Jenkins build log to analyze:\n\n"
)

TOKENS_PER_CHUNK = 100000
CHARS_PER_TOKEN = 4  # Safe estimate
CHUNK_SIZE = TOKENS_PER_CHUNK * CHARS_PER_TOKEN  # 400,000 characters

def frequency_to_cron(frequency):
    """Convert frequency string to cron expression"""
    frequency_map = {
        'daily': '0 9 * * *',      # Daily at 9 AM
        'weekly': '0 9 * * 1',     # Weekly on Monday at 9 AM
        'monthly': '0 9 1 * *',    # Monthly on 1st at 9 AM
        'hourly': '0 * * * *'      # Every hour
    }
    return frequency_map.get(frequency.lower())

def split_by_chars(text, chunk_size):
    """Split text into chunks by character count"""
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def summarize_chunk(chunk):
    """Summarize a single chunk using LLaMA API"""
    prompt = SUMMARY_PROMPT + chunk
    BODY_DATA = {
        "model": "meta/llama-3.1-70b-instruct",
        "messages": [
            { "role": "system", "content": "You are a data analysis expert" },
            { "role": "user", "content": prompt }
        ],
        "max_tokens": 1024
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}",
    }
    try:
        response = requests.post(
            f"{MODEL_ENDPOINT}{API_PATH}",
            headers=headers,
            data=json.dumps(BODY_DATA),
            verify=False,
            timeout=60  # 60 second timeout
        )
        resp_json = response.json()
        return resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        return f"[ERROR] Failed to summarize chunk: {str(e)}"

def iterative_summarize(text, chunk_size=CHUNK_SIZE):
    """
    Repeatedly splits text into character-based chunks, summarizes each chunk, 
    and then summarizes the summaries, until the result fits in one chunk.
    """
    while len(text) > chunk_size:
        chunks = split_by_chars(text, chunk_size)
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            print(f"[AI] Processing chunk {i+1}/{len(chunks)}...")
            summary = summarize_chunk(chunk)
            chunk_summaries.append(summary)
        text = "\n\n".join(chunk_summaries)
    # Final summary
    print("[AI] Generating final summary...")
    return summarize_chunk(text)

def analyze_jenkins_log(log_content):
    """Analyze Jenkins log using direct API call"""
    try:
        print(f"[AI] Starting analysis of log ({len(log_content)} characters)")
        return iterative_summarize(log_content)
    except Exception as e:
        return f"[AI ANALYSIS ERROR]: {str(e)}"

class JenkinsLogProcessor:
    def __init__(self):
        self.email_reporter = EmailReport()

    def process_jenkins_log(self, job_id, jenkins_url=None, username=None, password=None):
        """Process Jenkins log and return analysis directly"""
        try:
            if not db_manager.client:
                return None, "Database connection not available. Make sure MongoDB is running on localhost:27017"

            job_details = db_manager.get_job_by_id(job_id)
            if not job_details:
                return None, f"Job with ID {job_id} not found"

            jenkins_url = jenkins_url or job_details.get('jenkins_url')
            username = username or job_details.get('username')
            password = password or job_details.get('password')
            job_name = job_details['job_name']

            if not all([jenkins_url, username, password]):
                return None, "Missing Jenkins credentials or URL"

            print(f"[JENKINS] Connecting to {jenkins_url} for job: {job_name}")
            server = jenkins.Jenkins(jenkins_url, username=username, password=password)
            job_info = server.get_job_info(job_name)
            
            if not job_info.get('lastCompletedBuild'):
                return None, f"No completed builds for job: {job_name}"

            build_number = job_info['lastCompletedBuild']['number']
            print(f"[JENKINS] Fetching log for build #{build_number}")
            jenkins_log = server.get_build_console_output(job_name, build_number)
            
            if not jenkins_log:
                return None, f"No log found for build #{build_number}"

            print(f"[JENKINS] Log fetched successfully ({len(jenkins_log)} characters)")
            
            # Analyze the log directly
            analysis_result = analyze_jenkins_log(jenkins_log)
            
            return {
                "analysis": analysis_result,
                "job_name": job_name,
                "build_number": build_number,
                "job_details": job_details
            }, None

        except Exception as e:
            print(f"[ERROR] Error in process_jenkins_log: {e}")
            return None, str(e)

    def send_email_report(self, analysis_data, email_address, frequency, job_id):
        """Send email report with analysis"""
        try:
            job_name = analysis_data.get("job_name", "Unknown Job")
            build_number = analysis_data.get("build_number", "Unknown Build")
            analysis_result = analysis_data.get("analysis", "No analysis result")
            
            print(f"[EMAIL] Preparing email report for {email_address}")
            
            # Save analysis to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_job_name = "".join(c for c in job_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"jenkins_analysis_{safe_job_name}_{timestamp}.txt"
            filepath = os.path.join("reports", filename)
            
            # Create reports directory if it doesn't exist
            os.makedirs("reports", exist_ok=True)
            
            # Write analysis result to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Jenkins Log Analysis Report\n")
                f.write(f"=" * 60 + "\n")
                f.write(f"Job Name: {job_name}\n")
                f.write(f"Job ID: {job_id}\n")
                f.write(f"Build Number: {build_number}\n")
                f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Frequency: {frequency}\n")
                f.write(f"=" * 60 + "\n\n")
                f.write(f"AI Analysis Result:\n")
                f.write(f"-" * 40 + "\n")
                f.write(f"{analysis_result}\n")
                f.write(f"-" * 40 + "\n")
                f.write(f"\nReport generated by Jenkins Log Analyzer (Simple Mode)")
            
            print(f"[EMAIL] Analysis report saved to {filepath}")
            
            # Send email with the file as attachment
            subject = f"Jenkins Log Analysis Report - {job_name}"
            
            self.email_reporter.send_email(
                filename=filepath,
                subject=subject,
                to_email=[email_address]
            )
            
            print(f"[EMAIL] ✅ Report successfully sent to {email_address}")
            return True
            
        except Exception as e:
            print(f"[EMAIL] ❌ Error sending email report: {e}")
            return False

# Initialize processor
processor = JenkinsLogProcessor()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    if not db_manager.client:
        return jsonify({'success': False, 'error': 'Database connection not available. Make sure MongoDB is running on localhost:27017'}), 500
    try:
        jobs = db_manager.get_active_jobs()
        return jsonify({'success': True, 'jobs': jobs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/jobs', methods=['POST'])
def add_job():
    if not db_manager.client:
        return jsonify({'success': False, 'error': 'Database connection not available. Make sure MongoDB is running on localhost:27017'}), 500
    try:
        data = request.get_json()
        for field in ['name', 'url', 'username', 'password']:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'Missing field: {field}'}), 400

        job_data = {
            'name': data['name'].strip(),
            'url': data['url'].strip(),
            'username': data['username'].strip(),
            'password': data['password'].strip(),
            'email': data.get('email', '').strip(),
            'description': data.get('description', '').strip()
        }

        job_id = db_manager.insert_job(job_data)
        if job_id:
            return jsonify({'success': True, 'message': 'Job added', 'job_id': job_id})
        return jsonify({'success': False, 'error': 'Insert failed'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analyze', methods=['POST'])
def analyze_log():
    try:
        data = request.get_json()
        if 'job_id' not in data:
            return jsonify({'success': False, 'error': 'Missing job_id'}), 400

        job_id = data['job_id']
        jenkins_url = data.get('jenkins_url')
        username = data.get('username')
        password = data.get('password')

        print(f"[API] Starting analysis for job_id: {job_id}")
        
        # Process Jenkins log and get analysis directly
        result, error = processor.process_jenkins_log(job_id, jenkins_url, username, password)
        if error:
            return jsonify({'success': False, 'error': error}), 400

        print(f"[API] Analysis completed successfully")
        
        return jsonify({
            'success': True,
            'response': result['analysis'],
            'job_name': result['job_details'].get('display_name', result['job_name']),
            'build_number': result['build_number'],
            'message': 'Analysis completed successfully'
        })

    except Exception as e:
        print(f"[API] Error in analyze_log: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/schedule-email/<job_id>', methods=['POST'])
def schedule_or_send_email(job_id):
    try:
        data = request.get_json()
        frequency = data.get('frequency')  # e.g. 'daily', 'weekly', 'monthly', or None for immediate
        email = data.get('email')

        if not email:
            return jsonify({'error': 'Email is required'}), 400

        # Get job details from database
        if not db_manager.client:
            return jsonify({'error': 'Database connection not available. Make sure MongoDB is running on localhost:27017'}), 500
            
        job_details = db_manager.get_job_by_id(job_id)
        if not job_details:
            return jsonify({'error': 'Job not found'}), 404

        job_name = job_details['job_name']
        jenkins_url = job_details.get('jenkins_url')
        username = job_details.get('username') 
        password = job_details.get('password')

        def generate_and_send_summary():
            """Generate latest Jenkins log analysis and send via email"""
            try:
                print(f"[EMAIL] Generating summary for job: {job_name}")
                
                # Process Jenkins log and get analysis directly
                result, error = processor.process_jenkins_log(job_id, jenkins_url, username, password)
                if error:
                    print(f"[EMAIL] Error processing Jenkins log: {error}")
                    return

                # Send email with analysis
                success = processor.send_email_report(result, email, frequency or 'immediate', job_id)
                if success:
                    print(f"[EMAIL] ✅ Summary sent successfully to {email}")
                else:
                    print(f"[EMAIL] ❌ Failed to send summary to {email}")
                
            except Exception as e:
                print(f"[EMAIL] Error in generate_and_send_summary: {e}")

        if frequency:
            # Schedule recurring email
            cron_expr = frequency_to_cron(frequency)
            if not cron_expr:
                return jsonify({'error': 'Invalid frequency. Use: daily, weekly, monthly, hourly'}), 400
            
            try:
                scheduler.add_job(
                    func=generate_and_send_summary,
                    trigger=CronTrigger.from_crontab(cron_expr),
                    id=f"email_{job_id}_{email}",
                    replace_existing=True
                )
                print(f"[EMAIL] Scheduled {frequency} email for job {job_name} to {email}")
                return jsonify({
                    'success': True,
                    'message': f'Email scheduled {frequency} for job "{job_name}" to {email}',
                    'frequency': frequency,
                    'cron_expression': cron_expr,
                    'job_name': job_name
                }), 200
            except Exception as e:
                return jsonify({'error': f'Failed to schedule email: {str(e)}'}), 500
        else:
            # Send immediately in background thread
            threading.Thread(target=generate_and_send_summary, daemon=True).start()
            return jsonify({
                'success': True,
                'message': f'Analysis started and email will be sent to {email} for job "{job_name}"',
                'job_name': job_name,
                'note': 'Email will be sent when analysis completes'
            }), 200
            
    except Exception as e:
        print(f"[EMAIL] Error in schedule_or_send_email: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/schedule-email/<job_id>', methods=['DELETE'])
def cancel_scheduled_email(job_id):
    """Cancel scheduled email for a job"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'error': 'Email is required to cancel scheduled job'}), 400
            
        job_id_email = f"email_{job_id}_{email}"
        
        # Check if job exists in scheduler
        existing_job = scheduler.get_job(job_id_email)
        if existing_job:
            scheduler.remove_job(job_id_email)
            return jsonify({
                'success': True,
                'message': f'Scheduled email cancelled for job {job_id} to {email}'
            }), 200
        else:
            return jsonify({'error': 'No scheduled email found for this job and email'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/scheduled-emails', methods=['GET'])
def list_scheduled_emails():
    """List all scheduled email jobs"""
    try:
        jobs = scheduler.get_jobs()
        scheduled_emails = []
        
        for job in jobs:
            if job.id.startswith('email_'):
                # Parse job ID to extract job_id and email
                parts = job.id.split('_', 2)  # email_jobid_email
                if len(parts) >= 3:
                    job_id = parts[1]
                    email = parts[2]
                    
                    # Get job details
                    job_details = db_manager.get_job_by_id(job_id) if db_manager.client else None
                    job_name = job_details.get('display_name', 'Unknown') if job_details else 'Unknown'
                    
                    scheduled_emails.append({
                        'job_id': job_id,
                        'job_name': job_name,
                        'email': email,
                        'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                        'trigger': str(job.trigger)
                    })
        
        return jsonify({
            'success': True,
            'scheduled_emails': scheduled_emails,
            'total': len(scheduled_emails)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'healthy', 
        'timestamp': time.time(),
        'mode': 'simple',
        'description': 'Direct API mode - no Kafka required'
    })

if __name__ == '__main__':
    import atexit
    
    # Register cleanup function
    def cleanup():
        print("Shutting down scheduler...")
        scheduler.shutdown()
    
    atexit.register(cleanup)
    
    print("Starting Jenkins Log Analyzer Web App (Simple Mode)...")
    print("🚀 Direct API mode - no Kafka required!")
    print("Email scheduler is running...")
    
    port = int(os.getenv('FLASK_PORT', 5003))  # Different port to avoid conflicts
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug, host=host, port=port)
