import tempfile,unittest
from pathlib import Path
from check_baseline import compare_variants,parse_config,parse_symvers

def module(name='driver',imports=None,exports=None,source='Vendor',namespaces=None):
    return {'name':name,'file':name+'.ko','sha256':'0'*64,'loaded_name':True,
        'source_class':source,'protected_source_policy':'vendor',
        'versions':imports or {'needed':'12345678'},'exports':exports or {},
        'modinfo':{'import_ns':namespaces or []}}
def check(rows,exports=None,protected=None):return compare_variants({'variants':rows},exports or {},protected or set())
class BaselineCheckerTests(unittest.TestCase):
    def test_kernel_crc_mismatch_is_failure(self):
        r=check([module()],{'needed':[{'crc':'87654321','namespace':''}]})
        self.assertEqual(r[0]['crc_status'],'FAIL')
    def test_vendor_provider_is_resolved_without_disabling_checks(self):
        p=module('provider',imports={'kernel':'11111111'},exports={'needed':{'crc':'12345678','namespace':''}})
        r=check([module(),p],{'kernel':[{'crc':'11111111','namespace':''}]})
        self.assertTrue(all(x['crc_status']=='PASS_IMPORT_CRC_ONLY' for x in r))
        self.assertTrue(all(x['signature_trust']=='UNVERIFIED' for x in r))
    def test_protected_export_collision_is_failure(self):
        r=check([module(exports={'reserved':{'crc':'12345678','namespace':''}})],{'needed':[{'crc':'12345678','namespace':''}]},{'reserved'})
        self.assertEqual(r[0]['crc_status'],'FAIL')
    def test_namespace_is_enforced(self):
        r=check([module()],{'needed':[{'crc':'12345678','namespace':'PROTECTED_NS'}]})
        self.assertEqual(r[0]['crc_status'],'FAIL')
    def test_missing_provider_is_failure(self):self.assertEqual(check([module()])[0]['crc_status'],'FAIL')
    def test_config_missing_is_distinct_from_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config';p.write_text('# CONFIG_A is not set\nCONFIG_B=m\n')
            c=parse_config(p);self.assertEqual(c['CONFIG_A'],'n');self.assertEqual(c['CONFIG_B'],'m');self.assertNotIn('CONFIG_C',c)
if __name__=='__main__':unittest.main()
