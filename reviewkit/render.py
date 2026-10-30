from pathlib import Path
import html
from .storage import digest, resolve_source
from .engine import validate_explanations

TEMPLATES = Path(__file__).resolve().parent/'templates'


def e(value):return html.escape(str(value))
def pre(value):return '<pre>'+e(value)+'</pre>'
def p(value):return '<p>'+e(value)+'</p>'
def fold(title,body):return '<details><summary>'+e(title)+'</summary><div class="inside">'+body+'</div></details>'
def table(headers,rows):
    return '<div class="table-scroll"><table><thead><tr>'+''.join('<th>'+e(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def reference(repo,file,line,end_line=None):
    path=resolve_source(repo,file)
    return '<a href="'+e(path.as_uri())+'#L'+str(line)+'">'+e(file)+':'+str(line)+(('–'+str(end_line)) if end_line and end_line!=line else '')+'</a> <button class="copy" data-copy="'+e(str(path)+':'+str(line))+'">复制位置</button>'


def render(facts, explanations, target, title='代码流程 Review'):
    freshness=validate_explanations(explanations,facts)
    repo=Path(facts['repository']); fn={f['id']:f for f in facts['functions']}
    missing_or_changed=[]
    for name,file_hash in facts['source_files'].items():
        path=resolve_source(repo,name)
        if not path.is_file() or digest(path.read_bytes())!=file_hash:missing_or_changed.append(name)
    cards=[]; rows=[]
    flow=facts.get('flow',{})
    stage_ids={f.get('flow_id'): 'card-'+str(n) for n,i in enumerate(facts['root_ids'],1) for f in [fn[i]]}
    for number,ident in enumerate(facts['root_ids'],1):
        f=fn[ident]; note=explanations.get('cards',{}).get(ident,{})
        explained=bool(note.get('steps'))
        state='current' if freshness.get(ident) and not missing_or_changed else 'stale'
        if not explained:state='automatic'
        status={'current':'源码解释 · 证据匹配（未运行验证）','stale':'旧解释 · 待复核','automatic':'自动提取 · 业务含义待补充'}[state]
        link=lambda item:reference(repo,item['file'],item['line'],item.get('end_line'))
        label=note.get('title') if explained else f['name']
        inputs=p(note.get('input','')) if note.get('input') else p('源码参数：')
        inputs+=''.join(p(x) for x in note.get('inputs',[]))
        if f.get('view')!='business':inputs+=pre(f['parameters'])
        if explained:
            steps=''
            for n,step in enumerate(note['steps'],1):
                ref=fn[step.get('reference',ident)]
                steps+=fold(f'{n:02d} · '+step['title'],p(step['detail'])+link(ref))
        else:
            steps=p('以下为语法提取；业务阶段和实际执行顺序仍需解释。')
            for n,stmt in enumerate(f['statements'],1):
                calls=[c['name'] for c in f['calls'] if stmt['line']<=c['line']<=stmt['end_line']]
                label_auto=' / '.join(dict.fromkeys(calls))[:100] or stmt['kind']
                steps+=fold(f'{n:02d} · '+label_auto,pre(stmt['text'])+link({'file':f['file'],**stmt}))
        branches=note.get('branches',[])
        errors=note.get('errors',[])+[item for branch in branches for item in branch['items']]
        detail_errors=table(['条件','返回值','收尾／下一步'],[(e(x['condition']),e(x['returns']),e(x['handling'])) for x in errors]) if errors else p('错误业务解释尚未补充。下面的自动证据含 ?、显式分支和错误构造点；不代表全部错误路径已归纳。')
        auto=''
        auto+=fold('调用表达式 · '+str(len(f['calls'])),table(['调用名称','接收者（语法）','位置'],[(e(c['name']),e(c.get('receiver') or '—'),reference(repo,f['file'],c['line'],c['end_line'])) for c in f['calls']]))
        auto+=fold('分支 · '+str(len(f['branches'])),table(['语法','条件','其他分支'],[(e(b['kind']),pre(b['condition']),p('含 else' if b['has_else'] else '无 else')+''.join(pre(a) for a in b['arms'])+reference(repo,f['file'],b['line'])) for b in f['branches']]))
        auto+=fold('? 传播点 · '+str(len(f['tries'])),''.join(pre(t['text'])+reference(repo,f['file'],t['line']) for t in f['tries']))
        auto+=fold('返回与错误构造', ''.join(pre(x.get('text',x.get('expression','')))+reference(repo,f['file'],x['line']) for x in f['returns']+f['errors']) or p('本函数内未提取到显式 return 或命名错误构造；这不表示不会出错。'))
        auto+=fold('Result 等组合调用',table(['名称','位置'],[(e(c['name']),reference(repo,f['file'],c['line'])) for c in f['combinators']]))
        auto+=fold('宏（未展开）', ''.join(pre(x['text']) for x in f['macros']) or p('无宏调用。'))
        output=p(note.get('normal_output',''))+(pre(f['return_type']) if f.get('view')!='business' else '')
        output+=''.join(p(x) for x in note.get('outputs',[]))
        related=[t for t in facts['types'] if t['name'] in f['return_type']] if f.get('view')!='business' else []
        output+=''.join(fold('返回相关类型 · '+t['name'],pre(t['text'])+link(t)) for t in related)
        source=f.get('source','')
        if not source:
            path=resolve_source(repo,f['file'])
            if path.exists():source='\n'.join(path.read_text(encoding='utf-8-sig').splitlines()[f['line']-1:f['end_line']])
        if note.get('state'):steps+='<div class="state">'+e(note['state'])+'</div>'
        sources=''.join('<div class="source"><strong>'+e(s.get('label','源码'))+'</strong>'+reference(repo,s['file'],s['line'],s['end_line'])+fold('引用上下文 · '+s['kind'],pre(s['snippet']))+'</div>' for s in f.get('sources',[]))
        implementation=fold('功能实现',steps)+fold('错误返回与降级',detail_errors)+fold('自动证据',auto)+fold('代码位置与源码',sources+link(f)+pre(source))
        if note.get('notes'):implementation+=fold('实现边界', ''.join(p(x) for x in note['notes']))
        sidehtml=[]
        for side in ['left','right']:
            groups=[b for b in branches if b.get('side','right' if b['kind']=='degrade' else 'left')==side]
            items=[x for x in note.get('errors',[]) if x.get('side','left')==side]
            if groups:
                body=''
                for b in groups:
                    resume=next((x for x in flow.get('edges',[]) if x['kind']=='resume' and x['from']==f.get('flow_id') and x['branch']==b['id']),None)
                    attrs=' data-branch="'+e(b['id'])+'"'
                    if resume:attrs+=' data-resume="'+e(stage_ids[resume['to']])+'" data-port="'+e(resume.get('port','output'))+'"'
                    kind='降级后继续' if b['kind']=='degrade' else '错误／中止'
                    detail=''.join(fold(x['condition'],pre(x['returns'])+p(x['handling'])) for x in b['items'])
                    if resume:detail+='<a class="resume-link" href="#'+e(stage_ids[resume['to']])+'">'+e(resume.get('label','回到主流程'))+'</a>'
                    body+='<div class="branch '+b['kind']+'"'+attrs+'><div class="branch-kind">'+kind+'</div>'+fold(b.get('title',kind),p(b.get('state',''))+detail)+'</div>'
            elif not items and side=='left' and not errors:
                body=p('待补充错误条件与返回值。')
            elif not items:body=''
            else:body=''.join(fold(x['condition'],pre(x['returns'])+p(x['handling'])) for x in items)
            sidehtml.append('<aside class="fault '+side+'">'+(body if groups else '<h3>错误输出</h3>'+body if body else '<span class="muted">此侧无已解释分支</span>')+'</aside>')
        heading=label if f.get('view')=='business' else f['name']
        subtitle=f['name'] if f.get('view')=='business' else label
        cards.append(f'<section class="stage" id="card-{number}" data-flow-id="{e(f.get("flow_id",""))}" data-status="{state}"><div class="spine"><div class="io input">'+fold('输入 · '+note.get('input_title','函数参数'),inputs)+'</div><article class="function"><div class="meta">'+f'{number:02d} / '+e(note.get('scope',''))+' · '+e(status)+'</div><h2><button class="function-link" data-source="source-'+str(number)+'">'+e(heading)+'</button></h2><p class="fn-name">'+e(subtitle)+'</p>'+implementation+'</article></div><div class="io stage-output">'+fold('正常输出 · '+note.get('output_title',f['return_type']),output)+'</div>'+''.join(sidehtml)+'</section>')
        rows.append((str(number),e(f['name']),link(f),e(status)))
    callers=table(['调用者候选','类别','位置'],[(e(c['caller']), '测试' if c['test'] else '生产候选', reference(repo,c['file'],c['line'])) for c in facts['callers']])
    macros=table(['宏内提及（未解析为普通调用）','位置'],[(e(m['caller']),reference(repo,m['file'],m['line'])) for m in facts['macro_mentions']])
    edges=table(['来源','调用名','候选目标'],[(e(x['from']),e(x['name']),'<br>'.join(e(c) for c in x['candidates'])) for x in facts['edges']])
    inventory=fold('按图索骥 · 查看顺序',table(['顺序','函数','文件与代码行','解释状态'],rows))
    inventory+=fold('调用关系 · 语法候选',callers+edges+macros)
    inventory+=fold('相关类型与错误枚举',''.join(fold(t['name'],pre(t['text'])+reference(repo,t['file'],t['line'],t['end_line'])) for t in facts['types']))
    inventory+=fold('生成信息与边界',p('顺序由函数选择或业务清单给出；调用边仅为语法候选。默认无运行验证。')+pre(facts['index_stats'])+p('深度上限：'+str(facts['limits']['depth'])+'；节点上限：'+str(facts['limits']['max_nodes']))+p('超限未纳入：'+str(len(facts['limits']['truncated_nodes'])))+p('解析错误文件：'+str(len(facts.get('parse_errors',[]))))+p('相关文件变化后请重新 build；解释证据不匹配时显示待复核。'))
    warning=p('当前源码与这份事实快照不同：'+', '.join(missing_or_changed)) if missing_or_changed else ''
    template=(TEMPLATES/'review.html').read_text(encoding='utf-8')
    values={'TITLE':e(title),'CSS':(TEMPLATES/'review.css').read_text(encoding='utf-8'),
            'JS':(TEMPLATES/'review.js').read_text(encoding='utf-8'),'WARNING':warning,
            'CARDS':''.join(cards),'INVENTORY':inventory,'COUNT':str(len(cards)),
            'GENERATED':e(facts['generated_utc']),
            'START':'<div class="terminal" id="flow-start">'+e(flow['start_label'])+'</div>' if flow.get('start_label') else '',
            'END':'<div class="terminal" id="flow-end">'+e(flow['end_label'])+'</div>' if flow.get('end_label') else ''}
    # Substitute once: annotation/source text containing template markers is never interpreted.
    import re
    result=re.sub(r'\{\{([A-Z]+)\}\}',lambda m:values[m.group(1)],template)
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(result,encoding='utf-8')
    return {'cards':len(cards),'explained':sum(bool(explanations.get('cards',{}).get(i,{}).get('steps')) for i in facts['root_ids']),
            'stale_cards':[i for i,s in freshness.items() if not s], 'source_changed':missing_or_changed}
