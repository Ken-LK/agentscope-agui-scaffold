"""Pure business tool functions used by the scaffold registry."""

from __future__ import annotations

import ast
import operator
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_NOTES: dict[tuple[str, str], list[str]] = {}


def _eval_expression(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _eval_expression(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _eval_expression(node.left)
        right = _eval_expression(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 12:
            raise ValueError("Exponent is too large for the scaffold calculator.")
        return _BINARY_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_eval_expression(node.operand))
    raise ValueError("Only numeric expressions are supported.")


def calculate_expression(expression: str) -> dict:
    """Evaluate a safe arithmetic expression."""

    parsed = ast.parse(expression, mode="eval")
    result = _eval_expression(parsed)
    return {"expression": expression, "result": result}


def current_datetime(timezone_name: str = "Asia/Shanghai") -> dict:
    """Return the current time for a timezone."""

    now = datetime.now(ZoneInfo(timezone_name))
    return {
        "timezone": timezone_name,
        "iso": now.isoformat(timespec="seconds"),
        "display": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }


def search_scaffold_knowledge(
    query: str,
    *,
    source_path: str | Path | None = None,
    limit: int = 3,
) -> list[dict]:
    """Search the bundled scaffold knowledge file with a small lexical matcher."""

    path = (
        Path(source_path)
        if source_path
        else Path(__file__).parents[1] / "knowledge" / "scaffold_knowledge.md"
    )
    text = path.read_text(encoding="utf-8")
    terms = [term.lower() for term in re.findall(r"[\w\u4e00-\u9fff]+", query)]
    sections = re.split(r"\n(?=## )", text)
    scored: list[tuple[int, str, str]] = []
    for section in sections:
        title_match = re.match(r"##\s+(.+)", section)
        title = title_match.group(1).strip() if title_match else "Scaffold Knowledge"
        haystack = section.lower()
        score = sum(haystack.count(term) for term in terms)
        if score:
            scored.append((score, title, section.strip()))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {"title": title, "score": score, "content": content}
        for score, title, content in scored[:limit]
    ]


def remember_note(user_id: str, session_id: str, note: str) -> dict:
    """Store a short scaffold note in memory for this process."""

    key = (user_id, session_id)
    _NOTES.setdefault(key, []).append(note)
    return {"stored": True, "count": len(_NOTES[key]), "note": note}


def list_notes(user_id: str, session_id: str) -> list[str]:
    """List scaffold notes for this process."""

    return list(_NOTES.get((user_id, session_id), []))
