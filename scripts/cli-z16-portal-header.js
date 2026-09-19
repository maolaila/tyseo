async (page) => {
  const base='__BASE__',out={states:[],tabs:[],screenshots:[]};
  const audit=__LAYOUT_AUDIT__;
  const alpha=color=>{
    if(color==='transparent')return 0;
    const m=color.match(/^rgba?\(([^)]+)\)$/);
    return m&&m[1].split(',').length===4?Number(m[1].split(',')[3]):1;
  };
  for(const width of [390,768,1280,1920])for(const theme of ['light','dark']){
    await page.setViewportSize({width,height:900});
    const response=await page.goto(base+'/',{waitUntil:'domcontentloaded'});
    await page.evaluate(t=>document.documentElement.setAttribute('data-theme',t),theme);
    const box=page.locator('[data-sl-data-table-scroll]').first();
    if(!await box.count()){
      out.states.push({width,theme,status:'blocked',reason:'portal standings table missing',http:response.status()});continue;
    }
    await box.scrollIntoViewIfNeeded();
    const issues=await page.evaluate(audit,{components:[{selector:'.sl-data__table',required:true,critical:true}]});
    const headerFailures=issues.findings.filter(x=>x.rule_id.startsWith('LAYOUT-STICKY-HEADER-')&&x.status==='fail');
    const max=await box.evaluate(x=>x.scrollHeight-x.clientHeight);
    for(const offset of [0,24,56,max]){
      const state=await box.evaluate((el,scroll)=>{
        el.scrollTop=scroll;
        const cells=[...el.querySelectorAll('thead th')],rows=[...el.querySelectorAll('tbody tr')];
        const labels=cells.map(th=>{
          const s=getComputedStyle(th),r=th.getBoundingClientRect(),line=parseFloat(s.lineHeight),pad=parseFloat(s.paddingTop)+parseFloat(s.paddingBottom);
          const hit=document.elementFromPoint((r.left+r.right)/2,(r.top+r.bottom)/2);
          return {text:th.innerText,background:s.backgroundColor,oneLine:Number.isFinite(line)&&r.height-pad<=line*1.5,
            hit:hit===th||th.contains(hit),height:r.height};
        });
        return {scrollTop:el.scrollTop,maxScroll:el.scrollHeight-el.clientHeight,
          localOverflow:el.scrollWidth-el.clientWidth,labels,rowCount:rows.length,
          pageOverflow:document.documentElement.scrollWidth-innerWidth};
      },offset);
      state.width=width;state.theme=theme;state.http=response.status();state.auditFailures=headerFailures;
      state.status=response.status()===200&&state.rowCount>0&&state.localOverflow<=2&&state.pageOverflow<=2&&
        state.labels.length>=5&&state.labels.every(x=>alpha(x.background)>=.99&&x.oneLine&&x.hit)&&!headerFailures.length?'pass':'fail';
      out.states.push(state);
      if([390,1280].includes(width)&&offset===24){
        const name=`__OUTPUT__/z16-table-${width}-${theme}-scrolled.png`;
        await box.screenshot({path:name,animations:'disabled'});out.screenshots.push(name);
      }
    }
    const tabs=page.locator('[data-sl-data-leagues] [role=tab]');
    if(await tabs.count()>1){
      await box.evaluate(el=>el.scrollTop=40);
      const before={title:await page.locator('[data-sl-data-table-title]').innerText(),
        rows:await page.locator('[data-sl-data-table-body] tr').allInnerTexts()};
      await tabs.nth(1).click();
      const after={title:await page.locator('[data-sl-data-table-title]').innerText(),
        rows:await page.locator('[data-sl-data-table-body] tr').allInnerTexts(),
        selected:await tabs.nth(1).getAttribute('aria-selected'),scroll:await box.evaluate(el=>el.scrollTop)};
      const tab={width,theme,before,after,status:before.title!==after.title&&JSON.stringify(before.rows)!==JSON.stringify(after.rows)&&
        after.selected==='true'&&after.scroll===0?'pass':'fail'};
      out.tabs.push(tab);
    }else out.tabs.push({width,theme,status:'blocked',reason:'no alternate league tab'});
  }
  out.passed=out.states.length===32&&out.tabs.length===8&&out.states.every(x=>x.status==='pass')&&out.tabs.every(x=>x.status==='pass');
  return out;
}
