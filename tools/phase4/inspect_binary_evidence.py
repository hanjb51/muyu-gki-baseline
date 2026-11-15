"""Read existing boot/CI images only; inspect BTF and embedded public certificates."""
import hashlib,json,struct,os
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization

ROOT=Path(__file__).resolve().parent
PROJECT=Path(os.environ.get('MUYU_PROJECT_ROOT',str(ROOT.parent)))
ROOT=PROJECT/'muyu-gki-phase4'
OUT=ROOT/'evidence';OUT.mkdir(exist_ok=True)
NAMES={'page','folio','swap_info_struct','swap_extent','address_space','signal_struct','task_struct','module','mm_struct','dma_buf','file','inode'}

def certs(data):
    rows=[];start=0
    while True:
        i=data.find(b'\x30\x82',start)
        if i<0:break
        start=i+2
        if i+4>len(data):continue
        n=int.from_bytes(data[i+2:i+4],'big')+4
        if not 100<n<16000 or i+n>len(data):continue
        try:c=x509.load_der_x509_certificate(data[i:i+n])
        except ValueError:continue
        rows.append({'offset':i,'bytes':n,'subject':c.subject.rfc4514_string(),'issuer':c.issuer.rfc4514_string(),'serial':hex(c.serial_number),'sha256':c.fingerprint(hashes.SHA256()).hex(),'spki_sha256':hashlib.sha256(c.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).hexdigest()})
        (OUT/('certificate-'+c.fingerprint(hashes.SHA256()).hex()+'.der')).write_bytes(data[i:i+n])
    return rows

def btf(data):
    start=0
    while True:
        i=data.find(b'\x9f\xeb\x01\x00',start)
        if i<0:return None
        start=i+4
        if i+24>len(data):continue
        magic,ver,flags,hdr,to,tl,so,sl=struct.unpack_from('<HBBIIIII',data,i)
        if hdr<24 or hdr>64 or tl<1000 or sl<1000 or i+hdr+max(to+tl,so+sl)>len(data):continue
        strings=data[i+hdr+so:i+hdr+so+sl]
        if strings[0]!=0:continue
        def string(n):
            if n>=len(strings):return '<split-base-string>'
            stop=strings.find(b'\0',n)
            return strings[n:stop if stop>=0 else len(strings)].decode('utf-8','replace')
        types={};pos=i+hdr+to;end=pos+tl;type_id=0
        try:
            while pos<end:
                no,info,size=struct.unpack_from('<III',data,pos);pos+=12;kind=info>>24&31;vlen=info&65535;flag=bool(info>>31);type_id+=1
                row={'id':type_id,'name':string(no),'kind':kind,'size_or_type':size}
                if kind in (4,5):
                    row['members']=[]
                    for _ in range(vlen):
                        name,t,offset=struct.unpack_from('<III',data,pos);pos+=12
                        row['members'].append({'name':string(name),'type':t,'bit_offset':offset&0xffffff if flag else offset,'bitfield_size':offset>>24 if flag else 0})
                elif kind in (6,19):
                    row['values']=[]
                    for _ in range(vlen):
                        fields=struct.unpack_from('<III' if kind==19 else '<II',data,pos);pos+=12 if kind==19 else 8
                        row['values'].append({'name':string(fields[0]),'value':fields[1]+((fields[2]<<32) if kind==19 else 0)})
                elif kind==13:
                    row['parameters']=[]
                    for _ in range(vlen):
                        name,t=struct.unpack_from('<II',data,pos);pos+=8;row['parameters'].append({'name':string(name),'type':t})
                else:
                    extra={1:4,2:0,3:12,7:0,8:0,9:0,10:0,11:0,12:0,14:4,15:vlen*12,16:0,17:4,18:0}.get(kind)
                    if extra is None:raise ValueError('Unknown kind')
                    if kind==3:row['array']=struct.unpack_from('<III',data,pos)
                    pos+=extra
                if pos>end:raise ValueError('Bad bounds')
                types[type_id]=row
            def label(t):
                if t==0:return 'void'
                r=types.get(t)
                if not r:return '<unknown>'
                if r['kind']==2:return '*'+label(r['size_or_type'])
                if r['kind']==3:return '['+str(r['array'][2])+']'+label(r['array'][0])
                if r['kind']==13:return 'fn('+','.join(label(v['type']) for v in r['parameters'])+')->'+label(r['size_or_type'])
                if r['kind'] in (4,5) and not r['name']:
                    return str(r['kind'])+'{'+str(r['size_or_type'])+':'+','.join(m['name']+'@'+str(m['bit_offset'])+'/'+str(m['bitfield_size'])+':'+label(m['type']) for m in r['members'])+'}'
                if r['kind'] in (6,19) and not r['name']:
                    return 'enum{'+','.join(v['name']+'='+str(v['value']) for v in r['values'])+'}'
                if r['kind'] in (9,10,11):return ['volatile','const','restrict'][r['kind']-9]+' '+label(r['size_or_type'])
                return str(r['kind'])+':'+r['name']
            selected=[]
            for r in types.values():
                if r['kind'] in (4,5) and r['name'] in NAMES:
                    selected.append({**r,'members':[{**m,'type_label':label(m['type'])} for m in r['members']]})
            wanted=set()
            import re
            for line in (OUT/'reachable-types.txt').read_text().splitlines():
                key=line.split(' ',1)[0]
                if '#' in key:wanted.add(key.split('#',1)[1])
            shapes=[]
            for r in types.values():
                if r['name'] not in wanted:continue
                if r['kind'] in (4,5):shape={'bytes':r['size_or_type'],'members':[(m['name'],m['bit_offset'],m['bitfield_size'],label(m['type'])) for m in r['members']]}
                elif r['kind'] in (6,19):shape={'values':r['values']}
                elif r['kind']==8:shape={'target':label(r['size_or_type'])}
                else:continue
                shapes.append({'kind':r['kind'],'name':r['name'],'shape':shape})
            feature_names=sorted({r['name'] for r in types.values() if any(s in r['name'].lower() for s in ['contpte','dmabuf_huge','dma_buf_huge','xiaomi_dmabuf'])})
            return {'offset':i,'bytes':hdr+max(to+tl,so+sl),'sha256':hashlib.sha256(data[i:i+hdr+max(to+tl,so+sl)]).hexdigest(),'type_count':len(types),'selected_structs':selected,'reachable_named_types':shapes,'feature_names':feature_names}
        except (ValueError,struct.error,RecursionError):continue

def main():
    boot=PROJECT/'muyu-gki-phase1/phase2/muyu-readonly-20261115-173854/boot_a.img'
    raw=boot.read_bytes();n=struct.unpack_from('<I',raw,8)[0];stock=raw[4096:4096+n]
    candidate=(PROJECT/'muyu-gki-phase3/evidence/run-3-artifact/out/dist/Image').read_bytes()
    results={}
    for label,data in [('stock',stock),('candidate',candidate)]:
        result={'image_sha256':hashlib.sha256(data).hexdigest(),'image_bytes':len(data),'embedded_certificates':certs(data),'btf':btf(data)}
        results[label]=result
        (OUT/(label+'-image-inspection.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    diffs=[]
    if all(results[x]['btf'] for x in results):
        def layouts(label):
            return {r['name']:{'bytes':r['size_or_type'],'members':[(m['name'],m['bit_offset'],m['bitfield_size'],m['type_label']) for m in r['members']]} for r in results[label]['btf']['selected_structs']}
        a,b=layouts('stock'),layouts('candidate')
        for name in sorted(set(a)|set(b)):
            diffs.append({'name':name,'equal_direct_layout':a.get(name)==b.get(name),'stock_bytes':a.get(name,{}).get('bytes'),'candidate_bytes':b.get(name,{}).get('bytes')})
    (OUT/'btf-layout-comparison.json').write_text(json.dumps(diffs,indent=2)+'\n')
    import collections
    grouped={}
    for label in results:
        groups=collections.defaultdict(set)
        for row in results[label]['btf']['reachable_named_types']:
            groups[str(row['kind'])+':'+row['name']].add(json.dumps(row['shape'],sort_keys=True))
        grouped[label]=groups
    differences=[]
    for name in sorted(set(grouped['stock'])|set(grouped['candidate'])):
        a,b=grouped['stock'].get(name,set()),grouped['candidate'].get(name,set())
        if a!=b:differences.append({'type':name,'stock':[json.loads(x) for x in a],'candidate':[json.loads(x) for x in b]})
    (OUT/'btf-reachable-differences.json').write_text(json.dumps(differences,indent=2)+'\n')
    print('REACHABLE_DIFFERENCES',json.dumps([r['type'] for r in differences]))
    print(json.dumps({'images':{k:{'certificates':v['embedded_certificates'],'btf_types':v['btf']['type_count'] if v['btf'] else None} for k,v in results.items()},'layouts':diffs},indent=2))

if __name__=='__main__':main()
