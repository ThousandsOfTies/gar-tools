# Linux Device Hardware Template

Default hardware definition CSV files for the Linux device / RasPi-compatible
target.

`GaplessAgentRuntime` copies these files into a local project `hardware/`
directory with:

```bash
gar hw init
```

The local `hardware/` directory is the project-specific override. These files
remain the target template source of truth.
