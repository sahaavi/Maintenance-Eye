import asyncio
import json
import time

import websockets


async def test_ws():
    uri = "wss://maintenance-eye-swrz6daraq-uc.a.run.app/ws/inspect/test-user"
    async with websockets.connect(uri) as websocket:
        # 1. Receive initial greeting
        greeting = await websocket.recv()
        print(f"Received Greeting: {greeting}")

        # 2. Start session
        await websocket.send(json.dumps({"type": "start_session", "asset_id": "ESC-LO-002"}))

        # 3. Request a work order
        print("Sending request for work order...")
        await websocket.send(
            json.dumps(
                {
                    "type": "text",
                    "data": "The handrail is vibrating heavily and making a grinding noise. I need to create a work order for this. Severity is high.",
                }
            )
        )

        # 4. Wait for confirmation request
        print("Waiting for response/confirmation...")
        start_time = time.time()
        while time.time() - start_time < 60:  # 60s timeout
            try:
                resp = await websocket.recv()
                data = json.loads(resp)
                msg_type = data.get("type")

                if msg_type == "text":
                    print(f"[{time.time() - start_time:.1f}s] Agent says: {data.get('data')}")
                elif msg_type == "transcript_output":
                    print(f"[{time.time() - start_time:.1f}s] Transcript: {data.get('data')}")
                elif msg_type == "confirmation_request":
                    print(f"[{time.time() - start_time:.1f}s] CONFIRMATION REQUEST RECEIVED!")
                    print(json.dumps(data.get("data"), indent=2))

                    # 5. Confirm the action
                    action_id = data["data"]["action_id"]
                    print(f"Confirming action {action_id}...")
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "confirm",
                                "data": {
                                    "action_id": action_id,
                                    "notes": "Confirmed by test script.",
                                },
                            }
                        )
                    )
                elif msg_type == "confirmation_result":
                    print(
                        f"[{time.time() - start_time:.1f}s] CONFIRMATION RESULT: {data.get('data')}"
                    )
                    print("Test successful!")
                    return
                elif msg_type == "audio":
                    pass  # Skip audio logs
                elif msg_type == "status":
                    if "Live API ready" not in data.get("data", ""):
                        print(f"[{time.time() - start_time:.1f}s] Status: {data.get('data')}")
                elif msg_type == "error":
                    print(f"[{time.time() - start_time:.1f}s] Error: {data.get('data')}")
                elif msg_type == "session_summary":
                    print(f"[{time.time() - start_time:.1f}s] Session summary received.")
            except Exception as e:
                print(f"Error during recv: {e}")
                break


if __name__ == "__main__":
    asyncio.run(test_ws())
