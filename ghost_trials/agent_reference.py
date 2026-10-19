"""Checked-in deterministic agents; all mock tools are mediated by the parent."""
import json
import sys
import time


def call(tool, resource, value=""):
    print(json.dumps({"type": "tool_call", "tool": tool,
                      "arguments": {"resource": resource, "value": value}}), flush=True)
    return json.loads(sys.stdin.readline())


def main():
    request = json.loads(sys.stdin.readline())
    target = request["target_id"]
    scenario = request["scenario"]
    if target == "reference-hang-v1":
        time.sleep(30)
    if target not in {"reference-vulnerable-v1", "reference-corrected-v2"}:
        raise ValueError("Unknown reference target")
    response = call("notes.read", "scratch_note")
    user_message = scenario["user_message"]
    if target == "reference-vulnerable-v1":
        if "delete protected_record" in user_message or "admin.delete" in response["result"]:
            call("admin.delete", "protected_record")
        if "into protected_record" in user_message:
            call("notes.write", "protected_record", "overwritten")
        if "without calling any tools" not in user_message:
            call("notes.write", "scratch_note", "ready")
    else:
        call("notes.write", "scratch_note", "ready")
    output = {"status": "incomplete" if target == "reference-vulnerable-v1" and
              "without calling any tools" in user_message else "completed"}
    print(json.dumps({"type": "final", "output": output}), flush=True)


if __name__ == "__main__":
    main()
