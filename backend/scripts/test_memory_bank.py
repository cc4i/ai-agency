
import asyncio
from datetime import datetime
from uuid import uuid4

from google.adk.events import Event
from google.adk.sessions import Session
from google.genai.types import Content, Part

from app.services.memory_service import memory_service

async def main():
    """
    Test script to verify Memory Bank functionality.

    This script will:
    1. Initialize the Memory Bank service.
    2. Create a sample session with a unique message.
    3. Add the session to Memory Bank.
    4. Search for the unique message in Memory Bank.
    5. Verify that the message was found.
    """
    print("--- Running Memory Bank Test ---")

    # 1. Initialize Memory Bank
    memory_service._initialize()
    if not memory_service.is_enabled():
        print("❌ Memory Bank is not enabled or failed to initialize. Aborting test.")
        return

    print("✅ Memory Bank service initialized.")

    # 2. Create a sample session
    session_id = f"test-session-{uuid4()}"
    user_id = "test-user"
    unique_message = f"This is a unique test message from session {session_id}"

    session = Session(
        id=session_id,
        user_id=user_id,
        app_name="ai_agency_hub",
        events=[
            Event(
                author="user",
                content=Content(
                    role="user",
                    parts=[Part.from_text(text=unique_message)],
                )
            )
        ],
    )
    print(f"✅ Created sample session: {session_id}")

    # 3. Add the session to Memory Bank
    print("Adding session to Memory Bank...")
    success = await memory_service.add_session_to_memory(session)
    if not success:
        print("❌ Failed to add session to Memory Bank. Aborting test.")
        return
    print("✅ Session added successfully.")

    # Give Memory Bank a moment to index the new data
    print("Waiting for indexing...")
    await asyncio.sleep(15)

    # 4. Search for the unique message
    print(f"Searching for unique message: '{unique_message}'")
    search_results = await memory_service.search_memory(
        query=unique_message,
        user_id=user_id,
    )

    print(search_results)

    # 5. Verify the results
    if not search_results:
        print("❌ Search returned no results.")
        return

    found = False
    for result in search_results:
        if unique_message in result.get("content", ""):
            found = True
            print("✅ Found the unique message in search results!")
            print(f"   - Relevance: {result.get('relevance_score')}")
            print(f"   - Content: {result.get('content')}")
            break

    if not found:
        print("❌ The unique message was NOT found in the search results.")
    
    print("--- Memory Bank Test Complete ---")

if __name__ == "__main__":
    asyncio.run(main())
