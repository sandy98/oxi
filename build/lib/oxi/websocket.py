#-*- coding: utf_8  -*-

import typing, json, asyncio
from time import time, strftime
from uuid import uuid4
from . import __version__ as oxi_version

oxi_version

CONNECTING = 0
CONNECTED = 1
DISCONNECTED = 2
RESPONSE = 3

class WSDisconnection(Exception):
    def __init__(self, code: int = 1000, reason= None) -> None:
        self.code = code
        self.reason = reason or ""

class WebSocket:
    """Server side counterpart of the client WebSocket object"""

    def __init__(self, scope: dict, receive: typing.Callable, send: typing.Callable, *, heartbeat_rate = 6):
        assert scope.get("type") == "websocket"
        self._scope = scope
        self._receive = receive
        self._send = send
        self._heartbeat_rate  = heartbeat_rate
        self._pings_sent = 0
        self._ping_time = 0
        self._pong_time = 0
        self._pings = {}
        self._pongs = {}
        self._roundtrips = {}
        self.client_state = CONNECTING
        self.application_state = CONNECTING

    async def start_heartbeat(self):
        async def do_heartbeating(interval: int):
            while True:
                try:
                    await asyncio.sleep(interval)
                    await self.send_ping()
                    if self.application_state != CONNECTED:
                        break
                    if self.client_state != CONNECTED:
                        break
                except:
                    await self.close()
                    break

        heartbeat_interval = 60 // self._heartbeat_rate
        await do_heartbeating(heartbeat_interval)

    async def receive(self) -> dict:
        """
        Receive ASGI websocket messages.
        """
        if self.client_state == CONNECTING:
            message = await self._receive()
            message_type = message.get("type")
            if message_type != "websocket.connect":
                raise RuntimeError(
                    'Expected ASGI message "websocket.connect", '
                    f"but got {message_type!r}"
                )
            self.client_state = CONNECTED
            return message
        elif self.client_state == CONNECTED:
            message = await self._receive()
            message_type = message.get("type", "websocket.receive")
            if message_type not in {"websocket.receive", "websocket.disconnect", "websocket.ping", "websocket.pong"}:
                raise RuntimeError(
                    'Expected ASGI message "websocket.receive" or '
                    f'"websocket.disconnect" or "websocket.ping" or "websocket.pong", but got {message_type!r}'
                )
            if message_type == "websocket.disconnect":
                self.client_state = DISCONNECTED
            elif message_type == "websocket.ping":
                await self.send_pong(message)
            elif message_type =="websocket.pong":
                payload = message.get('bytes').decode('utf_8')
                if payload in self._pings.keys():
                    start_time = self._pings.get(payload)
                    end_time = time()
                    self._pongs[payload] = end_time
                    roundtrip_time = end_time - start_time
                    self._roundtrips[payload] = roundtrip_time
                    print(f"Roundtrip time for ping-pong '{payload}' is: {roundtrip_time} secs.") 
            return message
        else:
            raise RuntimeError(
                'Cannot call "receive" once a disconnect message has been received.'
            )

    async def send(self, message: dict) -> None:
        """
        Send ASGI websocket messages, ensuring valid state transitions.
        """
        if self.application_state == CONNECTING:
            message_type = message.get("type")
            if message_type not in {
                "websocket.accept",
                "websocket.close",
                "websocket.http.response.start",
            }:
                raise RuntimeError(
                    'Expected ASGI message "websocket.accept",'
                    '"websocket.close" or "websocket.http.response.start",'
                    f"but got {message_type!r}"
                )
            if message_type == "websocket.close":
                self.application_state = DISCONNECTED
            elif message_type == "websocket.http.response.start":
                self.application_state = RESPONSE
            else:
                self.application_state = CONNECTED
                # await self.start_heartbeat()
            await self._send(message)
        elif self.application_state == CONNECTED:
            message_type = message.get("type")
            if message_type not in {"websocket.send", "websocket.close", "websocket.ping", "websocket.pong"}:
                raise RuntimeError(
                    'Expected ASGI message "websocket.send" or "websocket.close" or "websocket.ping" or "websocket.pong"'
                    f"but got {message_type!r}"
                )
            if message_type == "websocket.close":
                self.application_state = DISCONNECTED
            try:
                await self._send(message)
            except OSError:
                self.application_state = DISCONNECTED
                raise WSDisconnection(code=1006)
            except Exception as exc:
                self.application_state = DISCONNECTED
                print(f"Exception inf {__file__}, line 115: {repr(exc)}")
        elif self.application_state == RESPONSE:
            message_type = message["type"]
            if message_type != "websocket.http.response.body":
                raise RuntimeError(
                    'Expected ASGI message "websocket.http.response.body", '
                    f"but got {message_type!r}"
                )
            if not message.get("more_body", False):
                self.application_state = DISCONNECTED
            await self._send(message)
        else:
            print(f"""{RuntimeError('Cannot call "send" once a close message has been sent.')}""")
            raise RuntimeError('Cannot call "send" once a close message has been sent.')

    async def accept(
        self,
        subprotocol= None,
        # headers: typing.Iterable[tuple[bytes, bytes]] | None = None,
        headers = None,
    ) -> None:
        headers = headers or []

        if self.client_state == CONNECTING:
            # If we haven't yet seen the 'connect' message, then wait for it first.
            recvd = await self.receive()
            print(f"Received: {repr(recvd)}")
        await self.send(
            {"type": "websocket.accept", "subprotocol": subprotocol, "headers": headers}
        )
        try:
            asyncio.create_task(self.start_heartbeat())
        except Exception as exc:
            print(f"Exception {exc} happened in heartbeat coroutine.")

    def raise_disconnection(self, message: dict) -> None:
        message_type = message.get("type")
        if not message_type:
            return
        if message_type == "websocket.disconnect":
            # self.application_state = DISCONNECTED
            raise WSDisconnection(message.get("code", 1000), message.get("reason", ''))

    async def receive_text(self) -> str:
        if self.application_state != CONNECTED:
            raise RuntimeError(
                'WebSocket is not connected. Need to call "accept" first.'
            )
        message = await self.receive()
        msg_type = message.get("type")
        if msg_type== "websocket.ping" or msg_type == "websocket.pong":
            return ''
        self.raise_disconnection(message)
        # if self.application_state == DISCONNECTED:
        #     return ''
        return typing.cast(str, message.get("text"))

    async def receive_bytes(self) -> bytes:
        if self.application_state != CONNECTED:
            raise RuntimeError(
                'WebSocket is not connected. Need to call "accept" first.'
            )
        message = await self.receive()
        msg_type = message.get("type")
        if msg_type== "websocket.ping" or msg_type == "websocket.pong":
            return b''
        self.raise_disconnection(message)
        return typing.cast(bytes, message.get("bytes"))

    async def receive_json(self, mode: str = "text") -> typing.Any:
        if mode not in {"text", "binary"}:
            raise RuntimeError('The "mode" argument should be "text" or "binary".')
        if self.application_state != CONNECTED:
            raise RuntimeError(
                'WebSocket is not connected. Need to call "accept" first.'
            )
        message = await self.receive()
        msg_type = message.get("type")
        if msg_type== "websocket.ping" or msg_type == "websocket.pong":
            return {}

        self.raise_disconnection(message)
        if not hasattr(message, 'get'):
            return
        keys = message.keys()
        if 'bytes' in keys:
            text = message.get('bytes', b'').decode('utf_8')
        elif 'text' in keys:
            text = message.get('text', '')
        else:
            return
        
        try:
            jsontxt = json.loads(text)
        except:
            jsontxt = ''
        return jsontxt

    async def send_text(self, data: str) -> None:
        await self.send({"type": "websocket.send", "text": data})

    async def send_bytes(self, data: bytes) -> None:
        await self.send({"type": "websocket.send", "bytes": data})

    async def send_json(self, data: typing.Any, mode: str = "text") -> None:
        if mode not in {"text", "binary"}:
            raise RuntimeError('The "mode" argument should be "text" or "binary".')
        text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        if mode == "text":
            await self.send({"type": "websocket.send", "text": text})
        else:
            await self.send({"type": "websocket.send", "bytes": text.encode("utf_8")})

    async def send_ping(self):
        # await asyncio.sleep(0.1)
        if not self._pings_sent:
            print("\nStarting hearbeat.")
            print()
        self._pings_sent += 1
        self._ping_time = time()
        payload = uuid4().hex.encode('utf_8')
        # payload = b''
        print(f"Sending ping number {self._pings_sent} at {strftime('%X')} with payload: '{payload.decode()}'")
        if len(self._pings) > 10:
            self._pings = {}
            self._pongs = {}
            self._roundtrips = {}
        self._pings[payload.decode('utf_8')] = time()    
        try:
            await self.send({"type": "websocket.ping", "bytes": payload})
        except:
            await self.close()
    
    async def send_pong(self, message):
        if hasattr(message, 'get'):
            payload = message.get('bytes', b'')
        else:
            payload = b''
        await self.send({"type": "websocket.pong", "bytes": payload})

    # async def close(self, code: int = 1000, reason: str | None = None) -> None:
    async def close(self, code: int = 1000, reason= None) -> None:
        await self.send(
            {"type": "websocket.close", "code": code, "reason": reason or ""}
        )
        self.application_state = DISCONNECTED

    @property
    def closed(self):
        return self.application_state == DISCONNECTED or self.client_state == DISCONNECTED