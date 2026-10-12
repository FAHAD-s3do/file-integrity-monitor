# File Integrity Monitor

![File Integrity Monitor workflow](assets/workflow.svg)

One-shot SHA-256 baselines and JSON reports for added, modified and removed regular files.

**Fresh portfolio implementation • Python 3.10+ • Standard library only**

## Run

```bash
python3 --version
python3 monitor.py baseline /path/to/watched /path/outside/watched/baseline.json
python3 -m unittest discover -s tests -v
```

```bash
python3 monitor.py check /path/to/watched /path/outside/watched/baseline.json
```
Use `python3 examples/demo.py` for a self-contained temporary-directory demonstration.

## Implemented behavior

- Compares file content hash, size and Unix permission mode.
- Skips symlinks and non-regular files; detects ordinary file mutation during hashing using before/after metadata.
- Coverage errors turn absent files into unresolved absences instead of confirmed deletions.
- Refuses baseline overwrite and baseline placement inside the watched tree.
- Check exit codes: 0 no confirmed changes, 1 confirmed changes, 2 errors/unresolved absences.

## Scope and limitations

Not a daemon or trusted forensic acquisition tool. No ACLs, ownership, xattrs, signatures, remote storage or authenticated baseline. Parent-directory races and hostile privileged tampering are outside its guarantees; scan a quiescent trusted tree. Linux/POSIX target; O_NOFOLLOW support matters. Hashing large trees can be expensive; no size limit. Skipped paths make coverage incomplete even if check exits 0. Store and protect baselines separately; whoever can alter both baseline and target can hide changes. Root path must match the baseline.

## Validation

7 unit tests passed locally on Python 3.12.14. Synthetic CLI examples were executed and results are included under `examples/`. No customer data, historical lab results or production effectiveness is claimed. CI configuration is supplied; remote CI status must be checked after publishing.

## Files

- `monitor.py` — implementation and CLI.
- `tests/test_main.py` — regression and boundary tests.
- `examples/` — synthetic inputs and generated output.
- `assets/workflow.svg` — project-specific animation with reduced-motion support.
- `.github/workflows/ci.yml` — pinned-action CI.

## Safe operation

Use inputs and hosts you own or are authorized to assess. Review reports before publication; real files, headers and logs can contain sensitive information. These tools do not establish that a system is secure or compromised.
