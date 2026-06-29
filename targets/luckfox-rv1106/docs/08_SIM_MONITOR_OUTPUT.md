# Sim Monitor Output (Dummy)

This provides a simulator-first dummy monitor output for Luckfox workflow.

It reads ISP state JSON and renders a pseudo-screen frame.

## Script

- `runtime/bin/gar-luckfox-sim-monitor`

## Inputs / Outputs

- Input state: `/tmp/gar-isp-state.json`
- Output frame: `/tmp/gar-monitor-frame.txt`

## Run in terminal

targets/luckfox-rv1106/runtime/bin/gar-luckfox-sim-monitor --terminal

## Run as frame writer only

targets/luckfox-rv1106/runtime/bin/gar-luckfox-sim-monitor

## One-shot render

targets/luckfox-rv1106/runtime/bin/gar-luckfox-sim-monitor --once

## Recommended 3-terminal flow

1. Terminal A: state engine + rotary UI

targets/luckfox-rv1106/runtime/bin/gar-luckfox-sim-control-loop

2. Terminal B: monitor output dummy

targets/luckfox-rv1106/runtime/bin/gar-luckfox-sim-monitor --terminal

3. Terminal C: observe apply log

tail -f /tmp/gar-isp-apply.jsonl

This setup gives a simulator-first path for rotary control -> ISP state ->
monitor output without hardware display.
