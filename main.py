from fastapi import FastAPI, Request, Response
import os

app = FastAPI()

# Make sure this matches what you type in Meta Portal
VERIFY_TOKEN = "hafiz_test_token_123"

@app.get("/")
async def root():
    return {"message": "Hafiz's WhatsApp API is Live!"}

@app.get("/webhook")
async def verify(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)

@app.post("/webhook")
async def handle_messages(request: Request):
    body = await request.json()
    print("📩 New Message Received!")
    print(body)
    return {"status": "ok"}

if __name__ == "__main__":
    # Render uses the PORT environment variable
    port = int(os.environ.get("PORT", 8000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)