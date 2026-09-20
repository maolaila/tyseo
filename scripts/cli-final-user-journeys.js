async (page) => {
  const base=__BASE__, name=__NAME__, paths=__PATHS__, spec=__SPEC__, folder=__OUTPUT__;
  const audit=__LAYOUT_AUDIT__, out={pages:[],common:[],specific:[],screenshots:[]};
  const short=e=>String(e).slice(0,180);
  const open=async path=>{
    const response=await page.goto(base+path,{waitUntil:'domcontentloaded',timeout:25000});
    await page.waitForLoadState('load',{timeout:8000}).catch(()=>{});
    const gate=page.locator('#z9-entry-enter,#z10-entry-enter').filter({visible:true}).first();
    if(await gate.count())await gate.click({timeout:3000});
    return response;
  };
  const record=(target,id,status,actual,extra={})=>target.push({rule_id:id,status,actual,...extra});
  for(const width of [390,1280]){
    await page.setViewportSize({width,height:900});
    for(const item of paths){
      try{
        const response=await open(item.path);
        const state=await page.evaluate(audit,{components:[]});
        const hard=state.findings.filter(x=>x.status==='fail'&&(/STICKY-HEADER|LAYOUT-PAGE-OVERFLOW|LAYOUT-CONTROL-OCCLUDED/.test(x.rule_id)));
        const text=await page.locator('body').innerText();
        const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
        const status=response.status()!==200?'blocked':text.trim().length<20||overflow>2||hard.length?'fail':'pass';
        out.pages.push({path:item.path,page_types:item.types,width,status,http:response.status(),body_chars:text.trim().length,
          page_overflow:overflow,layout_failures:hard.slice(0,8)});
        if(item.path==='/'&&[390,1280].includes(width)){
          const filename=`${folder}/${name}-home-${width}-light.png`;
          await page.screenshot({path:filename,animations:'disabled'});out.screenshots.push(filename);
        }
      }catch(error){out.pages.push({path:item.path,page_types:item.types,width,status:'blocked',error:short(error)});}
    }
  }
  for(const width of [390,1280]){
    await page.setViewportSize({width,height:900});
    for(const theme of ['light','dark']){
      try{
        await open('/');
        await page.evaluate(t=>document.documentElement.setAttribute('data-theme',t),theme);
        const background=await page.evaluate(()=>getComputedStyle(document.body).backgroundColor);
        const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
        record(out.common,'HOME-RESPONSIVE-THEME',overflow<=2?'pass':'fail',{width,theme,background,overflow},{path:'/',width,theme});
        if(theme==='dark'){
          const filename=`${folder}/${name}-home-${width}-dark.png`;
          await page.screenshot({path:filename,animations:'disabled'});out.screenshots.push(filename);
        }
      }catch(error){record(out.common,'HOME-RESPONSIVE-THEME','blocked',short(error),{path:'/',width,theme});}
    }
  }
  await page.setViewportSize({width:390,height:900});
  try{
    await open('/');
    const menu=page.locator('[data-nav-toggle],[data-z7-more],.z1-mobile-menu,.z2-mobile-menu,.z3-mobile-menu,.z4-rail-toggle,.z5-rail-toggle,.z6-rail-toggle,.z8-nav-toggle,.z9-mobile-menu-toggle,.z10-mobile-menu-toggle,.z11-mobile-menu-toggle,.z12-mobile-menu-toggle,.z13-nav-toggle,.z14-mobile-menu-toggle,.z15-mobile-menu-toggle,.z16-mobile-menu-toggle,.z17-mobile-menu-toggle').filter({visible:true}).first();
    if(!await menu.count())record(out.common,'MOBILE-MENU','needs_review','No recognized visible menu control',{path:'/',width:390});
    else{
      const before=await menu.getAttribute('aria-expanded');await menu.click({timeout:3500});
      const after=await menu.getAttribute('aria-expanded');
      const shown=await page.locator('nav a[href]').filter({visible:true}).count();
      await page.keyboard.press('Escape');
      record(out.common,'MOBILE-MENU',before!==after&&shown>0?'pass':'needs_review',{before,after,visible_nav_links:shown},{path:'/',width:390});
    }
  }catch(error){record(out.common,'MOBILE-MENU','blocked',short(error),{path:'/',width:390});}
  try{
    await open('/');
    const toggle=page.locator('[data-theme-toggle],[class*="theme-toggle"],[class*="theme-btn"],.sl-theme,.ps-theme-btn,.z11-tool-theme,.z12-tool-theme').filter({visible:true}).first();
    if(!await toggle.count())record(out.common,'THEME-TOGGLE','needs_review','No recognized visible theme toggle',{path:'/'});
    else{
      const before=await page.locator('html').getAttribute('data-theme');
      const appearance=()=>page.evaluate(()=>[...document.querySelectorAll('body,body *')].filter(x=>x.getClientRects().length).slice(0,120).map(x=>{
        const s=getComputedStyle(x);return [s.backgroundColor,s.color,s.borderTopColor].join('|');}).join(';'));
      const appearanceBefore=await appearance();
      await toggle.click({timeout:3500});
      const after=await page.locator('html').getAttribute('data-theme');
      const appearanceAfter=await appearance();
      await page.reload({waitUntil:'domcontentloaded'});
      const persisted=await page.locator('html').getAttribute('data-theme');
      record(out.common,'THEME-TOGGLE',before===after||after!==persisted?'fail':appearanceBefore===appearanceAfter?'needs_review':'pass',
        {before,after,persisted,computed_appearance_changed:appearanceBefore!==appearanceAfter},{path:'/'});
    }
  }catch(error){record(out.common,'THEME-TOGGLE','blocked',short(error),{path:'/'});}
  try{
    await page.setViewportSize({width:1280,height:900});await open('/');
    const target=page.locator('a[href="/zuqiu"]').filter({visible:true}).first();
    if(!await target.count())record(out.common,'NAV-CLICK','needs_review','No visible football navigation link',{path:'/',width:1280});
    else{
      if(name==='z8')await page.locator('.z8-nav-toggle').click({timeout:3500});
      let status=null;const listener=r=>{if(r.request().isNavigationRequest()&&r.url().endsWith('/zuqiu'))status=r.status();};
      page.on('response',listener);await target.click({timeout:4000});await page.waitForTimeout(200);page.off('response',listener);
      record(out.common,'NAV-CLICK',status===200&&page.url()===base+'/zuqiu'?'pass':status===null?'needs_review':'fail',
        {url:page.url(),http:status},{path:'/',width:1280});}
  }catch(error){record(out.common,'NAV-CLICK','blocked',short(error),{path:'/',width:1280});}
  await page.setViewportSize({width:390,height:900});
  for(const mode of ['enter','button']){
    try{
      await open('/');
      let input=page.locator('form[action="/search"] input[name="q"]').filter({visible:true}).first();
      if(!await input.count()){
        const opener=page.locator('#mobile-search-icon,button[aria-label*="搜索"]').filter({visible:true}).first();
        if(await opener.count())await opener.click({timeout:3000});
        input=page.locator('form[action="/search"] input[name="q"]').filter({visible:true}).first();
      }
      if(!await input.count()){record(out.common,'SITE-SEARCH','needs_review','No visible site search input',{path:'/',mode});continue;}
      await input.fill(mode==='enter'?'英超':'NBA');
      if(mode==='enter')await input.press('Enter',{timeout:4000});
      else{
        const submit=input.locator('xpath=ancestor::form').locator('button[type="submit"],input[type="submit"]').first();
        if(!await submit.count()){record(out.common,'SITE-SEARCH','needs_review','No submit button',{path:'/',mode});continue;}
        await submit.click({timeout:4000});
      }
      const url=page.url(),body=await page.locator('body').innerText();
      record(out.common,'SITE-SEARCH',/\/search(?:\?|$)/.test(url)&&body.trim().length>20?'pass':'fail',{url,body_chars:body.trim().length},{path:'/',mode});
    }catch(error){record(out.common,'SITE-SEARCH','blocked',short(error),{path:'/',mode});}
  }
  try{
    await open('/');
    await page.evaluate(()=>{document.documentElement.style.scrollBehavior='auto';scrollTo(0,document.body.scrollHeight)});
    const before=await page.evaluate(()=>scrollY);
    await page.waitForTimeout(250);
    const top=page.locator('#scroll-to-top,.z1-back-top,[data-back-top],[class*="scroll-top"],[class*="back-top"]').filter({visible:true}).first();
    if(before<100)record(out.common,'GOTO-TOP','not_applicable','Home page does not scroll',{path:'/'});
    else if(!await top.count())record(out.common,'GOTO-TOP','needs_review','No recognized visible control',{path:'/'});
    else{await top.click({timeout:3500});await page.waitForFunction(()=>scrollY<5,null,{timeout:4000}).catch(()=>{});const after=await page.evaluate(()=>scrollY);
      record(out.common,'GOTO-TOP',after<5?'pass':'fail',{before,after},{path:'/'});}
  }catch(error){record(out.common,'GOTO-TOP','blocked',short(error),{path:'/'});}
  try{
    await open(spec.path);
    const buttons=page.locator(spec.selector),count=await buttons.count();
    if(!count){record(out.specific,'SPECIFIC-COMPONENT','blocked','Target control absent',{path:spec.path,selector:spec.selector});}
    else if(spec.type==='numbered-tabs'){
      for(let i=0;i<count;i++){
        const button=buttons.nth(i),value=await button.getAttribute('data-tab');
        const panel=page.locator('#tab_content'+(Number(value)+1));
        if(!await button.isVisible())continue;
        await button.click({timeout:4000});
        const check=await page.evaluate(n=>{
          const visible=e=>e&&!e.hidden&&getComputedStyle(e).display!=='none'&&getComputedStyle(e).visibility!=='hidden'&&!!e.getClientRects().length;
          const p=document.getElementById('tab_content'+n),all=[...document.querySelectorAll('[id^="tab_content"]')];
          return {exists:!!p,visible:visible(p),other_visible:all.filter(x=>x!==p&&visible(x)).length,chars:p?.innerText.trim().length||0};
        },Number(value)+1).catch(()=>null);
        const selected=await button.getAttribute('aria-selected');
        record(out.specific,'NUMBERED-TAB',check?.exists&&check.visible&&check.other_visible===0&&selected==='true'?'pass':'fail',
          {tab:await button.innerText(),selected,panel:check},{path:spec.path,selector:spec.selector});
      }
    }else if(spec.type==='paired-tabs'){
      for(let i=0;i<count;i++){
        const button=buttons.nth(i),key=await button.getAttribute(spec.key);
        if(await button.isDisabled())continue;
        await button.click({timeout:4000});
        const check=await page.evaluate(s=>{
          const visible=e=>e&&!e.hidden&&getComputedStyle(e).display!=='none'&&getComputedStyle(e).visibility!=='hidden'&&!!e.getClientRects().length;
          const panels=[...document.querySelectorAll(s.panel)],p=panels.find(x=>x.getAttribute(s.panel_key)===s.key);
          return {exists:!!p,visible:visible(p),other_visible:panels.filter(x=>x!==p&&visible(x)).length,chars:p?.innerText.trim().length||0};
        },{panel:spec.panel,panel_key:spec.panel_key,key});
        const selected=await button.getAttribute('aria-selected');
        record(out.specific,'PAIRED-TAB',check.exists&&check.visible&&check.other_visible===0&&selected==='true'?'pass':'fail',
          {tab:await button.innerText(),selected,panel:check},{path:spec.path,selector:spec.selector});
      }
    }else if(spec.type==='date-filter'){
      for(let i=0;i<count;i++){
        const button=buttons.nth(i);await button.click({timeout:4000});
        const key=await button.getAttribute('data-date');
        const check=await page.evaluate(s=>[...document.querySelectorAll(s.rows)].filter(x=>!x.hidden&&getComputedStyle(x).display!=='none'&&!!x.getClientRects().length).map(x=>x.getAttribute('data-match-date')?.slice(0,10)),spec);
        record(out.specific,'DATE-FILTER',key&&check.every(x=>x===key)&&await button.getAttribute('aria-selected')==='true'?'pass':'fail',
          {date:key,visible_rows:check},{path:spec.path,selector:spec.selector});
      }
    }else if(spec.type==='row-filter'){
      for(let i=0;i<count;i++){
        const button=buttons.nth(i),key=await button.getAttribute(spec.key);await button.click({timeout:4000});
        const check=await page.evaluate(s=>[...document.querySelectorAll(s.rows)].map(x=>({
          expected:s.key==='all'||s.key==='live'&&x.getAttribute('data-phase')==='live'||s.key!=='live'&&x.getAttribute('data-sport')===s.key,
          visible:!x.hidden&&getComputedStyle(x).display!=='none'&&!!x.getClientRects().length})),{rows:spec.rows,key});
        record(out.specific,'ROW-FILTER',check.every(x=>x.expected===x.visible)&&await button.getAttribute('aria-selected')==='true'?'pass':'fail',
          {key,total:check.length,mismatch:check.filter(x=>x.expected!==x.visible).length},{path:spec.path,selector:spec.selector});
      }
    }else if(spec.type==='standings'){
      const pool=await page.locator('#fp-standings-json').evaluate(x=>JSON.parse(x.textContent));
      for(let i=0;i<count;i++){
        const button=buttons.nth(i);await button.click({timeout:4000});
        const body=await page.locator(spec.panel).innerText(),href=await page.locator(spec.more).getAttribute('href');
        const selected=await button.getAttribute('aria-selected'),league=pool[i];
        const correct=league.rows?.length?body.includes(league.rows[0].teamName||league.rows[0].name||'__unknown__'):
          body.includes('暂无'+league.name+'积分榜数据');
        record(out.specific,'STANDINGS-TAB',selected==='true'&&href===league.more&&correct?'pass':'fail',
          {tab:league.name,selected,more:href,body:body.slice(0,180),configured_rows:league.rows?.length||0},{path:spec.path,selector:spec.selector});
      }
    }else if(spec.type==='expand'){
      await page.setViewportSize({width:1280,height:900});
      const button=buttons.first();await button.click({timeout:4000});
      const expanded=await button.getAttribute('aria-expanded');
      const target=await page.locator(spec.target).isVisible();
      record(out.specific,'EXPAND-MENU',expanded==='true'&&target?'pass':'fail',{expanded,target_visible:target},{path:spec.path,selector:spec.selector});
    }
    const filename=`${folder}/${name}-specific.png`;
    await page.screenshot({path:filename,animations:'disabled'});out.screenshots.push(filename);
  }catch(error){record(out.specific,'SPECIFIC-COMPONENT','blocked',short(error),{path:spec.path,selector:spec.selector});}
  return out;
}
