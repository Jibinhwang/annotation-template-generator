#!/usr/bin/env python3
"""
render_v2.py — plan + hits.csv → template.html (MTurk) / preview.html (로컬)

    python render_v2.py prep_out/hits.csv --plan plan.json --out render_out [--all-previews]

v1 render.py와 같은 외형(사수 템플릿 구조·CSS)을 쓰되, 화면 구성은 전부 plan.display / plan.questions 에서 온다.
위젯: multi_select, single_choice, likert, free_text.  반복: per="unit" 1회 / per="role:<r>" 그 role 원소마다.
"""
import argparse, csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from plan import load_plan
from theme import CSS as CSS_V1, esc

csv.field_size_limit(10**9)

CSS = CSS_V1 + r"""
.q-block{background:#fff;border:2px solid #ddd6fe;border-radius:12px;padding:14px 16px;margin-bottom:14px;}
.q-prompt{font-size:15px;font-weight:600;color:#374151;margin-bottom:10px;}
.rep-item{border-top:1px dashed #e5e7eb;padding:10px 0;} .rep-item:first-of-type{border-top:none;}
.rep-text{display:flex;gap:8px;align-items:flex-start;font-size:14px;color:#1e293b;margin-bottom:8px;}
.likert{display:flex;gap:6px;flex-wrap:wrap;align-items:center;} .likert-lbl{font-size:12px;color:#6b7280;margin:0 6px;}
.lk-opt{cursor:pointer;} .lk-opt input{display:none;} .lk-btn{display:inline-block;min-width:38px;text-align:center;padding:8px 10px;border-radius:8px;border:2px solid #d1d5db;background:#f9fafb;font-weight:700;color:#374151;}
.lk-opt.ab-sel .lk-btn{background:#7c3aed;color:#fff;border-color:#7c3aed;}
.ft{width:100%;box-sizing:border-box;min-height:70px;border:2px solid #d1d5db;border-radius:8px;padding:8px 10px;font:inherit;font-size:14px;} .ft:focus{outline:none;border-color:#7c3aed;}
.ft-count{font-size:12px;color:#6b7280;text-align:right;}
.sc-row{display:flex;gap:10px;flex-wrap:wrap;} .sc-opt{cursor:pointer;} .sc-opt input{display:none;}
.sc-btn{display:inline-block;padding:9px 18px;border-radius:9px;border:2px solid #d1d5db;background:#f9fafb;font-weight:700;font-size:14px;color:#374151;}
.sc-opt.ab-sel .sc-btn{background:#4f46e5;color:#fff;border-color:#4f46e5;}
.ctx-list{margin:6px 0 0;}
"""


def instructions_html(ins, n_items):
    defs = "".join(f'<div class="trait-def-row"><span class="trait-def-label">{esc(k)}:</span> <span class="def-text">{v}</span></div>' for k, v in ins.get("definitions", []))
    howto = "".join(f"<li>{h}</li>" for h in ins.get("howto", []))
    bg = f'<h3>Background:</h3><p>{ins["background"]}</p>' if ins.get("background") else ""
    dd = f'<h3>Definitions:</h3><div class="trait-def-box">{defs}</div>' if defs else ""
    tip = f'<div class="notice-box notice-tip">&#9733; <strong>Tip:</strong> {ins["tip"]}</div>' if ins.get("tip") else ""
    return f"""
<div class="panel panel-primary"><div class="panel-heading"><strong>Instructions</strong></div><div class="panel-body">
<p><span class="highlight-yellow">{ins["summary"]}</span></p>{bg}{dd}
<h3>How to Evaluate:</h3><ul>{howto}<li>You must answer every required question before submitting.</li></ul>{tip}
<div class="notice-box notice-attention">&#9888; <strong>Attention Check Notice:</strong> Some items have an obvious answer and are used to check attention. Responses that fail these checks may be <strong>rejected</strong>.</div>
<div class="notice-box notice-research">&#9888; <strong>Research Use Notice:</strong> Only your responses will be used for academic research purposes.</div>
</div></div>
<div class="panel-body"><strong><span style="font-size:12px;">Your current progress</span></strong>
<div id="progressBarContainer"><div id="progressBar"><span id="progressPercentage">0%</span></div></div></div>
<div class="panel-body highlight-remaining"><div id="incompleteContent"><strong>&nbsp;</strong></div></div>
<p style="text-align:center;color:#64748b;font-size:14px;margin:16px 0;">Click the tabs below to navigate between items ({n_items} items).</p>"""


JS = r"""
function parseList(v){ if (typeof v==='string'){ try{return JSON.parse(v);}catch(e){return [v];} } return Array.isArray(v)?v:[v]; }
function esc(s){ if(s==null) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function escBr(s){ return esc(s).replace(/\n/g,'<br>'); }
var ROLES=parseList(D.roles), UNITS=parseList(D.unit), N=ROLES.length;
var DISP=PLAN.display, QS=PLAN.questions;

function idxBadge(i){ return '<span class="chk-idx">'+(i+1)+'</span>'; }
function renderValue(v){
  if (Array.isArray(v)){ var h='<ol class="num-list">'; for (var i=0;i<v.length;i++) h+='<li>'+idxBadge(i)+' <span>'+escBr(typeof v[i]==='object'?JSON.stringify(v[i]):v[i])+'</span></li>'; return h+'</ol>'; }
  if (v && typeof v==='object') return '<pre style="white-space:pre-wrap;margin:0">'+esc(JSON.stringify(v,null,1))+'</pre>';
  return escBr(v);
}
function sourceValue(src, idx){
  if (src==='unit') return UNITS[idx].value; if (src==='unit.a') return UNITS[idx].a; if (src==='unit.b') return UNITS[idx].b;
  if (src && src.indexOf('role:')===0) return ROLES[idx][src.slice(5)]; return null;
}
function card(cls,title,body){ return '<div class="script-card '+cls+'"><div class="script-hdr '+cls+'-hdr">'+esc(title)+'</div><div class="script-body">'+body+'</div></div>'; }

// ---- 위젯
function wMulti(name, q, idx){
  var opts = q.options_from ? (sourceValue(q.options_from, idx)||[]) : (q.options||[]);
  var h='<div class="chk-list">';
  for (var i=0;i<opts.length;i++) h+='<label class="chk-opt"><input type="checkbox" name="'+name+'" value="'+i+'">'+idxBadge(i)+'<span class="chk-txt">'+escBr(opts[i])+'</span></label>';
  if (q.none_option) h+='<label class="chk-opt chk-none"><input type="checkbox" name="'+name+'" value="none"><span class="chk-txt">'+esc(q.none_option)+'</span></label>';
  return h+'</div>';
}
function wSingle(name, q){
  var h='<div class="sc-row">';
  for (var i=0;i<q.options.length;i++) h+='<label class="sc-opt" data-name="'+name+'"><input type="radio" name="'+name+'" value="'+esc(q.options[i])+'"><span class="sc-btn">'+esc(q.options[i])+'</span></label>';
  return h+'</div>';
}
function wLikert(name, q){
  var s=q.scale, h='<div class="likert">'+(s.min_label?'<span class="likert-lbl">'+esc(s.min_label)+'</span>':'');
  for (var v=s.min; v<=s.max; v++) h+='<label class="lk-opt" data-name="'+name+'"><input type="radio" name="'+name+'" value="'+v+'"><span class="lk-btn">'+v+'</span></label>';
  return h+(s.max_label?'<span class="likert-lbl">'+esc(s.max_label)+'</span>':'')+'</div>';
}
function wText(name, q){ return '<textarea class="ft" name="'+name+'" data-min="'+(q.min_chars||0)+'" placeholder="Type here..."></textarea><div class="ft-count" id="cnt_'+name+'"></div>'; }
function widget(q, name, idx){
  if (q.widget==='multi_select') return wMulti(name,q,idx); if (q.widget==='single_choice') return wSingle(name,q);
  if (q.widget==='likert') return wLikert(name,q); return wText(name,q);
}
function reps(q, idx){ // 반복 대상 리스트 (per=unit이면 [null])
  if (!q.per || q.per==='unit') return [null];
  var v=sourceValue(q.per, idx); return Array.isArray(v)?v:[v];
}
function qname(idx, qi, ri){ return 'q_'+idx+'_'+qi+'_'+ri; }

function buildItem(idx){
  var ctx='';
  for (var c=0;c<(DISP.context||[]).length;c++){ var cc=DISP.context[c], v=ROLES[idx][cc.role]; if (v==null) continue;
    ctx+='<div class="ctx-sub"><span class="info-k">'+esc(cc.label||cc.role)+'</span><div class="'+(Array.isArray(v)?'ctx-list':'ctx-query')+'">'+renderValue(v)+'</div></div>'; }
  var cards='';
  if (DISP.left) cards+=card('script-card-a', DISP.left.label||'', renderValue(sourceValue(DISP.left.source, idx)));
  if (DISP.right) cards+=card('script-card-b', DISP.right.label||'', renderValue(sourceValue(DISP.right.source, idx)));
  var qh='';
  for (var qi=0; qi<QS.length; qi++){ var q=QS[qi], rs=reps(q, idx);
    qh+='<div class="q-block"><div class="q-prompt">'+q.prompt+(q.required===false?' <span style="color:#9ca3af;font-weight:400">(optional)</span>':'')+'</div>';
    for (var ri=0; ri<rs.length; ri++){
      qh+='<div class="rep-item">'+(rs[ri]!==null?'<div class="rep-text">'+idxBadge(ri)+'<span>'+escBr(rs[ri])+'</span></div>':'')+widget(q, qname(idx,qi,ri), idx)+'</div>';
    }
    qh+='</div>';
  }
  return '<div class="tab-inner"><h3 class="tab-title">Item '+(idx+1)+' / '+N+'</h3>'
    +(ctx?'<div class="prod-card"><div class="prod-body">'+ctx+'</div></div>':'')
    +(cards?'<div class="scripts-side-by-side"'+(DISP.right?'':' style="grid-template-columns:1fr"')+'>'+cards+'</div>':'')
    +'<div class="comp-section"><div class="comp-section-hdr">'+esc(PLAN.instructions.title||'Your judgment')+'</div><div class="comp-card">'+qh+'</div></div></div>';
}

var tabBar=document.getElementById('tabBar'), tabBody=document.getElementById('tabBody');
for (var i=0;i<N;i++){
  var b=document.createElement('button'); b.type='button'; b.className='tab-btn'; b.textContent='Item '+(i+1);
  b.onclick=(function(k){return function(){showTab(k);};})(i); tabBar.appendChild(b);
  var p=document.createElement('div'); p.className='tab-pane'; p.id='pane_'+i; p.innerHTML=buildItem(i); tabBody.appendChild(p);
}
function showTab(k){ var bs=tabBar.children, ps=tabBody.children; for (var i=0;i<N;i++){ bs[i].classList.toggle('active',i===k); ps[i].style.display=(i===k)?'block':'none'; } window.scrollTo(0, tabBar.offsetTop-10); }
showTab(0);

// ---- 답 읽기 / 완료 판정
function readOne(q, name){
  if (q.widget==='multi_select'){ var v=[]; var els=document.querySelectorAll('input[name="'+name+'"]:checked'); for (var i=0;i<els.length;i++) v.push(els[i].value);
    if (!v.length) return {value:null, done:false}; var none=v.indexOf('none')>=0; return {value: none?[]:v.map(Number), none:none, done:true}; }
  if (q.widget==='free_text'){ var t=document.querySelector('textarea[name="'+name+'"]'); var s=t?t.value.trim():''; var min=q.min_chars||0;
    return {value:s, done: q.required===false ? true : s.length>=Math.max(1,min)}; }
  var r=document.querySelector('input[name="'+name+'"]:checked'); var val=r?(q.widget==='likert'?Number(r.value):r.value):null;
  return {value:val, done: val!==null};
}
function itemAnswer(idx){
  var out={}, done=true;
  for (var qi=0; qi<QS.length; qi++){ var q=QS[qi], rs=reps(q, idx), arr=[];
    for (var ri=0; ri<rs.length; ri++){ var a=readOne(q, qname(idx,qi,ri)); arr.push(a.value); if (q.required!==false && !a.done) done=false; }
    out[q.id] = (!q.per||q.per==='unit') ? arr[0] : arr;
  }
  return {answers:out, done:done};
}
function updateProgress(){
  var done=0, inc=[];
  for (var i=0;i<N;i++){ if (itemAnswer(i).done) done++; else inc.push(i+1); }
  var pct=Math.round(done/N*100);
  document.getElementById('progressBar').style.width=pct+'%'; document.getElementById('progressPercentage').innerText=pct+'%';
  var btn=document.getElementById('submitButton'); btn.disabled=(done!==N); btn.className=(done===N)?'btn-enabled':'';
  document.getElementById('incompleteContent').innerHTML = done===N ? '<strong style="color:#10b981;">All items complete! You can now submit.</strong>'
      : '<strong style="color:#dc2626;">'+(N-done)+' item(s) remaining - incomplete: '+inc.join(', ')+'</strong>';
  var bs=tabBar.children; for (var i=0;i<N;i++) bs[i].classList.toggle('done', itemAnswer(i).done);
}
document.addEventListener('change', onInput); document.addEventListener('input', onInput);
function onInput(e){
  var t=e.target; if(!t||!t.name) return;
  if (t.type==='checkbox'){ var sib=document.querySelectorAll('input[name="'+t.name+'"]');
    if (t.value==='none' && t.checked){ for (var i=0;i<sib.length;i++) if (sib[i]!==t) sib[i].checked=false; }
    else if (t.value!=='none' && t.checked){ for (var i=0;i<sib.length;i++) if (sib[i].value==='none') sib[i].checked=false; }
    for (var i=0;i<sib.length;i++) sib[i].closest('.chk-opt').classList.toggle('chk-sel', sib[i].checked); }
  if (t.type==='radio'){ var labs=document.querySelectorAll('label[data-name="'+t.name+'"]'); for (var i=0;i<labs.length;i++) labs[i].classList.toggle('ab-sel', labs[i].querySelector('input').checked); }
  if (t.tagName==='TEXTAREA'){ var c=document.getElementById('cnt_'+t.name); var min=Number(t.getAttribute('data-min')||0); if(c) c.textContent = min? (t.value.trim().length+' / '+min+' chars min') : ''; }
  updateProgress();
}
function collectAnswers(){ var res={hit_id:D.hit_id, plan:PLAN.name, items:[]}; for (var i=0;i<N;i++) res.items.push({item_idx:i, answers:itemAnswer(i).answers}); return res; }
updateProgress();
"""
JS_MTURK = r"""
function handleFormSubmit(){
  var form=document.querySelector('crowd-form'); if(!form) return;
  var hidden=form.querySelector('input[name="input_answers"]');
  if(!hidden){ hidden=document.createElement('input'); hidden.type='hidden'; hidden.name='input_answers'; form.appendChild(hidden); }
  hidden.value=JSON.stringify(collectAnswers());
  var inputs=document.querySelectorAll('input[type=checkbox],input[type=radio],textarea'); for (var i=0;i<inputs.length;i++) inputs[i].removeAttribute('name');
  form.submit();
}"""
JS_PREVIEW = r"""
function handleFormSubmit(){ var out=document.getElementById('previewOut'); out.style.display='block';
  out.querySelector('pre').textContent=JSON.stringify(collectAnswers(),null,2); out.scrollIntoView({behavior:'smooth'}); }"""

TEMPLATE_DATA = ["hit_id", "roles", "unit"]   # qid / is_attention / unit_meta / expected 는 의도적으로 제외 (소스 노출 방지)


def page(plan, n_items, data_js, mode):
    body = instructions_html(plan["instructions"], n_items) + """
<div id="summary-container"><div id="tabBar"></div><div id="tabBody"></div>
<div style="text-align:center;margin-top:30px;"><button disabled="disabled" id="submitButton" type="button" onclick="handleFormSubmit()">Submit</button></div>
<div id="previewOut"><b>Submitted answers (what MTurk would receive as <code>input_answers</code>)</b><pre></pre></div></div>"""
    pl = {k: plan[k] for k in ("name", "display", "questions", "instructions")}
    script = f"<script>\nvar PLAN={json.dumps(pl, ensure_ascii=False)};\n{data_js}\n{JS}\n{JS_MTURK if mode == 'mturk' else JS_PREVIEW}\n</script>"
    if mode == "mturk":
        return f'<script src="https://assets.crowd.aws/crowd-html-elements.js"></script>\n<crowd-form>\n<section class="entire-UI">{body}\n{script}\n</section>\n</crowd-form>\n<style>{CSS}</style>\n'
    banner = '<div class="preview-banner"><b>Local preview</b> — one HIT from hits.csv is inlined. Submit shows the answer JSON instead of sending to MTurk.</div>'
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(plan["instructions"]["title"])} — preview</title><style>{CSS}</style></head><body><section class="entire-UI">{banner}{body}\n{script}\n</section></body></html>')


def run(hits_csv, plan, out, preview_hit=0, all_previews=False):
    rows = list(csv.DictReader(open(hits_csv, encoding="utf-8")))
    if not rows:
        raise SystemExit("hits.csv 비어 있음")
    os.makedirs(out, exist_ok=True)
    n = int(rows[0]["n_items"])
    data_mturk = "var D={roles:${roles},unit:${unit},hit_id:\"${hit_id}\"};"
    open(os.path.join(out, "template.html"), "w", encoding="utf-8").write(page(plan, n, data_mturk, "mturk"))

    def prev(row):
        d = {"hit_id": row["hit_id"], "roles": json.loads(row["roles"]), "unit": json.loads(row["unit"])}
        return page(plan, int(row["n_items"]), "var D=" + json.dumps(d, ensure_ascii=False).replace("</", "<\\/") + ";", "preview")
    open(os.path.join(out, "preview.html"), "w", encoding="utf-8").write(prev(rows[preview_hit]))
    if all_previews:
        pd = os.path.join(out, "preview_all"); os.makedirs(pd, exist_ok=True)
        for r in rows:
            open(os.path.join(pd, r["hit_id"] + ".html"), "w", encoding="utf-8").write(prev(r))
    print(f"[{plan['name']}] wrote {out}/template.html, {out}/preview.html" + (f", {len(rows)} previews" if all_previews else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hits_csv"); ap.add_argument("--plan", required=True); ap.add_argument("--out", default="render_out")
    ap.add_argument("--preview-hit", type=int, default=0); ap.add_argument("--all-previews", action="store_true")
    a = ap.parse_args()
    run(a.hits_csv, load_plan(a.plan), a.out, a.preview_hit, a.all_previews)


if __name__ == "__main__":
    main()
