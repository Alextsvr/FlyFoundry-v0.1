# Persistence

Mechanism: orphan branch `flyfoundry-state` holding `manifest.json` and up to 3 `ckpt_NNNNNN.json.gz`. Chosen because it is free, durable
(unlike Actions cache: evicted after 7 days; artifacts: expire), versioned, and needs no external service.

Integrity: gzip(JSON{schema, payload, payload_sha256}); manifest lists file sha256 and has its own hash; arrays are stored bit-exactly
(base64 of raw bytes); RNG states are stored. Every save is read back and verified; the CLI also checks reload equals in-memory state.
Invariants checked on load: all runners at the same generation, evals == pop_size x generations, history length == generation, config identity
hash equals the stored one (immutable configuration), benchmark-world fingerprint equals the stored one.

Failure behaviour: missing state → exit 4 (fresh start only with `--allow-fresh`; the workflow allows it only for the first ever run or
`fresh_start=true`, otherwise it fails with "state lost"); corrupt newest → fall back to newest valid with warning in log, summary and report;
nothing valid → exit 3; config drift → exit 5. The state branch is force-pushed as a single commit each run; the previous version is
not retained in git history (the 3 checkpoints inside the branch provide the rollback window).

Privacy: in a public repository the state branch is public. Contents are synthetic. If real evidence or business data is ever added, use a
private repository (free Actions minutes are limited there) and do not publish Pages.
