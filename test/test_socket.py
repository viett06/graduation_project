import asyncio
import websockets
import httpx
import json


async def test_realtime_flow():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjo0LCJlbWFpbCI6InZpZXQzQGV4YW1wbGUuY29tIiwiaXNfYWN0aXZlIjp0cnVlLCJpc19zdXBlcnVzZXIiOmZhbHNlLCJleHAiOjE3NzcxOTkzNDMsInR5cGUiOiJhY2Nlc3MiLCJyb2xlcyI6WyJ1c2VyIl0sInBlcm1pc3Npb25zIjpbInVzZXI6dXBkYXRlIiwidXNlcjpyZWFkIl19.0p3ZbwWVd-fysoCg_e6EjKIAMqhu9tzSJMQtlpMOrkI"

    uri = f"ws://localhost:8000/ws/rates?token={token}"
    api_url = "http://localhost:8000/api/v1/crawler/trigger?bank_code=AGRIBANK"

    auth_headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket Connected!")

            async with httpx.AsyncClient() as client:
                print("📡 Triggering API...")
                response = await client.post(api_url, headers=auth_headers)
                print(f"API Response Status: {response.status_code}")

            print("⏳ Waiting for real-time message...")

            try:
                message = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=10
                )

                data = json.loads(message)

                print("🚀 Received Event:", data)

            except asyncio.TimeoutError:
                print("ℹ️ No realtime event received (no rate changes detected).")

    except Exception as e:
        print(f"❌ Error: {type(e).__name__} - {e}")


asyncio.run(test_realtime_flow())