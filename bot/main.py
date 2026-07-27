import asyncio
import threading
from aiohttp import web, ClientSession
from bot import app
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
    url = f"http://127.0.0.1:{FLASK_INTERNAL_PORT}/{path}"
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


def _start_flask_background():
    """Run Flask on an internal port in a daemon thread."""
    from web.app import create_app
    flask_app = create_app()
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
    _start_flask_background()
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

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Start PTB webhook on its own internal port, then run unified server
    # on $PORT with Flask panel + health, proxying webhook to PTB
    ptb_port = port + 1 if port < 65534 else port - 1

    async def _run_both():
        # Start PTB webhook on internal port
        await app.bot.set_webhook(
            url=f"{WEBHOOK_URL.rstrip('/')}/{TELEGRAM_BOT_TOKEN}",
            allowed_updates=["message", "callback_query"],
        )
        # We still need PTB's webhook receiver — run it via run_webhook on ptb_port
        # But since we can't easily merge, just use PTB's built-in on the SAME port
        # Actually simplest: just add panel_proxy to PTB's own server
        pass

    # Simplest reliable approach: PTB owns the port, Flask runs in background thread,
    # and we add a custom route to PTB's aiohttp app via post_init
    async def post_init(application):
        """Inject Flask panel proxy into PTB's aiohttp web app."""
        _start_flask_background()
        await asyncio.sleep(0.5)
        application.web_app.router.add_route("*", "/panel/{path_info:.*}", panel_proxy)
        print("Flask panel mounted at /panel/ on webhook server")

    app.post_init = post_init
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=TELEGRAM_BOT_TOKEN,
        webhook_url=public_url,
    )


if __name__ == "__main__":
    load_data()
    start_routine_watcher()

    use_webhook = os.environ.get("USE_WEBHOOK", "False")
    if use_webhook == "True" and IS_LOCAL != "True":
        run_webhook()
    else:
        run_local()