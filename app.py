
#https://kite-callback.onrender.com/
from flask import Flask, request
import hashlib
import requests
import os

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")

@app.route("/")
def home():
    return "Server running"

@app.route("/kite/postback", methods=["POST"])
def kite_postback():
    data = request.json
    print(data)
    return "OK"

@app.route("/kite/callback")
def kite_callback():
    request_token = request.args.get("request_token")

    if not request_token:
        return "No request token received"

    # Generate checksum
    data = API_KEY + request_token + API_SECRET
    checksum = hashlib.sha256(data.encode()).hexdigest()

    # Exchange for access_token
    url = "https://api.kite.trade/session/token"
    payload = {
        "api_key": API_KEY,
        "request_token": request_token,
        "checksum": checksum
    }

    response = requests.post(url, data=payload)
    data = response.json()

    access_token = data.get("access_token")

    return f"Access token generated successfully: {access_token}"
