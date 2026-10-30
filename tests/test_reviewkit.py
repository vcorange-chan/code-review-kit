from pathlib import Path
import tempfile
import unittest
import json
import sys

HOME=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(HOME),str(HOME/'.deps')]
from reviewkit.indexer import build_index
from reviewkit.rust import RustAdapter
from reviewkit.engine import extract, blank_explanations, validate_explanations, make_packet, choose
from reviewkit.render import render
from reviewkit.cli import main
from reviewkit.business import extract_business,validate_graph
from reviewkit.storage import read_json
import hashlib
import contextlib
import io


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        self.cache=self.root/'cache';self.adapter=RustAdapter()
    def tearDown(self):self.temp.cleanup()
    def put(self,name,text):
        path=self.repo/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8');return path
    def index(self):return build_index(self.repo,self.adapter,self.cache)
    def facts(self,symbol='run'):
        return extract(self.index(),[{'symbol':symbol}],depth=2)
    def test_cache_reuses_and_removes_files(self):
        self.put('lib.rs','fn run() {}');self.put('other.rs','fn other() {}')
        self.assertEqual(self.index()['stats']['parsed_files'],2)
        self.assertEqual(self.index()['stats']['reused_files'],2)
        self.put('other.rs','fn other() { let x=1; }')
        self.assertEqual(self.index()['stats']['parsed_files'],1)
        (self.repo/'other.rs').unlink();self.assertEqual(self.index()['stats']['removed_files'],1)
    def test_ambiguous_symbol_is_not_guessed(self):
        self.put('a.rs','fn run() {}');self.put('b.rs','fn run() {}')
        with self.assertRaisesRegex(ValueError,'匹配 2 项'):self.facts()
    def test_macro_gap_is_exposed(self):
        self.put('lib.rs','fn run() {} fn test() { run(); assert!(run().is_ok()); }')
        facts=self.facts();self.assertEqual(len(facts['callers']),1);self.assertEqual(len(facts['macro_mentions']),1)
    def test_downstream_change_invalidates_explanation(self):
        self.put('lib.rs','fn run() { child(); } fn child() {}')
        facts=self.facts();notes=blank_explanations(facts);root=facts['root_ids'][0]
        self.assertTrue(validate_explanations(notes,facts)[root])
        self.put('lib.rs','fn run() { child(); } fn child() { let x=1; }')
        self.assertFalse(validate_explanations(notes,self.facts())[root])
    def test_unrelated_change_keeps_explanation(self):
        self.put('lib.rs','fn run() {}');self.put('unrelated.rs','fn other() {}')
        old=self.facts();notes=blank_explanations(old)
        self.put('unrelated.rs','fn other() { let x=2; }')
        self.assertTrue(validate_explanations(notes,self.facts())[old['root_ids'][0]])
    def test_business_invalidates_only_affected_card(self):
        self.put('lib.rs','fn first() {} fn second() {}')
        old=extract(self.index(),[{'symbol':'first'},{'symbol':'second'}]);notes=blank_explanations(old)
        self.put('lib.rs','fn first() { let x=1; } fn second() {}')
        fresh=extract(self.index(),[{'symbol':'first'},{'symbol':'second'}])
        status=validate_explanations(notes,fresh)
        self.assertFalse(status[old['root_ids'][0]]);self.assertTrue(status[old['root_ids'][1]])
    def test_moved_lines_refresh_links_without_stale_explanation(self):
        self.put('lib.rs','fn run() { child(); } fn child() {}')
        old=self.facts();notes=blank_explanations(old)
        self.put('lib.rs','\n\nfn run() { child(); } fn child() {}')
        fresh=self.facts();self.assertEqual(fresh['functions'][0]['line'],3)
        self.assertTrue(validate_explanations(notes,fresh)[old['root_ids'][0]])
    def test_import_change_invalidates_context(self):
        self.put('lib.rs','use a::child; fn run() { child(); }')
        old=self.facts();notes=blank_explanations(old)
        self.put('lib.rs','use b::child; fn run() { child(); }')
        self.assertFalse(validate_explanations(notes,self.facts())[old['root_ids'][0]])
    def test_packet_obeys_actual_byte_limit(self):
        self.put('lib.rs','fn run() {'+'let data="中文信息";'*1000+'}')
        packet=make_packet(self.facts(),2048)
        self.assertLessEqual(len(json.dumps(packet,ensure_ascii=False,separators=(',',':')).encode()),2048)
        self.assertTrue(packet['omissions_notice'])
    def test_nested_function_returns_do_not_belong_to_parent(self):
        self.put('lib.rs','fn run() { fn inner() { return; } }')
        self.assertEqual(self.facts()['functions'][0]['returns'],[])
    def test_unknown_reference_is_rejected(self):
        self.put('lib.rs','fn run() {}');facts=self.facts();notes=blank_explanations(facts)
        notes['cards'][facts['root_ids'][0]]['steps']=[{'title':'x','detail':'x','reference':'invented'}]
        with self.assertRaises(ValueError):validate_explanations(notes,facts)
    def test_malformed_explanation_is_a_readable_validation_error(self):
        self.put('lib.rs','fn run() {}');facts=self.facts()
        with self.assertRaises(ValueError):validate_explanations([],facts)
        notes=blank_explanations(facts)
        notes['cards'][facts['root_ids'][0]]['steps']=[{'title':'x','detail':'x','reference':{}}]
        with self.assertRaises(ValueError):validate_explanations(notes,facts)
    def test_annotations_are_escaped_and_template_is_fixed(self):
        self.put('lib.rs','fn run() {}');facts=self.facts();notes=blank_explanations(facts)
        card=notes['cards'][facts['root_ids'][0]]
        card.update({'title':'<script>attack()</script>','input':'{{JS}}','steps':[{'title':'a','detail':'<img onerror=attack()>','reference':facts['root_ids'][0]}]})
        out=self.root/'review.html';render(facts,notes,out)
        text=out.read_text(encoding='utf-8')
        self.assertNotIn('<script>attack()',text);self.assertIn('&lt;img',text);self.assertIn('{{JS}}',text)
    def test_business_runs_without_model_or_narrative(self):
        self.put('lib.rs','fn first() {} fn second() {}')
        manifest=self.root/'business.json';manifest.write_text(json.dumps({'schema_version':1,'repository':str(self.repo),'title':'业务','nodes':[{'symbol':'first'},{'symbol':'second'}]}),encoding='utf-8')
        out=self.root/'out'
        self.assertEqual(main(['business','--manifest',str(manifest),'--out',str(out),'--cache',str(self.cache)]),0)
        self.assertEqual(len(json.loads((out/'facts.json').read_text())['root_ids']),2)
        self.assertIn('自动提取', (out/'index.html').read_text(encoding='utf-8'))
    def test_syntax_error_is_detected(self):
        self.put('lib.rs','fn run() { let x = ; }')
        self.assertTrue(self.index()['files']['lib.rs']['parse_error'])
    def test_business_views_share_function_but_keep_separate_cards(self):
        self.put('lib.rs','fn run() {}')
        manifest={'nodes':[{'id':n,'sources':[{'file':'lib.rs','line':1}]} for n in ['read','write']]}
        facts=extract_business(self.index(),manifest,0,16)
        self.assertEqual(facts['root_ids'],['business::read','business::write'])
        self.assertEqual(len([f for f in facts['functions'] if f.get('view')!='business']),1)
    def test_context_source_without_language_adapter_is_labeled(self):
        self.put('screen.dart','void showResult() {}')
        facts=extract_business(self.index(),{'nodes':[{'id':'screen','sources':[{'file':'screen.dart','line':1}]}]},0,16)
        self.assertEqual(facts['functions'][0]['sources'][0]['kind'],'source_context')
        self.assertEqual(facts['limits']['resolution'],'source_context_only')
    def test_source_anchor_cannot_escape_repository(self):
        (self.root/'private.txt').write_text('private')
        with self.assertRaises(ValueError):
            extract_business(self.index(),{'nodes':[{'id':'x','sources':[{'file':'../private.txt','line':1}]}]},0,16)
    def test_resume_requires_valid_node_branch_and_kind(self):
        self.put('lib.rs','fn run() {}')
        manifest={'nodes':[{'id':'x','sources':[{'file':'lib.rs','line':1}]}],
                  'edges':[{'from':'x','to':'x','kind':'resume','branch':'optional'}]}
        facts=extract_business(self.index(),manifest,0,16);notes=blank_explanations(facts)
        card=notes['cards']['business::x'];card['steps']=[{'title':'x','detail':'x'}]
        with self.assertRaises(ValueError):validate_explanations(notes,facts)
        card['branches']=[{'id':'optional','kind':'degrade','title':'fallback','state':'raw','items':[]}]
        self.assertTrue(validate_explanations(notes,facts)['business::x'])
        manifest['edges'][0]['to']='missing'
        with self.assertRaises(ValueError):extract_business(self.index(),manifest,0,16)
    def test_crlf_does_not_change_explanation_identity(self):
        path=self.put('lib.rs','fn run() {\n}\n');first=self.facts()
        path.write_bytes(b'fn run() {\r\n}\r\n')
        self.assertEqual(first['card_evidence'],self.facts()['card_evidence'])
    def test_unchanged_build_reuses_exact_html(self):
        self.put('lib.rs','fn run() {}');out=self.root/'out'
        args=['function','--repo',str(self.repo),'--symbol','run','--out',str(out),'--cache',str(self.cache)]
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(args),0)
        checksum=hashlib.sha256((out/'index.html').read_bytes()).hexdigest()
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(args),0)
        self.assertTrue(read_json(out/'build-stats.json')['html_reused'])
        self.assertEqual(checksum,hashlib.sha256((out/'index.html').read_bytes()).hexdigest())
        self.put('lib.rs','fn run() { let x=1; }')
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(args),0)
        self.assertFalse(read_json(out/'build-stats.json')['html_reused'])
    def test_resume_markup_is_data_driven_and_escaped(self):
        self.put('lib.rs','fn run() {}')
        manifest={'nodes':[{'id':'x','sources':[{'file':'lib.rs','line':1}]}],
                  'edges':[{'from':'x','to':'x','kind':'resume','branch':'fallback'}]}
        facts=extract_business(self.index(),manifest,0,16);notes=blank_explanations(facts)
        notes['cards']['business::x'].update({'steps':[{'title':'Step','detail':'Detail'}],
           'branches':[{'id':'fallback','kind':'degrade','title':'<bad>','state':'raw',
                        'items':[{'condition':'optional fails','returns':'raw','handling':'continue'}]}]})
        target=self.root/'review.html';render(facts,notes,target)
        text=target.read_text(encoding='utf-8')
        self.assertIn('data-resume="card-1"',text);self.assertIn('class="branch degrade"',text)
        self.assertIn('&lt;bad&gt;',text)


if __name__=='__main__':unittest.main()
