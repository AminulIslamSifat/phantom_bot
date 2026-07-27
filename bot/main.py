import asyncio
import threading
from aiohttp import web, ClientSession
from telegram import Update
from bot import build_app, register_handlers, app
import os
from bot.services.database import load_data
from bot.services.routine import start_routine_watcher
from config import IS_LOCAL, TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PORT

FLASK_INTERNAL_PORT = 5001


async def health(request):
    return web.Response(text="ok")


async def panel_proxy(request):
    """Reverse-proxy /panel/* requests to the internal Flask server."""
    path = request.match_info.get("path_info", "")
    url = f"http://127.0.0.1:{FLASK_INTERNAL_PORT}/panel/{path}"
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "transfer-encoding")}
    body = await request.read()
    async with ClientSession() as session:
        async with session.request(
            request.method, url, headers=headers, data=body,
            params=request.query, allow_redirects=False,
        ) as resp:
            content = await resp.read()
            return web.Response(
                status=resp.status, body=content,
                headers={k: v for k, v in resp.headers.items()
                         if k.lower() not in ("transfer-encoding", "content-encoding")},
            )


def _start_flask_background(url_prefix: str = ""):
    """Run Flask on an internal port in a daemon thread."""
    from web.app import create_app
    flask_app = create_app(url_prefix=url_prefix)
    t = threading.Thread(
        target=lambda: flask_app.run(
            host="127.0.0.1", port=FLASK_INTERNAL_PORT, debug=False, use_reloader=False,
        ),
        daemon=True,
    )
    t.start()
    print(f"Flask admin panel running internally on port {FLASK_INTERNAL_PORT}")


async def start_unified_server(port: int, mode_label: str):
    """Start aiohttp with health check + Flask panel proxy on one port."""
    _start_flask_background(url_prefix="/panel")
    await asyncio.sleep(0.5)  # let Flask bind

    web_app = web.Application(client_max_size=50 * 1024 * 1024)
    web_app.router.add_get("/", health)
    web_app.router.add_route("*", "/panel/{path_info:.*}", panel_proxy)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"{mode_label} server on port {port} (panel at /panel/)")
    await asyncio.Event().wait()


def run_local():
    """Polling mode for local development."""
    print("Starting in POLLING mode (IS_LOCAL=True)")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    port = int(os.environ.get("PORT", 8000))
    loop.create_task(start_unified_server(port, "Local"))
    app.run_polling()


async def _run_custom_webhook(port: int, public_url: str):
    """
    Custom webhook server following PTB v21 official pattern.
    Owns the aiohttp server directly — handles Telegram updates + Flask panel on one port.
    See: https://docs.python-telegram-bot.org/en/v21.9/examples.customwebhookbot.html
    """
    webhook_path = TELEGRAM_BOT_TOKEN

    # Build a fresh app without PTB's built-in updater — we manage the server
    ptb_app = build_app(with_updater=False)
    register_handlers(ptb_app)

    async def telegram_webhook(request):
        """Receive Telegram updates and feed them into PTB's update queue."""
        data = await request.json()
        update = Update.de_json(data=data, bot=ptb_app.bot)
        await ptb_app.update_queue.put(update)
        return web.Response(status=200)

    # Build aiohttp app with all routes
    web_app = web.Application(client_max_size=50 * 1024 * 1024)
    web_app.router.add_get("/", health)
    web_app.router.add_post(f"/{webhook_path}", telegram_webhook)
    web_app.router.add_route("*", "/panel/{path_info:.*}", panel_proxy)

    # Start Flask in background thread
    _start_flask_background(url_prefix="/panel")
    await asyncio.sleep(0.5)

    # Set webhook URL with Telegram API
    await ptb_app.bot.set_webhook(
        url=public_url,
        allowed_updates=["message", "callback_query"],
    )

    # Start PTB application (handlers, post_init, etc.) without its own server
    async with ptb_app:
        await ptb_app.start()

        # Start our custom aiohttp server
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        print(f"Custom webhook + Flask panel on port {port} (panel at /panel/)")

        # Keep running forever
        await asyncio.Event().wait()


def run_webhook():
    """Webhook mode for production deployment (Render)."""
    if not WEBHOOK_URL:
        raise RuntimeError(
            "WEBHOOK_URL is not set. "
            "Add it to .env (e.g. WEBHOOK_URL=https://your-domain.com)"
        )
    port = int(os.environ.get("PORT", WEBHOOK_PORT))
    public_url = f"{WEBHOOK_URL.rstrip('/')}/{TELEGRAM_BOT_TOKEN}"
    print(f"Starting in WEBHOOK mode → {public_url} (port {port})")

    asyncio.run(_run_custom_webhook(port, public_url))


if __name__ == "__main__":
    load_data()
    start_routine_watcher()

    use_webhook = os.environ.get("USE_WEBHOOK", "False")
    if use_webhook == "True" and IS_LOCAL != "True":
        run_webhook()
    else:
        run_local()