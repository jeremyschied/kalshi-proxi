import os
import time
import base64
from datetime import datetime
from flask import Flask, request, jsonify, Response
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend

app = Flask(__name__)

# Configuration
KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_API_KEY = os.environ.get("KALSHI_API_KEY", "")
KALSHI_PRIVATE_KEY_PATH = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "kalshi_private_key.pem")

# Load private key at startup
_private_key = None

def get_private_key():
    """Load and cache the RSA private key."""
    global _private_key
    if _private_key is None:
        try:
            with open(KALSHI_PRIVATE_KEY_PATH, "rb") as key_file:
                _private_key = load_pem_private_key(
                    key_file.read(),
                    password=None,
                    backend=default_backend()
                )
            print(f"Successfully loaded private key from {KALSHI_PRIVATE_KEY_PATH}")
        except FileNotFoundError:
            print(f"ERROR: Private key file not found at {KALSHI_PRIVATE_KEY_PATH}")
            raise
        except Exception as e:
            print(f"ERROR: Failed to load private key: {e}")
            raise
    return _private_key


def sign_request(method: str, path: str, timestamp: str) -> str:
    """
    Sign a request using RSA-PSS with SHA256.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: API path (e.g., /trade-api/v2/exchange/status)
        timestamp: Unix timestamp in milliseconds as string
    
    Returns:
        Base64-encoded signature
    """
    # Build the message to sign: timestamp + method + path
    message = f"{timestamp}{method}{path}"
    message_bytes = message.encode("utf-8")
    
    # Sign using RSA-PSS with SHA256
    private_key = get_private_key()
    signature = private_key.sign(
        message_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    return base64.b64encode(signature).decode("utf-8")


def get_auth_headers(method: str, path: str) -> dict:
    """Generate authentication headers for a Kalshi API request."""
    timestamp = str(int(time.time() * 1000))
    signature = sign_request(method, path, timestamp)
    
    return {
        "KALSHI-ACCESS-KEY": KALSHI_API_KEY,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "api_key_configured": bool(KALSHI_API_KEY)
    })


@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy(path):
    """Proxy requests to Kalshi API with authentication."""
    # Build the full API path
    api_path = f"/trade-api/v2/{path}"
    full_url = f"{KALSHI_API_BASE.rstrip('/trade-api/v2')}{api_path}"
    
    # Get authentication headers
    headers = get_auth_headers(request.method, api_path)
    
    # Forward the request
    try:
        response = requests.request(
            method=request.method,
            url=full_url,
            headers=headers,
            json=request.get_json(silent=True) if request.data else None,
            params=request.args.to_dict() if request.args else None,
            timeout=30
        )
        
        # Return the response
        return Response(
            response.content,
            status=response.status_code,
            content_type=response.headers.get("Content-Type", "application/json")
        )
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Validate configuration
    if not KALSHI_API_KEY:
        print("WARNING: KALSHI_API_KEY environment variable not set")
    
    # Test loading the private key
    try:
        get_private_key()
    except Exception as e:
        print(f"WARNING: Could not load private key: {e}")
    
    # Run the server
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Kalshi proxy server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
