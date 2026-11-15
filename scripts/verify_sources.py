"""Verify a complete synced checkout against LOCK.json and record SHA256."""
import argparse,hashlib,json,subprocess
from pathlib import Path

def git(path,*args):return subprocess.check_output(['git','-C',str(path),*args],text=True).strip()
def normhash(p):return hashlib.sha256((p.read_text('utf-8').rstrip()+'\n').encode()).hexdigest()
def main():
    a=argparse.ArgumentParser();a.add_argument('--workspace',required=True);a.add_argument('--toolkit',required=True);a.add_argument('--out',required=True)
    args=a.parse_args();ws=Path(args.workspace).resolve();kit=Path(args.toolkit).resolve();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    lock=json.loads((kit/'source-lock/LOCK.json').read_text())
    if hashlib.sha256((kit/'source-lock/manifest.xml').read_bytes()).hexdigest()!=lock['manifest_sha256']:raise RuntimeError('Locked manifest SHA256 changed')
    rows=[]
    for project in lock['sources']:
        path=ws/project['path'];actual=git(path,'rev-parse','HEAD')
        if actual!=project['commit']:raise RuntimeError('Commit mismatch: '+project['path'])
        if git(path,'status','--porcelain','--untracked-files=no'):raise RuntimeError('Tracked source changes: '+project['path'])
        h=hashlib.sha256()
        with subprocess.Popen(['git','-C',str(path),'archive','--format=tar','HEAD'],stdout=subprocess.PIPE) as p:
            for b in iter(lambda:p.stdout.read(1024*1024),b''):h.update(b)
            if p.wait()!=0:raise RuntimeError('Source archive failed: '+project['path'])
        rows.append({**project,'archive_sha256':h.hexdigest(),'git_tree':git(path,'rev-parse','HEAD^{tree}')})
    expected={
        'common/BUILD.bazel':'evidence/candidate-common-BUILD.bazel',
        'common/arch/arm64/configs/gki_defconfig':'evidence/candidate-gki_defconfig',
        'common/android/abi_gki_protected_exports_aarch64':'source-lock/protected-exports.txt',
        'common/android/gki_aarch64_protected_modules':'source-lock/protected-modules.txt',
        'common/build.config.constants':'evidence/candidate-build.config.constants',
        'common/build.config.common':'evidence/candidate-build.config.common'}
    file_checks=[]
    for actual,snapshot in expected.items():
        if normhash(ws/actual)!=normhash(kit/snapshot):raise RuntimeError('Source protection/config changed: '+actual)
        file_checks.append({'path':actual,'sha256':hashlib.sha256((ws/actual).read_bytes()).hexdigest(),'normalized_matches_snapshot':True})
    constants=(ws/'common/build.config.constants').read_text()
    if 'CLANG_VERSION=r487747c' not in constants:raise RuntimeError('Incorrect toolchain release')
    build=(ws/'common/BUILD.bazel').read_text()
    for required in ['"kmi_symbol_list_strict_mode": True','"protected_exports_list": "android/abi_gki_protected_exports_aarch64"','"protected_modules_list": "android/gki_aarch64_protected_modules"']:
        if required not in build:raise RuntimeError('Required KMI protection missing')
    if not (ws/'common/android/abi_gki_aarch64.stg').is_file():raise RuntimeError('No upstream reference STG; do not disable ABI comparison')
    tool_hashes=[]
    for p in [ws/'prebuilts/clang/host/linux-x86/clang-r487747c/bin/clang',ws/'prebuilts/clang/host/linux-x86/clang-r487747c/bin/ld.lld',ws/'prebuilts/bazel/linux-x86_64/bazel']:
        if not p.is_file():raise RuntimeError('Pinned executable not present: '+str(p))
        h=hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        tool_hashes.append({'path':str(p.relative_to(ws)),'sha256':h.hexdigest()})
    (out/'source-verification.json').write_text(json.dumps({'sources':rows,'source_files':file_checks,'tool_binaries':tool_hashes},indent=2)+'\n')
    print('Verified all',len(rows),'project commits, source archives, protection files and tool binaries.')
if __name__=='__main__':main()
