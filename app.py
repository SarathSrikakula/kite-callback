
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


@app.route("/love")
def love():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>For Kousthubha ❤️</title>
        <style>
            body {
                margin: 0;
                background: linear-gradient(to top right, #1a001a, #330033, #660066);
                overflow: hidden;
                font-family: 'Segoe UI', sans-serif;
                text-align: center;
                color: white;
            }

            h1 {
                margin-top: 15%;
                font-size: 60px;
                color: #ff66cc;
                animation: glow 2s infinite alternate;
            }

            @keyframes glow {
                from { text-shadow: 0 0 10px #ff99cc; }
                to { text-shadow: 0 0 40px #ff0066; }
            }

            #message {
                font-size: 28px;
                margin-top: 20px;
                height: 40px;
            }

            .heart {
                position: absolute;
                color: #ff4d88;
                font-size: 25px;
                animation: float 6s linear infinite;
            }

            @keyframes float {
                0% {
                    transform: translateY(100vh) scale(1);
                    opacity: 1;
                }
                100% {
                    transform: translateY(-10vh) scale(1.5);
                    opacity: 0;
                }
            }

            .sparkle {
                position: absolute;
                width: 5px;
                height: 5px;
                background: white;
                border-radius: 50%;
                animation: sparkle 3s infinite;
            }

            @keyframes sparkle {
                0% { opacity: 0; transform: scale(0); }
                50% { opacity: 1; transform: scale(1.5); }
                100% { opacity: 0; transform: scale(0); }
            }
        </style>
    </head>
    <body>

        <h1>❤️ Kousthubha ❤️</h1>
        <div id="message"></div>

        <script>
            // Typing animation
            const text = "You are my heart, my happiness, my forever 💕";
            let index = 0;

            function typeEffect() {
                if (index < text.length) {
                    document.getElementById("message").innerHTML += text.charAt(index);
                    index++;
                    setTimeout(typeEffect, 80);
                }
            }
            typeEffect();

            // Floating hearts
            function createHeart() {
                const heart = document.createElement("div");
                heart.className = "heart";
                heart.innerHTML = "❤️";
                heart.style.left = Math.random() * 100 + "vw";
                heart.style.animationDuration = (Math.random() * 3 + 3) + "s";
                document.body.appendChild(heart);

                setTimeout(() => {
                    heart.remove();
                }, 6000);
            }
            setInterval(createHeart, 300);

            // Sparkles
            function createSparkle() {
                const sparkle = document.createElement("div");
                sparkle.className = "sparkle";
                sparkle.style.left = Math.random() * 100 + "vw";
                sparkle.style.top = Math.random() * 100 + "vh";
                document.body.appendChild(sparkle);

                setTimeout(() => {
                    sparkle.remove();
                }, 3000);
            }
            setInterval(createSparkle, 200);
        </script>

    </body>
    </html>
    """
