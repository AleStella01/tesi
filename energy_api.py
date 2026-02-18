import os
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import requests
import json
from codecarbon import EmissionsTracker
from pymongo import MongoClient

# =========================
# CONFIG
# =========================

LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://127.0.0.1:8080")
LLAMA_API_KEY = os.getenv("LLAMA_API_KEY", "dummy-key")  # llama.cpp accetta qualsiasi valore
EMISSIONS_DIR = os.getenv("EMISSIONS_DIR", "./emissions")

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://127.0.0.1:27017/chatui")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "chatui")

mongo_client = MongoClient(MONGODB_URL)
mongo_db = mongo_client[MONGO_DB_NAME]

os.makedirs(EMISSIONS_DIR, exist_ok=True)

app = FastAPI(title="Energy API with CodeCarbon")


def llama_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLAMA_API_KEY}",
    }

def build_clean_messages(payload):
    messages = payload.get("messages", [])

    last_user = None
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = m
            break

    user_content = ""
    if last_user:
        user_content = normalize_content(last_user.get("content", "")).strip()

    return [
        {
            "role": "system",
            "content": "Rispondi in modo conciso e diretto."
        },
        {
            "role": "user",
            "content": user_content
        }
    ]

def normalize_content(content):
    #"""
    #Normalizza il contenuto dei messaggi per llama.cpp:
    #- garantisce una stringa
    #- rimuove wrapper tipo 'User message: "..."`
    #"""
    if content is None:
        return ""

    if not isinstance(content, str):
        return str(content)

    # Rimuove wrapper legacy di Chat UI
    if content.startswith("User message:"):
        content = content.replace("User message:", "", 1).strip()
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]

    return content.strip()

def build_messages_from_chatui(conversation_id: str) -> list[dict]:
    # 1) carica events
    events = list(
        mongo_db["messageEvents"].find(
            {"conversationId": conversation_id}
        ).sort("createdAt", 1)
    )

    messages: list[dict] = []
    for ev in events:
        # Struttura tipica: ev.role e ev.content (ma può variare)
        role = ev.get("role")
        content = ev.get("content")

        # Alcune build salvano sotto "message" o "data"
        if content is None:
            msg = ev.get("message") or ev.get("data") or {}
            role = role or msg.get("role")
            content = msg.get("content")

        if role and content:
            messages.append({"role": role, "content": str(content)})

    return messages

# =========================
# HEALTH / MODELS
# =========================

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "llamantino",
                "object": "model",
                "owned_by": "local",
            }
        ],
    }


# =========================
# CHAT COMPLETIONS
# =========================

@app.post("/chat/completions")
async def chat_completions(request: Request):
    payload = await request.json()

    # forza streaming
    payload["stream"] = True

    conv_id = request.headers.get("chatui-conversation-id") or ""
    print("CHATUI CONV ID:", conv_id)
    
    if conv_id:
        hist = build_messages_from_chatui(conv_id)
        if hist:
            payload["messages"] = hist
            print("REPLAYED HISTORY. NEW MESSAGE COUNT:", len(hist))
        else: 
            print("REPLAY: no events found for conv_id:", conv_id)
    else:
        print("REPLAY: conv_id empty (normal on first message)")
    
    print("HEADERS:", dict(request.headers))
    print("BODY KEYS", list(payload.keys()))
    print("FINAL MESSAGE COUNT:", len(payload.get("messages", [])))

    tracker = EmissionsTracker(
        output_dir="./emissions",
        tracking_mode="process",
        log_level="error",
    )

    def event_generator():
        tracker_started = False
        try:
            tracker.start()
            tracker_started = True

            with requests.post(
                f"{LLAMA_BASE_URL}/v1/chat/completions",
                json=payload,
                headers=llama_headers(),
                stream=True,
                timeout=None,
            ) as r:
                r.raise_for_status()

                for line in r.iter_lines():
                    if not line:
                        continue

                    decoded = line.decode("utf-8")

                    messages = payload.get("messages",[])

                    # tieni solo l'ultimo messaggio dell'utente
                    last_user = None
                    for m in reversed(messages):
                        if m.get("role") == "user":
                            last_user = m
                            break

                    if last_user is None:
                        last_user = {"role": "user", "content": ""}

                    messages = payload.get("messages", [])

                    last_user = None
                    for m in reversed(messages):
                        if m.get("role") == "user":
                            last_user = m
                            break

                    if last_user is not None:
                        user_content = normalize_content(last_user.get("content", "")).strip()
                    else:
                        user_content = ""

                    #payload["messages"] = build_clean_messages(payload)


                    if decoded.startswith("data:"):
                        yield decoded + "\n\n"

                        if decoded.strip() == "data: [DONE]":
                            break
                #print("FORWARDED PAYLOAD:\n", json.dumps(payload, indent=2, ensure_ascii=False))
                #print("CONTEXT CHECK")
                #print("MESSAGE COUNT:", len(payload.get("messages", [])))
                #print(json.dumps(payload.get("messages", []), indent=2, ensure_ascii=False)[:3000])
                #print("-----------------")
                for k in ["conversationsId", "conversations_id", "chatId", "chat_id", "id"]:
                    if k in payload:
                        print("FOUND", k, payload[k])

        except Exception as e:
            err = {
                "error": {
                    "message": str(e),
                    "type": "proxy_error",
                }
            }
            yield f"data: {json.dumps(err)}\n\n"

        finally:
            if tracker_started:
                tracker.stop()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
