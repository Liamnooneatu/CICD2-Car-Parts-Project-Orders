import aio_pika
import asyncio
import json
import os

RABBIT_URL = os.getenv("RABBIT_URL")
EXCHANGE_NAME = "events_topic"


async def main():
    if not RABBIT_URL:
        raise RuntimeError("RABBIT_URL is not set. Run: set -a; source .env; set +a")

    conn = await aio_pika.connect_robust(RABBIT_URL)
    ch = await conn.channel()

    ex = await ch.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC)

    queue = await ch.declare_queue("order_events_queue", durable=True)
    await queue.bind(ex, routing_key="order.*")

    print("Listening for order events (routing key: 'order.*')...")

    async with queue.iterator() as q:
        async for msg in q:
            async with msg.process():
                data = json.loads(msg.body)
                print("Order Event:", msg.routing_key, data)


if __name__ == "__main__":
    asyncio.run(main())
