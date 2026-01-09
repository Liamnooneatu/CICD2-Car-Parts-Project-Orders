from fastapi import FastAPI, HTTPException, status
import httpx
import os
from pydantic import BaseModel, Field

app = FastAPI(title="Service C - Orders API")

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://service_a:8000")

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
    """
    Create an order and synchronously call Service A (Parts service) to:
    - confirm the part exists
    - check stock
    - get current price
    """
    global next_id

    part_url = f"{SERVICE_A_BASE_URL}/api/parts/{payload.part_id}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(part_url)
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Parts service unavailable")

    if r.status_code == 404:
        raise HTTPException(status_code=400, detail="Part does not exist")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Unexpected response from Parts service")

    part = r.json()

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


