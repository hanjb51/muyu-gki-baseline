"""Fail-closed baseline acceptance: all module variants + full stock config."""
import argparse,collections,hashlib,json,re
from pathlib import Path

def parse_config(path):
    result={}
    for line in path.read_text('utf-8-sig').splitlines():
        m=re.fullmatch(r'(CONFIG_\w+)=(.*)',line)
        off=re.fullmatch(r'# (CONFIG_\w+) is not set',line)
        if m:result[m[1]]=m[2]
        elif off:result[off[1]]='n'
    return result

def parse_symvers(path):
    exports=collections.defaultdict(list)
    for number,line in enumerate(path.read_text().splitlines(),1):
        if not line.strip():continue
        fields=line.split()
        if len(fields)<4:raise ValueError(f'Invalid Module.symvers line {number}')
        crc,symbol,provider,kind=fields[:4]
        exports[symbol].append({'crc':f'{int(crc,16):08x}','provider':provider,
                                'kind':kind,'namespace':fields[4] if len(fields)>4 else ''})
    return exports

def compare_variants(inventory,candidate,protected_exports):
    stock_providers=collections.defaultdict(list)
    for row in inventory['variants']:
        if row['source_class']!='Vendor':continue
        for symbol,entry in row['exports'].items():
            stock_providers[symbol].append({'provider':row['name'],**entry})
    results=[]
    for row in inventory['variants']:
        errors=[];uncertain=[];providers=collections.Counter()
        imports=row.get('versions',{})
        if not imports:uncertain.append('No decoded __versions entries')
        for symbol,crc in imports.items():
            available=candidate.get(symbol,[])
            matching=[p for p in available if p['crc']==crc]
            if available and not matching:
                errors.append({'symbol':symbol,'reason':'candidate_crc_mismatch','required':crc,'candidate':available});continue
            if matching:
                compatible_licenses={'GPL','GPL v2','GPL and additional rights','Dual BSD/GPL','Dual MIT/GPL','Dual MPL/GPL'}
                if all(p.get('kind','')=='EXPORT_SYMBOL_GPL' for p in matching) and not (set(row.get('modinfo',{}).get('license',[]))&compatible_licenses):
                    errors.append({'symbol':symbol,'reason':'GPL_only_export_without_compatible_module_license'})
                namespaces={p['namespace'] for p in matching if p['namespace']}
                declared=set(row.get('modinfo',{}).get('import_ns',[]))
                if namespaces and not (namespaces&declared):
                    errors.append({'symbol':symbol,'reason':'missing_import_namespace','namespaces':sorted(namespaces)})
                providers['candidate_export']+=1
            else:
                possible=stock_providers.get(symbol,[])
                if any(p['crc']==crc for p in possible):
                    providers['stock_vendor_export']+=1
                elif possible and all(p['crc'] is not None for p in possible):
                    errors.append({'symbol':symbol,'reason':'stock_provider_crc_mismatch','required':crc,'providers':possible})
                elif possible:
                    uncertain.append('Provider CRC not decoded: '+symbol)
                else:errors.append({'symbol':symbol,'reason':'no_candidate_or_collected_vendor_provider','required':crc})
        collisions=sorted(set(row['exports'])&protected_exports) if row['source_class']=='Vendor' else []
        if collisions:errors.append({'reason':'vendor_exports_protected_symbols','symbols':collisions})
        results.append({'name':row['name'],'file':row['file'],'sha256':row['sha256'],
            'loaded_name':row['loaded_name'],'source_class':row['source_class'],
            'protected_source_policy':row['protected_source_policy'],
            'signature_trust':'UNVERIFIED','import_count':len(imports),
            'providers':dict(providers),'errors':errors,'uncertainties':uncertain,
            'crc_status':'FAIL' if errors else 'INCOMPLETE' if uncertain else 'PASS_IMPORT_CRC_ONLY'})
    return results

def main():
    p=argparse.ArgumentParser();p.add_argument('--dist',required=True);p.add_argument('--analysis',required=True)
    p.add_argument('--toolkit',required=True);p.add_argument('--abi-exit',required=True,type=int)
    a=p.parse_args();root=Path(a.toolkit);dist=Path(a.dist);out=Path(a.analysis);out.mkdir(parents=True,exist_ok=True)
    inv=json.loads((root/'inputs/stock-modules.json').read_text('utf-8'))
    lock=json.loads((root/'source-lock/LOCK.json').read_text('utf-8'))
    final=out/'final.config';symvers=out/'Module.symvers'
    result={'source_exact_oem':False,'common_commit':lock['companion_common_commit'],
            'abi_exit_code':a.abi_exit,'abi_stg':'PASS' if a.abi_exit==0 else 'FAILED_OR_NOT_COMPLETED',
            'allow_droidspaces_features':False,'reason':'User review required; exact OEM source and protected-key trust remain unverified.'}
    missing=[name for name in ['Image','vmlinux','System.map'] if not (dist/name).is_file()]
    result['missing_required_artifacts']=missing
    result['compile_artifacts_present']=not missing
    if not final.is_file() or not symvers.is_file():
        result['status']='INCOMPLETE_NO_FINAL_CONFIG_OR_SYMVERS'
        (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');return 1
    config=parse_config(final);stock=parse_config(root/'evidence/stock-full-config.txt')
    diff=[{'symbol':k,'stock':stock.get(k,'MISSING'),'baseline':config.get(k,'MISSING')} for k in sorted(set(config)|set(stock)) if config.get(k)!=stock.get(k)]
    (out/'config-diff.json').write_text(json.dumps(diff,indent=2)+'\n')
    result['config_difference_count']=len(diff)
    result['config_matches_stock_exactly']=not diff
    result['critical_config_failures']={k:{'expected':v,'actual':config.get(k,'MISSING')} for k,v in lock['required_build_configuration'].items() if config.get(k)!=v}
    result['unexpected_feature_enables']=[k for k in lock['must_remain_disabled'] if config.get(k) in ('y','m')]
    protected={line.strip() for line in (root/'source-lock/protected-exports.txt').read_text().splitlines() if line.strip() and not line.startswith('#')}
    rows=compare_variants(inv,parse_symvers(symvers),protected)
    (out/'module-variants-790.json').write_text(json.dumps(rows,indent=2)+'\n')
    names=collections.defaultdict(list)
    for row in rows:names[row['name']].append(row)
    merged=[{'name':name,'loaded':any(r['loaded_name'] for r in variants),
        'variant_count':len(variants),'variant_crc_statuses':dict(collections.Counter(r['crc_status'] for r in variants)),
        'source_classes':sorted({r['source_class'] for r in variants}),
        'protected_source_policy':sorted({r['protected_source_policy'] for r in variants}),
        'signature_trust':'UNVERIFIED'} for name,variants in sorted(names.items())]
    (out/'module-names-508.json').write_text(json.dumps(merged,indent=2)+'\n')
    result.update(module_variants_checked=len(rows),module_names_checked=len(names),
        loaded_names_checked=sum(x['loaded'] for x in merged),
        module_variant_statuses=dict(collections.Counter(r['crc_status'] for r in rows)),
        module_error_count=sum(len(r['errors']) for r in rows),
        protected_signature_trust='UNVERIFIED',kernel_release='PENDING')
    image=(dist/'Image').read_bytes() if (dist/'Image').is_file() else b''
    match=re.search(rb'Linux version ([^\s\x00]+)',image)
    if match:result['kernel_release']=match[1].decode('ascii','replace')
    result['kernel_release_matches_oem']=result['kernel_release']==inv['snapshot_kernel_release']
    structural_pass=(a.abi_exit==0 and not missing and not result['critical_config_failures'] and not result['unexpected_feature_enables'] and not result['module_error_count'])
    result['status']='CRC_AND_ABI_CHECKS_PASS_WITH_UNRESOLVED_ACCEPTANCE_GATES' if structural_pass else 'FAILED_OR_INCOMPLETE'
    # Exact config and runtime signature trust are separate gates; never auto-promote.
    result['full_acceptance']='NOT_ACCEPTED_PENDING_REVIEW_AND_UNRESOLVED_GATES'
    (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
    return 0 if structural_pass and not diff and all(r['crc_status']=='PASS_IMPORT_CRC_ONLY' for r in rows) else 1

if __name__=='__main__':raise SystemExit(main())
