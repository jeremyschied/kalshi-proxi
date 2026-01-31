import base64
import hashlib
import os
import time
from datetime import datetime
from typing import Optional

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Kalshi Proxy Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration from environment variables
KALSHI_API_KEY = os.environ.get("KALSHI_API_KEY", "")
KALSHI_PRIVATE_KEY = os.environ.get("KALSHI_PRIVATE_KEY", "")
KALSHI_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


def load_private_key():
    """Load the RSA private key from environment variable."""
    key = os.environ.get("KALSHI_PRIVATE_KEY", "")
    if not key:
        raise ValueError("KALSHI_PRIVATE_KEY environment variable not set")
    
    # Handle escaped newlines in environment variable
    key_data = key.replace("\\n", "\n")
    
    private_key = serialization.load_pem_private_key(
        key_data.encode(),
        password=None,
        backend=default_backend()
    )
    return private_key


def sign_request(method: str, path: str, timestamp: int) -> str:
    """
    Sign a request using RSA-SHA256.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: API path (e.g., /trade-api/v2/portfolio/balance)
        timestamp: Unix timestamp in milliseconds
    
    Returns:
        Base64-encoded signature
    """
    private_key = load_private_key()
    
    # Create the message to sign: timestamp + method + path
    message = f"{timestamp}{method}{path}"
    
    # Sign using RSA with SHA256
    signature = private_key.sign(
        message.encode(),
        padding.PKCS1v15(),
        hashlib.sha256()
    )
    
    return base64.b64encode(signature).decode()


def get_auth_headers(method: str, path: str) -> dict:
    """Generate authentication headers for Kalshi API."""
    timestamp = int(time.time() * 1000)  # Milliseconds
    signature = sign_request(method, path, timestamp)
    
    return {
        "KALSHI-ACCESS-KEY": KALSHI_API_KEY,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": str(timestamp),
        "Content-Type": "application/json",
    }


# Response models
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    kalshi_api_key_configured: bool
    kalshi_private_key_configured: bool


class BalanceResponse(BaseModel):
    balance: int
    available_balance: Optional[int] = None


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        kalshi_api_key_configured=bool(KALSHI_API_KEY),
        kalshi_private_key_configured=bool(KALSHI_PRIVATE_KEY),
    )


@app.get("/balance")
async def get_balance():
    """Get account balance from Kalshi."""
    path = "/trade-api/v2/portfolio/balance"
    headers = get_auth_headers("GET", path)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{KALSHI_BASE_URL}/portfolio/balance",
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Kalshi API error: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting to Kalshi: {str(e)}"
            )


@app.get("/markets")
async def get_markets(
    limit: int = 100,
    cursor: Optional[str] = None,
    event_ticker: Optional[str] = None,
    series_ticker: Optional[str] = None,
    status: Optional[str] = None,
):
    """Get markets from Kalshi."""
    path = "/trade-api/v2/markets"
    headers = get_auth_headers("GET", path)
    
    params = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    if event_ticker:
        params["event_ticker"] = event_ticker
    if series_ticker:
        params["series_ticker"] = series_ticker
    if status:
        params["status"] = status
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{KALSHI_BASE_URL}/markets",
                headers=headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Kalshi API error: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting to Kalshi: {str(e)}"
            )


@app.get("/markets/{ticker}")
async def get_market(ticker: str):
    """Get a specific market by ticker."""
    path = f"/trade-api/v2/markets/{ticker}"
    headers = get_auth_headers("GET", path)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{KALSHI_BASE_URL}/markets/{ticker}",
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Kalshi API error: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting to Kalshi: {str(e)}"
            )


class OrderRequest(BaseModel):
    ticker: str
    side: str  # "yes" or "no"
    action: str  # "buy" or "sell"
    count: int
    type: str = "limit"  # "limit" or "market"
    yes_price: Optional[int] = None  # Price in cents (1-99)
    no_price: Optional[int] = None
    expiration_ts: Optional[int] = None
    client_order_id: Optional[str] = None


@app.post("/orders")
async def create_order(order: OrderRequest):
    """Create a new order on Kalshi."""
    path = "/trade-api/v2/portfolio/orders"
    headers = get_auth_headers("POST", path)
    
    body = {
        "ticker": order.ticker,
        "side": order.side,
        "action": order.action,
        "count": order.count,
        "type": order.type,
    }
    
    if order.yes_price is not None:
        body["yes_price"] = order.yes_price
    if order.no_price is not None:
        body["no_price"] = order.no_price
    if order.expiration_ts is not None:
        body["expiration_ts"] = order.expiration_ts
    if order.client_order_id:
        body["client_order_id"] = order.client_order_id
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{KALSHI_BASE_URL}/portfolio/orders",
                headers=headers,
                json=body,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Kalshi API error: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting to Kalshi: {str(e)}"
            )


@app.get("/positions")
async def get_positions(
    limit: int = 100,
    cursor: Optional[str] = None,
    settlement_status: Optional[str] = None,
    ticker: Optional[str] = None,
):
    """Get current positions."""
    path = "/trade-api/v2/portfolio/positions"
    headers = get_auth_headers("GET", path)
    
    params = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    if settlement_status:
        params["settlement_status"] = settlement_status
    if ticker:
        params["ticker"] = ticker
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{KALSHI_BASE_URL}/portfolio/positions",
                headers=headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Kalshi API error: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting to Kalshi: {str(e)}"
            )


@app.get("/orders")
async def get_orders(
    limit: int = 100,
    cursor: Optional[str] = None,
    ticker: Optional[str] = None,
    status: Optional[str] = None,
):
    """Get orders."""
    path = "/trade-api/v2/portfolio/orders"
    headers = get_auth_headers("GET", path)
    
    params = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    if ticker:
        params["ticker"] = ticker
    if status:
        params["status"] = status
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{KALSHI_BASE_URL}/portfolio/orders",
                headers=headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Kalshi API error: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting to Kalshi: {str(e)}"
            )


@app.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    """Cancel an order."""
    path = f"/trade-api/v2/portfolio/orders/{order_id}"
    headers = get_auth_headers("DELETE", path)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(
                f"{KALSHI_BASE_URL}/portfolio/orders/{order_id}",
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Kalshi API error: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error connecting to Kalshi: {str(e)}"
            )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
