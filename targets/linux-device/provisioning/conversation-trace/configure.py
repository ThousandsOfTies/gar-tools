"""Root-only, temporary loopback Node inspection. No restart or saved payloads."""

import base64
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen


def trace(settings):
    if os.geteuid() != 0:
        raise RuntimeError("root_required")
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{1,128}\.service", settings["service"]):
        raise ValueError("invalid_service")
    if (
        not isinstance(settings["durationMs"], int)
        or not 1000 <= settings["durationMs"] <= 60000
    ):
        raise ValueError("invalid_duration")
    module = Path(settings["module"]).resolve()
    if not module.is_file() or module.suffix != ".cjs":
        raise ValueError("invalid_runtime_module")
    if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]{0,127}", settings["prototypeExport"]):
        raise ValueError("invalid_prototype_export")
    function = base64.b64decode(settings["traceFunctionBase64"], validate=True)
    if len(function) > 32768:
        raise ValueError("trace_function_too_large")
    source = base64.b64decode(settings["observerBase64"], validate=True)
    if len(source) > 32768:
        raise ValueError("observer_too_large")
    if not Path(settings["node"]).is_file() or not os.access(settings["node"], os.X_OK):
        raise ValueError("node_unavailable")
    pid = int(
        subprocess.check_output(
            ["systemctl", "show", settings["service"], "-p", "MainPID", "--value"],
            text=True,
            timeout=5,
        )
    )
    command = (Path("/proc") / str(pid) / "cmdline").read_bytes()
    entrypoint = Path(settings["entrypoint"])
    if not entrypoint.is_absolute() or not any(
        Path(arg.decode()).resolve() == entrypoint.resolve()
        for arg in command.split(b"\0")
        if arg.startswith(b"/") and arg.endswith(b".cjs")
    ):
        raise RuntimeError("unexpected_application_process")
    with socket.socket() as check:
        check.settimeout(0.2)
        if check.connect_ex(("127.0.0.1", 9229)) == 0:
            raise RuntimeError("inspector_already_in_use")
    os.kill(pid, signal.SIGUSR1)
    targets = None
    for _ in range(30):
        try:
            with urlopen("http://127.0.0.1:9229/json/list", timeout=1) as response:
                targets = json.load(response)
            break
        except OSError:
            time.sleep(0.1)
    if not targets:
        raise RuntimeError("inspector_unavailable")
    endpoint = targets[0].get("webSocketDebuggerUrl", "")
    if not endpoint.startswith("ws://127.0.0.1:9229/"):
        raise RuntimeError("unexpected_inspector_endpoint")
    with tempfile.TemporaryDirectory(prefix="gar-conversation-trace-") as directory:
        script = Path(directory) / "observe.cjs"
        script.write_bytes(source)
        os.chmod(script, 0o600)
        job = subprocess.run(
            [settings["node"], str(script)],
            input=json.dumps(
                {
                    "url": endpoint,
                    "module": str(module),
                    "prototypeExport": settings["prototypeExport"],
                    "traceFunctionBase64": settings["traceFunctionBase64"],
                    "durationMs": settings["durationMs"],
                    "closeInspector": True,
                }
            ),
            capture_output=True,
            text=True,
            timeout=85,
        )
    try:
        report = json.loads(job.stdout)
    except ValueError:
        raise RuntimeError("invalid_trace_result") from None
    if job.returncode or not report.get("ok"):
        raise RuntimeError("conversation_trace_failed")
    return {"ok": True, "state": "observed", "trace": report["trace"]}


if __name__ == "__main__":
    print("__GAR_WIFI_INPUT__", flush=True)
    try:
        report = trace(json.loads(sys.stdin.readline()))
    except Exception as error:
        message = str(error)
        report = {
            "ok": False,
            "state": "failed",
            "error": message if re.fullmatch("[a-z_]+", message) else "trace_failed",
        }
    print("__GAR_WIFI_RESULT__" + json.dumps(report), flush=True)
