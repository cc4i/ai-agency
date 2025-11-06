"""Test script to verify text message handling via WebSocket."""

import asyncio
import json
import websockets

async def test_text_message():
    """Send a test text message to the WebSocket endpoint."""

    # Configuration
    session_id = "test_session_123"
    project_id = "aura_smart_sneaker"
    model = "gemini-live-2.5-flash"
    voice = "Kore"

    uri = f"ws://localhost:8000/ws/adk/{session_id}/{project_id}?model={model}&voice={voice}"

    print(f"🔗 Connecting to: {uri}")

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")

            # Wait for initial connection confirmation
            response = await websocket.recv()
            print(f"📨 Received: {response}")

            # Send a text message
            text_message = {
                "type": "text",
                "text": "Hello, this is a test message!"
            }

            print(f"📤 Sending text message: {text_message}")
            await websocket.send(json.dumps(text_message))

            # Wait for responses (timeout after 5 seconds)
            try:
                for _ in range(10):  # Wait for up to 10 messages
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(response)
                    print(f"📨 Response: {data.get('type', 'unknown')} - {str(data)[:100]}")

                    if data.get('type') == 'turn_complete':
                        print("✅ Turn complete - test successful!")
                        break
            except asyncio.TimeoutError:
                print("⏱️ No more responses (timeout)")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_text_message())
