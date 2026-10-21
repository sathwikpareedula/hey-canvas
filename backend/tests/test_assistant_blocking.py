import asyncio
import time

import pytest
from app.assistant.blocking_runner import run_orchestrator
from app.assistant_orchestration.models import AssistantModelInput
from app.assistant_orchestration.service import AcademicAssistantOrchestrator
from app.assistant_tools.models import (
    AssistantRequest,
    AssistantResponse,
    AssistantResponseBlock,
    ResponseBlockType,
)
from app.assistant_tools.service import AcademicToolService
from zoneinfo import ZoneInfo


class SlowProvider:
    def complete(self, model_input: AssistantModelInput) -> AssistantResponse:
        time.sleep(1.5)
        return AssistantResponse(
            status="ok",
            blocks=(
                AssistantResponseBlock(type=ResponseBlockType.TEXT, text="slow ok"),
            ),
            course_id=model_input.plan.course_id,
        )

    def stream(self, model_input: AssistantModelInput):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_run_orchestrator_does_not_block_event_loop(session) -> None:
    tools = AcademicToolService(session, academic_timezone=ZoneInfo("UTC"))
    orchestrator = AcademicAssistantOrchestrator(tools, provider=SlowProvider())
    request = AssistantRequest(query="hello", course_id="101")
    assistant_task = asyncio.create_task(run_orchestrator(orchestrator, request))
    await asyncio.sleep(0.1)
    loop_ok = asyncio.create_task(asyncio.sleep(0.05))
    await loop_ok
    response = await assistant_task
    assert response.blocks[0].text == "slow ok"
