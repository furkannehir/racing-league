from src.config.config import Config
from apscheduler.schedulers.background import BackgroundScheduler
import requests


scheduler = BackgroundScheduler()

def ping_frontend():
    """Ping the frontend URL"""
    frontend_url = Config.ORIGINS[0] if Config.ORIGINS else "http://localhost:5173"
    # Add your specific frontend ping endpoint
    ping_endpoint = f"{frontend_url}"  # Adjust this to your frontend's ping endpoint
    
    try:
        response = requests.get(ping_endpoint, timeout=5)
        print(f"Frontend ping successful: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Frontend ping failed: {str(e)}")

def start_scheduler():
    print("Starting scheduler to ping frontend every 30 seconds")
    scheduler.add_job(func=ping_frontend, trigger="interval", seconds=30)
    scheduler.start()


import atexit
atexit.register(lambda: scheduler.shutdown())