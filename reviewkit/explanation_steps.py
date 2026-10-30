"""Language-independent links from narrative blocks to already selected evidence."""


def step_location(step, default_id, functions):
    reference = step.get("reference", default_id)
    if not isinstance(reference, str) or reference not in functions:
        raise ValueError("Step reference must identify selected evidence")
    location = functions[reference]
    if "source_index" in step:
        index = step["source_index"]
        sources = location.get("sources", [])
        if type(index) is not int or not 0 <= index < len(sources):
            raise ValueError("Step source_index must select an existing source")
        location = sources[index]
    width = location["end_line"] - location["line"]
    offset = step.get("offset", 0)
    end = step.get("end_offset", offset if "offset" in step else width)
    if type(offset) is not int or type(end) is not int or not 0 <= offset <= end <= width:
        raise ValueError("Step offsets must stay inside the selected source range")
    return {
        "file": location["file"],
        "line": location["line"] + offset,
        "end_line": location["line"] + end,
    }
