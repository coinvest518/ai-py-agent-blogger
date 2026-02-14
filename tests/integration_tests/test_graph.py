import pytest

from agent import graph

pytestmark = pytest.mark.anyio


@pytest.mark.langsmith
async def test_agent_simple_passthrough() -> None:
    inputs = {"message": "Hello, how are you?"}
    res = await graph.ainvoke(inputs)
    assert res is not None
    assert "blog_status" in res
