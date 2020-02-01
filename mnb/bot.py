import aiohttp
import asyncio
import os
import yaml
import logging
import sys
import pprint
import time

from nio import events
from nio.api import Api
from nio import responses
from nio.client.async_client import AsyncClient, AsyncClientConfig, SyncError
from xdg import XDG_CONFIG_HOME, XDG_DATA_HOME

from mnb.nextcloud import Nextcloud


class MatrixNextcloudBot:
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG)

        self.data_dir = os.path.join(XDG_DATA_HOME, "matrix-nextcloud-bot")
        if not os.path.exists(self.data_dir):
            os.mkdir(self.data_dir)
        self.config_dir = os.path.join(XDG_CONFIG_HOME, "matrix-nextcloud-bot")
        if not os.path.exists(self.config_dir):
            os.mkdir(self.config_dir)

        config_fn = os.path.join(self.config_dir, "config.yml")
        logging.info("Reading config from: %s", config_fn)
        try:
            with open(config_fn) as fd:
                self.__config = yaml.load(fd, Loader=yaml.SafeLoader)
        except:
            self.die("Config not found: %s", config_fn)

        self.timestamp_minimum = {}

        self.nextcloud = Nextcloud(
            self.config('nextcloud.server'),
            self.config('nextcloud.user'),
            self.config('nextcloud.password'))



    def die(self, msg, *args):
        logging.error(msg, *args)
        sys.exit("Exiting.")

    def config(self, key, default=None):
        parts = key.split(".")
        ret = self.__config
        while parts:
            if parts[0] not in ret:
                if default is not None:
                    return default
                self.die("config %s not found.", key)
            ret = ret[parts[0]]
            del parts[0]
        return ret

    def room_config(self, matrix_room):
        for room in self.config("matrix.rooms", []):
            ids = (room, getattr(matrix_room, "room_id"), getattr(matrix_room, "canonical_alias"))
            if "canonical_alias" in room:
                if room['canonical_alias'] in ids:
                    return room
            if "room_id" in room:
                if room['room_id'] in ids:
                    return room

    async def main(self):
        config = AsyncClientConfig(
            # FIXME: store=nio.store.database.DefaultStore,
        )
        self.client = AsyncClient(
            self.config('matrix.server'),
            self.config('matrix.user'),
            self.config('matrix.device_id', "AABBCCDD"),
            # FIXME: store_path,
            config=config
        )

        login = await self.client.login(self.config('matrix.password'))
        logging.info("Matrix Login: %s", login)

        # Register all the events
        for event in (events.RoomMessageText, events.InviteMemberEvent, events.RoomMessageImage):
            cb_name   = "event_{}".format(event.__name__)
            cb_method = getattr(self, cb_name)
            self.client.add_event_callback(cb_method, event)

        # Sync loop
        sync_token = self.get_sync_token()
        while True:
            # Sync with the server
            self.sync_response = await self.client.sync(timeout=30000,
                                                   full_state=True,
                                                   since=sync_token)

            # Check if the sync had an error
            if type(self.sync_response) == SyncError:
                logger.warning("Error in client sync: %s", sync_response.message)
                continue

            # Save the latest sync token to the database
            token = self.sync_response.next_batch
            if token and sync_token != token:
                sync_token = token
                # Comment the next line for debugging
                self.set_sync_token(token)

            # Sleep for a second to save power
            await asyncio.sleep(1)


    def get_sync_token(self):
        sync_token_fn = os.path.join(self.data_dir, "sync_token")
        if not os.path.exists(sync_token_fn):
            return None
        with open(sync_token_fn) as fd:
            return fd.read()

    def set_sync_token(self, value):
        sync_token_fn = os.path.join(self.data_dir, "sync_token")
        with open(sync_token_fn, "w+") as fd:
            return fd.write(value)

    async def event_RoomMessageText(self, room, event):
        # Ignore old messages after join
        if self.timestamp_minimum.get(room.room_id, 0) > event.server_timestamp:
            return
        
        logging.debug(
            "{} | {}: {}".format(
                room.display_name, room.user_name(event.sender), event.body
            )
        )

        # Mark messages as read
        await self.room_read_markers(room.room_id, event.event_id, event.event_id)

    async def event_RoomMessageImage(self, room, event):
        # Ignore old messages after join
        if self.timestamp_minimum.get(room.room_id, 0) > event.server_timestamp:
            return

        room_config = self.room_config(room)
        if not (room_config
                and room_config.get("nextcloud")
                and room_config["nextcloud"].get("images")):
            return
        target_dir = room_config["nextcloud"]["images"]
        file_name = event.body
        http_url = await self.client.mxc_to_http(event.url)

        success, msg = self.nextcloud.upload(target_dir, file_name, url=http_url)

        await self.send_message(room.room_id, f"nextcloud: {msg}")

        # Mark messages as read
        # self.client.room_read_markers
        await self.room_read_markers(room.room_id, event.event_id, event.event_id)

        

    async def event_InviteMemberEvent(self, room, event):
        if event.membership != "invite": return
        room_name = room.canonical_alias or room.room_id
        logging.info("Invited from %s into %s", event.sender, room_name)
        response = await self.client.join(room.room_id)
        if isinstance(response, responses.JoinResponse):
            logging.info("Joined %s", room_name)
        else:
            logging.info("Error joining %s", response)
            return

        self.timestamp_minimum[room.room_id] = time.time()

        msg = self.config("matrix.welcome_message", None)
        if msg:
            await self.send_message(room.room_id, msg)

    async def send_message(self, room_id, msg):
        content = {
            "body": msg,
            "msgtype": "m.text"
        }
        return await self.client.room_send(room_id, 'm.room.message', content)

    async def room_read_markers(self, room_id, fully_read_event, read_event=None):
        # This should be in nio.client.async.AyncClient
        method, path, data = Api.room_read_markers(
            self.client.access_token,
            room_id,
            fully_read_event,
            read_event
        )

        return await self.client._send(
            responses.RoomReadMarkersResponse,
            method,
            path,
            data,
            response_data = (room_id,),
        )

