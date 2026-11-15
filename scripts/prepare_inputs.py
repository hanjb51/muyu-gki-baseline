"""Prepare frozen source metadata and all stock module variants, offline only."""
import collections,configparser,hashlib,json,re,struct,tarfile,xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'muyu-gki-phase1'/'phase2'
def write(path,obj):
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

tree=json.loads((ROOT/'evidence/superproject-tree.json').read_text('utf-8'))
revisions={x['path']:x['sha'] for x in tree['tree'] if x['type']=='commit'}
manifest=ET.fromstring((ROOT/'evidence/original-manifest.xml').read_bytes())
manifest.find('remote').set('fetch','https://android.googlesource.com/')
manifest.find('default').attrib.pop('revision',None)
manifest.find('superproject').set('revision','c5fd854d46f3fe29b89a80e5f2cf3bc643c64f20')
sources=[]
for project in manifest.findall('project'):
    path=project.get('path');revision=revisions.pop(path)
    project.set('revision',revision)
    # Fetch immutable objects without depending on historical branch availability.
    project.attrib.pop('upstream',None)
    project.attrib.pop('dest-branch',None)
    sources.append({'path':path,'name':project.get('name'),'commit':revision,
                    'url':'https://android.googlesource.com/'+project.get('name'),
                    'archive_sha256':'PENDING_CI_SYNC'})
if revisions:raise RuntimeError('Unmapped superproject entries: '+str(revisions))
ET.indent(manifest,space='  ')
manifest_path=ROOT/'source-lock/manifest.xml'
ET.ElementTree(manifest).write(manifest_path,encoding='utf-8',xml_declaration=True)
repo_tool=ROOT/'tools/repo'
lock={'policy':'Pristine upstream companion GKI baseline; no Droidspaces patch or configuration change applied.',
      'oem_exact_commit_available':False,'oem_requested_commit_prefix':'7b9e94e37cfa',
      'companion_common_commit':'0c3d559bcd85c64dae9c9c9687abbe5347fff3ad',
      'manifest_origin_commit':'848f8dbd7fc7c40a884b614ad29f5d89199ddaff',
      'superproject_commit':'c5fd854d46f3fe29b89a80e5f2cf3bc643c64f20',
      'manifest_origin_branch':'common-android14-6.1-2025-06',
      'manifest_sha256':digest(manifest_path),'sources':sources,
      'repo_tool_commit':'d7c431b9968d928373fe9b463a51d304d3b2c48a','repo_launcher_sha256':digest(repo_tool),
      'clang_release':'r487747c','clang_prebuilt_commit':next(x['commit'] for x in sources if x['path']=='prebuilts/clang/host/linux-x86'),
      'bazel_prebuilt_commit':next(x['commit'] for x in sources if x['path']=='prebuilts/bazel/linux-x86_64'),
      'bazel_runtime_version':'PENDING_CI_EXECUTION',
      'sysvipc_patch_sha256':digest(ROOT/'evidence/sysvipc.patch'),
      'stock_config_sha256':digest(ROOT/'evidence/stock-full-config.txt'),
      'required_build_configuration':{'CONFIG_MODVERSIONS':'y','CONFIG_LTO_CLANG_THIN':'y','CONFIG_CFI_CLANG':'y','CONFIG_ARM64_4K_PAGES':'y','CONFIG_ANDROID_KABI_RESERVE':'y','CONFIG_MODULE_SIG':'y','CONFIG_MODULE_SIG_ALL':'y','CONFIG_MODULE_SIG_PROTECT':'y','CONFIG_TRIM_UNUSED_KSYMS':'y'},
      'must_remain_disabled':['CONFIG_SYSVIPC','CONFIG_POSIX_MQUEUE','CONFIG_PID_NS','CONFIG_IPC_NS','CONFIG_USER_NS','CONFIG_DEVTMPFS','CONFIG_NETFILTER_XT_MATCH_ADDRTYPE','CONFIG_CFS_BANDWIDTH','CONFIG_CGROUP_PIDS']}
write('source-lock/LOCK.json',lock)

def elf_exports(data):
    shoff=struct.unpack_from('<Q',data,40)[0];n=struct.unpack_from('<H',data,60)[0]
    sections=[struct.unpack_from('<IIQQQQIIQQ',data,shoff+i*64) for i in range(n)]
    symbols={}
    for section in sections:
        if section[1]!=2:continue
        table=sections[section[6]];strings=data[table[4]:table[4]+table[5]]
        for pos in range(section[4],section[4]+section[5],24):
            ni,info,other,index,value,size=struct.unpack_from('<IBBHQQ',data,pos)
            name=strings[ni:].split(b'\0')[0].decode('utf-8','replace')
            symbols[name]=(index,value)
    exports={}
    for name in symbols:
        if not name.startswith('__ksymtab_'):continue
        symbol=name.removeprefix('__ksymtab_');crc=None;namespace=''
        entry=symbols.get('__crc_'+symbol)
        if entry:
            index,value=entry
            if index==0xfff1:crc=f'{value&0xffffffff:08x}'
            elif 0<index<len(sections):
                sec=sections[index]
                if value+4<=sec[5]:crc=f'{struct.unpack_from("<I",data,sec[4]+value)[0]:08x}'
        ns=symbols.get('__kstrtabns_'+symbol)
        if ns and 0<ns[0]<len(sections):
            sec=sections[ns[0]];namespace=data[sec[4]+ns[1]:sec[4]+sec[5]].split(b'\0')[0].decode('utf-8','replace')
        exports[symbol]={'crc':crc,'namespace':namespace}
    return exports

protected_paths=(ROOT/'source-lock/protected-modules.txt').read_text().splitlines()
protected={Path(p).stem.replace('-','_') for p in protected_paths if p.strip()}
gki={Path(p).stem.replace('-','_') for p in re.findall(r'"([^"]+\.ko)"',(ROOT/'source-lock/gki-modules.bzl').read_text())}
loaded={line.split()[0] for line in (OLD/'muyu-readonly-20261115-173854/loaded-modules.txt').read_text().splitlines() if re.match(r'^\w+\s+\d+\s+\d+',line)}
rows=[]
for folder,group in [('modules-00','vendor_dlkm'),('modules-01','system_dlkm')]:
    d=OLD/'muyu-readonly-20261115-173854'/folder
    info={m['file']:m for m in json.loads((d/'module-inspection.json').read_text('utf-8'))}
    canonical=json.loads((d/'manifest.json').read_text('utf-8'))['canonical']
    with tarfile.open(d/'files.tar') as t:
        for member in t:
            if not member.isfile() or not member.name.endswith('.ko'):continue
            path=canonical+'/'+member.name.removeprefix('./');record=info[path]
            data=t.extractfile(member).read();record['exports']=elf_exports(data);record['source_group']=group
            rows.append(record)
cpio=(OLD/'review-vendorboot-174806/fragment-0.cpio').read_bytes()
members={m['path']:m for m in json.loads((OLD/'review-vendorboot-174806/cpio-manifest.json').read_text('utf-8'))}
for record in json.loads((OLD/'review-vendorboot-174806/early-modules.json').read_text('utf-8')):
    member=members[record['file']];data=cpio[member['data_offset']:member['data_offset']+member['bytes']]
    record['exports']=elf_exports(data);record['source_group']='vendor_boot';rows.append(record)
byname=collections.defaultdict(list)
for row in rows:
    row['name']=(row['modinfo'].get('name') or [Path(row['file']).stem.replace('-','_')])[0]
    row['loaded_name']=row['name'] in loaded
    if row['source_group']=='system_dlkm':
        row['source_class']='GKI'
        row['protected_source_policy']='protected' if row['name'] in protected else 'unprotected'
    else:row.update(source_class='Vendor',protected_source_policy='vendor')
    row['signature_trust']='UNVERIFIED'
    byname[row['name']].append(row)
if len(rows)!=790 or len(byname)!=508 or not loaded<=set(byname):raise RuntimeError('Module inventory coverage invariant failed')
inventory={'snapshot_kernel_release':'6.1.138-android14-11-g7b9e94e37cfa-mi',
           'total_file_variants':len(rows),'unique_names':len(byname),'loaded_names':sorted(loaded),
           'protected_policy_names':sorted(protected),'gki_policy_names':sorted(gki),'variants':rows}
write('inputs/stock-modules.json',inventory)
classification=[]
for name,variants in sorted(byname.items()):
    classification.append({'name':name,'loaded':name in loaded,'variants':len(variants),
        'distinct_file_sha256':len({v['sha256'] for v in variants}),
        'source_classes':sorted({v['source_class'] for v in variants}),
        'protected_source_policy':sorted({v['protected_source_policy'] for v in variants}),
        'signature_trust':'UNVERIFIED','candidate_crc_status':'NOT_BUILT'})
write('inputs/module-classification-508.json',classification)
dependencies={}
for row in rows:
    for name in ','.join(row['modinfo'].get('depends',[])).split(','):
        if name and name.replace('-','_') not in byname:dependencies.setdefault(row['name'],set()).add(name)
write('evidence/stock-dependency-audit.json',{k:sorted(v) for k,v in dependencies.items()})
write('evidence/input-summary.json',{'file_variants':len(rows),'unique_names':len(byname),'loaded_names':len(loaded),
    'protected_source_policy_name_count':len(protected),'variant_classes':dict(collections.Counter(v['protected_source_policy'] for v in rows)),
    'extracted_module_exports':sum(len(v['exports']) for v in rows),'module_exports_without_decoded_crc':sum(x['crc'] is None for v in rows for x in v['exports'].values()),
    'missing_dependency_names':len(dependencies),'manifest_projects':len(sources)})
print((ROOT/'evidence/input-summary.json').read_text())
