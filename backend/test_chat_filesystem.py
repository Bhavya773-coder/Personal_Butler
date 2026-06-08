import asyncio
import httpx
import websockets
import json
import os
from pathlib import Path

API_BASE = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/ws/events"

async def test_chat_message(message: str) -> str:
    print(f"\nSending message: '{message}'")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{API_BASE}/chat", json={"message": message})
        res = r.json()
        print(f"Response: '{res.get('response')}'")
        return res.get('response', '')

async def test_create_folder_with_permission():
    print("\n--- Testing Create Folder with WebSocket Permission Flow ---")
    desktop = Path.home() / "Desktop"
    target_folder = desktop / "Jarvis Test"
    
    # Ensure cleanup first
    if target_folder.exists():
        import shutil
        if target_folder.is_dir():
            shutil.rmtree(str(target_folder))
        else:
            os.remove(str(target_folder))

    async with websockets.connect(WS_URL) as ws:
        # Start listening in a background task
        async def listen_and_approve():
            try:
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    print(f"[WS Event] {data.get('type')}: {data.get('message', '')}")
                    
                    if data.get("type") == "permission_required":
                        req_id = data.get("request_id")
                        action = data.get("action")
                        print(f"[WS Event] Received permission request {req_id} for '{action}'. Approving via REST API...")
                        
                        # Approve via REST API
                        async with httpx.AsyncClient() as client:
                            approve_res = await client.post(
                                f"{API_BASE}/permission/approve",
                                json={"request_id": req_id, "approved": True}
                            )
                            print(f"[REST] Approval status: {approve_res.json()}")
                            
                    elif data.get("type") == "final":
                        print(f"[WS Event] Final response: '{data.get('response')}'")
                        break
            except Exception as e:
                print(f"[WS Error] {e}")

        listener_task = asyncio.create_task(listen_and_approve())
        
        # Send chat message to WS
        await ws.send(json.dumps({
            "type": "chat",
            "message": "Create a folder on Desktop called Jarvis Test"
        }))
        
        # Wait for listener to complete
        await asyncio.wait_for(listener_task, timeout=15.0)

    # Verify folder was actually created
    exists = target_folder.exists() and target_folder.is_dir()
    print(f"Jarvis Test folder exists on Desktop: {exists}")
    
    # Clean up
    if target_folder.exists():
        import shutil
        shutil.rmtree(str(target_folder))
        
    return exists

async def test_delete_with_dangerous_permission():
    print("\n--- Testing Delete Safety with WebSocket Permission Flow ---")
    async with websockets.connect(WS_URL) as ws:
        async def listen_and_approve_delete():
            try:
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    print(f"[WS Event] {data.get('type')}: {data.get('message', '')}")
                    
                    if data.get("type") == "permission_required":
                        req_id = data.get("request_id")
                        action = data.get("action")
                        level = data.get("level")
                        print(f"[WS Event] Received permission request {req_id} for '{action}' with level '{level}'. Approving via REST API...")
                        
                        # Approve via REST API
                        async with httpx.AsyncClient() as client:
                            approve_res = await client.post(
                                f"{API_BASE}/permission/approve",
                                json={"request_id": req_id, "approved": True}
                            )
                            print(f"[REST] Approval status: {approve_res.json()}")
                            
                    elif data.get("type") == "final":
                        print(f"[WS Event] Final response: '{data.get('response')}'")
                        break
            except Exception as e:
                print(f"[WS Error] {e}")

        listener_task = asyncio.create_task(listen_and_approve_delete())
        
        # Send delete message to WS
        await ws.send(json.dumps({
            "type": "chat",
            "message": "Delete Jarvis Test folder from Desktop"
        }))
        
        # Wait for listener to complete
        await asyncio.wait_for(listener_task, timeout=15.0)

async def test_denied_permission_flow():
    print("\n--- Testing Create Folder with Denied Permission Flow ---")
    async with websockets.connect(WS_URL) as ws:
        async def listen_and_deny():
            try:
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    print(f"[WS Event] {data.get('type')}: {data.get('message', '')}")
                    
                    if data.get("type") == "permission_required":
                        req_id = data.get("request_id")
                        print(f"[WS Event] Denying permission request {req_id} via REST API...")
                        
                        # Deny via REST API
                        async with httpx.AsyncClient() as client:
                            deny_res = await client.post(
                                f"{API_BASE}/permission/deny",
                                json={"request_id": req_id, "approved": False}
                            )
                            print(f"[REST] Deny status: {deny_res.json()}")
                            
                    elif data.get("type") == "final":
                        print(f"[WS Event] Final response: '{data.get('response')}'")
                        break
            except Exception as e:
                print(f"[WS Error] {e}")

        listener_task = asyncio.create_task(listen_and_deny())
        
        # Send create folder message to WS
        await ws.send(json.dumps({
            "type": "chat",
            "message": "Create a folder on Desktop called Jarvis Test"
        }))
        
        # Wait for listener to complete
        await asyncio.wait_for(listener_task, timeout=15.0)

async def main():
    print("=== JARVIS E2E Filesystem Chat Tests ===")
    
    # 1. List files in Downloads
    await test_chat_message("List files in Downloads")
    
    # 2. Search my Downloads folder for PDF files
    await test_chat_message("Search my Downloads folder for PDF files")
    
    # 3. Find files named invoice on Desktop
    await test_chat_message("Find files named invoice on Desktop")
    
    # 4. Create a folder on Desktop called Jarvis Test (permission approved)
    folder_created = await test_create_folder_with_permission()
    
    # 5. Create a folder on Desktop called Jarvis Test (permission denied)
    await test_denied_permission_flow()
    
    # 6. Temporary files read tests
    # Create temp files
    txt_path = Path("temp_test.txt").resolve()
    txt_path.write_text("This is an end-to-end file reading test for Jarvis Core.", encoding="utf-8")
    md_path = Path("temp_test.md").resolve()
    md_path.write_text("# Test Markdown\nThis is MD.", encoding="utf-8")
    
    try:
        await test_chat_message(f"Read this text file: {txt_path}")
        await test_chat_message(f"Read this markdown file: {md_path}")
        await test_chat_message(f"Summarize this file: {md_path}")
    finally:
        if txt_path.exists():
            os.remove(str(txt_path))
        if md_path.exists():
            os.remove(str(md_path))
            
    # 7. Delete Jarvis Test folder from Desktop (dangerous approval -> blocked result)
    await test_delete_with_dangerous_permission()

if __name__ == "__main__":
    asyncio.run(main())
