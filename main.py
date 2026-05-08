import os
# ⚠️ Render-ലെ proxy സെറ്റിംഗ്സ് സുപ്പബേസ് കണക്ഷനെ ബാധിക്കാതിരിക്കാൻ ഇത് നിർബന്ധമായും ചേർക്കുക
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
import httpx
import logging
from fastapi import FastAPI, Request
from supabase import create_client, Client
from fastapi.middleware.cors import CORSMiddleware

# ലോക്സ് സെറ്റ് ചെയ്യുന്നു - Render Logs-ൽ വിവരങ്ങൾ കാണാൻ ഇത് സഹായിക്കും
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()



# CORS സെറ്റിംഗ്സ് - ഫ്ലട്ടർ വെബ് ആപ്പിൽ നിന്ന് കണക്ട് ചെയ്യാൻ ഇത് ആവശ്യമാണ്
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- സുപ്പബേസ് കണക്ഷൻ ---
logger.info("🚀 Starting Supabase Initialization...")
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    logger.error("❌ ERROR: SUPABASE_URL or SUPABASE_KEY is missing in Render Environment!")
    supabase = None
else:
    try:
        # പ്രോക്സി പ്രശ്നം ഒഴിവാക്കിയ ശേഷം ക്ലയന്റ് ഉണ്ടാക്കുന്നു
        supabase: Client = create_client(url, key)
        logger.info("✅ Supabase Client initialized successfully!")
    except Exception as e:
        logger.error(f"❌ Supabase Connection Error: {e}")
        supabase = None

@app.get("/")
def home():
    return {"message": "Multi-Restaurant WhatsApp ERP is Live and Database Connected!"}

# --- WEBHOOK: മെറ്റാ വാട്സ്ആപ്പിൽ നിന്ന് മെസ്സേജുകൾ സ്വീകരിക്കാൻ ---
@app.post("/webhook")
async def handle_messages(request: Request):
    if not supabase:
        logger.error("❌ Webhook ignored: Supabase not connected")
        return {"status": "error", "message": "Database not connected"}

    body = await request.json()
    try:
        if 'entry' in body:
            for entry in body['entry']:
                restaurant_id = entry['id'] # Meta നൽകുന്ന ബിസിനസ് ഐഡി
                if 'changes' in entry:
                    for change in entry['changes']:
                        value = change['value']
                        if 'messages' in value:
                            for msg in value['messages']:
                                # സുപ്പബേസിലേക്ക് ഇൻകമിംഗ് മെസ്സേജ് സേവ് ചെയ്യുന്നു
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

# --- SEND: ഫ്ലട്ടർ ആപ്പിൽ നിന്ന് മെസ്സേജുകൾ അയക്കാൻ ---
@app.post("/send")
async def send_message(to_number: str, message_text: str, restaurant_id: str):
    if not supabase:
        return {"status": "error", "message": "Database not connected"}
        
    try:
        # 1. 'restaurants' ടേബിളിൽ നിന്ന് ആ റെസ്റ്റോറന്റിന്റെ ടോക്കൺ എടുക്കുന്നു
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
        logger.error(f"❌ Send Error: {e}")
        return {"status": "error", "message": str(e)}

# --- GET: ഫ്ലട്ടർ ആപ്പിലേക്ക് മെസ്സേജ് ലിസ്റ്റ് എടുക്കാൻ ---
@app.get("/api/messages")
async def get_messages(restaurantId: str):
    if not supabase:
        return {"data": []}
        
    try:
        response = supabase.table("messages")\
            .select("*")\
            .eq("restaurant_id", restaurantId)\
            .order("created_at", desc=False)\
            .execute()
        return {"data": response.data}
    except Exception as e:
        logger.error(f"❌ Fetch Error: {e}")
        return {"data": []}

@app.get("/")
def home():
    return {"message": "Multi-Restaurant WhatsApp ERP is Live!"}

# --- WEBHOOK ---
@app.post("/webhook")
async def handle_messages(request: Request):
    if not supabase:
        return {"status": "error", "message": "Database not connected"}
    
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
                    "message_text": msg['text']['body'],
                    "is_outgoing": False
                }
                supabase.table("messages").insert(data).execute()
                logger.info(f"✅ Message received for Restaurant {restaurant_id}")
    except Exception as e:
        logger.error(f"❌ Webhook Error: {e}")
    return {"status": "ok"}

# --- SEND ---
@app.post("/send")
async def send_message(to_number: str, message_text: str, restaurant_id: str):
    if not supabase:
        return {"status": "error", "message": "Database not connected"}
        
    try:
        res = supabase.table("restaurants").select("*").eq("id", restaurant_id).single().execute()
        
        if not res.data:
            return {"status": "error", "message": "Restaurant not found in database!"}

        token = res.data['whatsapp_token']
        phone_id = res.data['phone_number_id']

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

# --- GET MESSAGES ---
@app.get("/api/messages")
async def get_messages(restaurantId: str):
    if not supabase:
        return {"data": []}
        
    response = supabase.table("messages")\
        .select("*")\
        .eq("restaurant_id", restaurantId)\
        .order("created_at", desc=False)\
        .execute()
    return {"data": response.data}