"""Read-only static analysis of the supplied ZIP's extracted Image.
Never imports or executes anything supplied inside the ZIP.
Requires previous Phase 1/3/4 snapshot inputs; writes new evidence only.
"""
from pathlib import Path
import collections, gzip, hashlib, importlib.util, json, os, re, struct, tarfile, zipfile, sys
from cryptography import x509
HERE=Path(__file__).resolve().parent
PROJECT=Path(os.environ.get('MUYU_PROJECT_ROOT',str(HERE.parent)))
ROOT=PROJECT/'muyu-droidspaces-reference'; OUT=ROOT/'evidence'; OUT.mkdir(parents=True,exist_ok=True)
def mod(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def sha(b):return hashlib.sha256(b).hexdigest()
def save(name,data):(OUT/name).write_text(json.dumps(data,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')
binary=mod('p4_binary',PROJECT/'muyu-gki-phase4/inspect_binary_evidence.py')
exports=mod('p4_exports',PROJECT/'muyu-gki-phase4/extract_image_export_crcs.py')
trust=mod('p4_trust',PROJECT/'muyu-gki-phase4/inspect_module_trust.py')
if len(sys.argv)>1:
    archive=Path(sys.argv[1]);inventory=[]
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if item.is_dir():continue
            data=z.read(item);target=ROOT/'extracted'/item.filename
            assert target.resolve().is_relative_to((ROOT/'extracted').resolve())
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            inventory.append({'path':item.filename,'size':len(data),'sha256':sha(data)})
    save('reproduction-zip-inventory.json',{'zip_sha256':sha(archive.read_bytes()),'files':inventory})
b=(ROOT/'extracted/Image').read_bytes()
installer=OUT/'installer';installer.mkdir(exist_ok=True)
for path in ['anykernel.sh','tools/ak3-core.sh','META-INF/com/google/android/update-binary','META-INF/com/google/android/updater-script']:
    (installer/Path(path).name).write_bytes((ROOT/'extracted'/path).read_bytes())
markers=['v4.1.0-82d85024@ReSukiSU','susfs is initialized! version: v2.1.0','disagrees about version of symbol %s','But ignore']
save('binary-markers.json',[{'text':s,'offset':b.find(s.encode())} for s in markers])
fdt=[];pos=0
while True:
    pos=b.find(b'\xd0\x0d\xfe\xed',pos)
    if pos<0:break
    if pos+40<=len(b):
        h=struct.unpack_from('>10I',b,pos);_,total,st,ss,rv,ver,last,_,sstr,sst=h
        if 40<=total<=len(b)-pos and ver>=16 and last<=ver and st<total and ss<total and rv<total and ss+sstr<=total and st+sst<=total:fdt.append({'offset':pos,'total_size':total,'header':h})
    pos+=4
save('fdt-scan.json',{'valid_flattened_device_tree_candidates':fdt,'method':'scan FDT magic and validate v16+ header bounds; absence is not an exhaustive disassembly proof'})
start=b.find(b'IKCFG_ST');end=b.find(b'IKCFG_ED',start)
assert start>=0 and end>start
cfg=gzip.decompress(b[start+8:end]);(OUT/'reference.config').write_bytes(cfg)
binary.NAMES.update({'user_struct','ucounts','nsproxy','ipc_namespace','pid_namespace'})
btf=binary.btf(b) # reads Phase 4 type-name list only
btf.pop('reachable_named_types',None) # retain targeted layouts, not unrelated dependency inventory
binary.OUT=OUT;certs=binary.certs(b)
save('reference-image.json',{'image_sha256':sha(b),'size':len(b),'arm64_magic':b[56:60].hex(),'arm64_header_image_size':struct.unpack_from('<Q',b,16)[0],'linux_banners':[m.group().decode(errors='replace') for m in re.finditer(rb'Linux version [^\0\r\n]{1,1200}',b)],'config_sha256':sha(cfg),'config_offset':start,'certificates':certs,'btf':btf,'crc_bypass_string_present':b'disagrees about version of symbol %s, But ignore' in b,'usual_crc_warning_present':b'disagrees about version of symbol %s' in b})
try:
    recovered=exports.recover(b,'__page_file_index');save('reference-raw-export-crcs.json',recovered)
    (OUT/'reference-exports.tsv').write_text('symbol\tkind\tcrc\n'+''.join(x['name']+'\t'+x['kind']+'\t'+x['crc']+'\n' for x in recovered['exports']),encoding='utf-8')
    save('reference-export-table-layout.json',{k:v for k,v in recovered.items() if k!='exports'})
    checks=[]
    for anchor in ['page_swap_info','unuse_swap_pte']:
        alt=exports.recover(b,anchor)
        assert alt['exports']==recovered['exports']
        checks.append(anchor)
    save('raw-table-validation.json',{'anchors':['__page_file_index']+checks,'all_recover_identical':True,'limits':'No reference vmlinux or Module.symvers; matching anchors do not substitute for full ELF/STG ABI validation.'})
    actual={x['name']:x['crc'] for x in recovered['exports']}
    comparisons={}
    for label in ['stock','candidate']:
        old=json.loads((PROJECT/f'muyu-gki-phase4/evidence/{label}-raw-export-crcs.json').read_text(encoding='utf-8'))
        known={x['name']:x['crc'] for x in old['exports']};common=set(actual)&set(known)
        comparisons[label]={'common':len(common),'same_crc':sum(actual[k]==known[k] for k in common),'crc_differences':[{'symbol':k,'reference':actual[k],label:known[k]} for k in sorted(common) if actual[k]!=known[k]],'missing_from_reference':sorted(set(known)-set(actual)),'extra_in_reference':sorted(set(actual)-set(known))}
    metadata=json.loads((PROJECT/'muyu-gki-phase3/inputs/stock-modules.json').read_text(encoding='utf-8'))
    module_rows=[]
    for r in metadata['variants']:
        missing=[s for s in r['versions'] if s not in actual]
        mismatches=[{'symbol':s,'module':v,'reference':actual[s]} for s,v in r['versions'].items() if s in actual and v.lower().removeprefix('0x')!=actual[s]]
        if mismatches:module_rows.append({'name':r['name'],'sha256':r['sha256'],'file':r['file'],'mismatches':mismatches})
    save('reference-crc-comparison.json',{'method':'Phase 4 PREL32 parser, independently cross-checked on candidate ELF/Module.symvers in Phase 4; no reference ELF/Module.symvers available. Partial raw-table comparison, not ABI acceptance.','reference_export_count':len(actual),'comparisons':comparisons,'stock_module_crc_conflict_variants':module_rows,'note':'Module imports absent from vmlinux can be provided by other modules; absence alone is not an unresolved-symbol verdict.'})
except Exception as ex:save('reference-crc-comparison.json',{'error':repr(ex),'status':'UNKNOWN'})
configs={label:Path(p).read_text(encoding='utf-8') for label,p in {'reference':OUT/'reference.config','stock':PROJECT/'muyu-gki-phase3/evidence/stock-full-config.txt','candidate':PROJECT/'muyu-gki-phase3/evidence/run-3-artifact/out/analysis/final.config'}.items()}
def config(text):
    d={}
    for l in text.splitlines():
        if l.startswith('CONFIG_') and '=' in l:k,v=l.split('=',1);d[k]=v
        elif l.startswith('# CONFIG_') and l.endswith(' is not set'):d[l[2:-11]]='n'
    return d
cs={k:config(v) for k,v in configs.items()};keys=sorted(set().union(*(set(c) for c in cs.values())))
save('config-comparison.json',{'config_sha256':{k:sha(v.encode()) for k,v in configs.items()},'rows':[{'symbol':key,**{k:v.get(key,'MISSING') for k,v in cs.items()}} for key in keys if len(set(v.get(key,'MISSING') for v in cs.values()))>1]})
wanted='SYSVIPC POSIX_MQUEUE IPC_NS PID_NS USER_NS UTS_NS NET_NS CGROUPS CGROUP_PIDS CGROUP_FREEZER CGROUP_BPF DEVTMPFS DEVTMPFS_MOUNT SECCOMP NAMESPACES MODVERSIONS MODULE_SIG MODULE_SIG_FORCE MODULE_SIG_PROTECT SECCOMP_FILTER CGROUP_DEVICE MEMCG CFS_BANDWIDTH TMPFS TMPFS_XATTR TMPFS_POSIX_ACL PROC_FS SYSFS EPOLL SIGNALFD TIMERFD INOTIFY_USER FHANDLE KVM VETH BRIDGE OVERLAY_FS ARM64_CONTPTE XIAOMI_DMABUF_HUGETLB'.split()
save('feature-config-matrix.json',[{'symbol':'CONFIG_'+k,**{label:c.get('CONFIG_'+k,'MISSING') for label,c in cs.items()}} for k in wanted])
cert_objects=[x509.load_der_x509_certificate((OUT/('certificate-'+r['sha256']+'.der')).read_bytes()) for r in certs]
checks=[]
with tarfile.open(PROJECT/'muyu-gki-phase1/phase2/muyu-readonly-20261115-173854/modules-01/files.tar') as t:
    for m in t:
        if not m.isfile() or not m.name.endswith('.ko'):continue
        data=t.extractfile(m).read();checks.append({'file':m.name,'sha256':sha(data),'certificate_verifications':[trust.verify(data,c) for c in cert_objects]})
save('reference-key-stock-module-tests.json',{'scope':'CMS cryptography against recovered reference public certificates only; no kernel loader test','modules':checks})
# Keep BTF padding placement and unchanged field offsets explicit.
stock_btf=json.loads((PROJECT/'muyu-gki-phase4/evidence/stock-image-inspection.json').read_text(encoding='utf-8'))['btf']
st=next(t for t in stock_btf['selected_structs'] if t['name']=='task_struct')
rt=next(t for t in btf['selected_structs'] if t['name']=='task_struct')
def named(t):return {m['name']:(m['bit_offset'],m['bitfield_size'],m['type_label']) for m in t['members'] if m['name'] and not m['name'].startswith('android_kabi_reserved')}
sa,ra=named(st),named(rt)
save('task-padding-comparison.json',{'stock_bytes':st['size_or_type'],'reference_bytes':rt['size_or_type'],'reference_members_near_padding':[m for m in rt['members'] if 28700<=m['bit_offset']<=29400],'stock_members_near_padding':[m for m in st['members'] if 28700<=m['bit_offset']<=29400],'named_nonreserve_field_differences':[{'member':k,'stock':sa.get(k),'reference':ra.get(k)} for k in sorted(set(sa)|set(ra)) if sa.get(k)!=ra.get(k)],'limitation':'Anonymous union contents and vendor use of padding still require source/semantic audit.'})
print(json.dumps({'certificates':certs,'btf_type_count':btf['type_count'] if btf else None,'reference_exports':len(actual) if 'actual' in locals() else None,'crc_summary':{k:{a:c[a] for a in ['common','same_crc']} for k,c in comparisons.items()} if 'comparisons' in locals() else None,'config_changes_vs_candidate':sum(cs['reference'].get(k,'MISSING')!=cs['candidate'].get(k,'MISSING') for k in keys),'signature_tests':len(checks)},indent=2))
