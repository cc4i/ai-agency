# Agent Execution Refactor Plan

This document outlines the necessary tasks to refactor the agent execution workflow from a synchronous (blocking) process to a fully asynchronous one using Celery.

### The Problem

The current implementation executes agent tasks synchronously. When Gemini Live issues a tool call, the entire backend connection is blocked until the agent completes its work. This freezes the user interface and prevents any further interaction until the task is done, leading to a poor user experience.

### The Goal

To make agent execution fully asynchronous, allowing the UI to remain responsive and interactive while agents are working in the background.

---

### Task 1: Create a Dedicated Celery Task for Agent Execution

The logic for running an agent, which is currently inside the `AgentOrchestrator`, needs to be moved into a formal Celery task.

*   **File to Create:** `backend/app/tasks.py`
*   **Action:**
    1.  Define a new Celery task named `run_agent_task`.
    2.  This task will accept `agent_id`, `task` details, and `project_id` as arguments.
    3.  Inside this task, move the core logic from `orchestration.py`'s `execute_agent` method: get the agent from the registry, call `agent.execute()`, and store the result in Redis.

### Task 2: Modify the Orchestrator to Dispatch, Not Execute

The `AgentOrchestrator` should act as a dispatcher that sends jobs to the Celery queue, rather than executing them directly.

*   **File to Modify:** `backend/app/services/orchestration.py`
*   **Action:**
    1.  Change the `execute_agent` method.
    2.  Instead of calling `await agent.execute(...)` directly, it should now use `celery.send_task("app.tasks.run_agent_task", ...)` to send the job to the background worker.
    3.  The function should then return immediately, without waiting for the agent to finish.

### Task 3: Re-architect the Tool Response Flow

Since the orchestrator will now return immediately, a new mechanism is required to send the agent's final result back to the Gemini Live session when the background task is complete.

*   **File to Modify:** `backend/app/services/gemini_live.py`
*   **Action:**
    1.  **Change `_execute_agent_function`**: It should no longer `await` a result from the orchestrator. It should simply trigger the orchestrator and finish.
    2.  **Create a Result Listener**: A new, persistent listener task must be created inside the `GeminiLiveConnection` class. Its job is to subscribe and listen to a specific Redis Pub/Sub channel dedicated to agent results for the current session.
    3.  **Update the Celery Task**: After the `run_agent_task` (from Task 1) completes its work and gets a result, its final step must be to **publish** that result to the session-specific Redis channel.
    4.  **Send Response from Listener**: When the new listener in `GeminiLiveConnection` receives a result from the Redis channel, *it* will be responsible for calling `self.gemini_session.send_tool_response(...)`. This sends the agent's output back to Gemini, allowing the main conversation to continue.
