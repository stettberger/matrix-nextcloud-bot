import aiohttp
import asyncio
from nio import *
import logging

class MatrixNextcloudBot:
    def __init__(self):
        self.server = "https://riot.entwicklerin.net"
        self.user = "@stettberger:riot.entwicklerin.net"


    async def main(self):
        self.client = AsyncClient(self.server, self.user)
        
        await self.client.login(self.password)
        self.client.add_event_callback(self.message_cb, RoomMessageText)
        self.client.add_event_callback(self.message_cb, RoomMessageFile)
        self.client.add_event_callback(self.message_picture, RoomMessageImage)

        await self.client.sync_forever(timeout=30000)

    async def message_cb(self, room, event):
        logging.debug("{} {} | {}: {}", type(event),
                      room.display_name, room.user_name(event.sender),
                      event.body)

    async def message_picture(self,room, event):
        print(room.canonical_alias, room.room_id, event.body, event.url)
        print(event.url)
        x = Api.mxc_to_http(event.url)
        print(x)
        print(x)

