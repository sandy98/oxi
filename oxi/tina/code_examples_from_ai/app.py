import sqlite3
import json
import secrets
from contextvars import ContextVar
from context import current_session  # Import session ContextVar

def get_user():
    """ Returns user data """
    return json.dumps({"user": current_session.get()["user"]})

class TinApp:
    async def __call__(self, scope, receive, send):
        assert scope["type"] == "http"

        # Get session ID from cookies
        session_id = self.get_session_id(scope)
        session_data = await self.get_session(session_id)

        # Store session in ContextVar (isolated per request)
        token = current_session.set(session_data)

        # Process request and get response
        response_body = await self.route_handler(scope["path"])

        # Save updated session
        await self.save_session(session_id, current_session.get())

        # Reset ContextVar after request (cleanup)
        current_session.reset(token)

        # Send response
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({
            "type": "http.response.body",
            "body": response_body.encode(),
        })

    async def route_handler(self, path):
        """ Dispatches to the correct route """
        if path == "/getuser":
            return await get_user()
        return "Unknown route"

    def get_session_id(self, scope):
        """ Extracts session ID from cookies """
        headers = dict(scope["headers"])
        cookies = headers.get(b"cookie", b"").decode()
        cookies = {k.strip(): v.strip() for k, v in (c.split("=") for c in cookies.split(";") if "=" in c)}
        return cookies.get("session_id", secrets.token_hex(16))  # Generate new session if missing

    async def get_session(self, session_id):
        """ Retrieve session data from SQLite """
        conn = sqlite3.connect("sessions.db")
        cur = conn.cursor()
        cur.execute("SELECT data FROM sessions WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        conn.close()
        return json.loads(row[0]) if row else {"user": "guest"}

    async def save_session(self, session_id, data):
        """ Save session data to SQLite """
        conn = sqlite3.connect("sessions.db")
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO sessions (session_id, data) VALUES (?, ?) ON CONFLICT(session_id) DO UPDATE SET data=?",
            (session_id, json.dumps(data), json.dumps(data))
        )
        conn.commit()
        conn.close()

