from flask import Flask, request

app = Flask(__name__)

@app.route("/")
def home():
    return "Kite callback server is running"

@app.route("/kite/callback")
def kite_callback():
    request_token = request.args.get("request_token")
    return f"Request token received: {request_token}"

if __name__ == "__main__":
    app.run()
