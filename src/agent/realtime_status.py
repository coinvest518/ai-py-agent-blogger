"""Real-time status broadcasting for agent activity."""

import asyncio
import json
import logging
from collections import deque
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)

class RealtimeStatusBroadcaster:
    """Broadcasts real-time agent status updates to connected clients."""
    
    def __init__(self, max_history: int = 100):
        """Initialize broadcaster with max history size."""
        self.clients: List[asyncio.Queue] = []
        self.history: deque = deque(maxlen=max_history)
        self.current_step: str | None = None
        self.total_steps: int = 0
        self.completed_steps: int = 0
        
    def add_client(self) -> asyncio.Queue:
        """Add a new client connection."""
        queue = asyncio.Queue()
        self.clients.append(queue)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
        return queue
        
    def remove_client(self, queue: asyncio.Queue):
        """Remove a client connection."""
        if queue in self.clients:
            self.clients.remove(queue)
            logger.info(f"Client disconnected. Total clients: {len(self.clients)}")
            
    async def broadcast(self, event_type: str, message: str, data: Dict | None = None):
        """Broadcast a status update to all connected clients."""
        event = {
            "type": event_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "step": self.current_step,
            "progress": {
                "current": self.completed_steps,
                "total": self.total_steps
            },
            "data": data or {}
        }
        
        # Add to history
        self.history.append(event)
        
        # Log the event
        logger.info(f"[{event_type}] {message}")
        
        # Broadcast to all clients
        disconnected = []
        for client_queue in self.clients:
            try:
                await client_queue.put(json.dumps(event))
            except Exception as e:
                logger.error(f"Failed to send to client: {e}")
                disconnected.append(client_queue)
                
        # Clean up disconnected clients
        for queue in disconnected:
            self.remove_client(queue)
            
    async def start_run(self, total_steps: int):
        """Signal the start of an agent run."""
        self.total_steps = total_steps
        self.completed_steps = 0
        self.current_step = None
        await self.broadcast("run_start", f"Starting agent run with {total_steps} steps", {
            "total_steps": total_steps
        })
        
    async def start_step(self, step_name: str, description: str):
        """Signal the start of a specific step."""
        self.current_step = step_name
        await self.broadcast("step_start", f"Starting: {description}", {
            "step_name": step_name,
            "description": description
        })
        
    async def update(self, message: str, data: Dict | None = None):
        """Send a general update message."""
        await self.broadcast("update", message, data)
        
    async def complete_step(self, step_name: str, result: Dict | None = None):
        """Signal the completion of a step."""
        self.completed_steps += 1
        await self.broadcast("step_complete", f"Completed: {step_name}", {
            "step_name": step_name,
            "result": result
        })
        
    async def error(self, message: str, error_data: Dict | None = None):
        """Signal an error occurred."""
        await self.broadcast("error", message, error_data)
        
    async def complete_run(self, success: bool, results: Dict | None = None):
        """Signal the completion of the entire run."""
        status = "successfully" if success else "with errors"
        await self.broadcast("run_complete", f"Agent run completed {status}", {
            "success": success,
            "results": results
        })
        self.current_step = None
        
    def get_history(self) -> List[Dict]:
        """Get the event history."""
        return list(self.history)

# Global broadcaster instance
broadcaster = RealtimeStatusBroadcaster()
