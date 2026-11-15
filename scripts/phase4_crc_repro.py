#!/usr/bin/env python3
"""Phase 4: preprocessing and host genksyms only. Never build a kernel."""
import hashlib,json,os,re,shutil,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"phase4-results";OUT.mkdir(exist_ok=True)
WORK=ROOT/"phase4-work";WORK.mkdir(exist_ok=True)
BUNDLE=ROOT/"inputs/phase4-crc-inputs.tar.gz"
def run(args,**kw):
    return subprocess.run([str(x) for x in args],capture_output=True,**kw)
# Read the original artifact already retained by this same GitHub repository.
import io,urllib.request,zipfile
CI_ZIP=ROOT/"original-ci.zip"
if hashlib.sha256(CI_ZIP.read_bytes()).hexdigest()!="c4c49179a93518658c18a81f60d4f978f64cf2c5f6cd6517ab288828963ad9ab":
    raise RuntimeError("Original CI artifact digest mismatch")
BUNDLE.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(CI_ZIP) as z, tarfile.open(BUNDLE,"w:gz") as dest:
    records={}
    def add(name,data,mode=0o644):
        info=tarfile.TarInfo(name);info.size=len(data);info.mode=mode;info.mtime=0
        dest.addfile(info,io.BytesIO(data));records[name]={"path":name,"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)}
    for archive,select in [
      ("out/dist/kernel-headers.tar.gz",lambda n:n.startswith("include/") or n.startswith("arch/arm64/include/")),
      ("out/dist/modules_prepare_outdir.tar.gz",lambda n:n.startswith(("include/generated/","include/config/","arch/arm64/include/generated/")) or n in [".config","scripts/genksyms/genksyms"])]:
        with tarfile.open(fileobj=io.BytesIO(z.read(archive))) as t:
            for m in t:
                name=m.name.removeprefix("kernel-headers/").removeprefix("./")
                if m.isfile() and select(name):add(name,t.extractfile(m).read(),0o755 if name.endswith("/genksyms") else 0o644)
    for path in ["mm/swapfile.c","mm/internal.h","mm/swap.h"]:
        url="https://raw.githubusercontent.com/aosp-mirror-neo/kernel_common/0c3d559bcd85c64dae9c9c9687abbe5347fff3ad/"+path
        add(path,urllib.request.urlopen(url,timeout=90).read())
    add("official_swapfile.c",urllib.request.urlopen("https://raw.githubusercontent.com/MiCode/Xiaomi_Kernel_OpenSource/681e88870888dec258dd48b0ab8c908b303eb159/mm/swapfile.c",timeout=90).read())
    expected={}
    for line in z.read("out/analysis/Module.symvers").decode().splitlines():
        f=line.split()
        if len(f)>1 and f[1] in ["__page_file_index","add_swap_extent"]:expected[f[1]]=f[0]
    add("expected-candidate.json",json.dumps(expected).encode())
    inv=json.loads((ROOT/"inputs/stock-modules.json").read_text())
    cifs=next(x for x in inv["variants"] if x["name"]=="cifs")
    add("expected-stock.json",json.dumps({x:cifs["versions"][x] for x in expected}).encode())
    add("INPUT_MANIFEST.json",json.dumps(list(records.values()),indent=2).encode())

with tarfile.open(BUNDLE) as t:
    for m in t:
        if not m.isfile():continue
        target=WORK/m.name
        if not target.resolve().is_relative_to(WORK.resolve()):raise RuntimeError("Unsafe bundle path")
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(t.extractfile(m).read())
        target.chmod(m.mode)
for row in json.loads((WORK/"INPUT_MANIFEST.json").read_text()):
    if hashlib.sha256((WORK/row["path"]).read_bytes()).hexdigest()!=row["sha256"]:
        raise RuntimeError("Input hash mismatch "+row["path"])
clang=shutil.which("clang")
if not clang:raise RuntimeError("No clang preprocessor")
version=run([clang,"--version"]).stdout.decode()
(OUT/"clang-version.txt").write_text(version)
gen=WORK/"scripts/genksyms/genksyms"
base=(WORK/"mm/swapfile.c").read_text()
case_sources={
  "candidate":base,
  "without_unuse_export":base.replace("EXPORT_SYMBOL_GPL(unuse_swap_pte);",""),
  "without_page_swap_info_export":base.replace("EXPORT_SYMBOL_GPL(page_swap_info);",""),
  "without_both_added_exports":base.replace("EXPORT_SYMBOL_GPL(unuse_swap_pte);","").replace("EXPORT_SYMBOL_GPL(page_swap_info);",""),
  "official_c_with_candidate_headers":(WORK/"official_swapfile.c").read_text(),
}
# A source-level ordering control, not a proposed patch.
lines=base.splitlines();exports=[x for x in lines if re.fullmatch(r"EXPORT_SYMBOL(?:_GPL)?\(\w+\);",x)]
case_sources["reversed_export_order"]="\n".join(x for x in lines if x not in exports)+"\n"+"\n".join(reversed(exports))+"\n"
summary={"bundle_sha256":hashlib.sha256(BUNDLE.read_bytes()).hexdigest(),"clang":version,"genksyms_sha256":hashlib.sha256(gen.read_bytes()).hexdigest(),"cases":{}}
includes=["arch/arm64/include","arch/arm64/include/generated","include","arch/arm64/include/uapi","arch/arm64/include/generated/uapi","include/uapi","include/generated/uapi"]
flags=[clang,"--target=aarch64-linux-gnu","-E","-D__KERNEL__","-D__GENKSYMS__","-nostdinc"]
for inc in includes:flags+=["-I",WORK/inc]
for header in ["include/linux/compiler-version.h","include/linux/kconfig.h","include/linux/compiler_types.h"]:flags+=["-include",WORK/header]
flags+=['-DKBUILD_MODNAME="swapfile"','-DKBUILD_MODFILE="mm/swapfile"','-DKBUILD_BASENAME="swapfile"']
for name,source in case_sources.items():
    directory=OUT/name;directory.mkdir(exist_ok=True)
    # Remain beside internal.h/swap.h for quoted includes.
    casefile=WORK/"mm"/("phase4_"+name+".c");casefile.write_text(source)
    pp=run(flags+[casefile])
    (directory/"preprocessor.stderr").write_bytes(pp.stderr)
    (directory/"input.i").write_bytes(pp.stdout)
    row={"preprocess_exit":pp.returncode,"source_sha256":hashlib.sha256(source.encode()).hexdigest(),"preprocessed_sha256":hashlib.sha256(pp.stdout).hexdigest(),"command":[str(a) for a in flags+[casefile]]}
    if pp.returncode==0:
        gs=run([gen,"-T",directory/"types.symtypes","-r","/dev/null"],input=pp.stdout)
        (directory/"genksyms.stdout").write_bytes(gs.stdout);(directory/"genksyms.stderr").write_bytes(gs.stderr)
        vals=dict(re.findall(r"#SYMVER\s+(\w+)\s+(0x[0-9a-fA-F]+)",gs.stdout.decode()))
        row.update(genksyms_exit=gs.returncode,export_count=len(vals),target_crcs={s:vals.get(s) for s in ["__page_file_index","add_swap_extent"]})
    summary["cases"][name]=row

# Controlled historical-header experiment. Fetch source blobs sparsely, never build.
oldroot=ROOT/"phase4-official-sparse"
oldroot.mkdir(exist_ok=True)
for args in [
 ["git","init",oldroot],
 ["git","-C",oldroot,"remote","add","origin","https://github.com/MiCode/Xiaomi_Kernel_OpenSource.git"],
 ["git","-C",oldroot,"sparse-checkout","init","--cone"],
 ["git","-C",oldroot,"sparse-checkout","set","include","arch/arm64/include","mm","scripts/genksyms"],
 ["git","-C",oldroot,"fetch","--depth=1","--filter=blob:none","origin","681e88870888dec258dd48b0ab8c908b303eb159"],
 ["git","-C",oldroot,"checkout","--detach","FETCH_HEAD"],
]:
    proc=run(args)
    if proc.returncode:raise RuntimeError(proc.stderr.decode(errors="replace"))
summary["official_source_head"]=run(["git","-C",oldroot,"rev-parse","HEAD"]).stdout.decode().strip()
oldflags=[clang,"--target=aarch64-linux-gnu","-E","-D__KERNEL__","-D__GENKSYMS__","-nostdinc"]
for inc in includes:oldflags+=["-I",(WORK if "generated" in inc else oldroot)/inc]
oldflags+=["-I",WORK/"include"]
for header in ["include/linux/compiler-version.h","include/linux/kconfig.h","include/linux/compiler_types.h"]:oldflags+=["-include",oldroot/header]
oldflags+=['-DKBUILD_MODNAME="swapfile"','-DKBUILD_MODFILE="mm/swapfile"','-DKBUILD_BASENAME="swapfile"']
for name,source in {"official_c_with_official_headers":(oldroot/"mm/swapfile.c").read_text(),"candidate_c_with_official_headers":base}.items():
    directory=OUT/name;directory.mkdir(exist_ok=True)
    casefile=oldroot/"mm"/("phase4_"+name+".c");casefile.write_text(source)
    pp=run(oldflags+[casefile]);(directory/"input.i").write_bytes(pp.stdout);(directory/"preprocessor.stderr").write_bytes(pp.stderr)
    row={"preprocess_exit":pp.returncode,"preprocessed_sha256":hashlib.sha256(pp.stdout).hexdigest(),"command":[str(x) for x in oldflags+[casefile]]}
    if pp.returncode==0:
        gs=run([gen,"-T",directory/"types.symtypes","-r","/dev/null"],input=pp.stdout)
        (directory/"genksyms.stdout").write_bytes(gs.stdout);(directory/"genksyms.stderr").write_bytes(gs.stderr)
        vals=dict(re.findall(r"#SYMVER\s+(\w+)\s+(0x[0-9a-fA-F]+)",gs.stdout.decode()))
        row.update(genksyms_exit=gs.returncode,target_crcs={x:vals.get(x) for x in ["__page_file_index","add_swap_extent"]})
    summary["cases"][name]=row

expected=json.loads((WORK/"expected-candidate.json").read_text())
summary["expected_candidate"]=expected;summary["expected_stock"]=json.loads((WORK/"expected-stock.json").read_text())
summary["candidate_reproduces_ci"]=summary["cases"]["candidate"].get("target_crcs")==expected
(OUT/"SUMMARY.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps({"candidate_reproduces_ci":summary["candidate_reproduces_ci"],"cases":{n:{"preprocess_exit":r["preprocess_exit"],"crcs":r.get("target_crcs")} for n,r in summary["cases"].items()}},indent=2))
# Preserve diagnostic output even if exact reproduction needs another iteration.
if not summary["candidate_reproduces_ci"]:raise SystemExit(1)
