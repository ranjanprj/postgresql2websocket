#!/usr/bin/env python
#
# Python >= 3.5

import asyncio
import configparser
import asyncpg
from aiohttp import web, WSCloseCode

def callback_queue(queue):
    def callback(connection, pid, channel, payload):
        asyncio.async(queue.put(message))
    return callback

async def parse(ws, queue):
    while True:
        uid, channel, message = await queue.get()
        ws.send_str(message)

async def websocket_handler(request):
    channel = request.match_info.get('channel', 'postgresql2websocket')
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    request.app['websockets'].append(ws)
    pool = request.app['pool']
    async with pool.acquire() as connection:
        queue = asyncio.Queue()
        await connection.add_listener(channel, callback_queue(queue))
        task = loop.create_task(parse(ws, queue))
        try:
            async for msg in ws:
                pass
        finally:
            task.cancel()
            request.app['websockets'].remove(ws)
    return ws

async def init_app(config):
    app = web.Application()
    app['pool'] = await asyncpg.create_pool(**config['postgresql'])
    app.router.add_route('GET', '/{channel}', websocket_handler)
    return app

async def on_shutdown(app):
    for task in asyncio.Task.all_tasks():
        task.cancel()
    for ws in app['websockets']:
        await ws.close(code=WSCloseCode.GOING_AWAY,
            message='Server shutdown')

def main(filename = 'postgresql2websocket.conf'):
    config = configparser.ConfigParser()
    if not config.read(filename):
        print("Unable to read %s" % filename)
        exit(1)
    loop = asyncio.get_event_loop()
    app = loop.run_until_complete(init_app(config))
    app['websockets'] = []
    app.on_shutdown.append(on_shutdown)
    try:
        web.run_app(app,
            host = config.get('web', 'host'),
            port = config.getint('web', 'port'),
        )
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

if __name__ == '__main__':
    main()
