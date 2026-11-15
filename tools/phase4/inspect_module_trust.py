"""Verify collected module signatures against public certificates recovered offline."""
import collections,hashlib,json,struct,tarfile,os
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding,ec

ROOT=Path(__file__).resolve().parent;PROJECT=Path(os.environ.get('MUYU_PROJECT_ROOT',str(ROOT.parent)));ROOT=PROJECT/'muyu-gki-phase4';OUT=ROOT/'evidence'
def der(data,pos=0):
    start=pos;tag=data[pos];pos+=1;n=data[pos];pos+=1
    if n&128:
        k=n&127;n=int.from_bytes(data[pos:pos+k],'big');pos+=k
    end=pos+n
    if end>len(data):raise ValueError('DER bounds')
    return {'tag':tag,'start':start,'offset':pos,'end':end,'value':data[pos:end],'raw':data[start:end]}
def children(n):
    data=n['value'];out=[];p=0
    while p<len(data):
        x=der(data,p);out.append(x);p=x['end']
    return out
def oid(n):
    a=n['value'];out=[a[0]//40,a[0]%40];v=0
    for b in a[1:]:
        v=(v<<7)|(b&127)
        if not b&128:out.append(v);v=0
    return '.'.join(map(str,out))
def section(data,name):
    off=struct.unpack_from('<Q',data,40)[0];ents,num,strings=struct.unpack_from('<HHH',data,58)
    records=[struct.unpack_from('<IIQQQQIIQQ',data,off+ents*n) for n in range(num)]
    sh=records[strings];names=data[sh[4]:sh[4]+sh[5]]
    for r in records:
        end=names.find(b'\0',r[0]);label=names[r[0]:end].decode()
        if label==name:return data[r[4]:r[4]+r[5]]
    return None
def verify(data,cert):
    marker=b'~Module signature appended~\n'
    if not data.endswith(marker):return {'status':'unsigned'}
    info=data[-len(marker)-12:-len(marker)];size=int.from_bytes(info[8:12],'big');pos=len(data)-len(marker)-12-size
    cms=data[pos:pos+size];signed=data[:pos-info[3]-info[4]]
    content=children(der(cms));sd=children(children(content[1])[0]);signer=children(children(sd[-1])[0])
    sid=children(signer[1]);serial=int.from_bytes(sid[-1]['value'],'big')
    digest_oid=oid(children(signer[2])[0]);algorithm={'2.16.840.1.101.3.4.2.1':hashes.SHA256,'2.16.840.1.101.3.4.2.2':hashes.SHA384,'2.16.840.1.101.3.4.2.3':hashes.SHA512,'1.3.14.3.2.26':hashes.SHA1}[digest_oid]()
    attrs=next((n for n in signer[3:] if n['tag']==0xa0),None)
    to_verify=signed
    if attrs:
        # CMS signs the SET tag rather than the context-specific wrapper.
        to_verify=b'\x31'+attrs['raw'][1:]
        for a in children(attrs):
            fields=children(a)
            if oid(fields[0])=='1.2.840.113549.1.9.4':
                digest=hashes.Hash(algorithm);digest.update(signed)
                if children(fields[1])[0]['value']!=digest.finalize():raise ValueError('CMS content digest mismatch')
    signature=signer[-1]['value']
    result={'signer_serial':hex(serial),'digest_oid':digest_oid,'signature_bytes':len(signature),'signed_attributes':bool(attrs),'serial_matches_certificate':serial==cert.serial_number}
    try:
        key=cert.public_key()
        if isinstance(key,ec.EllipticCurvePublicKey):key.verify(signature,to_verify,ec.ECDSA(algorithm))
        else:key.verify(signature,to_verify,padding.PKCS1v15(),algorithm)
        result['cryptographic_verification']='PASS'
    except Exception as ex:result['cryptographic_verification']='FAIL';result['exception']=type(ex).__name__
    return result

def main():
    stock_meta=json.loads((OUT/'stock-image-inspection.json').read_text())
    cert=x509.load_der_x509_certificate((OUT/('certificate-'+stock_meta['embedded_certificates'][0]['sha256']+'.der')).read_bytes())
    candidate_meta=json.loads((OUT/'candidate-image-inspection.json').read_text())
    candidate_cert=x509.load_der_x509_certificate((OUT/('certificate-'+candidate_meta['embedded_certificates'][0]['sha256']+'.der')).read_bytes())
    rows=[]
    archive=PROJECT/'muyu-gki-phase1/phase2/muyu-readonly-20261115-173854/modules-01/files.tar'
    with tarfile.open(archive) as t:
        for m in t:
            if not m.isfile() or not m.name.endswith('.ko'):continue
            data=t.extractfile(m).read();rows.append({'file':m.name,'sha256':hashlib.sha256(data).hexdigest(),**verify(data,cert),'candidate_certificate_verification':verify(data,candidate_cert)})
    (OUT/'stock-module-signature-checks.json').write_text(json.dumps(rows,indent=2)+'\n')
    summary={'certificate_sha256':stock_meta['embedded_certificates'][0]['sha256'],'modules_checked':len(rows),'verification_statuses':dict(collections.Counter(r.get('cryptographic_verification',r.get('status')) for r in rows)),'signer_serials':dict(collections.Counter(r.get('signer_serial') for r in rows))}
    summary['candidate_certificate_statuses']=dict(collections.Counter(r['candidate_certificate_verification'].get('cryptographic_verification') for r in rows))
    (OUT/'module-trust-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
    # Inspect the one collected cifs binary without extracting the full ramdisk.
    data=(PROJECT/'muyu-gki-phase1/phase2/review-vendorboot-174806/fragment-0.cpio').read_bytes();p=0
    while p+110<=len(data):
        if data[p:p+6] not in [b'070701',b'070702']:raise ValueError('CPIO header')
        f=[int(data[p+6+i*8:p+14+i*8],16) for i in range(13)];ns=f[11];size=f[6];name=data[p+110:p+110+ns-1].decode();begin=(p+110+ns+3)&~3;end=begin+size
        if name.endswith('/cifs.ko'):
            module=data[begin:end];btf=section(module,'.BTF');comment=section(module,'.comment')
            row={'cpio_name':name,'sha256':hashlib.sha256(module).hexdigest(),'comment':comment.decode(errors='replace') if comment else None,'btf_bytes':len(btf) if btf else None,'btf_type_tag_word_occurrences':btf.count(b'percpu\0') if btf else None}
            if btf:
                hdr=struct.unpack_from('<HBBIIIII',btf,0);row['btf_header']=hdr;row['btf_string_first_byte']=btf[hdr[3]+hdr[6]]
            (OUT/'cifs-binary-inspection.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row,indent=2));break
        p=(end+3)&~3

if __name__=='__main__':main()
