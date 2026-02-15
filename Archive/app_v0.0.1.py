from flask import Flask, request, render_template_string
from pymongo import MongoClient
import os

app = Flask(__name__)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["5e-database"]

TEMPLATE = """
<h1>5e Database Search</h1>

<form method="get">
    Collection:
    <input name="collection" required>
    Name:
    <input name="name">
    <button>Search</button>
</form>

{% if results %}
<h2>Results</h2>
<pre>{{ results }}</pre>
{% endif %}
"""

@app.route("/", methods=["GET"])
def index():
    collection_name = request.args.get("collection")
    name = request.args.get("name")

    results = None

    if collection_name:
        collection = db[collection_name]
        query = {}
        if name:
            query["name"] = {"$regex": name, "$options": "i"}

        results = list(collection.find(query, {"_id": 0}).limit(10))

    return render_template_string(TEMPLATE, results=results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
