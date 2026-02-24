"""
MongoDB configuration and models for Jenkins Log Analyzer
"""
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
import os
from dotenv import load_dotenv
from datetime import datetime
from bson import ObjectId
from urllib.parse import quote_plus

# Load environment variables
load_dotenv()

class DatabaseManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.jobs_collection = None
        self.initialize_db()
    
    def initialize_db(self):
        """Initialize MongoDB connection"""
        try:
            # Get MongoDB configuration from environment variables
            mongo_uri = os.getenv('MONGO_URI')
            
            # If MONGO_URI is not set, construct it from individual components
            if not mongo_uri:
                mongo_user = os.getenv('MONGO_USER', '')
                mongo_password = os.getenv('MONGO_PASSWORD', '')
                mongo_host = os.getenv('MONGO_HOST', 'localhost')
                mongo_port = os.getenv('MONGO_PORT', '27017')
                
                if mongo_user and mongo_password:
                    # URL encode the password to handle special characters
                    encoded_password = quote_plus(mongo_password)
                    mongo_uri = f"mongodb://{mongo_user}:{encoded_password}@{mongo_host}:{mongo_port}/"
                else:
                    mongo_uri = f"mongodb://{mongo_host}:{mongo_port}/"
            
            db_name = os.getenv('MONGO_DB_NAME', 'jenkins')
            
            # Create MongoDB client
            self.client = MongoClient(mongo_uri)
            
            # Test connection
            self.client.admin.command('ping')
            
            # Get database and collection
            self.db = self.client[db_name]
            self.jobs_collection = self.db.jobs
            
            # Create indexes for better performance
            self.jobs_collection.create_index([("job_name", 1)])
            self.jobs_collection.create_index([("is_active", 1)])
            
            print(f"[DB] Connected to MongoDB at {mongo_host}:{mongo_port}")
            print(f"[DB] Using database: {db_name}")
            
        except ConnectionFailure as e:
            print(f"[DB] Error connecting to MongoDB: {e}")
            raise
        except Exception as e:
            print(f"[DB] Error initializing database: {e}")
            raise
    
    def get_active_jobs(self):
        """Get all Jenkins jobs from MongoDB"""
        try:
            # Get all jobs (your jobs don't have is_active field)
            jobs_cursor = self.jobs_collection.find({}).sort("name", 1)
            
            job_list = []
            for job in jobs_cursor:
                # Use your actual field names: name, url, username, password, email, description
                job_list.append({
                    'id': str(job['_id']),  # Convert ObjectId to string
                    'job_name': job.get('name', ''),  # Your field is 'name'
                    'display_name': job.get('name', ''),  # Use name as display name
                    'description': job.get('description', '') or '',  # Handle None values
                    'jenkins_url': job.get('url', ''),  # Your field is 'url'
                    'username': job.get('username', ''),  # Available in your jobs
                    'password': job.get('password', ''),  # Available in your jobs
                    'email': job.get('email', '')  # Available in your jobs
                })
            
            return job_list
            
        except Exception as e:
            print(f"[DB] Error fetching jobs: {e}")
            return []
    
    def get_job_by_id(self, job_id):
        """Get specific job details by ID"""
        try:
            # Convert string ID to ObjectId
            if isinstance(job_id, str):
                job_id = ObjectId(job_id)
            
            job = self.jobs_collection.find_one({"_id": job_id})
            
            if job:
                return {
                    'id': str(job['_id']),
                    'job_name': job.get('name', ''),  # Your field is 'name'
                    'display_name': job.get('name', ''),  # Use name as display name
                    'description': job.get('description', '') or '',  # Handle None values
                    'jenkins_url': job.get('url', ''),  # Your field is 'url'
                    'username': job.get('username', ''),  # Available in your jobs
                    'password': job.get('password', ''),  # Available in your jobs
                    'email': job.get('email', '')  # Available in your jobs
                }
            return None
            
        except Exception as e:
            print(f"[DB] Error fetching job {job_id}: {e}")
            return None
    
    def insert_job(self, job_data):
        """Insert a new job into the database"""
        try:
            # Add timestamps
            job_data['created_at'] = datetime.utcnow()
            job_data['updated_at'] = datetime.utcnow()
            
            result = self.jobs_collection.insert_one(job_data)
            return str(result.inserted_id)
            
        except Exception as e:
            print(f"[DB] Error inserting job: {e}")
            return None
    
    def close_connection(self):
        """Close the MongoDB connection"""
        try:
            if self.client:
                self.client.close()
                print("[DB] MongoDB connection closed")
        except Exception as e:
            print(f"[DB] Error closing connection: {e}")

# Initialize database manager (will be imported by Flask app)
try:
    db_manager = DatabaseManager()
except Exception as e:
    print(f"[DB] Failed to initialize database: {e}")
    db_manager = None
