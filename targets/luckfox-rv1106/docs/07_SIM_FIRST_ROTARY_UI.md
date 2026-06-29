# Sim-First Rotary UI (\u25c0 \u25cf \u25b6)

This is a simulator-first control UI that mimics the rotary encoder behavior
before hardware integration.

## What it provides

- Terminal UI with `\u25c0 \u25cf \u25b6` indicator.
- NAV/EDIT mode switch with center press.
- Parameter focus/change events as JSONL log.

## Run

targets/luckfox-rv1106/runtime/bin/gar-luckfox-sim-rotary-ui

## Controls

- Left/Right arrow (or `a` / `d`): rotate
- Enter (or `s`): center press
- `q`: quit

## Event log

Default output:

- `/tmp/gar-rotary-events.jsonl`

Override path:

GAR_ROTARY_EVENT_LOG=/tmp/my-rotary.jsonl \
targets/luckfox-rv1106/runtime/bin/gar-luckfox-sim-rotary-ui

Unicode off (ASCII fallback):

GAR_ROTARY_UI_UNICODE=0 \
targets/luckfox-rv1106/runtime/bin/gar-luckfox-sim-rotary-ui

## Intended next integration

1. Feed JSONL events into ISP control state machine.
2. Reflect active item and value in local mini display renderer.
3. Broadcast current state as overlay/status for remote stream viewer.

This keeps simulator and real-device control semantics aligned while preserving
the zero-diff app policy.

## Control loop mode (recommended)

Run UI + simulated ISP state machine together:

targets/luckfox-rv1106/runtime/bin/gar-luckfox-sim-control-loop

Outputs:

- event log: `/tmp/gar-rotary-events.jsonl`
- current state: `/tmp/gar-isp-state.json`
- applied updates: `/tmp/gar-isp-apply.jsonl`

Watch applied updates live:

tail -f /tmp/gar-isp-apply.jsonl
