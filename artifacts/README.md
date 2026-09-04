# Radio State Snapshots

`artifacts/latest/` is the Git-tracked record of the most recently verified
state for each physical radio. It is a device-state record, not a generated
codeplug source and may differ from the current profile.

Each radio snapshot contains:

- `current.toml`: the decoded codeplug captured from the radio after a
  successful read-back verification.
- `reference.html`: a human-readable reference report for the corresponding
  configuration.
- `manifest.json`: capture provenance and SHA-256 checksums.

Update a snapshot only after reading the radio or after a write operation that
reports successful read-back verification. Copy the verified `current.toml`
and reference report into `artifacts/latest/<radio>/<instance>/`, update the
manifest, then commit the snapshot with the profile or operational change that
produced it.

Do not commit `.artifacts/`: it contains transient raw dumps, timestamped
captures, and operation logs retained only for local troubleshooting.