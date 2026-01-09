from fastapi import FastAPI
import httpx, os

app = FastAPI(title="Service B - Proxy API")
SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://localhost:8002")

@app.get("/api/proxy-greet")
def call_service_a(name: str = "world"):
    # Build the path-style URL for Service A
    url = f"{SERVICE_A_BASE_URL}/api/greet/{name}"
    with httpx.Client() as client:
        r = client.get(url) # no params= now
    return {"service_c": True, "service_a_response": r.json()}


