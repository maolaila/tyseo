(contract = {}) => {
  // Read-only geometry probes. Ambiguous overlap is triage, never automatic PASS.
  const findings = [], tolerance = 2, maxElements = 10000;
  const describe = e => e.id ? '#' + CSS.escape(e.id) : e.tagName.toLowerCase() + [...e.classList].slice(0, 3).map(c => '.' + CSS.escape(c)).join('');
  const rect = e => { const r = e.getBoundingClientRect(); return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height}; };
  const visible = e => { const s=getComputedStyle(e),r=rect(e); return s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity !== 0 && r.width>0 && r.height>0; };
  const related = (a,b) => a===b || a.contains(b) || b.contains(a);
  const intersects = (a,b) => Math.min(a.right,b.right)-Math.max(a.x,b.x)>tolerance && Math.min(a.bottom,b.bottom)-Math.max(a.y,b.y)>tolerance;
  const add = (rule,status,e,expected,actual,other=null) => findings.push({rule_id:rule,status,selector:describe(e),other_selector:other?describe(other):null,expected,actual,severity:status==='fail'?'P1':'P2',owner_layer:'template_or_asset_needs_triage'});
  const select = selector => { try {return [...document.querySelectorAll(selector)];} catch {findings.push({rule_id:'LAYOUT-CONTRACT',status:'blocked',selector,expected:'valid CSS selector',actual:'invalid selector',severity:'P1',owner_layer:'tool_contract'});return [];} };
  const all=select('body *');
  if(all.length>maxElements)findings.push({rule_id:'LAYOUT-COVERAGE',status:'needs_review',expected:'all elements scanned',actual:`${all.length} candidates exceeds ${maxElements} cap`,severity:'P2',owner_layer:'tool_limit'});
  const critical = new Set(), declared = new Set();
  for(const component of contract.components||[]) {
    const matches=select(component.selector);
    for(const e of matches)declared.add(e);
    if(component.required && !matches.some(visible))findings.push({rule_id:'LAYOUT-MISSING-COMPONENT',status:'blocked',selector:component.selector,expected:'required visible component in this state',actual:'absent or hidden',severity:'P1',owner_layer:'template_or_contract'});
    if(component.critical)for(const e of matches)critical.add(e);
  }
  const candidates=[...new Set([...all.slice(0,maxElements),...declared])].filter(visible);
  const root=document.documentElement;
  if(root.scrollWidth>innerWidth+tolerance)add('LAYOUT-PAGE-OVERFLOW','fail',root,`page width <= ${innerWidth+tolerance}`,root.scrollWidth);
  for(const e of candidates) {
    const r=rect(e),s=getComputedStyle(e),isCritical=critical.has(e);
    let clipped=false;
    for(let p=e.parentElement;p && p!==document.body;p=p.parentElement){
      const ps=getComputedStyle(p),pr=rect(p);
      if((/hidden|clip/.test(ps.overflowX)&&(r.x<pr.x-tolerance||r.right>pr.right+tolerance)) || (/hidden|clip/.test(ps.overflowY)&&(r.y<pr.y-tolerance||r.bottom>pr.bottom+tolerance))){
        add('LAYOUT-COMPONENT-CLIP',isCritical?'fail':'needs_review',e,'content fits clipping ancestor',{rect:r,ancestor:describe(p),ancestorRect:pr},p);clipped=true;break;
      }
    }
    if(!clipped && /hidden|clip/.test(s.overflow) && (e.scrollWidth>e.clientWidth+tolerance||e.scrollHeight>e.clientHeight+tolerance) && e.textContent.trim())
      add('LAYOUT-INTERNAL-CLIP',isCritical?'fail':'needs_review',e,'text/content fully available or approved truncation',{client:[e.clientWidth,e.clientHeight],scroll:[e.scrollWidth,e.scrollHeight]});
    const control=e.matches('a[href],button,input,select,textarea,summary,[role="button"],[role="tab"]');
    if(control && !e.matches(':disabled,[aria-disabled="true"]')) {
      const minimum=isCritical?44:24;
      if(r.width<minimum||r.height<minimum)add('LAYOUT-TARGET-SIZE',isCritical?'fail':'needs_review',e,`${minimum}px hit target or documented applicable exception`,r);
      if(r.x>=0 && r.y>=0 && r.right<=innerWidth && r.bottom<=innerHeight && s.pointerEvents!=='none'){
        const points=[[.5,.5],[.2,.2],[.8,.2],[.2,.8],[.8,.8]];
        const blocked=points.map(([x,y])=>document.elementFromPoint(r.x+r.width*x,r.y+r.height*y)).filter(top=>top&&!related(e,top));
        if(blocked.length)add('LAYOUT-CONTROL-OCCLUDED',isCritical?'fail':'needs_review',e,'control fully visible and receives pointer hit',{blockedPoints:blocked.length,points:5,blockers:[...new Set(blocked.map(describe))]},blocked[0]);
      }
    }
    if(e.tagName==='IMG') {
      if(e.complete&&!e.naturalWidth)add('LAYOUT-IMAGE-FAILED','needs_review',e,'image or reviewed fallback',e.getAttribute('src'));
      else if(e.naturalWidth && e.naturalHeight && s.objectFit==='fill' && Math.abs((r.width/r.height)/(e.naturalWidth/e.naturalHeight)-1)>.05)
        add('LAYOUT-IMAGE-DISTORTION','needs_review',e,'preserved aspect ratio or documented artwork treatment',{natural:[e.naturalWidth,e.naturalHeight],rendered:[r.width,r.height]});
    }
  }
  // Explicit component relationships avoid flagging every legitimate parent/child or badge overlay.
  for(const pair of contract.forbidden_overlap_pairs||[]) {
    for(const a of select(pair[0]).filter(visible))for(const b of select(pair[1]).filter(visible))
      if(!related(a,b)&&intersects(rect(a),rect(b)))add('LAYOUT-FORBIDDEN-OVERLAP','fail',a,'declared separate components do not overlap',{a:rect(a),b:rect(b)},b);
  }
  const siblings=new Set();
  for(const e of candidates.filter(e=>e.parentElement && e.children.length===0)){
    const parent=e.parentElement;if(siblings.has(parent))continue;siblings.add(parent);
    const children=[...parent.children].filter(visible);
    if(children.length>100){add('LAYOUT-PAIR-COVERAGE','needs_review',parent,'component pair coverage','more than 100 sibling elements; explicit contract needed');continue;}
    for(let i=0;i<children.length;i++)for(let j=i+1;j<children.length;j++){
      const a=children[i],b=children[j];
      if(intersects(rect(a),rect(b)))add('LAYOUT-OVERLAP-CANDIDATE','needs_review',a,'review intentional overlay vs collision',{a:rect(a),b:rect(b)},b);
    }
  }
  return {viewport:{width:innerWidth,height:innerHeight,scrollY},candidateCount:all.length,scanned:candidates.length,findings,
    coverage:{geometry:'document element boxes',hit_testing:'fully onscreen controls at current scroll position only',contrast:'not measured',pseudo_elements:'not measured',iframes:'outer frame only',shadow_dom:'not measured'},
    conclusion:'observations only; unresolved candidates and uncovered states prevent acceptance'};
}
