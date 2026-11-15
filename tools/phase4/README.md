# Phase 4 replay

These programs read existing files only. They do not use adb, modify a device, build a kernel, or alter the baseline.

The source preprocessor experiment is independently replayable with `.github/workflows/phase4-crc.yml` and `scripts/phase4_crc_repro.py` in this branch. It reads the original artifact from this same repository. Artifact retention is finite; preserve the existing local CI files.

The three binary-inspection scripts require the already-collected local project layout containing `muyu-gki-phase1`, `muyu-gki-phase3`, and `muyu-gki-phase4`. When downloading these scripts elsewhere, set `MUYU_PROJECT_ROOT` to that project's root. They are not clean-repository device probes.

Run binary inspection first, then module trust. Export extraction additionally uses the candidate ELF symbol-boundary JSON and existing candidate vmlinux/Image from the original CI. The local evidence archive preserves the boundary JSON, reachable genksyms types, full raw export tables and full BTF comparison records.

Public branch evidence contains derived summaries and exact input hashes. No stock boot image, private signing key, collected module binary or original CI input bundle is uploaded here.

Interpret `official_genksyms_c` in the CI summary as an intentionally hybrid diagnostic; only `complete_official_genksyms` is a matched historical tool build.
