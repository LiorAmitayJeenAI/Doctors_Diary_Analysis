"""Schedule-clock parsing and weekly-hours publication for Calendar Context & Baseline."""

from __future__ import annotations

import re
from datetime import datetime, time


def parse_schedule_time(value):
    """Return ``{"formatted", "minutes"}`` or None when the boundary is empty.

    Raises ValueError when a value is present but is not a schedule clock.
    Accepted forms are packed HHMM (``800``, ``1330``), ``HH:MM`` / ``HH:MM:SS``,
    an ISO or space-separated timestamp, and an Excel day fraction in ``(0, 1)``.
    """
    def clock(hour, minute):
        return {"formatted": f"{hour:02d}:{minute:02d}", "minutes": hour * 60 + minute}

    if isinstance(value, datetime):
        parsed = value.time().replace(microsecond=0)
        return clock(parsed.hour, parsed.minute)
    if isinstance(value, time):
        parsed = value.replace(microsecond=0)
        return clock(parsed.hour, parsed.minute)

    if value is None:
        text = None
    else:
        text = str(value).strip()
        if text.endswith(".0") and text[:-2].isdigit():
            text = text[:-2]
        text = text or None
    if text is None or text in {"0", "00", "000", "0000"}:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None

    clock_match = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
    if clock_match:
        hour, minute = int(clock_match.group(1)), int(clock_match.group(2))
        if hour > 23 or minute > 59:
            raise ValueError(f"Invalid schedule time '{text}'.")
        return clock(hour, minute)

    try:
        number = float(text.replace(",", ""))
    except Exception:
        number = None
    if number is not None and number == 0:
        return None
    if number is not None and 0 < number < 1:
        total_minutes = int(round(number * 24 * 60)) % (24 * 60)
        hour, minute = divmod(total_minutes, 60)
        return clock(hour, minute)

    digits = text
    if digits.endswith(".0") and digits[:-2].isdigit():
        digits = digits[:-2]
    if digits.isdigit() and 1 <= len(digits) <= 4:
        packed = digits.zfill(4)
        hour, minute = int(packed[:2]), int(packed[2:])
        if hour > 23 or minute > 59:
            raise ValueError(f"Invalid schedule time '{text}'.")
        return clock(hour, minute)
    if digits.isdigit() and 5 <= len(digits) <= 6:
        packed = digits.zfill(6)
        hour, minute, second = int(packed[:2]), int(packed[2:4]), int(packed[4:6])
        if hour > 23 or minute > 59 or second > 59:
            raise ValueError(f"Invalid schedule time '{text}'.")
        return clock(hour, minute)
    raise ValueError(f"Invalid schedule time '{text}'.")


def resolve_weekly_interval(freq, daily_minutes, warnings):
    """Use a weekly interval when a worked row has no numeric frequency.

    Negative numeric frequencies stay unresolved. ``0`` and ``1`` are already
    weekly before this helper runs.
    """
    resolved = dict(freq or {})
    interval = resolved.get("interval_weeks")
    if not daily_minutes or interval:
        return resolved, interval
    raw = resolved.get("raw")
    raw_text = "" if raw is None else str(raw).strip()
    if raw_text.startswith("-") and raw_text[1:].isdigit():
        return resolved, None
    resolved["interval_weeks"] = 1
    resolved["occurrences_per_week"] = 1.0
    resolved["type"] = "weekly"
    resolved["assumed_weekly_because_frequency_unparsed"] = True
    warnings.append(
        "Schedule frequency is missing or not numeric; weekly recurrence was assumed."
    )
    return resolved, 1


def published_weekly_totals(parsed_positive_shift, weekly_minutes):
    """Hide a zero total unless at least one shift actually contributed minutes."""
    if not parsed_positive_shift or not weekly_minutes:
        return None, None
    minutes = round(float(weekly_minutes), 3)
    return minutes, round(minutes / 60.0, 3)


def patch_baseline_source(code: str) -> str:
    """Insert the helpers into the live Calendar Context & Baseline component."""
    if (
        "return parse_schedule_time(value)" in code
        and "resolve_weekly_interval(freq, daily_minutes, row_warnings)" in code
        and "weekly_hours_value" in code
    ):
        return _replace_parser_function(code)
    if "def parse_schedule_time(" not in code:
        if "\nimport re\n" not in f"\n{code}":
            if "import math\n" not in code:
                raise ValueError("Baseline source is missing the math import anchor")
            code = code.replace("import math\n", "import math\nimport re\n", 1)
        helper_source = (
            _function_source(parse_schedule_time)
            + "\n\n"
            + _function_source(resolve_weekly_interval)
            + "\n\n"
            + _function_source(published_weekly_totals)
            + "\n\n\n"
        )
        anchor = "class CalendarContextBaseline(Component):\n"
        if code.count(anchor) != 1:
            raise ValueError("Expected one CalendarContextBaseline class")
        code = code.replace(anchor, helper_source + anchor, 1)

    code = _replace_method(
        code,
        "_time",
        "    def _time(self, value):\n        return parse_schedule_time(value)\n\n",
    )
    old_init = (
        "        weekly_minutes = 0.0\n"
        "        weekly_regular_segment_time_units = 0.0 if regular_segment_minutes else None\n"
    )
    new_init = (
        "        weekly_minutes = 0.0\n"
        "        parsed_positive_shift = False\n"
        "        weekly_regular_segment_time_units = 0.0 if regular_segment_minutes else None\n"
    )
    if code.count(old_init) != 1:
        raise ValueError("Expected one weekly-minutes initializer")
    code = code.replace(old_init, new_init, 1)

    old_frequency = (
        "            freq = self._frequency(row[\"frequency\"], row_warnings)\n"
        "            interval = freq.get(\"interval_weeks\")\n"
        "            weekly_equiv_minutes = daily_minutes / interval if interval else None\n"
        "            if interval:\n"
        "                intervals.append(interval)\n"
        "                weekly_minutes += weekly_equiv_minutes\n"
    )
    new_frequency = (
        "            freq = self._frequency(row[\"frequency\"], row_warnings)\n"
        "            freq, interval = resolve_weekly_interval(freq, daily_minutes, row_warnings)\n"
        "            weekly_equiv_minutes = daily_minutes / interval if interval else None\n"
        "            if daily_minutes:\n"
        "                parsed_positive_shift = True\n"
        "            if interval:\n"
        "                intervals.append(interval)\n"
        "                if weekly_equiv_minutes:\n"
        "                    weekly_minutes += weekly_equiv_minutes\n"
    )
    if code.count(old_frequency) != 1:
        raise ValueError("Expected one weekly-frequency accumulation block")
    code = code.replace(old_frequency, new_frequency, 1)

    old_publish = (
        "        cycle = reduce(math.lcm, intervals, 1) if intervals and len(intervals) == len(schedule_rows) else None\n"
    )
    new_publish = (
        "        weekly_minutes_value, weekly_hours_value = published_weekly_totals(\n"
        "            parsed_positive_shift, weekly_minutes\n"
        "        )\n"
        "        if schedule_rows and not parsed_positive_shift:\n"
        "            warnings.append(\n"
        "                \"Weekly working hours were not published because no schedule shift could be parsed.\"\n"
        "            )\n"
        "        elif schedule_rows and parsed_positive_shift and not weekly_minutes:\n"
        "            warnings.append(\n"
        "                \"Weekly working hours were not published because schedule frequency could not be applied.\"\n"
        "            )\n"
        "\n"
        "        cycle = reduce(math.lcm, intervals, 1) if intervals and len(intervals) == len(schedule_rows) else None\n"
    )
    if code.count(old_publish) != 1:
        raise ValueError("Expected one schedule-cycle publication anchor")
    code = code.replace(old_publish, new_publish, 1)

    old_fields = (
        "                \"weekly_equivalent_working_minutes\": round(weekly_minutes, 3),\n"
        "                \"weekly_equivalent_working_hours\": round(weekly_minutes / 60.0, 3),\n"
    )
    new_fields = (
        "                \"weekly_equivalent_working_minutes\": weekly_minutes_value,\n"
        "                \"weekly_equivalent_working_hours\": weekly_hours_value,\n"
    )
    if code.count(old_fields) != 1:
        raise ValueError("Expected one weekly-hours output field pair")
    return code.replace(old_fields, new_fields, 1)


def _replace_parser_function(code: str) -> str:
    current = _function_source(parse_schedule_time)
    pattern = re.compile(
        r"def parse_schedule_time\(value\):\n(?:.*\n)*?(?=\ndef |\nclass )",
    )
    updated, count = pattern.subn(lambda _match: current + "\n", code, count=1)
    if count != 1:
        raise ValueError("Expected one parse_schedule_time function to refresh")
    return updated


def _function_source(function) -> str:
    import inspect

    return inspect.getsource(function).rstrip() + "\n"


def _replace_method(code: str, name: str, replacement: str) -> str:
    pattern = re.compile(
        rf"    def {name}\(self, value\):\n(?:        .*\n)*?\n(?=    def )",
    )
    updated, count = pattern.subn(replacement, code, count=1)
    if count != 1:
        raise ValueError(f"Expected one {name} method to replace")
    return updated
