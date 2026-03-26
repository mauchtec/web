import asyncio
import json
import uuid
from typing import Any

from aiohttp import web
from django.core.management.base import BaseCommand
from django.db import OperationalError
from django.utils import timezone

from GateCore.models import GateTerminal
from GateCore.services.face_device_ws import handle_message
from face_devices.services import record_face_device_event


def _wrap_follow_up_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("cmd") == "to_device":
        wrapped = dict(payload)
        wrapped["extra"] = str(wrapped.get("extra") or "").strip() or str(uuid.uuid4())
        return wrapped

    body = dict(payload)
    command = str(body.pop("cmd", "unknown"))
    target = str(body.pop("sn", "") or "")
    action_id = str(body.pop("__action_id", "") or "")
    extra = action_id or str(uuid.uuid4())
    if "ip" in body:
        body.pop("ip", None)
    if "type" in body:
        body.pop("type", None)
    if "timestamp" in body:
        body.pop("timestamp", None)
    return {
        "cmd": "to_device",
        "to": target,
        "from": "server",
        "extra": extra,
        "data": {
            "cmd": command,
            **body,
        },
    }


def _resolve_terminal_for_event(device_identifier: str, remote_ip: str | None) -> GateTerminal | None:
    if device_identifier:
        terminal = GateTerminal.objects.filter(serial_number=device_identifier).first()
        if terminal:
            return terminal
    if remote_ip:
        return GateTerminal.objects.filter(ip_address=remote_ip).first()
    return None


async def _record_outbound_event(payload: dict[str, Any], remote: str | None) -> None:
    wrapper_cmd = str(payload.get("cmd") or "").strip()
    if wrapper_cmd == "to_device":
        nested = payload.get("data")
        command = str(nested.get("cmd") or "to_device") if isinstance(nested, dict) else "to_device"
        device_identifier = str(payload.get("to") or "")
    else:
        command = wrapper_cmd or "unknown"
        device_identifier = str(payload.get("sn") or "")
    terminal = await asyncio.to_thread(_resolve_terminal_for_event, device_identifier, remote)
    try:
        await asyncio.to_thread(
            record_face_device_event,
            terminal=terminal,
            device_identifier=device_identifier or (remote or "face-device"),
            direction="outbound",
            command=command,
            payload=payload,
            status="sent",
            remote_ip=remote,
        )
    except OperationalError as exc:
        print(
            "face-device-sync warning outbound-event-write "
            f"remote={remote or '<unknown>'} error={str(exc)}",
            flush=True,
        )


async def _handle_message_with_retry(payload: dict[str, Any] | str, remote: str | None):
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return await asyncio.to_thread(handle_message, payload, remote_ip=remote)
        except OperationalError as exc:
            last_error = exc
            await asyncio.sleep(0.15 * (attempt + 1))
    if last_error:
        raise last_error
    return await asyncio.to_thread(handle_message, payload, remote_ip=remote)


async def _websocket_handler(request: web.Request) -> web.StreamResponse:
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    remote = request.remote
    if not remote and request.transport:
        peername = request.transport.get_extra_info("peername")
        if isinstance(peername, (tuple, list)) and peername:
            remote = peername[0]
    print(f"face-device-sync websocket connected remote={remote or '<unknown>'} path={request.path}", flush=True)

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            raw = msg.data.strip()
            try:
                payload: dict[str, Any] | str = json.loads(raw)
                if not isinstance(payload, dict):
                    payload = raw
            except Exception:
                payload = raw

            try:
                result = await _handle_message_with_retry(payload, remote)
            except OperationalError as exc:
                print(
                    "face-device-sync warning message-handle "
                    f"remote={remote or '<unknown>'} error={str(exc)}",
                    flush=True,
                )
                continue
            if result.response:
                await ws.send_json(result.response)
                await _record_outbound_event(result.response, remote)
            for follow_up in result.follow_ups or []:
                outbound_payload = _wrap_follow_up_payload(follow_up)
                print(
                    "face-device-sync follow-up "
                    f"remote={remote or '<unknown>'} command={outbound_payload.get('cmd', '<unknown>')} "
                    f"payload={json.dumps(outbound_payload, ensure_ascii=True, default=str)}",
                    flush=True,
                )
                await ws.send_json(outbound_payload)
                await _record_outbound_event(outbound_payload, remote)
            if result.close:
                await ws.close()
                break
        elif msg.type == web.WSMsgType.ERROR:
            print(
                f"face-device-sync websocket error remote={remote or '<unknown>'} path={request.path} exception={ws.exception()}",
                flush=True,
            )
            break

    print(
        "face-device-sync websocket closed "
        f"remote={remote or '<unknown>'} path={request.path} close_code={ws.close_code} exception={ws.exception()}",
        flush=True,
    )
    return ws


async def _index_handler(request: web.Request) -> web.Response:
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return await _websocket_handler(request)
    return web.Response(
        text=(
            "Face sync server is running.\n\n"
            "WebSocket endpoint: /ws\n"
            "Health endpoint: /health\n"
        ),
        content_type="text/plain",
    )


async def _health_handler(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "success": True,
            "server_time": timezone.now().isoformat(),
            "message": "Face sync websocket server is running.",
        }
    )


class Command(BaseCommand):
    help = "Run the face-recognition websocket sync server for third-party devices."

    def add_arguments(self, parser):
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--port", type=int, default=12391)

    def handle(self, *args, **options):
        host = options["host"]
        port = int(options["port"])

        app = web.Application()
        app.router.add_get("/", _index_handler)
        app.router.add_get("/ws", _websocket_handler)
        app.router.add_get("/health", _health_handler)

        self.stdout.write(self.style.SUCCESS(f"Starting face sync websocket server on ws://{host}:{port}"))
        web.run_app(app, host=host, port=port)
