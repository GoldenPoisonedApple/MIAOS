from typing import Any


def parse_bool(value: Any, key: str) -> bool:
	"""bool または "true" / "false"（大文字小文字は問わない）を bool に変換する。"""
	if isinstance(value, bool):
		return value
	normalized = str(value).strip().lower()
	if normalized == "true":
		return True
	if normalized == "false":
		return False
	raise ValueError(f"Invalid {key}={value!r}; expected true or false")
