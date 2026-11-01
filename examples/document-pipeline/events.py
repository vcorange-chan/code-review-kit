"""Fictional event-driven document view; used as source evidence, not executed by Tutor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ViewState:
    phase: str = "idle"
    request_id: str | None = None
    text: str = ""
    error: str = ""


def reduce_event(state: ViewState, event: dict) -> ViewState:
    kind = event["kind"]
    if kind == "start":
        return ViewState("loading", event["request_id"])
    if kind == "cancel":
        return ViewState()
    if state.phase != "loading" or event.get("request_id") != state.request_id:
        return state
    if kind == "parsed":
        return ViewState("ready", state.request_id, text=event["text"])
    if kind == "failed":
        return ViewState("failed", state.request_id, error=event["message"])
    return state


def view_label(state: ViewState) -> str:
    labels = {"idle": "Choose a document", "loading": "Reading document",
              "ready": "Document ready", "failed": "Reading failed"}
    return labels[state.phase]
