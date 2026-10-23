"""Puente local MQTT -> WebSocket. No almacena un historial permanente."""

import asyncio
import base64
from contextlib import suppress
from datetime import datetime, timezone
import json
import logging
import math
import os
import time
from urllib.parse import urlsplit

from aiohttp import web
import paho.mqtt.client as mqtt

LOG = logging.getLogger("puente")
FIELDS = ("voltaje", "corriente", "resistencia", "fase")
MAX_PAYLOAD = 4096
BRIDGE_KEY = web.AppKey("bridge", object)


def parse_measurement(payload):
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("mensaje demasiado grande")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("se esperaba un objeto JSON")
    clean = {}
    for field in FIELDS:
        value = data.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field}: se requiere un número")
        try:
            value = float(value)
        except OverflowError as error:
            raise ValueError(f"{field}: fuera de rango") from error
        if not math.isfinite(value):
            raise ValueError(f"{field}: se requiere un número finito")
        clean[field] = value
    return clean


class Bridge:
    def __init__(self, *, host, port, user, password, topic, stale_seconds=10):
        if not math.isfinite(stale_seconds) or stale_seconds <= 0:
            raise ValueError("STALE_SECONDS debe ser mayor que cero")
        self.host, self.port, self.topic = host, port, topic
        self.stale_seconds = stale_seconds
        self.connected = False
        self.last_received = None
        self.last_message = None
        self.clients = set()
        self.events = asyncio.Queue(maxsize=128)
        self.tasks = []
        self.loop = None
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="iot-dashboard-bridge",
            protocol=mqtt.MQTTv311,
        )
        self.client.username_pw_set(user, password)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message
        self.client.on_connect_fail = lambda *_: LOG.warning(
            "Broker no disponible; se reintentará la conexión"
        )

    def enqueue(self, kind, payload):
        # Los callbacks MQTT se ejecutan en un hilo distinto al servidor web.
        def offer():
            if self.events.full():
                self.events.get_nowait()
            self.events.put_nowait((kind, payload))

        if self.loop is not None and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(offer)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            LOG.error("Conexión MQTT rechazada: %s", reason_code)
            self.enqueue("connection", False)
            return
        result, _ = client.subscribe(self.topic, qos=1)
        if result != mqtt.MQTT_ERR_SUCCESS:
            LOG.error("No se pudo solicitar la suscripción MQTT")
            self.enqueue("connection", False)

    def on_subscribe(self, client, userdata, mid, reason_codes, properties):
        ok = bool(reason_codes) and all(not code.is_failure for code in reason_codes)
        LOG.info("Suscripción MQTT %s", "lista" if ok else "rechazada")
        self.enqueue("connection", ok)

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        LOG.warning("Conexión MQTT cerrada: %s", reason_code)
        self.enqueue("connection", False)

    def on_message(self, client, userdata, message):
        if message.topic != self.topic:
            return
        # Un retained anterior no demuestra que el dispositivo siga publicando.
        if message.retain:
            LOG.info("Se ignoró una lectura retenida; se espera una lectura nueva")
            return
        try:
            data = parse_measurement(message.payload)
        except (ValueError, UnicodeError):
            LOG.warning("Medición rechazada: JSON inválido, campos ausentes o tipos incorrectos")
            return
        self.enqueue("measurement", (data, time.monotonic(), datetime.now(timezone.utc).isoformat()))

    def status(self):
        fresh = (
            self.connected
            and self.last_received is not None
            and time.monotonic() - self.last_received <= self.stale_seconds
        )
        return {
            "type": "status",
            "mqtt_connected": self.connected,
            "data_fresh": fresh,
            "last_update": self.last_message["received_at"] if self.last_message else None,
            "stale_seconds": self.stale_seconds,
        }

    async def broadcast(self, message):
        async def send(ws):
            try:
                await asyncio.wait_for(ws.send_json(message), timeout=2)
            except (ConnectionError, RuntimeError, asyncio.TimeoutError):
                self.clients.discard(ws)
                with suppress(Exception):
                    await ws.close()

        await asyncio.gather(*(send(ws) for ws in tuple(self.clients)))

    async def process_events(self):
        while True:
            kind, payload = await self.events.get()
            if kind == "connection":
                self.connected = payload
                # Tras reconectar exigimos una nueva lectura para marcar datos recientes.
                self.last_received = None
                await self.broadcast(self.status())
            else:
                data, received_mono, received_at = payload
                self.last_received = received_mono
                self.last_message = {
                    "type": "measurement", "data": data, "received_at": received_at
                }
                await self.broadcast(self.last_message)
                await self.broadcast(self.status())

    async def report_status(self):
        while True:
            await asyncio.sleep(1)
            await self.broadcast(self.status())

    async def start(self, app):
        self.loop = asyncio.get_running_loop()
        self.tasks = [asyncio.create_task(self.process_events()), asyncio.create_task(self.report_status())]
        self.client.connect_async(self.host, self.port, keepalive=30)
        self.client.loop_start()

    async def stop(self, app):
        for ws in tuple(self.clients):
            await ws.close(code=1001, message=b"Servidor detenido")
        self.client.disconnect()
        await asyncio.to_thread(self.client.loop_stop)
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)


async def websocket(request):
    bridge = request.app[BRIDGE_KEY]
    origin = request.headers.get("Origin")
    if origin and urlsplit(origin).netloc.lower() != request.host.lower():
        raise web.HTTPForbidden(text="Origen WebSocket no permitido")
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=1024, compress=False)
    await ws.prepare(request)
    bridge.clients.add(ws)
    try:
        await ws.send_json(bridge.status())
        if bridge.last_message:
            await ws.send_json({**bridge.last_message, "snapshot": True})
        async for _ in ws:
            # Dashboard de solo lectura: no acepta comandos del navegador.
            pass
    finally:
        bridge.clients.discard(ws)
    return ws


async def health(request):
    return web.json_response({"ok": True, **request.app[BRIDGE_KEY].status()})


def create_app(bridge):
    app = web.Application(client_max_size=1024)
    app[BRIDGE_KEY] = bridge
    app.router.add_get("/ws", websocket)
    app.router.add_get("/healthz", health)
    app.on_startup.append(bridge.start)
    app.on_shutdown.append(bridge.stop)
    return app


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    encoded = os.environ.get("MQTT_PASSWORD_B64", "")
    if not encoded:
        raise SystemExit("Faltan credenciales. Ejecuta python3 scripts/configurar.py antes de arrancar.")
    try:
        password = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (ValueError, UnicodeError) as error:
        raise SystemExit("MQTT_PASSWORD_B64 no es válido; ejecuta nuevamente el configurador") from error
    bridge = Bridge(
        host=os.environ.get("MQTT_HOST", "mosquitto"),
        port=int(os.environ.get("MQTT_PORT", "1883")),
        user=os.environ.get("MQTT_USER", "dashboard"),
        password=password,
        topic=os.environ.get("MQTT_TOPIC", "iot/monitoreo/mediciones"),
        stale_seconds=float(os.environ.get("STALE_SECONDS", "10")),
    )
    web.run_app(create_app(bridge), host="0.0.0.0", port=int(os.environ.get("PORT", "8765")))


if __name__ == "__main__":
    main()
