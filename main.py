from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import random
import uuid

colors = ["Red", "Blue", "Green", "Yellow", "Purple", "Orange", "Black", "White", "Pink", "Gray"]
animals = ["Tiger", "Eagle", "Shark", "Wolf", "Panda", "Falcon", "Fox", "Dolphin", "Hawk", "Bear"]


app = FastAPI()

# Allow frontend to connect (adjust if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rooms = {}  # Store room data: {room_code: {"users": [], "options": [], "locked": False}}


@app.websocket("/ws/{room_code}")
async def websocket_endpoint(websocket: WebSocket, room_code: str):
    user_id = str(uuid.uuid4())
    await websocket.accept()
    
    if room_code not in rooms:
        rooms[room_code] = {"users": {}, "options": {}, "locked": False, "choice": None, "used_names": set()}
    
    room = rooms[room_code]

    client_ip = websocket.client.host  # Direct client IP
    forwarded_ip = websocket.headers.get("X-Forwarded-For")  # If behind a reverse proxy

    ip_address = forwarded_ip.split(",")[0] if forwarded_ip else client_ip

    def generate_unique_username():
        while True:
            name = f"{random.choice(colors)}_{random.choice(animals)}_{random.randint(100, 999)}"
            if name not in room["used_names"]:
                room["used_names"].add(name)
                return name

    room["users"][user_id] = {'socket': websocket, 'locked': False, 'ip_address': ip_address, 'name': generate_unique_username()}


    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action == "add_option" and not room["locked"]:
                option = data.get("option")
                option_uuid = str(uuid.uuid4())
                room["options"][option_uuid] = option
            elif action == "remove_option" and not room["locked"]:
                option_uuid = data.get("option_uuid")
                del room["options"][option_uuid]
            elif action == "lock" and not room["locked"]:
                isUserLocked = data.get('isLocked')
                room["users"][user_id]['locked'] = isUserLocked
                isRoomLocked = True
                for user in room["users"].values():
                    if not user['locked']:
                        isRoomLocked = False
                        break
                room["locked"] = isRoomLocked and len(room["options"]) > 0

                if room["locked"]:
                    chosen = random.choice(list(room["options"].values())) if room["options"] else None
                    room["choice"] = chosen
                
            for user in room["users"].values():
                await user['socket'].send_json({"action": "update", "options": room["options"], "locked": room["locked"], "connected_users": [user_values["name"] for user_values in room["users"].values()]})
                if room["locked"]: await user['socket'].send_json({"action": "result", "choice": room["choice"]})

    except WebSocketDisconnect:
        del room['users'][user_id]
        for user in room["users"].values():
            await user['socket'].send_json({"action": "update", "options": room["options"], "locked": room["locked"], "connected_users": [user_values["name"] for user_values in room["users"].values()]})
        if not room["users"]:
            del rooms[room_code]

