from pymongo import MongoClient
import json

client = MongoClient("mongodb://localhost:27017")
db = client["5e-database"]

classes = sorted([c["name"] for c in db["2014-classes"].find({}, {"_id": 0, "name": 1})])
selected_class = "Wizard"
#classes = sorted([c for c in db["2014-subclasses"].find({}, {"_id": 0, "name": 1})])
subclasses = [c["name"] for c in db["2014-subclasses"].find({"class.name":selected_class}, {"_id": 0})]

for s in subclasses:
	print(s)

client.close()