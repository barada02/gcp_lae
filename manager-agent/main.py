import os
import json
from flask import Flask, request

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    # A simple health check to show it's alive
    return "Manager Agent is running.", 200

@app.route("/process", methods=["POST"])
def process_task():
    """
    This is the main endpoint that Cloud Tasks will call.
    """
    try:
        # 1. Get the job data from the Cloud Task
        file_data = request.get_json()

        print("---")
        print(f"✅ [Manager] Received job for file: {file_data.get('name')}")

        # 2. TODO: Call the 'Expert Agent' as a tool
        # (For now, we just pretend)
        print(f"🤖 [Manager] Dispatching to CSV Expert...")

        # 3. Respond with '200 OK'
        # This tells Cloud Tasks the job was received successfully.
        return "Job received and acknowledged.", 200

    except Exception as e:
        print(f"Error processing task: {e}")
        # Tell Cloud Tasks something went wrong so it can retry.
        return "Error processing", 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))