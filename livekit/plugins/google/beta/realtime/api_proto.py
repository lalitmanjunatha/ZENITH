from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Union

from google.genai import types

LiveAPIModels = Literal[
    "gemini-3-flash-preview",
    "gemini-2.5-flash-native-audio-preview-12-2025",
    "gemini-2.0-flash",
    "gemini-2.0-flash-live-001",
    "gemini-2.5-flash-preview-native-audio-dialog",
    "gemini-2.5-flash-exp-native-audio-thinking-dialog",
]

Voice = Literal["Puck", "Charon", "Kore", "Fenrir", "Aoede", "Leda", "Oru", "Zephyr"]


ClientEvents = Union[
    types.ContentListUnion,
    types.ContentListUnionDict,
    types.LiveClientContentOrDict,
    types.LiveClientRealtimeInput,
    types.LiveClientRealtimeInputOrDict,
    types.LiveClientToolResponseOrDict,
    types.FunctionResponseOrDict,
    Sequence[types.FunctionResponseOrDict],
]
