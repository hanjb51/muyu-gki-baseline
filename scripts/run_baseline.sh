#!/usr/bin/env bash
set -euo pipefail
kit=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work="$kit/workspace"
results="$kit/out"
mkdir -p "$work" "$results/logs" "$results/analysis" "$results/dist"
export LC_ALL=C.UTF-8
exec > >(tee -a "$results/logs/full-build.log") 2>&1
printf 'Pristine baseline only. No device access or Droidspaces enablement.\n'
date -u --iso-8601=seconds
df -h "$kit"
python3 - "$kit" <<'PY'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1]);lock=json.loads((p/'source-lock/LOCK.json').read_text())
assert hashlib.sha256((p/'tools/repo').read_bytes()).hexdigest()==lock['repo_launcher_sha256']
PY
cd "$work"
# This dedicated control repository carries the fully pinned manifest.
: "${GITHUB_REPOSITORY:?Run inside the prepared dedicated GitHub Actions repository}"
: "${GITHUB_SHA:?Control commit must be immutable}"
python3 "$kit/tools/repo" init \
  -u "https://github.com/${GITHUB_REPOSITORY}.git" -b "$GITHUB_SHA" \
  -m source-lock/manifest.xml --depth=1 --no-use-superproject \
  --repo-url=https://gerrit.googlesource.com/git-repo \
  --repo-rev=d7c431b9968d928373fe9b463a51d304d3b2c48a
python3 "$kit/tools/repo" sync -c -j4 --no-clone-bundle --no-tags
python3 "$kit/tools/repo" manifest -r -o "$results/analysis/resolved-manifest.xml"
python3 "$kit/scripts/verify_sources.py" --workspace "$work" --toolkit "$kit" --out "$results/analysis"
prebuilts/clang/host/linux-x86/clang-r487747c/bin/clang --version | tee "$results/logs/clang-version.log"
tools/bazel version | tee "$results/logs/bazel-version.log"
git -C common apply --check --verbose "$kit/evidence/sysvipc.patch" |& tee "$results/logs/sysvipc-check-only.log"
# The patch is NOT applied; common and gki_defconfig remain pristine.
tools/bazel query '//common:kernel_aarch64_abi_dist' | tee "$results/logs/abi-target-query.log"
set +e
tools/bazel run --config=stamp --lto=thin //common:kernel_aarch64_abi_dist -- --dist_dir="$results/dist" |& tee "$results/logs/bazel-build-and-abi.log"
abi_rc=${PIPESTATUS[0]}
set -e
printf '%s\n' "$abi_rc" > "$results/analysis/build-and-abi-exit-code.txt"
analysis_rc=1
if [[ -f "$results/dist/Image" ]]; then
  common/scripts/extract-ikconfig "$results/dist/Image" > "$results/analysis/final.config"
  tools/bazel cquery --config=stamp --lto=thin //common:kernel_aarch64 --output=files > "$results/analysis/cquery-kernel-files.txt"
  python3 - "$results" "$work" <<'PY'
from pathlib import Path
import hashlib,shutil,sys
out=Path(sys.argv[1]);work=Path(sys.argv[2]);possible=list((out/'dist').glob('*Module.symvers'))
for line in (out/'analysis/cquery-kernel-files.txt').read_text().splitlines():
    p=work/line
    if p.name.endswith('Module.symvers') and p.is_file():possible.append(p)
if not possible:raise RuntimeError('No complete Module.symvers output; vmlinux.symvers is not a replacement')
hashes={hashlib.sha256(p.read_bytes()).hexdigest() for p in possible}
if len(hashes)!=1:raise RuntimeError('Conflicting Module.symvers candidates')
shutil.copyfile(possible[0],out/'analysis/Module.symvers')
PY
  set +e
  python3 "$kit/scripts/check_baseline.py" --dist "$results/dist" --analysis "$results/analysis" --toolkit "$kit" --abi-exit "$abi_rc"
  analysis_rc=$?
  set -e
fi
# No source baselines, symbol lists, protected files or defconfig may be rewritten.
python3 "$kit/tools/repo" forall -c 'test -z "$(git status --porcelain --untracked-files=no)"'
python3 - "$results" <<'PY'
from pathlib import Path
import hashlib,sys
r=Path(sys.argv[1]);lines=[]
for p in sorted(r.rglob('*')):
    if not p.is_file() or p.name=='SHA256SUMS.txt' or 'logs' in p.relative_to(r).parts:continue
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    lines.append(h.hexdigest()+'  '+p.relative_to(r).as_posix())
(r/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n')
PY
if [[ "$abi_rc" -ne 0 ]]; then exit "$abi_rc"; fi
exit "$analysis_rc"
