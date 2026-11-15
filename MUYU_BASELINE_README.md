# Muyu pristine GKI baseline

This project builds an unmodified June 2025 6.1.138 candidate. It does not
enable Droidspaces or apply its SYSVIPC patch. The patch is checked only.
No device access, flash, reboot or slot change is implemented.

## Source lock

- OEM target: `7b9e94e37cfa` — not obtained; this is not an exact OEM rebuild.
- Google companion source: `0c3d559bcd85c64dae9c9c9687abbe5347fff3ad`.
- Manifest: `848f8dbd7fc7c40a884b614ad29f5d89199ddaff`.
- Historical superproject: `c5fd854d46f3fe29b89a80e5f2cf3bc643c64f20`.
- Kleaf/build: `06f7c2ac33c6d9927613bafd95def11d18924f5e`.
- Clang release: `r487747c`; all 20 project revisions are in `source-lock/LOCK.json`.

The manifest pins every project. CI verifies the primary AOSP checkouts,
records SHA256 for their Git archives and actual Clang/LLD/Bazel executables,
and preserves the resolved manifest. A floating branch head is never substituted
if a locked commit cannot be fetched.

## Start the authorized cloud baseline

Run `Start-Baseline.ps1` in a normal Windows PowerShell. It uses GitHub CLI,
requests sign-in if needed, creates the user's dedicated `muyu-gki-baseline`
fork of Xieansecn/buildGKI-6.1.138-android14, and pushes only
`baseline/muyu-gki`. That branch's push starts the new baseline workflow.
It enables Actions only in that dedicated fork. It does not modify the upstream
repository or any unrelated repository.

GitHub CLI needs permission to create/push a repository and workflow files.
The existing ChatGPT GitHub connection can inspect repositories and edit files,
but has no exposed fork/repository-creation or new-run-dispatch tool. The local
execution sandbox cannot use/validate the normal-terminal GitHub CLI login or reach Git endpoints.

## What remains unchanged

- `common` is the original companion commit with no tracked modifications.
- Original GKI defconfig, protected exports/modules lists, strict KMI mode and
  the STG reference stay intact.
- ThinLTO is requested; CFI, MODVERSIONS and 4KB pages are required in the
  actual config extracted from the resulting Image.
- The upstream `kernel_aarch64_abi_dist` target both builds the distribution
  and executes its enforced STG comparison. No ABI update target is run.

## Stock compatibility input

`inputs/stock-modules.json` contains all 790 file variants and their imported
CRCs, exported symbols/CRCs, dependencies, signature status and source groups.
It covers all 508 unique names, including the 504 loaded names. Device images,
private signing keys and user data are not included in this control project.

Protected policy classification follows the pinned source list: 57 GKI names,
114 file variants; 6 GKI variants are outside that protected list. Runtime
signature trust is not inferred from policy membership or signature presence.

## Results

Actions always retains `out/` and `source-lock/`, including closed logs and
SHA256SUMS. A failure is preserved as a failure. The final config and all 790
variants are checked even if the STG comparison fails after producing Image.

An exact config difference is reported, not silently approved. CRC matching
alone cannot produce full acceptance. `allow_droidspaces_features` remains
false, pending user review of BASELINE_REPORT.md and unresolved source,
configuration, structure and module signature trust gates.

The first run of this toolkit has not yet occurred until an Actions run URL
and artifacts exist. Local parser/regression checks are not kernel compilation.

The launcher uses explicit argument arrays and separate expected-missing-resource probes, validated with seven native-process checks under Windows PowerShell 5.1.
