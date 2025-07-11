from pymongo import MongoClient
from config import MONGO_URI

client = MongoClient(MONGO_URI)
db = client["AllVideosLink_Bot"]

users_collection = db["users"]
posts_collection = db["posts"]
