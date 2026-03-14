import asyncio
import json
import time

import websockets


async def test_ws():
    uri = "wss://maintenance-eye-swrz6daraq-uc.a.run.app/ws/inspect/test-user"
    async with websockets.connect(uri) as websocket:
        greeting = await websocket.recv()
        await websocket.send(json.dumps({"type": "start_session", "asset_id": "ELV-ED-004"}))

        print("Requesting report...")
        await websocket.send(
            json.dumps({"type": "text", "data": "Everything looks good. Generate report."})
        )

        start_time = time.time()
        while time.time() - start_time < 60:
            resp = await websocket.recv()
            data = json.loads(resp)
            if data.get("type") == "media_card":
                print("MEDIA CARD RECEIVED!")
                print(json.dumps(data.get("data"), indent=2))
                if "Inspection Report" in data.get("data", {}).get("title", ""):
                    print(
                        "SUCCESS: Report media card received with link:",
                        data.get("data", {}).get("action_link"),
                    )
                    return
            elif data.get("type") == "error":
                print("Error:", data.get("data"))
                return


if __name__ == "__main__":
    asyncio.run(test_ws())
