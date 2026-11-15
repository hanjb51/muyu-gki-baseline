"""Recover PREL32 export/CRC tables from existing raw Images; validate on CI ELF."""
import array,hashlib,json,re,struct,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent;PROJECT=Path(os.environ.get('MUYU_PROJECT_ROOT',str(ROOT.parent)));ROOT=PROJECT/'muyu-gki-phase4';OUT=ROOT/'evidence'

def symbol(data,pos):
    if pos<0 or pos+12>len(data):return None
    value,name,ns=struct.unpack_from('<iii',data,pos)
    value+=pos;name+=pos+4;ns+=pos+8
    # Per-CPU exported values can lie outside the flat Image mapping.
    if not all(0<=x<len(data) for x in [name,ns]):return None
    end=data.find(b'\0',name,name+200)
    if end<0:return None
    text=data[name:end]
    if not re.fullmatch(rb'[A-Za-z_][A-Za-z_0-9]*',text):return None
    if data.find(b'\0',ns,ns+128)<0:return None
    return text.decode()

def recover(data,anchor):
    locations=set();p=0
    while True:
        p=data.find(anchor.encode()+b'\0',p)
        if p<0:break
        locations.add(p);p+=1
    ints=array.array('i');ints.frombytes(data[:len(data)//4*4])
    candidates=[]
    for n,v in enumerate(ints):
        p=n*4
        if p+v in locations and symbol(data,p-4)==anchor:candidates.append(p-4)
    if len(candidates)!=1:raise ValueError(('Ambiguous anchor',candidates))
    at=candidates[0];start=at;last=anchor
    while start>=12:
        name=symbol(data,start-12)
        if name is None or name>last:break
        start-=12;last=name
    end=at+12;last=anchor
    while end+12<len(data):
        name=symbol(data,end)
        if name is None or name<last:break
        end+=12;last=name
    normal_end=start;normal_start=start-12;last=symbol(data,normal_start)
    if last is None:raise ValueError('No preceding normal table')
    while normal_start>=12:
        name=symbol(data,normal_start-12)
        if name is None or name>last:break
        normal_start-=12;last=name
    count_normal=(normal_end-normal_start)//12;count_gpl=(end-start)//12
    crc_normal=end;crc_gpl=crc_normal+count_normal*4
    rows=[]
    for group,a,b,crc in [('normal',normal_start,normal_end,crc_normal),('gpl',start,end,crc_gpl)]:
        for i,pos in enumerate(range(a,b,12)):
            rows.append({'name':symbol(data,pos),'kind':group,'crc':f'{struct.unpack_from("<I",data,crc+i*4)[0]:08x}'})
    return {'image_sha256':hashlib.sha256(data).hexdigest(),'normal_start':normal_start,'normal_end':normal_end,'gpl_start':start,'gpl_end':end,'normal_count':count_normal,'gpl_count':count_gpl,'crc_gpl_start':crc_gpl,'exports':rows}

def main():
    ci=PROJECT/'muyu-gki-phase3/evidence/run-3-artifact/out'
    candidate=(ci/'dist/Image').read_bytes();boot=(PROJECT/'muyu-gki-phase1/phase2/muyu-readonly-20261115-173854/boot_a.img').read_bytes();n=struct.unpack_from('<I',boot,8)[0];stock=boot[4096:4096+n]
    ca=recover(candidate,'__page_file_index');st=recover(stock,'__page_file_index')
    boundaries=json.loads((OUT/'candidate-export-symbol-boundaries.json').read_text());base=boundaries['_text']
    assert ca['normal_start']==boundaries['__start___ksymtab']-base
    assert ca['gpl_start']==boundaries['__start___ksymtab_gpl']-base
    assert ca['gpl_end']==boundaries['__stop___ksymtab_gpl']-base
    assert ca['crc_gpl_start']==boundaries['__start___kcrctab_gpl']-base
    expected={}
    for line in (ci/'analysis/Module.symvers').read_text().splitlines():
        f=line.split()
        if f[2]=='vmlinux':expected[f[1]]=f[0].removeprefix('0x')
    actual={r['name']:r['crc'] for r in ca['exports']}
    assert all(expected.get(k)==v for k,v in actual.items()),'Candidate table failed symvers cross-check'
    for label,d in [('stock',st),('candidate',ca)]:
        (OUT/(label+'-raw-export-crcs.json')).write_text(json.dumps(d,indent=2)+'\n')
    sa={r['name']:r['crc'] for r in st['exports']};diff=[{'symbol':k,'stock':sa[k],'candidate':actual[k]} for k in sorted(set(sa)&set(actual)) if sa[k]!=actual[k]]
    (OUT/'raw-export-crc-differences.json').write_text(json.dumps(diff,indent=2)+'\n')
    print(json.dumps({'candidate_exports_validated':len(actual),'stock_exports_recovered':len(sa),'differences':diff,'targets':{k:{'stock':sa[k],'candidate':actual[k]} for k in ['__page_file_index','add_swap_extent']}},indent=2))

if __name__=='__main__':main()
