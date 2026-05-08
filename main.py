import os

# ⚠️ ഏറ്റവും മുകളിൽ തന്നെ ഇത് നൽകണം (മറ്റ് ഇമ്പോർട്ടുകൾക്ക് മുൻപ്)
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

import httpx
import logging
from fastapi import FastAPI, Request
from supabase import create_client, Client
from fastapi.middleware.cors import CORSMiddleware

# ലോക്സ് സെറ്റ് ചെയ്യുന്നു
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
logger.info("🚀 Starting Supabase Initialization...")
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

try:
    supabase: Client = create_client(url, key)
    logger.info("✅ Supabase Client initialized successfully!")
except Exception as e:
    logger.error(f"❌ Supabase Connection Error: {e}")
    supabase = None

@app.get("/")
def home():
    return {"message": "Multi-Restaurant WhatsApp ERP is Live and Database Connected!"}

# --- WEBHOOK: ഇൻകമിംഗ് മെസ്സേജുകൾ സ്വീകരിക്കാൻ ---
@app.post("/webhook")
async def handle_messages(request: Request):
    if not supabase:
        logger.error("❌ Webhook ignored: Supabase not connected")
        return {"status": "error"}

    body = await request.json()
    try:
        if 'entry' in body:
            entry = body['entry'][0]
            restaurant_id = entry['id'] 
            changes = entry['changes'][0]['value']
            
            if 'messages' in changes:
                msg = changes['messages'][0]
                data = {
                    "restaurant_id": str(restaurant_id),
                    "customer_number": msg['from'],
                    "message_text": msg.get('text', {}).get('body', ''),
                    "is_outgoing": False
                }
                supabase.table("messages").insert(data).execute()
                logger.info(f"✅ Incoming message saved for {restaurant_id}")
    except Exception as e:
        logger.error(f"❌ Webhook Error: {e}")
    return {"status": "ok"}

# --- SEND: മെസ്സേജുകൾ അയക്കാൻ ---
@app.post("/send")
async def send_message(to_number: str, message_text: str, restaurant_id: str):
    if not supabase:
        return {"status": "error", "message": "Database not connected"}
        
    try:
        res = supabase.table("restaurants").select("*").eq("id", restaurant_id).single().execute()
        if not res.data:
            return {"status": "error", "message": "Restaurant not found"}

        token = res.data['whatsapp_token']
        phone_id = res.data['phone_number_id']

        meta_url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "messaging_product": "whatsapp", "to": to_number,
            "type": "text", "text": {"body": message_text}
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(meta_url, json=payload, headers=headers)
            if response.status_code == 200:
                data = {
                    "restaurant_id": restaurant_id,
                    "customer_number": to_number,
                    "message_text": message_text,
                    "is_outgoing": True
                }
                supabase.table("messages").insert(data).execute()
                return {"status": "success", "data": response.json()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- GET: മെസ്സേജുകൾ എടുക്കാൻ ---
@app.get("/api/messages")
async def get_messages(restaurantId: str):
    if not supabase: return {"data": []}
    response = supabase.table("messages").select("*").eq("restaurant_id", restaurantId).order("created_at").execute()
    return {"data": response.data}