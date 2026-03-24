import os
import uuid
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client

app = FastAPI(title="SuperEye API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://bottrader-iota.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
ADMIN_SECRET = os.environ["ADMIN_SECRET"]

def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def require_admin(x_admin_secret: str = Header(...)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

# ── Models ─────────────────────────────────────────────────────────────────────

class ValidateTokenRequest(BaseModel):
    token: str

class StatusUpdateRequest(BaseModel):
    token: str
    balance: float
    session_profit: float
    pair: str
    grid_size: int
    cycle: int
    loss_streak: int
    is_running: bool
    campaign_goal: float = 0.0
    campaign_earned: float = 0.0

class IssueTokenRequest(BaseModel):
    username: str
    role: str = "user"
    expires_days: Optional[int] = None  # None = never expires

class RevokeTokenRequest(BaseModel):
    token_id: str

class SendCommandRequest(BaseModel):
    user_id: str
    command: str  # "stop" or "start"

# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/validate-token")
def validate_token(req: ValidateTokenRequest):
    db = get_db()
    result = db.table("tokens").select(
        "*, users(id, username)"
    ).eq("token_string", req.token).single().execute()

    if not result.data:
        return {"valid": False, "reason": "Token not found"}

    t = result.data

    if t["revoked"]:
        return {"valid": False, "reason": "Token has been revoked"}

    if t["expires_at"]:
        expires = datetime.fromisoformat(t["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires:
            return {"valid": False, "reason": "Token has expired"}

    # Check for pending command
    command_pending = None
    user_id = t["users"]["id"] if t.get("users") else None
    if user_id:
        cmd = db.table("commands").select("*").eq(
            "user_id", user_id
        ).eq("acknowledged", False).order(
            "issued_at", desc=True
        ).limit(1).execute()
        if cmd.data:
            command_pending = cmd.data[0]["command"]

        # Update last_seen
        db.table("users").update({
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "is_online": True
        }).eq("id", user_id).execute()

    return {
        "valid": True,
        "username": t["users"]["username"] if t.get("users") else t.get("username", ""),
        "role": t["role"],
        "user_id": user_id,
        "command_pending": command_pending,
    }


@app.post("/status-update")
def status_update(req: StatusUpdateRequest):
    db = get_db()

    # Validate token first
    token_row = db.table("tokens").select(
        "*, users(id)"
    ).eq("token_string", req.token).single().execute()

    if not token_row.data or token_row.data["revoked"]:
        return {"acknowledged": False, "reason": "Invalid token", "command": None}

    user_id = token_row.data["users"]["id"] if token_row.data.get("users") else None
    if not user_id:
        return {"acknowledged": False, "reason": "User not found", "command": None}

    # Upsert status
    status_blob = {
        "balance": req.balance,
        "session_profit": req.session_profit,
        "pair": req.pair,
        "grid_size": req.grid_size,
        "cycle": req.cycle,
        "loss_streak": req.loss_streak,
        "is_running": req.is_running,
        "campaign_goal": req.campaign_goal,
        "campaign_earned": req.campaign_earned,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    db.table("users").update({
        "last_status": status_blob,
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "is_online": req.is_running,
    }).eq("id", user_id).execute()

    # Check for pending command
    cmd_result = db.table("commands").select("*").eq(
        "user_id", user_id
    ).eq("acknowledged", False).order(
        "issued_at", desc=True
    ).limit(1).execute()

    command = None
    if cmd_result.data:
        command = cmd_result.data[0]["command"]
        # Acknowledge it
        db.table("commands").update({"acknowledged": True}).eq(
            "id", cmd_result.data[0]["id"]
        ).execute()

    return {"acknowledged": True, "command": command}


@app.post("/command/send", dependencies=[Depends(require_admin)])
def send_command(req: SendCommandRequest):
    db = get_db()
    db.table("commands").insert({
        "id": str(uuid.uuid4()),
        "user_id": req.user_id,
        "command": req.command,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "acknowledged": False,
    }).execute()
    return {"ok": True}


@app.post("/admin/issue-token", dependencies=[Depends(require_admin)])
def issue_token(req: IssueTokenRequest):
    db = get_db()
    token_string = f"se-{uuid.uuid4().hex[:24]}"
    token_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    expires_at = None
    if req.expires_days:
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=req.expires_days)
        ).isoformat()

    # Create user
    db.table("users").insert({
        "id": user_id,
        "username": req.username,
        "is_online": False,
        "last_seen": None,
        "last_status": None,
    }).execute()

    # Create token
    db.table("tokens").insert({
        "id": token_id,
        "token_string": token_string,
        "user_id": user_id,
        "role": req.role,
        "revoked": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at,
    }).execute()

    return {
        "token": token_string,
        "token_id": token_id,
        "user_id": user_id,
        "username": req.username,
        "role": req.role,
        "expires_at": expires_at,
    }


@app.post("/admin/revoke-token", dependencies=[Depends(require_admin)])
def revoke_token(req: RevokeTokenRequest):
    db = get_db()
    db.table("tokens").update({"revoked": True}).eq("id", req.token_id).execute()
    return {"ok": True}


@app.post("/admin/extend-token", dependencies=[Depends(require_admin)])
def extend_token(token_id: str, days: int):
    db = get_db()
    new_expiry = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    db.table("tokens").update({"expires_at": new_expiry}).eq("id", token_id).execute()
    return {"ok": True, "new_expiry": new_expiry}


@app.get("/dashboard/users", dependencies=[Depends(require_admin)])
def get_all_users():
    db = get_db()
    users = db.table("users").select("*, tokens(id, role, revoked, expires_at, created_at)").execute()
    return users.data


@app.get("/dashboard/me")
def get_me(x_token: str = Header(...)):
    db = get_db()
    token_row = db.table("tokens").select(
        "*, users(*)"
    ).eq("token_string", x_token).single().execute()
    if not token_row.data or token_row.data["revoked"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token_row.data["users"]
