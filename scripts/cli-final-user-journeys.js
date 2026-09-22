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
      }catch(error){out.pages.push({path:item.path,page_types:item.types,width,status:'blocked',error:short(error)});}
    }
  }
  for(const width of [390,1280]){
    await page.setViewportSize({width,height:900});
    try{
      await open('/');
      const background=await page.evaluate(()=>getComputedStyle(document.body).backgroundColor);
      const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
      record(out.common,'HOME-RESPONSIVE',overflow<=2?'pass':'fail',{width,background,overflow},{path:'/',width});
      const filename=`${folder}/${name}-home-${width}.png`;
      await page.screenshot({path:filename,animations:'disabled'});out.screenshots.push(filename);
    }catch(error){record(out.common,'HOME-RESPONSIVE','blocked',short(error),{path:'/',width});}
  }
  await page.setViewportSize({width:390,height:900});
  try{
    await open('/');
    const menu=page.locator('[data-nav-toggle],[data-z7-more],.mobilemenu,.z1-mobile-menu,.z2-mobile-menu,.z3-mobile-menu,.z4-rail-toggle,.z5-rail-toggle,.z6-rail-toggle,.z8-nav-toggle,.z9-mobile-menu-toggle,.z10-mobile-menu-toggle,.z11-mobile-menu-toggle,.z12-mobile-menu-toggle,.z13-nav-toggle,.z14-mobile-menu-toggle,.z15-mobile-menu-toggle,.z16-mobile-menu-toggle,.z17-mobile-menu-toggle,.z18-mobile-menu-toggle').filter({visible:true}).first();
    if(!await menu.count())record(out.common,'MOBILE-MENU','fail','Required mobile drawer control absent',{path:'/',width:390});
    else{
      const beforeUrl=page.url(),beforeExpanded=await menu.getAttribute('aria-expanded');
      const beforeLinks=await page.locator('nav a[href]').filter({visible:true}).count();
      await menu.click({timeout:3500});
      const afterUrl=page.url(),afterExpanded=await menu.getAttribute('aria-expanded');
      const openLinks=await page.locator('nav a[href]').filter({visible:true}).count();
      await page.keyboard.press('Escape');await page.waitForTimeout(100);
      let closedExpanded=await menu.getAttribute('aria-expanded');
      let closedLinks=await page.locator('nav a[href]').filter({visible:true}).count();
      const opened=afterExpanded==='true'||openLinks>beforeLinks;
      if(opened&&closedExpanded!=='false'&&closedLinks>=openLinks){
        await menu.click({timeout:3500});await page.waitForTimeout(100);
        closedExpanded=await menu.getAttribute('aria-expanded');
        closedLinks=await page.locator('nav a[href]').filter({visible:true}).count();
      }
      const closed=closedExpanded==='false'||closedLinks<openLinks;
      record(out.common,'MOBILE-MENU',beforeUrl===afterUrl&&opened&&closed&&openLinks>0?'pass':'fail',
        {before_url:beforeUrl,after_url:afterUrl,before_expanded:beforeExpanded,after_expanded:afterExpanded,
          closed_expanded:closedExpanded,before_links:beforeLinks,open_links:openLinks,closed_links:closedLinks},{path:'/',width:390});
    }
  }catch(error){record(out.common,'MOBILE-MENU','blocked',short(error),{path:'/',width:390});}
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
  await page.setViewportSize({width:1280,height:900});
  try{
    await open('/');
    const more=page.locator('.header_menu_more_btn').filter({visible:true}).first();
    if(!await more.count())record(out.common,'MORE-EVENTS-MENU','blocked','r62-aligned more-events control absent',{path:'/',width:1280});
    else{
      await more.click({timeout:3500});
      const expanded=await more.getAttribute('aria-expanded');
      const links=await page.locator('.header_menu_more .header_menu_item_item a[href]').filter({visible:true}).count();
      record(out.common,'MORE-EVENTS-MENU',expanded==='true'&&links>0?'pass':'fail',{expanded,visible_links:links},{path:'/',width:1280});
    }
  }catch(error){record(out.common,'MORE-EVENTS-MENU','blocked',short(error),{path:'/',width:1280});}
  try{
    const playback=[];
    for(const item of paths){
      await open(item.path);
      const links=page.locator('a[href^="/play/"],a[onclick*="/play/"]');
      for(let i=0;i<await links.count();i++)playback.push({path:item.path,rel:await links.nth(i).getAttribute('rel')||''});
    }
    const missing=playback.filter(x=>!x.rel.split(/\s+/).includes('nofollow'));
    record(out.common,'LIVE-DETAIL-PLAYBACK-NOFOLLOW',missing.length?'fail':playback.length?'pass':'not_applicable',
      {links:playback.length,missing_nofollow:missing},{path:'all-sampled-pages'});
  }catch(error){record(out.common,'LIVE-DETAIL-PLAYBACK-NOFOLLOW','blocked',short(error),{path:'all-sampled-pages'});}
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
