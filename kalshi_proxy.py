import os
import time
import base64
import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Kalshi Trading Proxy")

app.add_middleware( CORSMiddleware, allow_origins=[""], allow_credentials=True, allow_methods=[""], allow_headers=[""], )

KALSHI_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2" API_KEY_ID = os.environ.get("API_KEY_ID") PRIVATE_KEY_PEM = os.environ.get("PRIVATE_KEY")

def get_private_key(): if not PRIVATE_KEY_PEM: raise ValueError("PRIVATE_KEY environment variable not set") return serialization.load_pem_private_key( PRIVATE_KEY_PEM.encode(), password=None )

def sign_request(method: str, path: str, timestamp_ms: int) -> str: message = f"{timestamp_ms}{method}{path}".encode() private_key = get_private_key() signature = private_key.sign( message, padding.PSS( mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH ), hashes.SHA256() ) return base64.b64encode(signature).decode()

def kalshi_request(method: str, path: str, body: dict = None): timestamp_ms = int(time.time() * 1000) signature = sign_request(method, path, timestamp_ms)

headers = {
    "KALSHI-ACCESS-KEY": API_KEY_ID,
    "KALSHI-ACCESS-SIGNATURE": signature,
    "KALSHI-ACCESS-TIMESTAMP": str(timestamp_ms),
    "Content-Type": "application/json"
}

url = f"{KALSHI_BASE_URL}{path}"

with httpx.Client() as client:
    if method == "GET":
        response = client.get(url, headers=headers)
    elif method == "POST":
        response = client.post(url, headers=headers, json=body)
    elif method == "DELETE":
        response = client.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")

if response.status_code >= 400:
    raise HTTPException(status_code=response.status_code, detail=response.text)

return response.json()*

class OrderRequest(BaseModel): ticker: str side: str action: str count: int type: str = "market" yes_price: Optional[int] = None no_price: Optional[int] = None

@app.get("/health") def health_check(): return {"status": "healthy", "api_key_configured": bool(API_KEY_ID)}

@app.get("/balance") def get_balance(): return kalshi_request("GET", "/portfolio/balance")

@app.get("/positions") def get_positions(): return kalshi_request("GET", "/portfolio/positions")

@app.get("/orders") def get_orders(): return kalshi_request("GET", "/portfolio/orders")

@app.get("/markets/{ticker}") def get_market(ticker: str): return kalshi_request("GET", f"/markets/{ticker}")

@app.get("/markets") def list_markets(limit: int = 100, status: str = "open"): return kalshi_request("GET", f"/markets?limit={limit}&status={status}")

@app.get("/events/{event_ticker}") def get_event(event_ticker: str): return kalshi_request("GET", f"/events/{event_ticker}")

@app.post("/order") def place_order(order: OrderRequest): body = { "ticker": order.ticker, "side": order.side, "action": order.action, "count": order.count, "type": order.type } if order.type == "limit": if order.yes_price: body["yes_price"] = order.yes_price if order.no_price: body["no_price"] = order.no_price

return kalshi_request("POST", "/portfolio/orders", body)

@app.delete("/order/{order_id}") def cancel_order(order_id: str): return kalshi_request("DELETE", f"/portfolio/orders/{order_id}")

@app.get("/fills") def get_fills(): return kalshi_request("GET", "/portfolio/fills")

