from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import jenkins
import pymongo
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
import sys
from dotenv import load_dotenv
from send_email import EmailReport
import time
import threading
import random
from datetime import datetime
from urllib.parse import quote_plus

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.llm_client import LLMClient, LLMClientConfig, LLMClientError, env_bool

# Load environment variables (prioritize .env.local for localhost)
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
    print("[CONFIG] Using .env.local for localhost MongoDB configuration")
else:
    load_dotenv()
    print("[CONFIG] Using .env for configuration")

# MongoDB setup with environment variables - simplified like app_simple.py
MONGO_USER = os.getenv("MONGO_USER", "sample")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "sample123")
MONGO_HOST = os.getenv("MONGO_HOST", "172.20.141.3")
MONGO_PORT = os.getenv("MONGO_PORT", "27018")
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

# LLM configuration (environment-based)
LLM_API_URL = os.getenv("LLM_API_URL", "")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "meta/llama-3.1-70b-instruct")
LLM_AUTH_TOKEN = os.getenv("LLM_AUTH_TOKEN", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_VERIFY_TLS = env_bool("LLM_VERIFY_TLS", True)

llm_client = LLMClient(
    LLMClientConfig(
        api_url=LLM_API_URL,
        auth_token=LLM_AUTH_TOKEN,
        default_model=LLM_MODEL_NAME,
        provider=LLM_PROVIDER,
        timeout_seconds=LLM_TIMEOUT_SECONDS,
        verify_tls=LLM_VERIFY_TLS,
        max_retries=LLM_MAX_RETRIES,
    )
)

if llm_client.is_configured():
    print(f"[CONFIG] LLM configured (provider={LLM_PROVIDER}, model={LLM_MODEL_NAME}, TLS verify={LLM_VERIFY_TLS})")
else:
    print("[CONFIG] LLM is not fully configured. For Ollama set LLM_PROVIDER=ollama, LLM_API_URL, LLM_MODEL_NAME.")

SUMMARY_PROMPT = (
    "Analyze the following Jenkins build log, with a focus on the pytest execution output. Identify and summarize:\n\n"
    "**Failed test cases** along with their names and file locations.\n\n"
    "**Selectors or locators** that caused the failures (e.g., CSS/XPath), and specify where in the code (file/function) they are defined or referenced, if visible.\n\n"
    "**Any tracebacks or error messages** related to element not found, timeout, or assertion errors.\n\n"
    "**Group the findings** to help testers quickly backtrack in the browser and debug.\n\n"
    "Format your response in a structured way that makes it easy for testers to understand what failed and where to look for fixes.\n\n"
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

TOKENS_PER_CHUNK = 60000  # Conservative limit to fit within 131k token context as the context window is 131072 tokens
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
    """Summarize a single chunk using shared LLM client"""
    # Check chunk size and truncate if necessary
    max_chunk_chars = 60000 * 4  # ~60k tokens worth of characters for safety
    if len(chunk) > max_chunk_chars:
        print(f"[AI] Chunk too large ({len(chunk)} chars), truncating to {max_chunk_chars} chars")
        chunk = chunk[-max_chunk_chars:]  # Take the end of the log which is usually most important
    
    if not llm_client.is_configured():
        return "[ERROR] LLM not configured. For Ollama set LLM_PROVIDER=ollama, LLM_API_URL, LLM_MODEL_NAME."

    prompt = SUMMARY_PROMPT + chunk
    
    try:
        print("[AI] Calling shared LLM client for chunk summary")
        content, usage = llm_client.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are a Jenkins build log analysis expert. Provide detailed, structured analysis of build logs.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            max_tokens=1024,
            temperature=0,
            frequency_penalty=0,
            presence_penalty=0.5,
        )
        print(f"[AI] ✅ Chunk processed successfully ({usage.get('total_tokens', 'unknown')} tokens)")
        return content
    except LLMClientError as e:
        return f"[ERROR] {str(e)}"
    except Exception as e:
        return f"[ERROR] Failed to summarize chunk: {str(e)}"

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
        
    except LLMClientError as e:
        return f"[AI ANALYSIS ERROR]: {str(e)}"
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
    return redirect('http://localhost:3000')

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

@app.route('/api/analyze-log', methods=['POST'])
def analyze_log_text():
    """Analyze raw log text directly (drag-and-drop / paste)"""
    try:
        # Support both JSON body and multipart file upload
        log_content = None
        filename = "uploaded_log"

        if request.content_type and 'multipart/form-data' in request.content_type:
            file = request.files.get('file')
            if file:
                log_content = file.read().decode('utf-8', errors='replace')
                filename = file.filename or filename
            else:
                return jsonify({'success': False, 'error': 'No file provided'}), 400
        else:
            data = request.get_json(silent=True) or {}
            log_content = data.get('log_text', '').strip()
            filename = data.get('filename', filename)

        if not log_content or len(log_content.strip()) < 50:
            return jsonify({'success': False, 'error': 'Log content is too short or empty. Please provide a meaningful Jenkins log.'}), 400

        print(f"[UPLOAD] Analyzing uploaded log: {filename} ({len(log_content)} chars)")

        analysis_result = safe_ai_request_with_retry(log_content)

        if analysis_result.startswith("[AI ANALYSIS ERROR]"):
            return jsonify({'success': False, 'error': f"AI analysis failed: {analysis_result}"}), 500

        return jsonify({
            'success': True,
            'response': analysis_result,
            'job_name': filename,
            'build_number': 'uploaded',
        })

    except Exception as e:
        print(f"Error analyzing uploaded log: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/email-log-report', methods=['POST'])
def email_log_report():
    """Analyze uploaded log text and email the report"""
    try:
        data = request.get_json(silent=True) or {}
        log_content = (data.get('log_text') or '').strip()
        email = (data.get('email') or '').strip()
        filename = data.get('filename', 'uploaded_log')

        if not email:
            return jsonify({'success': False, 'error': 'Email address is required'}), 400

        if not log_content or len(log_content) < 50:
            return jsonify({'success': False, 'error': 'Log content is too short or empty.'}), 400

        print(f"[EMAIL-LOG] Analyzing and emailing log: {filename} ({len(log_content)} chars) to {email}")

        analysis_result = safe_ai_request_with_retry(log_content)

        if analysis_result.startswith("[AI ANALYSIS ERROR]"):
            return jsonify({'success': False, 'error': f'AI analysis failed: {analysis_result}'}), 500

        # Send email with analysis
        analysis_data = {
            'analysis': analysis_result,
            'job_name': filename,
        }
        success = send_email_report(analysis_data, email, 'uploaded')

        return jsonify({
            'success': True,
            'message': f'Analysis report emailed to {email}' if success else 'Analysis complete but email delivery may be delayed.',
            'response': analysis_result,
            'job_name': filename,
            'build_number': 'uploaded',
        })

    except Exception as e:
        print(f"Error in email-log-report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat/support', methods=['POST'])
def support_chat():
    try:
        data = request.get_json(silent=True) or {}
        message = (data.get('message') or '').strip()
        context = data.get('context') or {}

        if not message:
            return jsonify({'success': False, 'error': 'Missing message'}), 400

        if not llm_client.is_configured():
            return jsonify({
                'success': False,
                'error': 'LLM not configured. For Ollama set LLM_PROVIDER=ollama, LLM_API_URL, and LLM_MODEL_NAME.'
            }), 500

        context_text = ""
        if isinstance(context, dict) and context:
            context_pairs = [f"{k}: {v}" for k, v in context.items()]
            context_text = "\n\nContext:\n" + "\n".join(context_pairs)

        user_prompt = f"User request:\n{message}{context_text}"

        content, usage = llm_client.chat_completion(
            messages=[
                {'role': 'system', 'content': SUPPORT_CHAT_SYSTEM_PROMPT},
                {'role': 'user', 'content': user_prompt}
            ],
            max_tokens=512,
            temperature=0.2,
            frequency_penalty=0,
            presence_penalty=0.1,
        )

        return jsonify({
            'success': True,
            'response': content,
            'usage': usage,
        }), 200

    except LLMClientError as e:
        return jsonify({'success': False, 'error': str(e)}), 502
    except Exception as e:
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

        job = None
        try:
            job = jobs_collection.find_one({'_id': ObjectId(job_id)})
        except Exception:
            pass  # job_id may not be a valid ObjectId

        # Accept direct Jenkins credentials from request
        jenkins_url = data.get('jenkins_url')
        username = data.get('username')
        password = data.get('password')
        job_name = data.get('job_name', '')

        if not job and all([jenkins_url, username, password, job_name]):
            # Auto-register the job for future use
            job_data = {
                'name': job_name,
                'url': jenkins_url,
                'username': username,
                'password': password,
                'email': email,
            }
            result = jobs_collection.insert_one(job_data)
            job_id = str(result.inserted_id)
            job = job_data
            job['_id'] = result.inserted_id
            print(f"[SCHEDULE] Auto-registered new job: {job_name} (ID: {job_id})")
        elif not job:
            return jsonify({'error': 'Job not found. Please provide Jenkins URL, username, password, and job name to register it.'}), 404

        job_name = job.get('name')
        jenkins_url = jenkins_url or job.get('url')
        username = username or job.get('username')
        password = password or job.get('password')

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

@app.route('/api/email-test', methods=['POST'])
def email_test():
    """Quick SMTP connectivity test — sends a tiny probe email."""
    try:
        data = request.get_json(silent=True) or {}
        to_email = (data.get('email') or '').strip()
        if not to_email:
            return jsonify({'success': False, 'error': 'Provide "email" in JSON body'}), 400

        smtp_server = os.getenv("SMTP_SERVER", "mxdns01.hpelabs.net")
        smtp_port = int(os.getenv("SMTP_PORT", "0"))
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes")
        use_tls = os.getenv("SMTP_USE_TLS", "false").lower() in ("1", "true", "yes")

        from email.mime.text import MIMEText
        msg = MIMEText("This is a test email from Jenkins Log Analyzer.\nIf you received this, SMTP is working!", "plain")
        msg["Subject"] = "Jenkins Log Analyzer — SMTP Test"
        msg["From"] = "projects@hpelabs.net"
        msg["To"] = to_email

        ports_to_try = [smtp_port] if smtp_port else [25, 587, 465]
        errors = []

        for port in ports_to_try:
            try:
                import smtplib
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
                return jsonify({
                    'success': True,
                    'message': f'Test email sent to {to_email} via {smtp_server}:{port}'
                }), 200
            except Exception as e:
                errors.append(f"{smtp_server}:{port} — {e}")

        return jsonify({
            'success': False,
            'error': 'All SMTP attempts failed',
            'details': errors,
            'config': {
                'SMTP_SERVER': smtp_server,
                'SMTP_PORT': smtp_port or 'auto',
                'SMTP_USE_TLS': use_tls,
                'SMTP_USE_SSL': use_ssl,
                'SMTP_USERNAME': smtp_username or '(none)',
            }
        }), 502

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
    
    app.run(debug=True, port=5005, host='0.0.0.0')
