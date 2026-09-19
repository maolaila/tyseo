async (page) => {
  const origin = 'http://127.0.0.1:__PORT__';
  const paths = __PATHS__;
  const out = [];
  const short = error => String(error).slice(0, 180);
  const navigate = async path => {
    for(let attempt=0;attempt<3;attempt++){
      try {
        const response=await page.goto(origin+path,{waitUntil:'domcontentloaded',timeout:18000});
        const gate=page.locator('#z9-entry-enter, #z10-entry-enter').filter({visible:true}).first();
        if(await gate.count())await gate.click({timeout:3500});
        return response;
      }
      catch(error){if(!String(error).includes('interrupted by another navigation')||attempt===2)throw error;await page.waitForTimeout(300);}
    }
  };
  const state = async () => page.evaluate(() => ({
    url: location.href,
    content: document.querySelector('main')?.innerText.slice(0, 3000) || document.body.innerText.slice(0, 3000),
    rows: [...document.querySelectorAll('[data-matchid], [data-id]')].filter(x => x.getClientRects().length && getComputedStyle(x).display !== 'none').map(x => x.dataset.matchid || x.dataset.id).slice(0, 100),
    scroll: scrollY
  }));
  for (const width of [390,1280]) {
    await page.setViewportSize({width,height:844});
  for (const path of paths) {
    const entry = {path,width, status: 'blocked', links: [], actions: [], untested: []};
    if(path.startsWith('/play/')){
      entry.error='shared /play route is outside the assigned template directories; backend review required';
      out.push(entry);
      continue;
    }
    try {
      const response = await navigate(path);
      entry.http_status = response?.status();
      if (entry.http_status !== 200) {out.push(entry);continue;}
      entry.status = 'observed';
      // HTTP audit checks every href. Browser clicks check two different visible
      // in-site navigation regions, including intercepted links.
      const linkOptions=()=>page.locator('a[href]').evaluateAll(xs => xs.map((x,i) => {
        const r=x.getBoundingClientRect(),cx=r.left+r.width/2,cy=r.top+r.height/2;
        const hit=cy>=0&&cy<innerHeight?document.elementFromPoint(cx,cy):null;
        return {i,href:x.getAttribute('href'),url:x.href,target:x.getAttribute('target'),role:x.getAttribute('role'),text:(x.innerText||x.getAttribute('aria-label')||'').slice(0,70),
          visible:!!x.getClientRects().length&&r.right>0&&r.left<innerWidth&&
            (cy<0||cy>=innerHeight||hit===x||x.contains(hit)),
          region:x.closest('main')?'main':x.closest('nav,aside[aria-label]')?'nav':'other'};
      }).filter(x => x.visible && x.role!=='tab' && x.href && !x.href.startsWith('#') && !x.href.startsWith('javascript:')));
      const seen = new Set();
      for (const region of ['nav','main']) {
        let linkCandidates=await linkOptions();
        let link = linkCandidates.find(x => x.region===region && !seen.has(x.href) && x.url.startsWith(origin+'/') && x.url!==origin+path);
        if(!link && region==='nav'){
          const opener=page.locator('[data-nav-toggle], button[aria-label*="菜单"], button[aria-label*="导航"]').filter({visible:true}).first();
          if(await opener.count()){
            await opener.click({timeout:3500}).catch(()=>{});
            await page.waitForTimeout(250);
            linkCandidates=await linkOptions();
            link=linkCandidates.find(x=>x.region==='nav'&&!seen.has(x.href)&&x.url.startsWith(origin+'/')&&x.url!==origin+path);
          }
        }
        if (!link) {entry.untested.push({rule_id:'LINK-NAVIGATION',region,reason:'no visible in-site representative'});continue;}
        seen.add(link.href);
        const result={rule_id:'LINK-NAVIGATION',region,href:link.href,text:link.text};
        try {
          const clickIndex=link.i;
          const before=page.url();let targetStatus=null;
          const onResponse=response=>{if(response.request().isNavigationRequest() && response.url().startsWith(origin+'/'))targetStatus=response.status();};
          page.on('response',onResponse);
          const popupPromise=link.target==='_blank'?page.waitForEvent('popup',{timeout:5000}).catch(()=>null):null;
          await page.locator('a[href]').nth(clickIndex).click({timeout:3500});
          await page.waitForTimeout(130);
          page.off('response',onResponse);
          if(popupPromise){
            const popup=await popupPromise;
            if(popup)await popup.waitForLoadState('domcontentloaded',{timeout:7000}).catch(()=>{});
            result.popup_url=popup?.url()||null;
            result.status=result.popup_url===link.url?'pass':'needs_review';
            if(popup)await popup.close();
            entry.links.push(result);
            await navigate(path);
            continue;
          }
          result.actual_url=page.url();result.http_status=targetStatus;
          result.status=page.url()===before?'fail':targetStatus===null?'needs_review':targetStatus>=400?'fail':
            page.url()===link.url?'pass':'needs_review';
        } catch(error){result.status='fail';result.error=short(error);}
        entry.links.push(result);
        await navigate(path);
      }
      // Keep a full inventory; supported deterministic controls are executed.
      const controls = await page.locator('button,select,input[type=radio],input[type=checkbox],[role=tab]').evaluateAll(xs => xs.map((x,i)=>({
        i, tag:x.tagName.toLowerCase(),type:x.getAttribute('type'), id:x.id, role:x.getAttribute('role'),
        text:(x.innerText||x.getAttribute('aria-label')||x.getAttribute('title')||'').slice(0,70),
        visible:!!x.getClientRects().length&&x.getBoundingClientRect().right>0&&x.getBoundingClientRect().left<innerWidth, disabled:x.disabled,
        attrs:[...x.attributes].filter(a=>a.name.startsWith('data-')).map(a=>a.name+'='+a.value).slice(0,5)
      })).filter(x=>x.visible&&!x.disabled));
      entry.control_count=controls.length;
      for (const control of controls) {
        const hint=[control.id,control.text,...control.attrs].join(' ').toLowerCase();
        let kind = /top|顶部|回顶/.test(hint)?'top':/theme|主题|夜间|日间|暗色|亮色/.test(hint)?'theme':
          /menu|菜单|导航|关闭|☰/.test(hint)?'menu':/filter|筛选|全部|主场|客场|联赛/.test(hint)?'filter':
          control.role==='tab'||/data-tab=/.test(hint)?'tab':control.tag==='select'?'select':
          control.type==='submit'?'submit':control.type==='radio'||control.type==='checkbox'?'option':'unknown';
        const item={rule_id:'ACTION-EFFECT',kind,control};
        try {
          await navigate(path);
          if(kind==='top'){
            await page.evaluate(()=>{document.documentElement.style.scrollBehavior='auto';scrollTo(0,document.body.scrollHeight);});
            await page.waitForTimeout(100);
          }
          const selector='button,select,input[type=radio],input[type=checkbox],[role=tab]';
          const resolveControl=()=>control.id?page.locator('[id='+JSON.stringify(control.id)+']').first():page.locator(selector).nth(control.i);
          const target=resolveControl();
          if(!(await target.isVisible())) {item.status='blocked';item.actual='not visible after fresh load';entry.actions.push(item);continue;}
          if(kind==='submit'){
            const form=target.locator('xpath=ancestor::form').first();
            const search=form.locator('input[name="q"]').first();
            if(!(await search.count())){item.status='needs_review';item.actual='submit is not a recognized site search form';entry.actions.push(item);continue;}
            const checks=[];
            for(const mode of ['button','enter']){
              await navigate(path);
              const fresh=resolveControl();
              const liveForm=fresh.locator('xpath=ancestor::form').first();
              const engine=liveForm.locator('[data-z13-search-engine]').first();
              if(await engine.count())await engine.selectOption('local');
              const siteEngine=liveForm.locator('xpath=..').locator('[data-engine="site"]').first();
              if(await siteEngine.count()&&await siteEngine.isVisible())await siteEngine.click({timeout:3500});
              const field=liveForm.locator('input[name="q"]').first();
              await field.fill(mode==='button'?'英超':'nba');
              let status=null;
              const listener=response=>{if(response.request().isNavigationRequest()&&response.url().startsWith(origin+'/'))status=response.status();};
              page.on('response',listener);
              if(mode==='button')await fresh.click({timeout:3500});else await field.press('Enter',{timeout:3500});
              await page.waitForTimeout(150);
              page.off('response',listener);
              checks.push({mode,url:page.url(),status,pass:page.url().includes('/search')&&status===200});
            }
            item.checks=checks;
            item.status=checks.every(x=>x.pass)?'pass':'fail';
            entry.actions.push(item);
            continue;
          }
          const before=await state();
          if(kind==='top'&&before.scroll<2){item.status='not_applicable';item.reason='page has no scroll distance';entry.actions.push(item);continue;}
          const beforeAria=await target.getAttribute('aria-expanded');
          const beforeTheme=await page.locator('html').getAttribute('data-theme');
          const beforeChecked=control.type==='radio'||control.type==='checkbox'?await target.isChecked():null;
          let actionStatus=null;
          const onActionResponse=response=>{if(response.request().isNavigationRequest() && response.url().startsWith(origin+'/'))actionStatus=response.status();};
          page.on('response',onActionResponse);
          if(kind==='select'){
            const options=await target.locator('option').evaluateAll(xs=>xs.map(x=>({value:x.value,disabled:x.disabled})));
            const old=await target.inputValue(),next=options.find(x=>x.value!==old&&!x.disabled);
            if(!next){item.status='not_applicable';item.reason='one selectable option';entry.actions.push(item);continue;}
            await target.selectOption(next.value,{timeout:3500});
            item.selection={old,next:next.value};
          }else if(kind==='option'){await target.check({timeout:3500});}
          else await target.click({timeout:3500});
          if(kind==='top')await page.waitForFunction(()=>scrollY<2,null,{timeout:4000}).catch(()=>{});
          await page.waitForTimeout(350);
          let after;
          try {after=await state();}
          catch(error){if(!String(error).includes('Execution context was destroyed'))throw error;
            await page.waitForLoadState('domcontentloaded',{timeout:6000});after=await state();}
          page.off('response',onActionResponse);
          item.navigation_status=actionStatus;
          item.navigation_url=after.url!==before.url?after.url:null;
          item.effect={url:before.url!==after.url,content:before.content!==after.content,
            rows:JSON.stringify(before.rows)!==JSON.stringify(after.rows),scroll:before.scroll!==after.scroll,
            aria:before.url===after.url&&beforeAria!==(await target.getAttribute('aria-expanded')),
            theme:beforeTheme!==(await page.locator('html').getAttribute('data-theme')),
            checked:beforeChecked!==null&&before.url===after.url&&beforeChecked!==(await target.isChecked())};
          item.status=actionStatus>=400?'fail':kind==='unknown'?'needs_review':after.url!==before.url&&actionStatus===null?'needs_review':
            kind==='top'?after.scroll<before.scroll?'pass':'fail':
            kind==='filter'?item.effect.rows||item.effect.content||item.effect.url?'pass':'needs_review':
            ['url','content','rows','aria','theme','checked'].some(key=>item.effect[key])?'pass':'needs_review';
          if(item.status!=='pass') item.actual={before:before.content.slice(0,140),after:after.content.slice(0,140),effect:item.effect};
        }catch(error){item.status='blocked';item.error=short(error);}
        entry.actions.push(item);
      }
    }catch(error){entry.error=short(error);}
    out.push(entry);
  }
  }
  return out;
}
