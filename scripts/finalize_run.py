"""Always render the baseline report and seal all closed log/artifact files."""
import hashlib,json,os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'out';OUT.mkdir(exist_ok=True)
lock=json.loads((ROOT/'source-lock/LOCK.json').read_text())
accept=OUT/'analysis/acceptance.json';data=json.loads(accept.read_text()) if accept.is_file() else {}
inventory=json.loads((ROOT/'evidence/input-summary.json').read_text())
run_id=os.environ.get('GITHUB_RUN_ID')
url='https://github.com/'+os.environ.get('GITHUB_REPOSITORY','')+'/actions/runs/'+run_id if run_id else 'NOT_STARTED'
report=f'''# BASELINE_REPORT

This report concerns a pristine candidate baseline only. No Droidspaces feature compilation is authorized by its results.

| Required question | Result |
|---|---|
| Exact OEM source match | No: `7b9e94e37cfa` has not been obtained. |
| Candidate source | June 2025 / 6.1.138, companion commit `{lock['companion_common_commit']}`. |
| Full dependency lock | 20 Git project revisions, manifest `{lock['manifest_origin_commit']}`, superproject `{lock['superproject_commit']}`. Actual checkout/archive SHA256 requires source-verification.json. |
| Compilation | {data.get('compile_artifacts_present','NOT_VERIFIED_OR_NOT_RUN')} |
| Kernel release | {data.get('kernel_release','NOT_BUILT')} |
| Final config equals stock | {data.get('config_matches_stock_exactly','NOT_VERIFIED')} |
| Final config differences | {data.get('config_difference_count','NOT_VERIFIED')} |
| ABI/STG | {data.get('abi_stg','NOT_VERIFIED_OR_NOT_COMPLETED')} |
| Module variants checked against candidate | {data.get('module_variants_checked',0)} / 790 |
| Unique module names checked | {data.get('module_names_checked',0)} / 508 |
| Loaded names checked | {data.get('loaded_names_checked',0)} / 504 |
| Original protected GKI signature trust | UNVERIFIED |
| Vendor compatibility | NOT_ACCEPTED: requires all candidate CRC/export checks, ABI/layout, signature and configuration gates. |
| May enter Droidspaces feature build | NO — user review and unresolved gate resolution required. |

Run: {url}

## Evidence

- `analysis/source-verification.json`: actual project commits, Git tree/archive SHA256, protection files and executable hashes.
- `analysis/resolved-manifest.xml`, `logs/clang-version.log`, `logs/bazel-version.log`.
- `logs/bazel-build-and-abi.log`, `analysis/build-and-abi-exit-code.txt`.
- `analysis/final.config`, `analysis/config-diff.json`, `analysis/Module.symvers`.
- `analysis/module-variants-790.json`, `analysis/module-names-508.json`, `analysis/acceptance.json`.
- `SHA256SUMS.txt`: all available outputs and logs sealed after the build command has closed them.

Missing evidence remains unverified, even if other artifacts exist. A build failure, ABI difference, config difference, missing export or signature trust issue is not bypassed.

## Unresolved items

The candidate exactly matches a Google GKI module companion found on the device, not the OEM kernel commit. Preserve all stock module variants; the 57 source-policy protected GKI names do not prove current key trust. Default newly generated signing keys cannot be assumed to authorize the existing stock system_dlkm modules. CRC agreement alone does not prove structure layout or runtime hardware compatibility.

No device connection, flash, reboot, slot switch or boot/init_boot/vendor_boot/vbmeta write is performed by this toolkit.
'''
(OUT/'BASELINE_REPORT.md').write_text(report,encoding='utf-8')
lines=[]
for p in sorted(OUT.rglob('*')):
    if not p.is_file() or p.name=='SHA256SUMS.txt':continue
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    lines.append(h.hexdigest()+'  '+p.relative_to(OUT).as_posix())
(OUT/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Report and hashes written:',OUT)
