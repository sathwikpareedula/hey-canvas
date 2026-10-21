"""Offline, standard-library-only Hey Canvas academic answer evaluator.

Usage: python scripts/evaluate.py --responses path/to/recorded_answers.json
Input: {"responses": [{"case_id":"...","answer":"...","source_ids":["..."],
"elapsed_ms": 1234, "course_id":"...", "status":"completed"}, ...]}
Never contacts Canvas or Ollama. No private data should be committed.
"""
import argparse
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'QA' / 'academic_ai_benchmark_cases.json'
RESULTS = ROOT / 'QA' / 'academic_ai_benchmark_results.json'
REPORT = ROOT / 'QA' / 'academic_ai_evaluation_report.md'
LEAK = re.compile(r'ROUTING_EVIDENCE|TOOL_PLAN|SYSTEM POLICY|<\|(?:system|developer)\|>|BEGIN_INTERNAL', re.I)


def extract_xy(answer):
    """Recognize simple numerical x=2, y=3 answer; avoid false matches in equations."""
    def match(axis):
        m = re.search(r'(?<![A-Za-z])' + axis + r'\s*=\s*(-?\d+(?:\.\d+)?)(?![\d.])', answer, re.I)
        return float(m.group(1)) if m else None
    return match('x'), match('y')


def check_rule(rule, answer):
    typ = rule['type']
    lower = answer.casefold()
    if typ == 'contains_all':
        missing = [x for x in rule['values'] if x.casefold() not in lower]
        return not missing, f'missing text: {missing}' if missing else ''
    if typ == 'not_contains':
        found = [x for x in rule['values'] if x.casefold() in lower]
        return not found, f'forbidden text: {found}' if found else ''
    if typ == 'no_internal_leak':
        match = LEAK.search(answer)
        return match is None, f'internal text leak: {match.group(0)}' if match else ''
    if typ == 'date_window':
        # The adapter must supply an authoritative normalized window; free-form
        # answer strings are not reliable evidence of correctly routed dates.
        return None, 'requires adapter-provided normalized_window'
    if typ == 'numeric_pair':
        x, y = extract_xy(answer)
        if x is None or y is None:
            return False, 'missing parseable numerical x/y pair'
        good = math.isclose(x, rule['x'], abs_tol=rule.get('tolerance', .01)) and math.isclose(y, rule['y'], abs_tol=rule.get('tolerance', .01))
        return good, '' if good else f'expected ({rule["x"]},{rule["y"]}); got ({x},{y})'
    raise ValueError(f'unsupported check type {typ}')


def evaluate(cases, recordings):
    by_id = {}
    duplicates = []
    for record in recordings:
        cid = record.get('case_id')
        if cid in by_id:
            duplicates.append(cid)
        by_id[cid] = record
    rows = []
    for case in cases:
        cid = case['id']
        record = by_id.get(cid)
        if record is None:
            rows.append({'case_id':cid,'category':case['category'],'status':'NOT_RUN','issues':['no recording']})
            continue
        issues = []
        not_verified = []
        answer = record.get('answer')
        if not isinstance(answer, str) or not answer.strip():
            issues.append('missing answer text')
            answer = ''
        if record.get('status','completed') != 'completed':
            issues.append(f'request status: {record.get("status")}')
        source_ids = record.get('source_ids')
        if source_ids is None:
            not_verified.append('citation/source IDs not provided')
            source_ids = []
        for expected in case['expected_source_ids']:
            if expected not in source_ids:
                issues.append(f'missing expected source {expected}')
        for forbidden in case['forbidden_source_ids']:
            if forbidden in source_ids:
                issues.append(f'forbidden source {forbidden}')
        for rule in case['checks']:
            if rule['type'] == 'date_window':
                actual = record.get('normalized_window')
                if actual is None:
                    not_verified.append('normalized_window missing; cannot verify date routing')
                elif actual != rule['value']:
                    issues.append(f'expected date window {rule["value"]}; got {actual}')
            else:
                good, issue = check_rule(rule, answer)
                if good is False:
                    issues.append(issue)
        if record.get('course_id') and case['course_id'] not in ('all',record['course_id']):
            issues.append(f'course mismatch: expected {case["course_id"]}, got {record["course_id"]}')
        latency = record.get('elapsed_ms')
        if latency is not None and (not isinstance(latency,(int,float)) or latency < 0):
            issues.append('invalid elapsed_ms')
        status = 'FAIL' if issues else ('NOT_VERIFIED' if not_verified else 'PASS')
        rows.append({'case_id':cid,'category':case['category'],'status':status,'issues':issues,'unverified':not_verified,'elapsed_ms':latency})
    for cid in duplicates:
        for row in rows:
            if row['case_id'] == cid:
                row['issues'].append('duplicate case recording')
                row['status'] = 'FAIL'
    return rows


def retrieval_metrics(cases, recordings):
    gold = {x['id']: set(x['expected_source_ids']) for x in cases if x['expected_source_ids']}
    seen = {x['case_id']:x for x in recordings}
    tp=fp=fn=0
    per_case=[]
    for cid,expected in gold.items():
        rec=seen.get(cid)
        if rec is None or rec.get('source_ids') is None:
            continue
        predicted=set(rec['source_ids'])
        a=len(predicted & expected);b=len(predicted-expected);c=len(expected-predicted)
        tp+=a;fp+=b;fn+=c
        per_case.append({'case_id':cid,'precision':a/(a+b) if a+b else 0,'recall':a/(a+c) if a+c else 0})
    return {'evaluated_cases':len(per_case),'true_positive':tp,'false_positive':fp,'false_negative':fn,
            'micro_precision':tp/(tp+fp) if tp+fp else None,
            'micro_recall':tp/(tp+fn) if tp+fn else None,'per_case':per_case,
            'limitation':'Source IDs alone do not prove a citation supports its claim; human/quote-span validation remains required.'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--responses',type=Path,help='Recorded output JSON; omit to create NOT_RUN baseline')
    parser.add_argument('--out',type=Path,default=RESULTS)
    parser.add_argument('--report',type=Path,default=REPORT)
    args=parser.parse_args()
    cases=json.loads(CASES.read_text())['cases']
    if args.responses:
        data=json.loads(args.responses.read_text())
        recordings=data['responses']
        evidence_type=data.get('evidence_type','unspecified')
    else:
        recordings=[]
        evidence_type='none'
    results=evaluate(cases,recordings)
    summary=dict(Counter(x['status'] for x in results))
    metrics=retrieval_metrics(cases,recordings)
    payload={'schema_version':1,'generated_at_utc':datetime.now(timezone.utc).isoformat(),
             'source_branch':'integration/v12-validated-candidate-20261016 (remote reference only)',
             'evidence_type':evidence_type,'summary':summary,'retrieval':metrics,'results':results}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(payload,indent=2)+'\n')
    lines=['# Academic AI Evaluation', '',f'**Evidence:** {evidence_type}',
           f'**Cases:** {len(cases)}',f'**Results:** {summary}',
           '', '**Important:** NOT_RUN and NOT_VERIFIED are not passes. Synthetic fixture checks are not real Ollama/Windows acceptance.',
           '', '## Retrieval',f'Cases with labeled source judgments: {metrics["evaluated_cases"]}',
           f'Micro precision: {metrics["micro_precision"]}; micro recall: {metrics["micro_recall"]}',
           metrics['limitation'],'','## Cases','| ID | Status | Issue |','|---|---|---|']
    for row in results:
        issue='; '.join(row.get('issues',[])+row.get('unverified',[])).replace('|','\\|')
        lines.append(f'| {row["case_id"]} | {row["status"]} | {issue} |')
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text('\n'.join(lines)+'\n')
    print('evaluated',len(cases),'cases:',summary)
    print('wrote',args.out,args.report)

if __name__=='__main__':
    main()
