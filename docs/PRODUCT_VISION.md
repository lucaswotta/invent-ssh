# Product Scope and Design Principles

## Purpose

`invent-ssh` collects hardware inventory from Linux machines over SSH without installing endpoint agents or requiring an external database server.

## Design Principles

1. **Input portability**: Target lists are standard `.xlsx`, `.xlsm`, or `.csv` files with arbitrary asset metadata columns.
2. **Bounded concurrency**: At most `max_workers` SSH connections run concurrently. A circuit breaker aborts the run if the first 10 consecutive connections fail with zero reachable hosts.
3. **Read-only target probe**: Each target receives a single read-only shell command bounded by `ssh_timeout`.
4. **Neutral analytics**: The `Parque` view presents factual hardware distributions (`NVMe`, `SSD`, `HDD`, RAM capacity tiers, Linux distributions, and counts per location) without automated upgrade judgments.
5. **Local snapshot history**: Completed runs are stored in a local SQLite database (`snapshots.db`) to enable field-by-field comparisons across collection dates.
