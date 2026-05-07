from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import httpx
import uvicorn

app = FastAPI()

# --- 1. CORS സെറ്റപ്പ് ---
# ഇത് നൽകിയാലേ നിങ്ങളുടെ HTML ഫയലിന് Render-ലേക്ക് ഡാറ്റ അയക്കാൻ അനുവാദം ലഭിക്കൂ
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. താൽക്കാലിക ഡാറ്റാബേസ് (List) ---
# സർവർ റൺ ചെയ്യുന്ന സമയം വരെ ഈ ലിസ്റ്റിൽ മെസ്സേജുകൾ സേവ് ആകും
db_messages = []

# --- 3. നിങ്ങളുടെ ക്രെഡൻഷ്യൽസ് ---
ACCESS_TOKEN = "EAAZCDxF91sjgBRWEpOGhN3LCvALjzaYVfE973mgaSaVKdDngJSpnqwkgqYJsBJLvdpS8PkdNB0y5TMe10tXZCOfktZCglraHr6EWziegYswhZBV4sB5pAeuycAzzVkJZAXfX6mzMWz2wjLnLTnh4sZChnpH7WPEZCZCscSrC6YCeQB2CBTaghYWcwshY0HfF6jsZAasUSFNrRTTpdpPoMMJCN09p3uNKpbRu7PWjSxgalbJgDbZABFHLg9lu66z9zVH14R9oE5ZAWzZAnmpgnaXf3B0dj9DHL8maA44vLmmGMxYZD"
PHONE_NUMBER_ID = "1104892906043582"
VERIFY_TOKEN = "hafiz_test_token_123"

@app.get("/")
async def root():
    return {"message": "Hafiz's Real-Time WhatsApp API is Live!"}

# --- 4. വെബ്ഹുക്ക് വെരിഫിക്കേഷൻ ---
@app.get("/webhook")
async def verify(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)

# --- 5. മെസ്സേജുകൾ സ്വീകരിക്കുകയും സേവ് ചെയ്യുകയും ചെയ്യുന്നു ---
@app.post("/webhook")
async def handle_messages(request: Request):
    body = await request.json()
    
    # Render ലോഗ്സിൽ മെസ്സേജ് പ്രിന്റ് ചെയ്യുന്നു
    print("📩 Incoming WhatsApp JSON:", body)

    try:
        if 'entry' in body and 'changes' in body['entry'][0]:
            value = body['entry'][0]['changes'][0]['value']
            
            # മെസ്സേജ് ഉണ്ടോ എന്ന് നോക്കുന്നു
            if 'messages' in value:
                msg_data = value['messages'][0]
                
                # നമുക്ക് ആവശ്യമായ വിവരങ്ങൾ മാത്രം എടുക്കുന്നു
                new_entry = {
                    "restaurantId": body['entry'][0]['id'], # Meta Business Account ID
                    "customerNumber": msg_data['from'],
                    "messageType": msg_data['type'],
                    "messageContent": msg_data,
                    "timestamp": msg_data['timestamp']
                }
                
                # ലിസ്റ്റിലേക്ക് സേവ് ചെയ്യുന്നു
                db_messages.append(new_entry)
                print(f"✅ Saved message from {msg_data['from']}")

    except Exception as e:
        print(f"❌ Error processing message: {e}")

    return {"status": "ok"}

# --- 6. ഡാഷ്‌ബോർഡിന് ഡാറ്റ നൽകാനുള്ള എൻഡ്‌പോയിന്റ് ---
# ഇത് ഉപയോഗിച്ചാണ് HTML ഫയൽ മെസ്സേജുകൾ എടുക്കുന്നത്
@app.get("/api/messages")
async def get_messages(restaurantId: str):
    # റെസ്റ്റോറന്റ് ഐഡി വെച്ച് ഫിൽറ്റർ ചെയ്യുന്നു
    filtered_messages = [m for m in db_messages if m['restaurantId'] == restaurantId]
    return {"data": filtered_messages}

# --- 7. മെസ്സേജ് അയക്കാനുള്ള എൻഡ്‌പോയിന്റ് ---
@app.post("/send")
async def send_whatsapp_message(to_number: str, message_text: str):
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
        response = await client.post(url, headers=headers, json=payload)
        return response.json()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)