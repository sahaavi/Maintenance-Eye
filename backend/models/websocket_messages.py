"""Typed server-to-client WebSocket message contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def _dump(message: Any) -> dict[str, Any]:
    return {"type": message.type, **message.model_dump(exclude_unset=True)}


class StatusMessage(BaseModel):
    type: Literal["status"] = "status"
    data: str
    session_id: str | None = None


class AudioMessage(BaseModel):
    type: Literal["audio"] = "audio"
    data: str
    mime_type: str


class TextMessage(BaseModel):
    type: Literal["text"] = "text"
    data: str


class TranscriptInputMessage(BaseModel):
    type: Literal["transcript_input"] = "transcript_input"
    data: str


class TranscriptOutputMessage(BaseModel):
    type: Literal["transcript_output"] = "transcript_output"
    data: str


class TurnCompleteMessage(BaseModel):
    type: Literal["turn_complete"] = "turn_complete"
    data: str = ""


class InterruptedMessage(BaseModel):
    type: Literal["interrupted"] = "interrupted"
    data: str = "Agent interrupted by user input"


class ConfirmationRequestMessage(BaseModel):
    type: Literal["confirmation_request"] = "confirmation_request"
    data: dict[str, Any]


class ConfirmationResultPayload(BaseModel):
    action_id: str
    status: Literal["confirmed", "rejected", "corrected"]
    corrected_data: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    execution_status: Literal["succeeded", "failed"] | None = None
    execution_error: str | None = None


class ConfirmationResultMessage(BaseModel):
    type: Literal["confirmation_result"] = "confirmation_result"
    data: ConfirmationResultPayload


class WorkOrderMessage(BaseModel):
    type: Literal["work_order"] = "work_order"
    data: dict[str, Any]


class MediaCardDetail(BaseModel):
    label: str
    value: str


class MediaCardPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    description: str | None = None
    image_url: str
    details: list[MediaCardDetail] = Field(default_factory=list)
    action_link: str | None = None


class MediaCardMessage(BaseModel):
    type: Literal["media_card"] = "media_card"
    data: MediaCardPayload


class SessionSummaryPayload(BaseModel):
    session_id: str
    findings_count: int
    confirmation_stats: dict[str, Any]


class SessionSummaryMessage(BaseModel):
    type: Literal["session_summary"] = "session_summary"
    data: SessionSummaryPayload


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    data: str


def status_message(data: str, session_id: str | None = None) -> dict[str, Any]:
    if session_id is None:
        return _dump(StatusMessage(data=data))
    return _dump(StatusMessage(data=data, session_id=session_id))


def audio_message(data: str, mime_type: str) -> dict[str, Any]:
    return _dump(AudioMessage(data=data, mime_type=mime_type))


def text_message(data: str) -> dict[str, Any]:
    return _dump(TextMessage(data=data))


def transcript_input_message(data: str) -> dict[str, Any]:
    return _dump(TranscriptInputMessage(data=data))


def transcript_output_message(data: str) -> dict[str, Any]:
    return _dump(TranscriptOutputMessage(data=data))


def turn_complete_message() -> dict[str, Any]:
    return _dump(TurnCompleteMessage(data=""))


def interrupted_message(data: str = "Agent interrupted by user input") -> dict[str, Any]:
    return _dump(InterruptedMessage(data=data))


def confirmation_request_message(data: dict[str, Any]) -> dict[str, Any]:
    return _dump(ConfirmationRequestMessage(data=data))


def confirmation_result_message(
    action_id: str,
    status: Literal["confirmed", "rejected", "corrected"],
    *,
    corrected_data: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
    execution_status: Literal["succeeded", "failed"] | None = None,
    execution_error: str | None = None,
) -> dict[str, Any]:
    payload_args: dict[str, Any] = {
        "action_id": action_id,
        "status": status,
    }
    if corrected_data is not None:
        payload_args["corrected_data"] = corrected_data
    if execution is not None:
        payload_args["execution"] = execution
    if execution_status is not None:
        payload_args["execution_status"] = execution_status
    if execution_error is not None:
        payload_args["execution_error"] = execution_error
    return _dump(ConfirmationResultMessage(data=ConfirmationResultPayload(**payload_args)))


def work_order_message(data: dict[str, Any]) -> dict[str, Any]:
    return _dump(WorkOrderMessage(data=data))


def media_card_message(data: dict[str, Any]) -> dict[str, Any]:
    return _dump(MediaCardMessage(data=MediaCardPayload.model_validate(data)))


def session_summary_message(
    session_id: str,
    findings_count: int,
    confirmation_stats: dict[str, Any],
) -> dict[str, Any]:
    return _dump(
        SessionSummaryMessage(
            data=SessionSummaryPayload(
                session_id=session_id,
                findings_count=findings_count,
                confirmation_stats=confirmation_stats,
            )
        )
    )


def error_message(data: str) -> dict[str, Any]:
    return _dump(ErrorMessage(data=data))
