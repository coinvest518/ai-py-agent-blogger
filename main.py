"""Main entry point for Railway deployment."""

import uvicorn
from src.agent.api import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
