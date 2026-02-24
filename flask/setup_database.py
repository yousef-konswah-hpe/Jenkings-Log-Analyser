#!/usr/bin/env python3
"""
MongoDB setup script for Jenkins Log Analyzer
Creates the required collections and optionally inserts sample data
"""
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager
from datetime import datetime

def setup_database():
    """Setup MongoDB collections and indexes"""
    try:
        db_manager = DatabaseManager()
        
        print("Setting up MongoDB collections and indexes...")
        
        # The indexes are already created in DatabaseManager.__init__()
        print("✅ Collections and indexes set up successfully!")
        
        return db_manager
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        return None

def show_current_jobs(db_manager):
    """Display current jobs in database"""
    try:
        jobs = db_manager.get_active_jobs()
        
        if jobs:
            print(f"\n📋 Current Jenkins Jobs in Database ({len(jobs)} jobs):")
            print("-" * 70)
            for job in jobs:
                print(f"ID: {job['id'][:8]}... | {job['display_name']}")
                print(f"      Job: {job['job_name']}")
                if job['description']:
                    print(f"      Desc: {job['description']}")
                print("-" * 70)
        else:
            print("\n📋 No jobs found in database")
            
    except Exception as e:
        print(f"❌ Error fetching jobs: {e}")

def show_database_info(db_manager):
    """Show database connection info"""
    try:
        # Get database stats
        stats = db_manager.db.command("dbstats")
        
        print(f"\n📊 MongoDB Database Info:")
        print(f"Database: {db_manager.db.name}")
        print(f"Collections: {len(db_manager.db.list_collection_names())}")
        print(f"Storage Size: {stats.get('storageSize', 0) / 1024:.2f} KB")
        
        # Show indexes
        indexes = list(db_manager.jobs_collection.list_indexes())
        print(f"Jobs Collection Indexes: {len(indexes)}")
        for idx in indexes:
            print(f"  - {idx['name']}: {idx.get('key', {})}")
            
    except Exception as e:
        print(f"❌ Error getting database info: {e}")

def debug_jobs_structure(db_manager):
    """Debug function to show the structure of jobs in the database"""
    try:
        print("\n🔍 Debug: Checking jobs collection structure...")
        
        # Get total count
        total_jobs = db_manager.jobs_collection.count_documents({})
        print(f"Total documents in 'jobs' collection: {total_jobs}")
        
        if total_jobs > 0:
            # Get first few jobs to see their structure
            sample_jobs = list(db_manager.jobs_collection.find({}).limit(3))
            
            print("\n📄 Sample job documents structure:")
            for i, job in enumerate(sample_jobs, 1):
                print(f"\nJob {i} fields:")
                for field, value in job.items():
                    if isinstance(value, str) and len(value) > 50:
                        print(f"  {field}: {value[:50]}...")
                    else:
                        print(f"  {field}: {value}")
        else:
            print("No documents found in 'jobs' collection")
            
    except Exception as e:
        print(f"❌ Error debugging jobs structure: {e}")

def main():
    print("🚀 Jenkins Log Analyzer - MongoDB Setup")
    print("=" * 50)
    
    # Check MongoDB configuration
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        mongo_user = os.getenv('MONGO_USER', '')
        mongo_host = os.getenv('MONGO_HOST', 'localhost')
        mongo_port = os.getenv('MONGO_PORT', '27017')
        if mongo_user:
            print(f"MongoDB Host: {mongo_host}:{mongo_port} (with authentication)")
        else:
            print(f"MongoDB Host: {mongo_host}:{mongo_port} (no authentication)")
    else:
        print(f"MongoDB URI: {mongo_uri}")
    
    db_name = os.getenv('MONGO_DB_NAME', 'jenkins')
    print(f"Database Name: {db_name}")
    print()
    
    # Setup database
    db_manager = setup_database()
    if not db_manager:
        print("❌ Database setup failed!")
        return
    
    # Show database info
    show_database_info(db_manager)
    
    # Debug: Show jobs structure
    debug_jobs_structure(db_manager)
    
    # Show current jobs (existing jobs from your database)
    show_current_jobs(db_manager)
    
    # Debug: Show jobs structure
    debug_jobs_structure(db_manager)
    
    print("\n🎉 MongoDB setup completed!")
    print("\nNext steps:")
    print("1. Start the AI agent: python3 model-server/ai_log_agent.py")
    print("2. Start the Flask app: python3 app.py")
    print("3. Open browser to: http://localhost:5000")
    
    print("\n📖 MongoDB Jobs Collection:")
    print("Your existing jobs are now available in the web interface dropdown!")
    print("The application will use jobs from the 'jobs' collection in your MongoDB database.")

if __name__ == '__main__':
    main()
