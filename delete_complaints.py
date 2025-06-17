from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["eoxs_chatbot"]
collection = db["complaints"]

# Find and delete the first 10 complaints
complaints_to_delete = collection.find().limit(10)
for complaint in complaints_to_delete:
    collection.delete_one({"_id": complaint["_id"]})

print("Deleted first 10 complaints.")
