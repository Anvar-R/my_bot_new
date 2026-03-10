import asyncio
from typing import Any, Dict, Union

from aiogram import BaseMiddleware, types
from aiogram.types import Message
from database.database import AddChat
from database.image import add_or_update_user


class AlbumMiddleware(BaseMiddleware):
    def __init__(self, latency: Union[int, float] = 0.1):
        # Initialize latency and album_data dictionary
        self.latency = latency
        self.album_data = {}
#
    def collect_album_messages(self, event: Message):
        """
        Collect messages of the same media group.
        """
#         # Check if media_group_id exists in album_data
        if event.media_group_id not in self.album_data:
#             # Create a new entry for the media group
            self.album_data[event.media_group_id] = {"messages": []}
#
#         # Append the new message to the media group
        self.album_data[event.media_group_id]["messages"].append(event)
#
#         # Return the total number of messages in the current media group
        return len(self.album_data[event.media_group_id]["messages"])
#
    async def __call__(self, handler, event: Message, data: Dict[str, Any]) -> Any:
        """
        Main middleware logic.
        """
#         # If the event has no media_group_id, pass it to the handler immediately
        if not event.media_group_id:
            return await handler(event, data)
#
#         # Collect messages of the same media group
        total_before = self.collect_album_messages(event)
#
#         # Wait for a specified latency period
        await asyncio.sleep(self.latency)
#
#         # Check the total number of messages after the latency
        total_after = len(self.album_data[event.media_group_id]["messages"])
#
#         # If new messages were added during the latency, exit
        if total_before != total_after:
            return
#
#         # Sort the album messages by message_id and add to data
        album_messages = self.album_data[event.media_group_id]["messages"]
        album_messages.sort(key=lambda x: x.message_id)
        data["album"] = album_messages
#
#         # Remove the media group from tracking to free up memory
        del self.album_data[event.media_group_id]
#         # Call the original event handler
        return await handler(event, data)

class IfInChatsMiddleware(BaseMiddleware):
    def __init__(self, allowed_chat_ids: list):
        self.allowed_chat_ids = allowed_chat_ids

    async def __call__(self, handler, event: Message, data: Dict[str, Any]) -> Any:
        # Register or update user in database
        if event.from_user:
            user_name = event.from_user.full_name
            await add_or_update_user(data['db_pool'], event.from_user.id, user_name)
        
        if event.chat.id in self.allowed_chat_ids:
            return await handler(event, data)
        else:
            new_chat = {}
            if event.chat.type == "private":
                new_chat = {"chat_id": event.chat.id, 
                            "chat_type": event.chat.type,
                            "chat_name": event.chat.first_name + " " + event.chat.last_name if event.chat.last_name else event.chat.first_name} 
            else:
                new_chat = {"chat_id": event.chat.id,
                            "chat_type": event.chat.type, 
                            "chat_name": event.chat.title}
            await AddChat(data['db_pool'], new_chat)
            return await handler(event, data)