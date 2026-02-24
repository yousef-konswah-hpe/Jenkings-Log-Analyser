from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import jenkins
import pymongo
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv
from send_email import EmailReport
import requests
import time
import threading
import random
from datetime import datetime
from urllib.parse import quote_plus

# Load environment variables (prioritize .env.local for localhost)
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
    print("[CONFIG] Using .env.local for localhost MongoDB configuration")
else:
    load_dotenv()
    print("[CONFIG] Using .env for configuration")

# MongoDB setup with environment variables - simplified like app_simple.py
MONGO_USER = os.getenv("MONGO_USER", "sample")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "sample@123")
MONGO_HOST = os.getenv("MONGO_HOST", "10.157.21.212")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_DB = os.getenv("MONGO_DB", "jenkins")
MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB", "admin")  # Authentication database

# Build MongoDB connection string with proper authentication
# URL encode username and password to handle special characters
encoded_user = quote_plus(MONGO_USER)
encoded_password = quote_plus(MONGO_PASSWORD)

# MongoDB connection string with authentication database
mongo_connection_string = f"mongodb://{encoded_user}:{encoded_password}@{MONGO_HOST}:{MONGO_PORT}/{MONGO_AUTH_DB}"

print(f"Connecting to MongoDB at: {MONGO_HOST}:{MONGO_PORT}")
print(f"Using database: {MONGO_DB}")
print(f"Authentication database: {MONGO_AUTH_DB}")

try:
    client = MongoClient(
        mongo_connection_string,
        serverSelectionTimeoutMS=5000,  # 5 second timeout
        connectTimeoutMS=5000,
        socketTimeoutMS=5000
    )
    # Test the connection
    client.server_info()
    print("Connected to MongoDB successfully.")
    db = client[MONGO_DB]
    jobs_collection = db['jobs']
    
    # Test database access
    try:
        jobs_collection.find_one()
        print("Database access verified.")
    except Exception as db_error:
        print(f"Database access test failed: {db_error}")
        
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    # Fallback to localhost if remote connection fails
    try:
        print("Attempting fallback to local MongoDB...")
        client = MongoClient("mongodb://localhost:27017/")
        client.server_info()
        print("Connected to local MongoDB as fallback.")
        db = client['jenkins']
        jobs_collection = db['jobs']
    except Exception as e2:
        print(f"Error connecting to local MongoDB: {e2}")
        raise Exception("Failed to connect to both remote and local MongoDB")

app = Flask(__name__)
CORS(app)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# New AI Model API configuration - same as app_simple.py
API_URL = "https://lama-3.project-user-private-cloud-ai.serving.pcai.r22n5640.lan/v1/chat/completions"
MODEL_NAME = "meta/llama-3.1-70b-instruct"
AUTH_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjFqZ3lUZXZ3ZE1KR05fYk9TODZCVGFoVFhYYTJhOGNUNWNKdjlVZ0U4LXcifQ.eyJhdWQiOlsiYXBpIiwiaXN0aW8tY2EiXSwiZXhwIjoxNzcyNzA2MzI2LCJpYXQiOjE3NjIzMzgzMjYsImlzcyI6Imh0dHBzOi8va3ViZXJuZXRlcy5kZWZhdWx0LnN2Yy5jbHVzdGVyLmxvY2FsIiwianRpIjoiMDIwNmM5ZDktMGZlMy00OTZhLWE0NDEtMDQyZDAyMWY5MDdjIiwia3ViZXJuZXRlcy5pbyI6eyJuYW1lc3BhY2UiOiJ1aSIsInNlcnZpY2VhY2NvdW50Ijp7Im5hbWUiOiJpc3ZjLWVwLTE3NjIzMzgzMjY0NDciLCJ1aWQiOiI0MDQzNjk2Mi1hNThmLTQ2NTktYmNlOC01NTJmYzUxZTFiZTkifX0sIm5iZiI6MTc2MjMzODMyNiwic3ViIjoic3lzdGVtOnNlcnZpY2VhY2NvdW50OnVpOmlzdmMtZXAtMTc2MjMzODMyNjQ0NyJ9.AbCDdnV4uZK_nfV_qpJM6obxEe8rxkzzPHxODXE_w6UahUjQ_5v7RDCG5crxNW8qx5Ocqul2bxv5ZhRU4THedJ2xWaHf7Djk2AnDJOVhBDvYabp4FYZFuL_KEYfYRWO0ZvmZqAj-f92zEOfSp08iuEUWe7f1IXhPbjaP7KB_or7XbPBLW_jJbZnrj1_T3ezaSb70vz8uxlyp4qQwM_UA26D6JoZgclA4d_GagUvJKhGCQJyll5uiuDYtemuAmAcCwYpSBCP399_DafjGS3PUrSzPyR_zs19dNrn5nNeEeRpU5EBcpLfCKRnXSu2U9zPC5hfEmC32aHVDZiN3_j0QZw"

SUMMARY_PROMPT = (
    "Analyze the following Jenkins build log, with a focus on the pytest execution output. Identify and summarize:\n\n"
    "**Failed test cases** along with their names and file locations.\n\n"
    "**Selectors or locators** that caused the failures (e.g., CSS/XPath), and specify where in the code (file/function) they are defined or referenced, if visible.\n\n"
    "**Any tracebacks or error messages** related to element not found, timeout, or assertion errors.\n\n"
    "**Group the findings** to help testers quickly backtrack in the browser and debug.\n\n"
    "Format your response in a structured way that makes it easy for testers to understand what failed and where to look for fixes.\n\n"
    "Jenkins build log to analyze:\n\n"
)

TOKENS_PER_CHUNK = 60000  # Conservative limit to fit within 131k token context
CHARS_PER_TOKEN = 4  # Safe estimate
CHUNK_SIZE = TOKENS_PER_CHUNK * CHARS_PER_TOKEN  # 240,000 characters

# Constants for chunking
CHUNK_OVERLAP = 1000  # Characters to overlap between chunks for context

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
    """Summarize a single chunk using new AI API with improved error handling"""
    # Check chunk size and truncate if necessary
    max_chunk_chars = 60000 * 4  # ~60k tokens worth of characters for safety
    if len(chunk) > max_chunk_chars:
        print(f"[AI] Chunk too large ({len(chunk)} chars), truncating to {max_chunk_chars} chars")
        chunk = chunk[-max_chunk_chars:]  # Take the end of the log which is usually most important
    
    prompt = SUMMARY_PROMPT + chunk
    
    # Prepare the request payload in OpenAI chat format
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "You are a Jenkins build log analysis expert. Provide detailed, structured analysis of build logs."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 1024,
        "temperature": 0,
        "frequency_penalty": 0,
        "presence_penalty": 0.5
    }
    
    # Prepare headers
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {AUTH_TOKEN}'
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"[AI] Making API request (attempt {attempt + 1}/{max_retries})")
            
            response = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                verify=False,
                timeout=600  # 10 minutes timeout for large chunks
            )
            
            if response.status_code == 200:
                response_json = response.json()
                
                # Extract the content from choices (same as app_simple.py)
                if response_json.get('choices') and len(response_json['choices']) > 0:
                    content = response_json['choices'][0]['message']['content']
                    if content and content.strip():
                        print(f"[AI] ✅ Chunk processed successfully ({response_json.get('usage', {}).get('total_tokens', 'unknown')} tokens)")
                        return content
                    else:
                        print(f"[AI] ⚠️ Empty content in response on attempt {attempt + 1}")
                else:
                    print(f"[AI] ⚠️ No choices found in response on attempt {attempt + 1}")
            else:
                print(f"[AI] ⚠️ HTTP {response.status_code} on attempt {attempt + 1}: {response.text[:200]}")
                
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(1, 3)
                print(f"[AI] Waiting {wait_time:.1f} seconds before retry...")
                time.sleep(wait_time)
                
        except requests.exceptions.Timeout:
            print(f"[AI] ⚠️ Request timeout on attempt {attempt + 1}")
        except requests.exceptions.ConnectionError as e:
            print(f"[AI] ⚠️ Connection error on attempt {attempt + 1}: {e}")
        except Exception as e:
            print(f"[AI] ⚠️ Unexpected error on attempt {attempt + 1}: {e}")
            
        if attempt < max_retries - 1:
            wait_time = (2 ** attempt) + random.uniform(2, 5)
            time.sleep(wait_time)
    
    return f"[ERROR] Failed to summarize chunk after {max_retries} attempts"

def iterative_summarize(text, chunk_size=CHUNK_SIZE):
    """
    Repeatedly splits text into character-based chunks, summarizes each chunk, 
    and then summarizes the summaries, until the result fits in one chunk.
    """
    original_length = len(text)
    print(f"[AI] Starting iterative summarization of {original_length} characters")
    
    iteration = 1
    while len(text) > chunk_size:
        print(f"[AI] Iteration {iteration}: Processing {len(text)} characters")
        chunks = split_by_chars(text, chunk_size)
        chunk_summaries = []
        
        for i, chunk in enumerate(chunks):
            print(f"[AI] Processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...")
            summary = summarize_chunk(chunk)
            if summary and not summary.startswith("[ERROR]"):
                chunk_summaries.append(summary)
            else:
                print(f"[AI] Warning: Chunk {i+1} failed to summarize, skipping")
        
        if not chunk_summaries:
            return "[ERROR] All chunks failed to summarize"
            
        text = "\n\n".join(chunk_summaries)
        print(f"[AI] Iteration {iteration} complete: Reduced to {len(text)} characters")
        iteration += 1
        
        # Safety check to prevent infinite loops
        if iteration > 10:
            print(f"[AI] Max iterations reached, proceeding with current text length")
            break
    
    # Final summary
    print("[AI] Generating final summary...")
    return summarize_chunk(text)

def analyze_jenkins_log(log_content):
    """Analyze Jenkins log using direct API call with better error handling"""
    try:
        print(f"[AI] Starting analysis of log ({len(log_content)} characters)")
        
        # Add timeout and better error handling
        result = iterative_summarize(log_content)
        
        if not result or result.strip() == "":
            return "[AI ANALYSIS ERROR]: Empty response from AI model"
            
        return result
        
    except requests.exceptions.Timeout as e:
        return f"[AI ANALYSIS ERROR]: Request timeout - {str(e)}"
    except requests.exceptions.ConnectionError as e:
        return f"[AI ANALYSIS ERROR]: Connection error - {str(e)}"
    except Exception as e:
        return f"[AI ANALYSIS ERROR]: {str(e)}"

def safe_ai_request_with_retry(log_content, max_retries=3):
    """Make AI request with retry logic (simplified like app_simple.py)"""
    for attempt in range(max_retries):
        try:
            print(f"[AI] Attempt {attempt + 1}/{max_retries} - Processing log ({len(log_content)} characters)")
            
            # Add delay for retries
            if attempt > 0:
                delay = 2 ** attempt + random.uniform(1, 3)
                print(f"[AI] Waiting {delay:.1f} seconds before retry...")
                time.sleep(delay)
            
            result = analyze_jenkins_log(log_content)
            
            # Check if result contains error
            if result and not result.startswith("[AI ANALYSIS ERROR]") and not result.startswith("[ERROR]"):
                print(f"[AI] ✅ Analysis completed successfully on attempt {attempt + 1}")
                return result
            else:
                print(f"[AI] ⚠️ Analysis returned error on attempt {attempt + 1}: {result[:100]}...")
                if attempt < max_retries - 1:
                    continue
                    
        except Exception as e:
            print(f"[AI] ❌ Error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                continue
    
    return f"[AI ANALYSIS ERROR]: Failed after {max_retries} attempts"

# Direct functions like app_simple.py

def send_email_report(analysis_data, email_address, job_id):
    """Send email report with analysis (simplified like app_simple.py)"""
    try:
        job_name = analysis_data.get("job_name", "Unknown Job")
        analysis_result = analysis_data.get("analysis", "No analysis result")
        
        # Save summary to file
        latest_summary_path = f"./logs/{job_name}_latest.txt"
        latest_summary_dir = os.path.dirname(latest_summary_path)
        os.makedirs(latest_summary_dir, exist_ok=True)
        
        with open(latest_summary_path, "w") as f:
            f.write(analysis_result)
            
        email_report = EmailReport()
        email_report.send_email(
            filename=latest_summary_path,
            subject=f"AI Log Analysis Report for Jenkins job: {job_name}",
            to_email=[email_address] if isinstance(email_address, str) else email_address
        )
        print(f"Email sent to {email_address} for job {job_name}")
        return True
        
    except Exception as e:
        print(f"Error sending email report: {e}")
        return False

def process_jenkins_log(job_id, jenkins_url=None, username=None, password=None):
    """Process Jenkins log and return analysis directly with chunking support"""
    try:
        job = jobs_collection.find_one({'_id': ObjectId(job_id)})
        if not job:
            return None, f"Job with ID {job_id} not found"

        jenkins_url = jenkins_url or job.get('url')
        username = username or job.get('username')
        password = password or job.get('password')
        job_name = job.get('name')

        if not all([jenkins_url, username, password]):
            return None, "Missing Jenkins credentials or URL"

        print(f"Analyzing job: {job_name}")
        
        # Connect to Jenkins
        server = jenkins.Jenkins(jenkins_url, username=username, password=password)
        
        # Get job info and validate
        job_info = server.get_job_info(job_name)
        if not job_info:
            return None, f'Jenkins job "{job_name}" not found'
        
        if 'lastCompletedBuild' not in job_info or not job_info['lastCompletedBuild']:
            return None, f'No completed builds found for job "{job_name}"'

        # Get the latest build
        build_number = job_info['lastCompletedBuild']['number']
        print(f"Analyzing build number: {build_number}")
        
        jenkins_log = server.get_build_console_output(job_name, build_number)
        
        if not jenkins_log or len(jenkins_log.strip()) < 100:
            return None, f"No meaningful log content found for build #{build_number}"

        print(f"Log fetched successfully ({len(jenkins_log)} characters)")
        
        # Use chunking analysis for large logs
        analysis_result = safe_ai_request_with_retry(jenkins_log)
        
        if analysis_result.startswith("[AI ANALYSIS ERROR]"):
            return None, f"AI analysis failed: {analysis_result}"
        
        return {
            "analysis": analysis_result,
            "job_name": job_name,
            "build_number": build_number,
            "job_details": job
        }, None

    except jenkins.NotFoundException:
        return None, "Jenkins job or build not found"
    except Exception as e:
        print(f"Error analyzing job: {e}")
        return None, str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    if not client:
        return jsonify({'success': False, 'error': 'Database connection not available. Make sure MongoDB is running'}), 500
    try:
        jobs = list(jobs_collection.find({}, {'name': 1}))
        print(f"Found {len(jobs)} jobs")
        
        formatted_jobs = []
        for job in jobs:
            formatted_jobs.append({
                'id': str(job['_id']),
                'display_name': job['name'],
                'description': job.get('description', '')
            })
        
        return jsonify({'success': True, 'jobs': formatted_jobs})
    except Exception as e:
        print(f"Error getting jobs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/jobs', methods=['POST'])
def add_job():
    if not client:
        return jsonify({'success': False, 'error': 'Database connection not available. Make sure MongoDB is running'}), 500
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'url', 'username', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'Field {field} is required'}), 400

        # Check if job already exists
        existing_job = jobs_collection.find_one({'name': data['name']})
        if existing_job:
            return jsonify({'success': False, 'error': 'Job with this name already exists'}), 400

        # Insert the new job
        job_data = {
            'name': data['name'],
            'url': data['url'],
            'username': data['username'],
            'password': data['password'],
            'email': data.get('email', ''),
            'description': data.get('description', '')
        }

        result = jobs_collection.insert_one(job_data)
        return jsonify({'success': True, 'job_name': data['name'], 'job_id': str(result.inserted_id)})

    except Exception as e:
        print(f"Error adding job: {e}")
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

        print(f"Starting analysis for job_id: {job_id}")
        
        # Process Jenkins log and get analysis directly (with chunking)
        result, error = process_jenkins_log(job_id, jenkins_url, username, password)
        if error:
            return jsonify({'success': False, 'error': error}), 400

        print("Analysis completed successfully")
        
        return jsonify({
            'success': True,
            'response': result['analysis'],
            'job_name': result['job_name'],
            'build_number': result['build_number']
        })

    except Exception as e:
        print(f"Error analyzing job: {e}")
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
        if not client:
            return jsonify({'error': 'Database connection not available. Make sure MongoDB is running'}), 500
            
        job = jobs_collection.find_one({'_id': ObjectId(job_id)})
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        job_name = job.get('name')
        jenkins_url = job.get('url')
        username = job.get('username') 
        password = job.get('password')

        def generate_and_send_summary():
            """Generate latest Jenkins log analysis and send via email (simplified like app_simple.py)"""
            try:
                print(f"Generating summary for job: {job_name}")
                
                # Process Jenkins log with chunking support
                result, error = process_jenkins_log(job_id, jenkins_url, username, password)
                if error:
                    print(f'Error processing Jenkins log for {job_name}: {error}')
                    # Still send email with error information
                    error_analysis = {
                        "analysis": f"[ERROR] Failed to analyze Jenkins log: {error}",
                        "job_name": job_name
                    }
                    send_email_report(error_analysis, email, job_id)
                    return

                # Send email with analysis
                success = send_email_report(result, email, job_id)
                if success:
                    print(f"Summary sent successfully to {email} for job {job_name}")
                else:
                    print(f"Failed to send summary to {email} for job {job_name}")
                
            except Exception as e:
                print(f"Error in generate_and_send_summary for job {job_name}: {e}")
                # Send error notification email
                try:
                    error_analysis = {
                        "analysis": f"[CRITICAL ERROR] Failed to process scheduled analysis: {str(e)}",
                        "job_name": job_name
                    }
                    send_email_report(error_analysis, email, job_id)
                except:
                    print(f"Failed to send error notification email for job {job_name}")

        if frequency:
            # Schedule recurring email with modified cron to spread jobs
            cron_expr = frequency_to_cron(frequency)
            if not cron_expr:
                return jsonify({'error': 'Invalid frequency. Use: daily, weekly, monthly, hourly'}), 400
            
            # Add random minute offset to spread daily jobs across time
            if frequency.lower() == 'daily':
                base_minute = random.randint(0, 59)
                cron_expr = f"{base_minute} 9 * * *"  # Random minute at 9 AM
            
            try:
                scheduler.add_job(
                    func=generate_and_send_summary,
                    trigger=CronTrigger.from_crontab(cron_expr),
                    id=f"email_{job_id}_{email}",
                    replace_existing=True,
                    max_instances=1  # Prevent overlapping executions
                )
                print(f"Scheduled {frequency} email for job {job_name} to {email} (cron: {cron_expr})")
                return jsonify({'message': 'Email scheduled successfully'}), 200
            except Exception as e:
                return jsonify({'error': f'Failed to schedule email: {str(e)}'}), 500
        else:
            # Send immediately
            threading.Thread(target=generate_and_send_summary, daemon=True).start()
            return jsonify({'message': f'Email sent to {email} for job {job_name}'}), 200
            
    except Exception as e:
        print(f"Error in schedule_or_send_email: {e}")
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
                    job_details = jobs_collection.find_one({'_id': ObjectId(job_id)})
                    job_name = job_details.get('name', 'Unknown') if job_details else 'Unknown'
                    
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
        'mode': 'chunks',
        'description': 'Direct API mode with chunking support for large logs'
    })

if __name__ == '__main__':
    import atexit
    
    # Register cleanup function
    def cleanup():
        print("Shutting down scheduler...")
        scheduler.shutdown()
    
    atexit.register(cleanup)
    
    print("Starting Jenkins Log Analyzer with Chunking Support...")
    print("Chunking mode enabled for large logs")
    
    app.run(debug=True, port=5004, host='0.0.0.0')
