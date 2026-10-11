"""Tool schemas the model sees. Fields follow partner-b2b-app/lib/partner/mcp/schemas.ts."""

from __future__ import annotations


def _tool(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    parameters: dict = {"type": "object", "properties": properties}
    if required:
        parameters["required"] = required
    return {"name": name, "description": description, "parameters": parameters}


def _str(
    max_length: int | None = None,
    fmt: str | None = None,
    enum: list[str] | None = None,
    description: str | None = None,
    min_length: int | None = None,
) -> dict:
    schema: dict = {"type": "string"}
    if min_length is not None:
        schema["minLength"] = min_length
    if max_length is not None:
        schema["maxLength"] = max_length
    if fmt:
        schema["format"] = fmt
    if enum:
        schema["enum"] = enum
    if description:
        schema["description"] = description
    return schema


def _num(minimum: float | None = None, maximum: float | None = None, integer: bool = False) -> dict:
    schema: dict = {"type": "integer" if integer else "number"}
    if minimum is not None:
        schema["minimum"] = minimum
    if maximum is not None:
        schema["maximum"] = maximum
    return schema


_UUID = _str(fmt="uuid")
_URL = _str(fmt="uri")
_IDEM = _str(
    max_length=255,
    description="Idempotency-Key header. Any 1-255 visible ASCII characters. Required on edits unless dry_run.",
)

_VOICE_SETTINGS = {
    "type": "object",
    "properties": {
        "speed": {"type": "number"},
        "stability": {"type": "number"},
        "similarity_boost": {"type": "number"},
        "style": {"type": "number"},
    },
}

_SCENE_PHOTO = {
    "type": "object",
    "properties": {
        "url": _URL,
        "role": _str(enum=["setting", "product", "prop"]),
        "caption": _str(max_length=200),
    },
    "required": ["url"],
}

_RESOLUTION = _str(enum=["480p", "720p", "1080p", "480P", "768P", "1080P"])

_VIDEO_FIELDS = {
    "mode": _str(enum=["talking_head", "scenes", "moving_scene"]),
    "character_id": _UUID,
    "voice_id": {"type": "string"},
    "script": _str(max_length=4000),
    "audio_url": _URL,
    "video_idea": _str(max_length=2000),
    "first_frame_url": _URL,
    "first_frame_asset_id": _UUID,
    "resolution": _RESOLUTION,
    "video_mode": _str(enum=["reference", "text"]),
    "voice_mode": _str(enum=["voice", "none"]),
    "target_seconds": _num(minimum=5, maximum=60),
    "scene_photos": {"type": "array", "items": _SCENE_PHOTO, "maxItems": 12},
    "scene_elements": {"type": "array", "items": _SCENE_PHOTO, "maxItems": 12},
    "scene_prompt": _str(max_length=400),
    "scene_lines": {"type": "array", "items": _str(max_length=600), "minItems": 1, "maxItems": 15},
    "voice_settings": _VOICE_SETTINGS,
    "language": {"type": "string"},
    "use_dynamic_captions": {"type": "boolean"},
    "captions_language": {"type": "string"},
    "captions_position": _str(enum=["top", "center", "bottom"]),
    "topic": {"type": "string"},
    "audience": {"type": "string"},
    "expected_credits": _num(minimum=0, integer=True),
    "client_request_id": _UUID,
    "fast": {"type": "boolean"},
    "narration_mode": {"type": "string"},
}

SCHEMAS = {
    "estimate_video": _tool(
        "estimate_video",
        "Price a video request without queueing it",
        _VIDEO_FIELDS,
        ["mode"],
    ),
    "create_video": _tool(
        "create_video",
        "Queue a video generation job (talking_head or scenes)",
        {**_VIDEO_FIELDS, "idempotency_key": _IDEM},
        ["mode", "character_id"],
    ),
    "create_character": _tool(
        "create_character",
        "Create a character (clone from selfies, or invent from a description)",
        {
            "name": _str(max_length=120),
            "selfie_image_urls": {"type": "array", "items": _URL, "minItems": 1, "maxItems": 3},
            "edit_instructions": _str(max_length=500),
            "description": _str(max_length=2000),
            "reference_image_urls": {"type": "array", "items": _URL, "maxItems": 3},
            "recast_attempt": _num(minimum=1, integer=True),
        },
        ["name"],
    ),
    "clone_voice": _tool(
        "clone_voice",
        "Create a voice (clone from samples, or pick a studio voice)",
        {
            "name": _str(max_length=80),
            "sample_urls": {"type": "array", "items": _URL, "minItems": 1},
            "preview_language": {"type": "string"},
            "language": {"type": "string"},
            "gender": _str(enum=["female", "male"]),
            "studio_voice": {"type": "string"},
        },
        ["name"],
    ),
    "list_voices": _tool("list_voices", "List your voices", {}),
    "get_balance": _tool(
        "get_balance",
        "Credit balance and usage in a date range",
        {
            "from": _str(description="ISO date-time. Defaults to the first instant of the current UTC month."),
            "to": _str(description="ISO date-time. Defaults to now."),
        },
    ),
    "get_job": _tool("get_job", "Poll a job's status", {"workflowId": _str(min_length=1)}, ["workflowId"]),
    "get_scenes": _tool(
        "get_scenes",
        "The scenes of a finished video (use the indices with the edit endpoints)",
        {"workflowId": _str(min_length=1)},
        ["workflowId"],
    ),
    "fix_scene": _tool(
        "fix_scene",
        "Fix one scene (makes a new video)",
        {
            "workflowId": _str(min_length=1),
            "scene_index": _num(minimum=0, maximum=99, integer=True),
            "description": _str(max_length=500),
            "expected_credits": _num(minimum=0, integer=True),
            "client_request_id": _UUID,
            "dry_run": {"type": "boolean", "description": "Return the quote only."},
            "idempotency_key": _IDEM,
        },
        ["workflowId", "scene_index"],
    ),
    "edit_script": _tool(
        "edit_script",
        "Give scenes new lines in the video's voice (makes a new video)",
        {
            "workflowId": _str(min_length=1),
            "lines": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "properties": {
                        "scene_index": _num(minimum=0, maximum=99, integer=True),
                        "line": _str(max_length=600),
                    },
                    "required": ["scene_index", "line"],
                },
            },
            "expected_credits": _num(minimum=0, integer=True),
            "client_request_id": _UUID,
            "dry_run": {"type": "boolean"},
            "idempotency_key": _IDEM,
        },
        ["workflowId", "lines"],
    ),
    "fix_sound": _tool(
        "fix_sound",
        "Put a new voice take on a video (makes a new video)",
        {
            "workflowId": _str(min_length=1),
            "audio_url": _URL,
            "tts_asset_id": _UUID,
            "voice_id": {"type": "string"},
            "script": _str(max_length=4000),
            "voice_settings": _VOICE_SETTINGS,
            "language": {"type": "string"},
            "expected_credits": _num(minimum=0, integer=True),
            "client_request_id": _UUID,
            "dry_run": {"type": "boolean"},
            "idempotency_key": _IDEM,
        },
        ["workflowId"],
    ),
    "list_characters": _tool("list_characters", "List your characters", {}),
    "get_character": _tool("get_character", "Get a character", {"id": _UUID}, ["id"]),
    "delete_character": _tool("delete_character", "Delete a character", {"id": _UUID}, ["id"]),
    "regenerate_character": _tool(
        "regenerate_character",
        "Re-render a character's sheet with an optional tweak (same person)",
        {"id": _UUID, "edit_instructions": _str(max_length=500)},
        ["id"],
    ),
    "list_voice_presets": _tool("list_voice_presets", "List the studio voices", {}),
    "delete_voice": _tool(
        "delete_voice",
        "Delete a voice (for cloned voices this frees the clone slot)",
        {"id": _str(min_length=1)},
        ["id"],
    ),
    "reclone_voice": _tool(
        "reclone_voice",
        "Clone a voice again from new samples (gets a NEW voice_id)",
        {
            "id": _str(min_length=1),
            "sample_urls": {"type": "array", "items": _URL, "minItems": 1},
            "preview_language": {"type": "string"},
        },
        ["id", "sample_urls"],
    ),
    "synthesize_speech": _tool(
        "synthesize_speech",
        "Synthesize speech with one of your own voices",
        {
            "voice_id": {"type": "string"},
            "text": _str(max_length=5000),
            "language_code": {"type": "string"},
            "language": {"type": "string"},
            "voice_settings": _VOICE_SETTINGS,
        },
        ["voice_id", "text"],
    ),
    "create_first_frame": _tool(
        "create_first_frame",
        "Generate a 9:16 still of a character (a talking-head frame or a realistic photo for scenes)",
        {
            "character_id": _UUID,
            "scene_description": _str(max_length=2000),
            "kind": _str(enum=["talking_head", "moving_scene"]),
            "scene_prompt": _str(max_length=400),
            "scene_photos": {"type": "array", "items": _SCENE_PHOTO, "maxItems": 12},
            "script": _str(max_length=4000),
            "language": {"type": "string"},
        },
        ["character_id"],
    ),
    "plan_scenes": _tool(
        "plan_scenes",
        "Preview the scenes a script will become (free)",
        {
            "video_type": _str(enum=["talking_head", "scenes", "moving_scene", "normal_video"]),
            "script": _str(max_length=4000),
            "audio_duration_seconds": _num(maximum=60.5),
            "voice_mode": _str(enum=["voice", "none"]),
            "language": {"type": "string"},
        },
        ["video_type", "script"],
    ),
    "list_assets": _tool(
        "list_assets",
        "List everything you've generated",
        {
            "kind": _str(enum=["character_sheet", "first_frame", "tts_audio", "video"]),
            "limit": _num(integer=True),
            "offset": _num(integer=True),
        },
    ),
    "get_asset": _tool("get_asset", "Get one asset", {"id": _UUID}, ["id"]),
    "list_jobs": _tool(
        "list_jobs",
        "Paginated job history",
        {"limit": _num(integer=True), "offset": _num(integer=True)},
    ),
}
