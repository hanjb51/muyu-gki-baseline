"""Phase 5: read saved inputs only. No kernel build or device access.

Run from the project snapshot root: python muyu-gki-phase5/offline_checks.py
Requires cryptography and the Phase 1/3/4 inputs identified in evidence.
The combined certificate test models signer lookup plus CMS verification;
it is explicitly not a Linux keyring or module-loader integration test.
"""
import collections, hashlib, importlib.util, inspect, json, os, struct, tarfile, zipfile
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding

HERE=Path(__file__).resolve().parent
PROJECT=Path(os.environ.get('MUYU_PROJECT_ROOT',str(HERE.parent)))
ROOT=PROJECT/'muyu-gki-phase5'; OUT=ROOT/'evidence'; OUT.mkdir(parents=True,exist_ok=True)
P4=PROJECT/'muyu-gki-phase4'
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
trust=module('phase4_trust',P4/'inspect_module_trust.py')
binary=module('phase4_binary',P4/'inspect_binary_evidence.py')
def digest(b):return hashlib.sha256(b).hexdigest()
def save(name,data):(OUT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
certs={label:x509.load_der_x509_certificate((P4/'evidence'/filename).read_bytes()) for label,filename in {
    'oem':'certificate-1ab85e414a2cdae609f86beb41f172da760df8a72ef486de320bc7c295624505.der',
    'candidate':'certificate-4bfd7d54a94838093efb3bb6476de8821ebf7aec70edba08131d77eab654ab5b.der'}.items()}
pem=b''.join(certs[n].public_bytes(Encoding.PEM) for n in ['candidate','oem'])
roundtrip=[x509.load_pem_x509_certificate(x+b'-----END CERTIFICATE-----\n') for x in pem.split(b'-----END CERTIFICATE-----\n') if x.strip()]
assert [c.fingerprint(__import__('cryptography').hazmat.primitives.hashes.SHA256()) for c in roundtrip]==[certs[n].fingerprint(__import__('cryptography').hazmat.primitives.hashes.SHA256()) for n in ['candidate','oem']]
# Persist public material only; neither certificate contains a private key.
(OUT/'combined-public-certificates.pem').write_bytes(pem)
(OUT/'oem-public-certificate.pem').write_bytes(certs['oem'].public_bytes(Encoding.PEM))
def check(data,labels):
    if not data.endswith(b'~Module signature appended~\n'):return False
    marker=28; info=data[-marker-12:-marker]; size=int.from_bytes(info[8:12],'big'); cms=data[-marker-12-size:-marker-12]
    sd=trust.children(trust.children(trust.children(trust.der(cms))[1])[0]); signer=trust.children(trust.children(sd[-1])[0]); sid=trust.children(signer[1])
    for label in labels:
        cert=certs[label]
        if sid[0]['raw']!=cert.issuer.public_bytes():continue
        r=trust.verify(data,cert)
        if r.get('serial_matches_certificate') and r.get('cryptographic_verification')=='PASS':return True
    return False
archive=PROJECT/'muyu-gki-phase1/phase2/muyu-readonly-20261115-173854/modules-01/files.tar'
rows=[];oem_example=None
with tarfile.open(archive) as t:
    for member in t:
        if not member.isfile() or not member.name.endswith('.ko'):continue
        b=t.extractfile(member).read();before=check(b,['candidate']);after=check(b,['candidate','oem'])
        rows.append({'class':'stock','file':member.name,'sha256':digest(b),'candidate_only':before,'combined':after})
        if after:oem_example=b
for p in sorted((PROJECT/'muyu-gki-phase3/evidence/run-3-artifact/out/dist').glob('*.ko')):
    b=p.read_bytes();rows.append({'class':'candidate','file':p.name,'sha256':digest(b),'candidate_only':check(b,['candidate']),'combined':check(b,['candidate','oem'])})
assert oem_example
tampered=bytes([oem_example[0]^1])+oem_example[1:]
tests={'pem_roundtrip':True,'oem_positive':check(oem_example,['candidate','oem']),
       'oem_removed_negative':not check(oem_example,['candidate']),
       'tampered_negative':not check(tampered,['candidate','oem']),
       'unsigned_negative':not check(oem_example[:-28],['candidate','oem'])}
assert all(tests.values())
counts={k:dict(collections.Counter(str((r['candidate_only'],r['combined'])) for r in rows if r['class']==k)) for k in ['stock','candidate']}
save('combined-trust-tests.json',{'scope':'issuer/serial lookup and CMS cryptography, NOT kernel integration','pem_sha256':digest(pem),'archive_sha256':digest(archive.read_bytes()),'counts':counts,'tests':tests,'negative_input_sha256':{'original':digest(oem_example),'tampered':digest(tampered)},'rows':rows})
metadata=json.loads((PROJECT/'muyu-gki-phase3/inputs/stock-modules.json').read_text(encoding='utf-8'))
metadata_by_sha={r['sha256']:r for r in metadata['variants']}
protected_path=PROJECT/'muyu-gki-phase3/evidence/run-3-artifact/source-lock/protected-exports.txt'
protected=set(protected_path.read_text().split());coverage=[]
for row in rows:
    if row['class']!='stock':continue
    meta=metadata_by_sha.get(row['sha256']);exports=set(meta.get('exports',[])) if meta else set()
    hits=sorted(exports&protected)
    if hits:coverage.append({'file':row['file'],'sha256':row['sha256'],'name':meta['name'],'protected_exports':hits,'combined_signature_verified':row['combined']})
save('protected-export-coverage.json',{'protected_list_sha256':digest(protected_path.read_bytes()),'rows':coverage})
# Extend the already validated Phase 4 parser in memory to retain BTF function prototypes.
src=inspect.getsource(binary.btf).replace("'type_count':len(types)","'feature_signatures':[{**r,'prototype':label(r['size_or_type'])} for r in types.values() if r['kind']==12 and r['name'] in feature_names], 'type_count':len(types)")
scope=dict(binary.__dict__);exec(src,scope)
boot=(PROJECT/'muyu-gki-phase1/phase2/muyu-readonly-20261115-173854/boot_a.img').read_bytes();n=struct.unpack_from('<I',boot,8)[0];stock=boot[4096:4096+n]
btf=scope['btf'](stock)
save('stock-feature-prototypes.json',{'image_sha256':digest(stock),'btf_sha256':btf['sha256'],'functions':btf['feature_signatures']})
# Audit reference inventory in existing archives, without extracting or running their code.
inventory=[]
dist=PROJECT/'muyu-gki-phase3/evidence/run-3-artifact/out/dist'
for name in ['kernel-headers.tar.gz','modules_prepare_outdir.tar.gz']:
    p=dist/name
    with tarfile.open(p) as t:names=t.getnames()
    inventory.append({'file':name,'sha256':digest(p.read_bytes()),'entries':len(names),'symref_files':[s for s in names if s.endswith('.symref')],'symtypes_files':[s for s in names if s.endswith('.symtypes')]})
zpath=P4/'evidence/crc-matched-tools.zip'
with zipfile.ZipFile(zpath) as z:
    types=z.read('candidate/types.symtypes').decode();stdout=z.read('candidate/genksyms.stdout').decode()
    wanted=['__page_file_index','add_swap_extent','page_swap_info','unuse_swap_pte']
    target_lines=[s for s in types.splitlines() if s.split(' ',1)[0] in wanted]
save('genksyms-input-audit.json',{'archives':inventory,'phase4_result_zip_sha256':digest(zpath.read_bytes()),'candidate_symtypes_sha256':digest(types.encode()),'target_symtypes':target_lines,'candidate_genksyms_output':stdout,'limitation':'No OEM preprocessor input, symtypes, symref or exact build command recovered; absence in candidate archives does not establish absence in OEM build.'})
print(json.dumps({'trust':counts,'tests':tests,'btf_functions':len(btf['feature_signatures']),'symref_counts':[len(r['symref_files']) for r in inventory]},indent=2))
