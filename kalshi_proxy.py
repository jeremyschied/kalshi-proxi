```python
from flask import Flask, request, jsonify
import requests
import os
from datetime import datetime

app = Flask(__name__)

# Kalshi API base URL
KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"

def get_kalshi_credentials():
    """Get Kalshi credentials fresh from environment variables each time."""
    email = os.environ.get("KALSHI_EMAIL")
    password = os.environ.get("KALSHI_PASSWORD")
    return email, password

def get_kalshi_token():
    """Get a fresh Kalshi API token using credentials from environment."""
    email, password = get_kalshi_credentials()

    if not email or not password:
        raise ValueError(f"Missing Kalshi credentials. KALSHI_EMAIL set: {bool(email)}, KALSHI_PASSWORD set: {bool(password)}")

    response = requests.post(
        f"{KALSHI_API_BASE}/login",
        json={"email": email, "password": password}
    )

    if response.status_code != 200:
        raise ValueError(f"Kalshi login failed: {response.status_code} - {response.text}")

    data = response.json()
    return data.get("token")

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    email, password = get_kalshi_credentials()
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "credentials_configured": bool(email and password)
    })

@app.route("/balance", methods=["GET"])
def get_balance():
    """Get Kalshi account balance."""
    try:
        token = get_kalshi_token()

        response = requests.get(
            f"{KALSHI_API_BASE}/portfolio/balance",
            headers={"Authorization": f"Bearer {token}"}
        )

        if response.status_code != 200:
            return jsonify({"error": f"Failed to get balance: {response.text}"}), response.status_code

        return jsonify(response.json())

    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/markets", methods=["GET"])
def get_markets():
    """Get available markets."""
    try:
        token = get_kalshi_token()

        # Get query parameters
        limit = request.args.get("limit", 20)
        cursor = request.args.get("cursor")
        status = request.args.get("status", "open")

        params = {"limit": limit, "status": status}
        if cursor:
            params["cursor"] = cursor

        response = requests.get(
            f"{KALSHI_API_BASE}/markets",
            headers={"Authorization": f"Bearer {token}"},
            params=params
        )

        if response.status_code != 200:
            return jsonify({"error": f"Failed to get markets: {response.text}"}), response.status_code

        return jsonify(response.json())

    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/market/<ticker>", methods=["GET"])
def get_market(ticker):
    """Get specific market details."""
    try:
        token = get_kalshi_token()

        response = requests.get(
            f"{KALSHI_API_BASE}/markets/{ticker}",
            headers={"Authorization": f"Bearer {token}"}
        )

        if response.status_code != 200:
            return jsonify({"error": f"Failed to get market: {response.text}"}), response.status_code

        return jsonify(response.json())

    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/orders", methods=["POST"])
def create_order():
    """Create a new order."""
    try:
        token = get_kalshi_token()

        order_data = request.json
        if not order_data:
            return jsonify({"error": "Order data required"}), 400

        response = requests.post(
            f"{KALSHI_API_BASE}/portfolio/orders",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=order_data
        )

        if response.status_code not in [200, 201]:
            return jsonify({"error": f"Failed to create order: {response.text}"}), response.status_code

        return jsonify(response.json())

    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/positions", methods=["GET"])
def get_positions():
    """Get current positions."""
    try:
        token = get_kalshi_token()

        response = requests.get(
            f"{KALSHI_API_BASE}/portfolio/positions",
            headers={"Authorization": f"Bearer {token}"}
        )

        if response.status_code != 200:
            return jsonify({"error": f"Failed to get positions: {response.text}"}), response.status_code

        return jsonify(response.json())

    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
