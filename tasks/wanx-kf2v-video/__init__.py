#region generated meta
import typing
class Inputs(typing.TypedDict):
    model: typing.Literal["wan2.2-kf2v-flash", "wanx2.1-kf2v-plus"]
    first_frame_url: str
    last_frame_url: str
    prompt: str | None
    negative_prompt: str | None
    resolution: typing.Literal["480P", "720P", "1080P"]
    prompt_extend: bool
    watermark: bool
    seed: float | None
class Outputs(typing.TypedDict):
    video_url: typing.NotRequired[str]
    task_id: typing.NotRequired[str]
    original_prompt: typing.NotRequired[str]
    actual_prompt: typing.NotRequired[str]
#endregion

from oocana import Context
import httpx
import asyncio


async def main(params: Inputs, context: Context) -> Outputs:
    """Generate video from first and last frame images using Wanx API."""

    # Get OOMOL token for API authentication
    token = await context.oomol_token()

    base_url = "https://fusion-api.oomol.com/v1/wanx-kf2v-video"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Prepare request payload
    payload: dict[str, typing.Any] = {
        "model": params["model"],
        "firstFrameURL": params["first_frame_url"],
        "lastFrameURL": params["last_frame_url"],
        "resolution": params["resolution"],
        "promptExtend": params["prompt_extend"],
        "watermark": params["watermark"]
    }

    # Add optional parameters
    if params.get("prompt"):
        payload["prompt"] = params["prompt"]
    if params.get("negative_prompt"):
        payload["negativePrompt"] = params["negative_prompt"]
    if params.get("seed") is not None:
        payload["seed"] = params["seed"]

    async with httpx.AsyncClient(timeout=300.0) as client:
        # Step 1: Submit task
        context.report_progress(10)
        submit_response = await client.post(
            f"{base_url}/submit",
            headers=headers,
            json=payload
        )
        submit_response.raise_for_status()
        submit_data = submit_response.json()

        if not submit_data.get("success"):
            raise RuntimeError(f"Failed to submit task: {submit_data}")

        session_id = submit_data["sessionID"]
        context.report_progress(20)

        # Step 2: Poll for task completion
        max_attempts = 300  # 10 minutes max (300 * 2 seconds)
        attempt = 0

        while attempt < max_attempts:
            await asyncio.sleep(2)  # Poll every 2 seconds

            state_response = await client.get(
                f"{base_url}/state/{session_id}",
                headers=headers
            )
            state_response.raise_for_status()
            state_data = state_response.json()

            if not state_data.get("success"):
                raise RuntimeError(f"Failed to get task state: {state_data}")

            state = state_data["state"]
            progress = state_data.get("progress", 0)

            # Report progress (20% to 80% based on task progress)
            context.report_progress(20 + int(progress * 0.6))

            if state == "completed":
                break
            elif state == "failed":
                raise RuntimeError(f"Task failed: {state_data}")

            attempt += 1

        if attempt >= max_attempts:
            raise TimeoutError("Task did not complete within the expected time")

        context.report_progress(90)

        # Step 3: Get final result
        result_response = await client.get(
            f"{base_url}/result/{session_id}",
            headers=headers
        )
        result_response.raise_for_status()
        result_data = result_response.json()

        if not result_data.get("success"):
            raise RuntimeError(f"Failed to get task result: {result_data}")

        data = result_data["data"]
        context.report_progress(100)

        return {
            "video_url": data["videoURL"],
            "task_id": data["taskId"],
            "original_prompt": data["origPrompt"],
            "actual_prompt": data["actualPrompt"]
        }
