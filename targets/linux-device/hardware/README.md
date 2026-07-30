# Linux Device Hardware Template

Default hardware definition CSV files for the Linux device / RasPi-compatible
target.

From a registered product workspace, `GaplessAgentRuntime` copies these files
into that project's `hardware/` directory with:

```bash
gar hw init
```

The local `hardware/` directory is the project-specific override. These files
remain the target template source of truth.
