import os
import httpx
import logging
from fastapi import FastAPI, Request
from supabase import create_client, Client
from fastapi.middleware.cors import CORSMiddleware

# ലോക്സിൽ വിവരങ്ങൾ കാണാൻ വേണ്ടി
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- സുപ്പബേസ് കണക്ഷൻ പരിശോധന ---
logger.info("🚀 Starting Supabase Initialization...")
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    logger.error("❌ ERROR: SUPABASE_URL or SUPABASE_KEY is missing in Render Environment!")
    # ഇവിടെ ആപ്പ് ക്രാഷ് ആകാതിരിക്കാൻ തൽക്കാലം ഒരു ഡമ്മി വാല്യൂ നൽകാം (അല്ലെങ്കിൽ ഇത് എറർ കാണിക്കും)
    supabase = None
else:
    try:
        supabase: Client = create_client(url, key)
        logger.info("✅ Supabase Client initialized successfully!")
    except Exception as e:
        logger.error(f"❌ Supabase Connection Error: {e}")
        supabase = None

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