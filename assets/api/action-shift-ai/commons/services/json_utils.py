import json
from typing import Any


def sanitize_json_with_control_chars(raw: str) -> str:
    out: list[str] = []
    in_string = False
    escape = False

    for ch in raw:
        if in_string:
            if escape:
                out.append(ch)
                escape = False
                continue

            if ch == "\\":
                out.append(ch)
                escape = True
                continue

            if ch == '"':
                out.append(ch)
                in_string = False
                continue

            if ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            else:
                o = ord(ch)
                if o < 0x20:
                    out.append(f"\\u{o:04x}")
                else:
                    out.append(ch)
        else:
            out.append(ch)
            if ch == '"':
                in_string = True
                escape = False

    return "".join(out)


def loads_json_with_sanitization(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(sanitize_json_with_control_chars(raw))
