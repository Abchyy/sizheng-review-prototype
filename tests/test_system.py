import copy
import json
import tempfile
import unittest
from pathlib import Path
from sizheng.core import Graph, parse_jev, segment, validate_review
from sizheng.harness import Harness
from sizheng.providers import ProviderError
from sizheng.verify import verify

class FakeClient:
    def __init__(self, answer='routine',fail=None):
        self.runtime=Path(tempfile.mkdtemp());self.answer=answer;self.fail=fail;self.calls=[]
    def post(self, provider, payload):
        self.calls.append(provider)
        if self.fail:raise ProviderError('test failure')
        if provider == 'jev':
            p={k:float(k==self.answer) for k in ['routine','deep','human']}
            body={'model':'typesafe/jev-1.13','answers':{'route':{'type':'choice','choice':self.answer,'probabilities':p}}}
        else:body={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'verdict':'no_issue','summary':'fixture','findings':[]})}}]}
        return {'provider':provider,'response':body,'latency_s':0,'cost_usd':0}

class SystemTests(unittest.TestCase):
    def test_source_and_freeze_integrity(self):self.assertTrue(verify()['ok'])
    def test_graph_links_alias_and_traverses(self):
        g=Graph();self.assertIn('curriculum',g.link('课程思政'))
        self.assertTrue({'F1','F2','F3','F4'} <= {f['id'] for f in g.retrieve('课程思政')})
        self.assertEqual(g.retrieve('不存在的试点文件'),[])
    def test_time_filter_excludes_future_validity(self):
        g=Graph();g.facts['F1']['valid_from']='2030-01-01'
        self.assertNotIn('F1',[f['id'] for f in g.retrieve('课程思政',as_of='2026-01-01')])
    def test_probability_parser_rejects_nan_and_boolean(self):
        body={'model':'typesafe/jev-1.13','answers':{'route':{'type':'choice','choice':'routine','probabilities':{'routine':1,'deep':0,'human':0}}}}
        parse_jev(body)
        for val in [float('nan'),True,-1,2]:
            bad=copy.deepcopy(body);bad['answers']['route']['probabilities']['routine']=val
            with self.assertRaises(ValueError):parse_jev(bad)
    def test_citation_requires_exact_span_source_and_quote(self):
        ev=Graph().retrieve('课程思政')
        review={'verdict':'issue','summary':'fixture','findings':[{'span':'课程思政','type':'scope','explanation':'fixture','suggestion':'fixture','evidence_ids':['invented'],'evidence_quotes':['invented']}]}
        self.assertEqual(validate_review(review,'课程思政',ev)['citation_status'],'invalid')
        review['findings'][0].update(evidence_ids=['F3'],evidence_quotes=['让所有高校、所有教师、所有课程都承担好育人责任'])
        self.assertEqual(validate_review(review,'课程思政',ev)['citation_status'],'verified')
        self.assertFalse(review['semantic_entailment_verified'])
    def test_explicit_claim_overrides_fast_routine(self):
        client=FakeClient();h=Harness(client,memory=False)
        r=h.review('课程思政指导纲要于2020年5月28日印发。')
        self.assertEqual(client.calls,['jev','deepseek'])
        self.assertEqual(r['chunks'][0]['route_reason'],'claim_or_context_override')
    def test_routine_avoids_deep_call(self):
        client=FakeClient();h=Harness(client,memory=False);r=h.review('老师邀请同学分享学习体会。')
        self.assertEqual(client.calls,['jev']);self.assertEqual(r['verdict'],'no_issue')
    def test_api_failure_is_human_not_clear(self):
        r=Harness(FakeClient(fail=True),memory=False).review('课堂讨论。')
        self.assertEqual(r['verdict'],'insufficient');self.assertTrue(r['requires_human'])
    def test_supporting_findings_do_not_override_explicit_verdict(self):
        class SupportingClient(FakeClient):
            def post(self,provider,payload):
                r=super().post(provider,payload)
                if provider=='deepseek':
                    r['response']['choices'][0]['message']['content']=json.dumps({'verdict':'no_issue','summary':'supported','findings':[{'span':'课程思政','type':'fact','explanation':'supported','suggestion':'无需修改','evidence_ids':['F1'],'evidence_quotes':['2020年5月28日']}]})
                return r
        r=Harness(SupportingClient(),memory=False).review('课程思政',mode='llm_graph')
        self.assertEqual(r['verdict'],'no_issue')
    def test_invalid_deep_response_preserves_paid_trace(self):
        class InvalidClient(FakeClient):
            def post(self,provider,payload):
                r=super().post(provider,payload)
                if provider=='deepseek':r['response']['choices'][0]['message']['content']='{}'
                return r
        r=Harness(InvalidClient(),memory=False).review('课程思政',mode='llm_graph')
        self.assertEqual(r['verdict'],'insufficient')
        self.assertEqual(len(r['traces']),1)
    def test_segmentation_keeps_long_paragraph(self):
        text='甲'*3001;self.assertEqual(''.join(segment(text)),text)
        with self.assertRaises(ValueError):segment('甲'*8001)
    def test_metrics_failures_remain_in_workflow_denominator(self):
        from sizheng.evaluate import metrics
        rows=[{'execution_status':'failed'}]
        m=metrics(rows);self.assertEqual(m['n_total'],1);self.assertEqual(m['auto_clear_coverage'],0);self.assertEqual(m['human_review_fraction'],1)

if __name__=='__main__':unittest.main()
