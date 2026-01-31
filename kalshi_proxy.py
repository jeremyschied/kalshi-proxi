import os
import base64
import time
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"

def get_credentials():
    """Read credentials fresh each time - fixes Railway env var timing issue"""
    api_key = os.environ.get("KALSHI_API_KEY", "")
    private_key_b64 = os.environ.get("KALSHI_PRIVATE_KEY", "")
    return api_key, private_key_b64

def sign_request(method: str, path: str, timestamp: str) -> str:
    """Sign the request using Ed25519"""
    _, private_key_b64 = get_credentials()

    if not private_key_b64:
        raise ValueError("KALSHI_PRIVATE_KEY environment variable not set")

    # Decode the base64-encoded private key
    private_key_pem = base64.b64decode(private_key_b64)
    private_key = load_pem_private_key(private_key_pem, password=None)

    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("Private key must be Ed25519")

    # Create the message to sign: timestamp + method + path
    message = f"{timestamp}{method}{path}".encode()
    signature = private_key.sign(message)

    return base64.b64encode(signature).decode()

def make_kalshi_request(method: str, endpoint: str, params: dict = None, data: dict = None):
    """Make an authenticated request to Kalshi API"""
    api_key, _ = get_credentials()

    if not api_key:
        raise ValueError("KALSHI_API_KEY environment variable not set")

    url = f"{KALSHI_API_BASE}{endpoint}"
    timestamp = str(int(time.time() * 1000))

    # Sign the request
    signature = sign_request(method, endpoint, timestamp)

    headers = {
        "KALSHI-ACCESS-KEY": api_key,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "Content-Type": "application/json"
    }

    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        params=params,
        json=data
    )

    return response

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    api_key, private_key_b64 = get_credentials()
    return jsonify({
        "status": "healthy",
        "has_api_key": bool(api_key),
        "has_private_key": bool(private_key_b64)
    })

@app.route("/balance", methods=["GET"])
def get_balance():
    """Get account balance"""
    try:
        response = make_kalshi_request("GET", "/portfolio/balance")
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/positions", methods=["GET"])
def get_positions():
    """Get current positions"""
    try:
        response = make_kalshi_request("GET", "/portfolio/positions")
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/markets/<ticker>", methods=["GET"])
def get_market(ticker: str):
    """Get market details"""
    try:
        response = make_kalshi_request("GET", f"/markets/{ticker}")
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/markets/<ticker>/orderbook", methods=["GET"])
def get_orderbook(ticker: str):
    """Get market orderbook"""
    try:
        response = make_kalshi_request("GET", f"/markets/{ticker}/orderbook")
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/orders", methods=["POST"])
def create_order():
    """Create a new order"""
    try:
        data = request.get_json()
        response = make_kalshi_request("POST", "/portfolio/orders", data=data)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/orders/<order_id>", methods=["DELETE"])
def cancel_order(order_id: str):
    """Cancel an order"""
    try:
        response = make_kalshi_request("DELETE", f"/portfolio/orders/{order_id}")
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/orders", methods=["GET"])
def get_orders():
    """Get all orders"""
    try:
        response = make_kalshi_request("GET", "/portfolio/orders")
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
