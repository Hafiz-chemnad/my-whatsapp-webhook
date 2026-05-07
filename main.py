from fastapi import FastAPI, Request, Response, HTTPException
import os
import httpx # Required for sending outgoing messages
import uvicorn

app = FastAPI()

# --- META CONFIGURATION ---
# Replace these with the actual values from your Meta Developer Portal
ACCESS_TOKEN = "EAAZCDxF91sjgBRdYJZC2m7ZCJqotWOnT1StqrQobmXlp5FM73lrdXo8aa2GJltCcACzqnmSgNMxvZAvsS5jj9DbglaQ1TfOdCkq0bWvIaDSZBBTFewpy6Xg1xmZA6CZAnTzQZA0Kg6kcZAcH8qb2NPQgIZBeucf4XHf9kbUkFzK9dEdPWawO1BtTpzV5XJMZBz0219ZBUkS3k5BGA9oVHZCvtSatZC8zp5XsSiiZBlranyYsi9cieeG7JsWDO4lOGaXlut5PhOtLoa7SeFGqqSWZAyZAhVbiihQjDadoKNuN8G8TydwZDZD"
PHONE_NUMBER_ID = "1104892906043582"
VERIFY_TOKEN = "hafiz_test_token_123"

@app.get("/")
async def root():
    return {"message": "Hafiz's WhatsApp API is Live and Connected!"}

# ==========================================
# 1. WEBHOOK VERIFICATION (GET)
# ==========================================
@app.get("/webhook")
async def verify(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook Verified Successfully!")
        return Response(content=challenge, media_type="text/plain")
    
    return Response(status_code=403)

# ==========================================
# 2. RECEIVE MESSAGES (POST)
# ==========================================
@app.post("/webhook")
async def handle_messages(request: Request):
    body = await request.json()
    
    # This prints the incoming message to your Render logs
    print("📩 Incoming WhatsApp JSON:")
    print(body)
    
    return {"status": "ok"}

# ==========================================
# 3. SEND MESSAGE ENDPOINT (POST)
# ==========================================
@app.post("/send")
async def send_whatsapp_message(to_number: str, message_text: str):
    """
    Sends a WhatsApp message to a specific number.
    'to_number' should include country code (e.g., 919876543210)
    """
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text}
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            result = response.json()
            
            if response.status_code == 200:
                return {"status": "success", "response": result}
            else:
                return {"status": "error", "details": result}
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)