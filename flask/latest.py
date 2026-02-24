from flask import Flask, request, jsonify , render_template
from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import jenkins
import pymongo
from bson.objectid import ObjectId
from flask_cors import CORS
import os
from dotenv import load_dotenv
from send_email import EmailReport
import xml.etree.ElementTree as ET
import requests
from urllib.parse import quote_plus
app = Flask(__name__)
CORS(app)

load_dotenv()

# MongoDB setup with environment variables
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
    client = pymongo.MongoClient(
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
        client = pymongo.MongoClient("mongodb://localhost:27017/")
        client.server_info()
        print("Connected to local MongoDB as fallback.")
        db = client['jenkins']
        jobs_collection = db['jobs']
    except Exception as e2:
        print(f"Error connecting to local MongoDB: {e2}")
        raise Exception("Failed to connect to both remote and local MongoDB")
# Flask-Mail setup
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
mail = Mail(app)

# Scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# New AI Model API configuration
API_URL = "https://lama-3.project-user-private-cloud-ai.serving.pcai.r22n5640.lan/v1/chat/completions"
MODEL_NAME = "meta/llama-3.1-70b-instruct"
AUTH_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjFqZ3lUZXZ3ZE1KR05fYk9TODZCVGFoVFhYYTJhOGNUNWNKdjlVZ0U4LXcifQ.eyJhdWQiOlsiYXBpIiwiaXN0aW8tY2EiXSwiZXhwIjoxNzcyNzA2MzI2LCJpYXQiOjE3NjIzMzgzMjYsImlzcyI6Imh0dHBzOi8va3ViZXJuZXRlcy5kZWZhdWx0LnN2Yy5jbHVzdGVyLmxvY2FsIiwianRpIjoiMDIwNmM5ZDktMGZlMy00OTZhLWE0NDEtMDQyZDAyMWY5MDdjIiwia3ViZXJuZXRlcy5pbyI6eyJuYW1lc3BhY2UiOiJ1aSIsInNlcnZpY2VhY2NvdW50Ijp7Im5hbWUiOiJpc3ZjLWVwLTE3NjIzMzgzMjY0NDciLCJ1aWQiOiI0MDQzNjk2Mi1hNThmLTQ2NTktYmNlOC01NTJmYzUxZTFiZTkifX0sIm5iZiI6MTc2MjMzODMyNiwic3ViIjoic3lzdGVtOnNlcnZpY2VhY2NvdW50OnVpOmlzdmMtZXAtMTc2MjMzODMyNjQ0NyJ9.AbCDdnV4uZK_nfV_qpJM6obxEe8rxkzzPHxODXE_w6UahUjQ_5v7RDCG5crxNW8qx5Ocqul2bxv5ZhRU4THedJ2xWaHf7Djk2AnDJOVhBDvYabp4FYZFuL_KEYfYRWO0ZvmZqAj-f92zEOfSp08iuEUWe7f1IXhPbjaP7KB_or7XbPBLW_jJbZnrj1_T3ezaSb70vz8uxlyp4qQwM_UA26D6JoZgclA4d_GagUvJKhGCQJyll5uiuDYtemuAmAcCwYpSBCP399_DafjGS3PUrSzPyR_zs19dNrn5nNeEeRpU5EBcpLfCKRnXSu2U9zPC5hfEmC32aHVDZiN3_j0QZw"

SUMMARY_PROMPT = (
    "Summarize and Analyze the following Jenkins build log. "
    "Please provide me a detailed overview "
    "Highlight the build status, failures, and any key steps or errors:\n\n"
)

def summarize_with_ollama(text):
    """
    Function to summarize text using the new AI model API
    """
    import requests
    import json
    
    try:
        # For very large logs, truncate to reasonable size
        max_chars = 50000  # Adjust based on your model's context window
        if len(text) > max_chars:
            text = text[-max_chars:]  # Take the last part of the log
            
        prompt = SUMMARY_PROMPT + text
        
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
            "max_tokens": 512,
            "temperature": 0,
            "frequency_penalty": 0,
            "presence_penalty": 0.5
        }
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {AUTH_TOKEN}'
        }
        
        # Make request to the API
        response = requests.post(API_URL, headers=headers, json=payload, verify=False, timeout=600)
        response.raise_for_status()
        
        # Parse the response
        response_json = response.json()
        
        # Extract the content from choices
        if response_json.get('choices') and len(response_json['choices']) > 0:
            content = response_json['choices'][0]['message']['content']
            print(f"Model: {response_json.get('model')}")
            print(f"Total Tokens: {response_json.get('usage', {}).get('total_tokens')}")
            return content
        else:
            print("No choices found in response")
            print("Full response:", response.text)
            return "Error: No response generated by model"
        
    except requests.exceptions.RequestException as e:
        print(f"Network error calling API: {e}")
        return f"Error: Network error - {str(e)}"
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return f"Error: Invalid JSON response - {str(e)}"
    except Exception as e:
        print(f"Error calling API: {e}")
        return f"Error: Could not generate summary - {str(e)}"

# Utility functions
def send_email_notification(email, job_name):
    with app.app_context():
        msg = Message(f"Scheduled Jenkins Job: {job_name}",
                      recipients=[email],
                      body=f"The job '{job_name}' was scheduled to run.")
        mail.send(msg)

def schedule_job_execution(job_id, cron_expr):
    job = jobs_collection.find_one({'_id': ObjectId(job_id)})
    if not job:
        print(f"Job with ID {job_id} not found in DB.")
        return

    job_name = job.get('name')
    jenkins_url = job.get('url')
    jenkins_user = job.get('username')
    jenkins_token = job.get('password')
    email = job.get('email')
    
    def trigger_build():
        try:
            server = jenkins.Jenkins(jenkins_url, username=jenkins_user, password=jenkins_token)
            server.build_job(job_name)
            print(f"Triggered build for job: {job_name}")
            if email:
                send_email_notification(email, job_name)
            else:
                print(f"No email found for job: {job_name}, skipping notification.")
        except Exception as e:
            print(f"Failed to trigger Jenkins job '{job_name}': {e}")

    scheduler.add_job(
        func=trigger_build,
        trigger=CronTrigger.from_crontab(cron_expr),
        id=str(job_id),
        replace_existing=True
    )
    print(f"Scheduled Jenkins build for job '{job_name}' with cron: {cron_expr}")

def insert_job_if_not_exists(job):
    existing_job = jobs_collection.find_one({'name': job['name']})
    if existing_job:
        return jsonify({"message": "Job with this name already exists."}), 200
    jobs_collection.insert_one(job)
    return jsonify({"message": "Job inserted successfully."}), 201

def frequency_to_cron(freq):
    return {
        'hourly': '0 * * * *',      # Every hour at minute 0
        'daily': '0 9 * * *',       # Every day at 9 AM
        'weekly': '0 9 * * MON'     # Every Monday at 9 AM
    }.get(freq, None)

# Routes


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch-jobs', methods=['POST'])
def fetch_jobs():
    data = request.json
    url = data['url']
    username = data['username']
    password = data['password']
    email = data['email']
    
    try:
        server = jenkins.Jenkins(url, username=username, password=password)
        jobs = server.get_jobs()
        jobs_collection.delete_many({})
        
        for job in jobs:
            job_info = server.get_job_info(job['name'])
            jobs_collection.insert_one({
                "name": job['name'],
                "description": job_info.get('description', ''),
                "url": url,
                "username": username,
                "password": password,
                "email": email,
            })
        return jsonify({"message": "Jobs fetched and stored"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/jobs', methods=['GET'])
def get_jobs_api():
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
        
        return jsonify({
            'success': True,
            'jobs': formatted_jobs
        })
    except Exception as e:
        print(f"Error getting jobs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/jobs', methods=['POST'])
def add_job_api():
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['name', 'url', 'username', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Field {field} is required'
                }), 400
        
        # Check if job already exists
        existing_job = jobs_collection.find_one({'name': data['name']})
        if existing_job:
            return jsonify({
                'success': False,
                'error': 'Job with this name already exists'
            }), 400
        
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
        
        return jsonify({
            'success': True,
            'job_name': data['name'],
            'job_id': str(result.inserted_id)
        })
        
    except Exception as e:
        print(f"Error adding job: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/analyze', methods=['POST'])
def analyze_job_api():
    try:
        data = request.json
        job_id = data.get('job_id')
        
        if not job_id:
            return jsonify({
                'success': False,
                'error': 'Job ID is required'
            }), 400
        
        # Get the job from database
        job = jobs_collection.find_one({'_id': ObjectId(job_id)})
        if not job:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404
        
        # Use credentials from the job if not provided in the request
        jenkins_url = job['url']
        username = job['username']
        password = job['password']
        job_name = job['name']
        
        print(f"Analyzing job: {job_name}")
        
        # Connect to Jenkins
        server = jenkins.Jenkins(jenkins_url, username=username, password=password)
        
        # Get job info and validate
        job_info = server.get_job_info(job_name)
        if not job_info:
            return jsonify({
                'success': False,
                'error': f'Jenkins job "{job_name}" not found'
            }), 404
        
        if 'lastCompletedBuild' not in job_info or not job_info['lastCompletedBuild']:
            return jsonify({
                'success': False,
                'error': f'No completed builds found for job "{job_name}"'
            }), 404
        
        # Get the latest build
        last_build_number = job_info['lastCompletedBuild']['number']
        print(f"Analyzing build number: {last_build_number}")
        
        console_output = server.get_build_console_output(job_name, last_build_number)
        
        # Summarize using Ollama
        summary = summarize_with_ollama(console_output)
        
        # Save summary to file
        latest_summary_path = f"./logs/{job_name}_latest.txt"
        latest_summary_dir = os.path.dirname(latest_summary_path)
        os.makedirs(latest_summary_dir, exist_ok=True)
        
        with open(latest_summary_path, "w") as f:
            f.write(summary)
        
        return jsonify({
            'success': True,
            'response': summary,
            'job_name': job_name,
            'build_number': last_build_number
        })
        
    except jenkins.NotFoundException:
        return jsonify({
            'success': False,
            'error': 'Jenkins job or build not found'
        }), 404
    except Exception as e:
        print(f"Error analyzing job: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/jobs/<job_id>', methods=['PUT'])
def update_job(job_id):
    data = request.json
    description = data.get('description')
    
    job = jobs_collection.find_one({'_id': ObjectId(job_id)})
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    job_name = job['name']
    jenkins_url = job['url']
    jenkins_user = job['username']
    jenkins_token = job['password']

    try:
        server = jenkins.Jenkins(jenkins_url, username=jenkins_user, password=jenkins_token)
        config_xml = server.get_job_config(job_name)

        # Modify XML description
        root = ET.fromstring(config_xml)
        desc_node = root.find('description')
        if desc_node is not None:
            desc_node.text = description
        else:
            desc_node = ET.SubElement(root, 'description')
            desc_node.text = description

        updated_config_xml = ET.tostring(root, encoding='unicode')
        server.reconfig_job(job_name, updated_config_xml)

        # Update in DB
        jobs_collection.update_one({'_id': ObjectId(job_id)}, {'$set': {'description': description}})
        return jsonify({'message': f'Job "{job_name}" updated in DB and Jenkins.'}), 200

    except jenkins.JenkinsException as e:
        return jsonify({'error': str(e)}), 500

@app.route('/schedule-job/<job_id>', methods=['POST'])
def schedule_job(job_id):
    data = request.json
    cron_expr = data.get('cron')

    if not cron_expr:
        return jsonify({'error': 'Cron expression is required'}), 400

    try:
        schedule_job_execution(job_id, cron_expr)
        return jsonify({'message': 'Job scheduled successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save-job-info', methods=['POST'])
def save_job_info():
    data = request.json
    job = {
        'url': data['url'],
        'username': data['username'],
        'password': data['password'],
        'name': data['jobName'],
        'email': data['email']
    }
    insert_job_if_not_exists(job)
    return jsonify({'message': 'Job info saved successfully'})

@app.route('/job-latest-build/<job_id>', methods=['GET'])
def get_latest_build_summary(job_id):
    try:
        job = jobs_collection.find_one({'_id': ObjectId(job_id)})
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        jenkins_url = job['url']
        username = job['username']
        password = job['password']
        job_name = job['name']
        
        print(f"Processing job: {job_name}")
        
        server = jenkins.Jenkins(jenkins_url, username=username, password=password)
        
        # Get job info and check for builds
        job_info = server.get_job_info(job_name)
        if not job_info:
            return jsonify({'error': f'Jenkins job "{job_name}" not found.'}), 404

        if 'lastCompletedBuild' not in job_info or not job_info['lastCompletedBuild']:
            return jsonify({'error': f'No completed builds found for job "{job_name}".'}), 404

        last_build_number = job_info['lastCompletedBuild']['number']
        print(f"Last build number: {last_build_number}")
        
        console_output = server.get_build_console_output(job_name, last_build_number)

        # Summarize the console output using Ollama
        final_summary = summarize_with_ollama(console_output)

        # Save summary to file
        latest_summary_path = f"./logs/{job_name}_latest.txt"
        latest_summary_dir = os.path.dirname(latest_summary_path)
        os.makedirs(latest_summary_dir, exist_ok=True)
        
        with open(latest_summary_path, "w") as f:
            f.write(final_summary)

        return jsonify({
            "job_name": job_name,
            "build_number": last_build_number,
            "summary": final_summary
        })

    except jenkins.NotFoundException:
        return jsonify({"error": "Job or build number not found"}), 404
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/schedule-email/<job_id>', methods=['POST'])
def schedule_or_send_email(job_id):
    data = request.json
    frequency = data.get('frequency')  # e.g. 'daily', or None for immediate
    email = data.get('email')

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    job = jobs_collection.find_one({'_id': ObjectId(job_id)})
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    job_name = job['name']

    def generate_and_send_summary():
        try:
            # Always generate the latest summary before sending
            jenkins_url = job['url']
            username = job['username']
            password = job['password']
            
            server = jenkins.Jenkins(jenkins_url, username=username, password=password)
            job_info = server.get_job_info(job_name)
            
            if 'lastCompletedBuild' not in job_info or not job_info['lastCompletedBuild']:
                print(f'No completed builds found for job "{job_name}".')
                return
                
            last_build_number = job_info['lastCompletedBuild']['number']
            console_output = server.get_build_console_output(job_name, last_build_number)
            final_summary = summarize_with_ollama(console_output)
            
            latest_summary_path = f"./logs/{job_name}_latest.txt"
            latest_summary_dir = os.path.dirname(latest_summary_path)
            os.makedirs(latest_summary_dir, exist_ok=True)
            
            with open(latest_summary_path, "w") as f:
                f.write(final_summary)
                
            email_report = EmailReport()
            email_report.send_email(
                filename=latest_summary_path,
                subject=f"AI Log Analysis Report for Jenkins job: {job_name}",
                to_email=[email] if isinstance(email, str) else email
            )
            print(f"Email sent to {email} for job {job_name}")
            
        except Exception as e:
            print(f"Error in generate_and_send_summary: {e}")

    if frequency:
        cron_expr = frequency_to_cron(frequency)
        if not cron_expr:
            return jsonify({'error': 'Invalid frequency'}), 400
            
        scheduler.add_job(
            func=generate_and_send_summary,
            trigger=CronTrigger.from_crontab(cron_expr),
            id=f"email_{job_id}",
            replace_existing=True
        )
        return jsonify({'message': 'Email scheduled successfully'}), 200
    else:
        # Send immediately
        generate_and_send_summary()
        return jsonify({'message': f'Email sent to {email} for job {job_name}'}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5001,host = '0.0.0.0')