import asyncio
from aiohttp import web
from bot import app
import os
from bot.services.database import load_data
from bot.services.routine import start_routine_watcher


async def health(request):
    return web.Response(text="ok")

async def start_server():
    web_app = web.Application()
    web_app.router.add_get("/", health)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8000)))
    await site.start()
    print(f"Health check running on port {os.environ.get('PORT', 8000)}")
    # Keep server alive forever
    await asyncio.Event().wait()


if __name__ == '__main__':
    load_data()
    start_routine_watcher()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Run both in parallel
    loop.create_task(start_server())
    app.run_polling()