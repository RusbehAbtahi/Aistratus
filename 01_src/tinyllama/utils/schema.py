"""Data-validation schemas for TinyLlama."""
from pydantic import BaseModel, root_validator, ValidationError


MAX_PROMPT_BYTES = 6 * 1024  # 6 KB
MIN_PROMPT_BYTES = 1
IDLE_MIN = 1
IDLE_MAX = 30


class PromptReq(BaseModel):
    """Request body for /infer and Lambda Router."""
    prompt: str
    idle: int

    @root_validator
    def _validate(cls, values):
        prompt: str = values.get("prompt")
        idle: int = values.get("idle")

        # prompt size check (UTF-8 bytes)
        size = len(prompt.encode("utf-8")) if isinstance(prompt, str) else 0
        if not (MIN_PROMPT_BYTES <= size <= MAX_PROMPT_BYTES):
            raise ValueError(
                f"prompt must be 1-{MAX_PROMPT_BYTES // 1024} KB UTF-8; got {size} B"
            )

        # idle range check
        if not (IDLE_MIN <= idle <= IDLE_MAX):
            raise ValueError(f"idle must be {IDLE_MIN}-{IDLE_MAX}; got {idle}")

        return values


# so tests can import the exception class directly
ValidationError = ValidationError
