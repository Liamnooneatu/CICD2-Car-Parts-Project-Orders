from fastapi import FastAPI, HTTPException, status
import pybreaker
import httpx
import os
from pydantic import BaseModel, Field

app = FastAPI(title="Service C - Orders API")

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://service_a:8000")

PARTS_BASE_URL = os.getenv("PARTS_BASE_URL", "http://service_a:8000")

# Circuit breaker:
parts_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=20)


def fetch_part_from_parts_service(part_id: int) -> dict:
    """Synchronous call (simple + works great with pybreaker)."""
    url = f"{PARTS_BASE_URL}/api/parts/{part_id}"
   
    with httpx.Client(timeout=2.0) as client:
        r = client.get(url)

    if r.status_code == 404:
        raise HTTPException(status_code=400, detail="Part does not exist")
    if r.status_code >= 400:       
        raise RuntimeError(f"Parts service error: {r.status_code}")

    return r.json()


def get_part_with_circuit_breaker(part_id: int) -> dict:
    """
    If breaker is OPEN, return fallback immediately.
    If breaker is CLOSED/HALF-OPEN, attempt the real call.
    """
    try:
        return parts_breaker.call(fetch_part_from_parts_service, part_id)
    except pybreaker.CircuitBreakerError:      
        raise HTTPException(
            status_code=503,
            detail="Parts service temporarily unavailable (circuit breaker open). Try again shortly."
        )
    except HTTPException:      
        raise
    except Exception:       
        raise HTTPException(status_code=503, detail="Parts service unavailable")

class OrderCreate(BaseModel):
    user_id: int = Field(..., ge=1)
    part_id: int = Field(..., ge=1)
    quantity: int = Field(1, ge=1)

class OrderOut(BaseModel):
    order_id: int
    user_id: int
    part_id: int
    quantity: int
    unit_price: float
    total_price: float
    status: str

orders: list[OrderOut] = []
next_id = 1


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/orders", response_model=list[OrderOut])
def list_orders():
    return orders


@app.get("/api/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int):
    for o in orders:
        if o.order_id == order_id:
            return o
    raise HTTPException(status_code=404, detail="Order not found")


@app.post("/api/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate):
    global next_id
    
    part = get_part_with_circuit_breaker(payload.part_id)

    stock = part.get("stock")
    price = part.get("price")

    if stock is None or price is None:
        raise HTTPException(status_code=502, detail="Parts service returned invalid data")

    if payload.quantity > stock:
        raise HTTPException(status_code=400, detail=f"Not enough stock (available={stock})")

    order = OrderOut(
        order_id=next_id,
        user_id=payload.user_id,
        part_id=payload.part_id,
        quantity=payload.quantity,
        unit_price=float(price),
        total_price=float(price) * payload.quantity,
        status="created",
    )

    next_id += 1
    orders.append(order)
    return order


@app.delete("/api/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(order_id: int):
    for i, o in enumerate(orders):
        if o.order_id == order_id:
            orders.pop(i)
            return
    raise HTTPException(status_code=404, detail="Order not found")


