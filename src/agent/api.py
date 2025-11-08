"""FastAPI application for running the FDWA agent."""

from fastapi import FastAPI

from agent.graph import graph

app = FastAPI()

# Compile graphs without checkpointer
twitter_agent = graph.compile()


@app.post("/run")
async def run_agent(input_data: dict) -> dict:
    """Run the agent with the provided input.

    Args:
        input_data: Input dictionary for the agent.

    Returns:
        Result dictionary from agent execution.
    """
    result = twitter_agent.invoke(input_data)
    return result

