from pymongo import MongoClient
from src.config.config import Config

# Get MongoDB URI from environment variables

# Connect to MongoDB
client = MongoClient(Config.MONGO_URI)
db = client['racing_league']

# Example function to get the database object if needed elsewhere
def get_db():
    return db
