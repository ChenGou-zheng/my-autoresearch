# Project

Describe the host project that this autoresearch harness should improve.

## Objective

Write one concrete objective for this project.

## In-Scope Files

List files and directories the agent should read or modify. Include only the
parts of the parent project that matter for the current research loop.

- `path/to/file_or_directory`

## Protected Files

List files and directories that must not be modified without explicit user
permission.

- `path/to/protected_file`

## Primary Metric

Define the main metric used to judge whether an attempt improves the project.
Include the exact command that computes it and where the output is written.

```bash
# command that evaluates the primary metric
```

## Secondary Signals

List proxy metrics, logs, visual checks, or smoke tests that can guide work but
do not replace the primary metric.

## Commands

Canonical commands for this project:

```bash
# setup or install

# run a smoke test

# run the main experiment

# evaluate the result
```

## Output Paths

Document generated artifacts, logs, checkpoints, reports, or other outputs that
the agent should inspect or preserve.

## Results TSV

Use this header unless the project needs different fields:

```text
commit	primary_metric	secondary_metric	runtime_or_cost	status	description
```

Status values are `keep`, `discard`, `crash`, `blocked`, and `continue`.

## Notes

Add project-specific constraints, environment notes, or decision rules here.
