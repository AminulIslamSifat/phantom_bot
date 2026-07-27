import asyncio
from aiohttp import web
from bot import app
import os
from bot.services.database import load_data
from bot.services.routine import start_routine_watcher
from config import IS_LOCAL, TELEGRAM_BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PORT


async def health(request):
    return web.Response(text="ok")


async def start_health_server():
    web_app = web.Application()
    web_app.router.add_get("/", health)

    runner = web.AppRunner(web_app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Health check running on port {port}")
    await asyncio.Event().wait()


def run_local():
    """Polling mode for local development."""
    print("Starting in POLLING mode (IS_LOCAL=True)")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(start_health_server())
    app.run_polling()


def run_webhook():
    """Webhook mode for production deployment."""
    if not WEBHOOK_URL:
        raise RuntimeError(
            "WEBHOOK_URL is not set. "
            "Add it to .env (e.g. WEBHOOK_URL=https://your-domain.com)"
        )
    webhook_path = TELEGRAM_BOT_TOKEN
    public_url = f"{WEBHOOK_URL.rstrip('/')}/{webhook_path}"
    print(f"Starting in WEBHOOK mode → {public_url}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(start_health_server())
    app.run_webhook(
        listen="0.0.0.0",
        port=WEBHOOK_PORT,
        url_path=webhook_path,
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