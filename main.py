import os
import httpx
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

# സുപ്പബേസ് കണക്ഷൻ (ഇത് മാറ്റരുത്)
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

@app.get("/")
def home():
    return {"message": "Multi-Restaurant WhatsApp ERP is Live!"}

# --- WEBHOOK: ഇൻകമിംഗ് മെസ്സേജുകൾ സ്വീകരിക്കാൻ ---
@app.post("/webhook")
async def handle_messages(request: Request):
    body = await request.json()
    try:
        if 'entry' in body:
            entry = body['entry'][0]
            restaurant_id = entry['id'] # Meta നൽകുന്ന ബിസിനസ് ഐഡി
            changes = entry['changes'][0]['value']
            
            if 'messages' in changes:
                msg = changes['messages'][0]
                
                # സുപ്പബേസിലേക്ക് ഇൻകമിംഗ് മെസ്സേജ് സേവ് ചെയ്യുന്നു
                data = {
                    "restaurant_id": str(restaurant_id),
                    "customer_number": msg['from'],
                    "message_text": msg['text']['body'],
                    "is_outgoing": False
                }
                supabase.table("messages").insert(data).execute()
                print(f"✅ Message received for Restaurant {restaurant_id}")
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
    return {"status": "ok"}

# --- SEND: മെസ്സേജുകൾ അയക്കാൻ (Multi-Token Support) ---
@app.post("/send")
async def send_message(to_number: str, message_text: str, restaurant_id: str):
    try:
        # 1. സുപ്പബേസിലെ 'restaurants' ടേബിളിൽ നിന്ന് ടോക്കൺ എടുക്കുന്നു
        res = supabase.table("restaurants").select("*").eq("id", restaurant_id).single().execute()
        
        if not res.data:
            return {"status": "error", "message": "Restaurant not found in database!"}

        token = res.data['whatsapp_token']
        phone_id = res.data['phone_number_id']

        # 2. Meta API വഴി മെസ്സേജ് അയക്കുന്നു
        meta_url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message_text}
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(meta_url, json=payload, headers=headers)
            
            if response.status_code == 200:
                # 3. അയച്ച മെസ്സേജും ഹിസ്റ്ററിയിലേക്ക് സേവ് ചെയ്യുന്നു
                data = {
                    "restaurant_id": restaurant_id,
                    "customer_number": to_number,
                    "message_text": message_text,
                    "is_outgoing": True
                }
                supabase.table("messages").insert(data).execute()
                return {"status": "success", "data": response.json()}
            else:
                return {"status": "error", "message": response.text}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- GET: മെസ്സേജ് ഹിസ്റ്ററി എടുക്കാൻ ---
@app.get("/api/messages")
async def get_messages(restaurantId: str):
    response = supabase.table("messages")\
        .select("*")\
        .eq("restaurant_id", restaurantId)\
        .order("created_at", desc=False)\
        .execute()
    return {"data": response.data}