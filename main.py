import os
import time
import httpx # മെറ്റാ എപിഐയിലേക്ക് അയക്കാൻ ഇത് ആവശ്യമാണ്
from fastapi import FastAPI, Request
from supabase import create_client, Client
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS സെറ്റിംഗ്സ്
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# സുപ്പബേസ് കണക്ഷൻ
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# മെറ്റാ വാട്സ്ആപ്പ് ക്രെഡൻഷ്യൽസ് (Render Env-ൽ സെറ്റ് ചെയ്യുക)
ACCESS_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")

@app.get("/")
def home():
    return {"message": "WhatsApp API is Live with Supabase!"}

# --- WEBHOOK: ഇൻകമിംഗ് മെസ്സേജുകൾ സ്വീകരിക്കാൻ ---
@app.post("/webhook")
async def handle_messages(request: Request):
    body = await request.json()
    try:
        if 'entry' in body:
            entry = body['entry'][0]
            restaurant_id = entry['id'] 
            changes = entry['changes'][0]['value']
            
            if 'messages' in changes:
                msg = changes['messages'][0]
                
                # സുപ്പബേസിലേക്ക് ഇൻകമിംഗ് മെസ്സേജ് സേവ് ചെയ്യുന്നു
                data = {
                    "restaurant_id": restaurant_id,
                    "customer_number": msg['from'],
                    "message_text": msg['text']['body'],
                    "is_outgoing": False
                }
                supabase.table("messages").insert(data).execute()
                print(f"✅ Incoming Saved: {msg['from']}")
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
    return {"status": "ok"}

# --- SEND: മെസ്സേജുകൾ അയക്കാൻ ---
@app.post("/send")
async def send_message(to_number: str, message_text: str, restaurant_id: str = "916110261462021"):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text}
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            # അയച്ച മെസ്സേജും ഹിസ്റ്ററിക്ക് വേണ്ടി സുപ്പബേസിൽ സേവ് ചെയ്യുന്നു
            data = {
                "restaurant_id": restaurant_id,
                "customer_number": to_number,
                "message_text": message_text,
                "is_outgoing": True # നമ്മൾ അയച്ചതുകൊണ്ട് True
            }
            supabase.table("messages").insert(data).execute()
            return {"status": "success", "data": response.json()}
        
    return {"status": "error", "message": response.text}

# --- GET: മെസ്സേജ് ഹിസ്റ്ററി എടുക്കാൻ ---
@app.get("/api/messages")
async def get_messages(restaurantId: str):
    # പഴയ മെസ്സേജുകൾ ആദ്യം വരുന്ന രീതിയിൽ സെലക്ട് ചെയ്യുന്നു (Order by created_at)
    response = supabase.table("messages")\
        .select("*")\
        .eq("restaurant_id", restaurantId)\
        .order("created_at", desc=False)\
        .execute()
    return {"data": response.data}