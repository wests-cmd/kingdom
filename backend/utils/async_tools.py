import asyncio

async def sleep(ms):
    await asyncio.sleep(ms / 1000)
