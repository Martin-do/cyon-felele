import json
from channels.generic.websocket import AsyncWebsocketConsumer

class BoardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'live_board'

        # Join the live board broadcast group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave the broadcast group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Receive message from room group triggered by the REST API
    async def new_contribution(self, event):
        data = event['data']

        # Send message to the connected WebSocket client
        await self.send(text_data=json.dumps({
            'type': 'new_contribution',
            'data': data
        }))
