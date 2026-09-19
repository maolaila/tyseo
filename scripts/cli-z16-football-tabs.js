async (page) => {
  const out={states:[],screenshots:[],journey:null};
  for(const width of [390,768,1280,1920])for(const theme of ['light','dark'])for(const path of ['/zuqiu','/lanqiu','/yingchao']){
    await page.setViewportSize({width,height:900});
    const response=await page.goto('__BASE__'+path,{waitUntil:'domcontentloaded'});
    await page.evaluate(t=>document.documentElement.setAttribute('data-theme',t),theme);
    const pool=await page.locator('#fp-standings-json').evaluate(x=>{
      try{return JSON.parse(x.textContent||'[]').map(y=>({name:y.name,more:y.more,rows:y.rows?.length||0}));}
      catch(e){return null;}
    });
    const tabs=page.locator('#fp-stand-tabs [data-fp-tab]');
    if(!pool||!pool.length){out.states.push({path,width,theme,status:'blocked',reason:'no valid standings config'});continue;}
    const indexes=await tabs.count()?pool.map((_,i)=>i):[0];
    for(const i of indexes){
      if(await tabs.count())await tabs.nth(i).click({timeout:4000});
      const state=await page.locator('.fp-stand').evaluate((card,item)=>{
        const body=card.querySelector('#fp-stand-body'),tabs=[...card.querySelectorAll('[data-fp-tab]')];
        const empty=body.querySelector('.fp-stand__row--empty');
        const br=body.getBoundingClientRect(),cr=card.getBoundingClientRect();
        return {body:body.innerText,empty:!!empty,rows:body.querySelectorAll('.fp-stand__row:not(.fp-stand__row--empty)').length,
          more:card.querySelector('#fp-stand-more')?.getAttribute('href'),
          selected:tabs.filter(t=>t.getAttribute('aria-selected')==='true').length,
          active:tabs[item]?.getAttribute('aria-selected'),contained:br.left>=cr.left-2&&br.right<=cr.right+2,
          pageOverflow:document.documentElement.scrollWidth-innerWidth};
      },i);
      const league=pool[i],isBb=path==='/lanqiu';
      const expectedEmpty='暂无'+league.name+(isBb?'排行榜':'积分榜')+'数据';
      const pass=response.status()===200&&state.more===league.more&&state.contained&&state.pageOverflow<=2&&
        (await tabs.count()?state.selected===1&&state.active==='true':true)&&
        (league.rows?state.rows>0&&!state.empty:state.empty&&state.body.includes(expectedEmpty));
      out.states.push({path,width,theme,tab:league.name,configuredRows:league.rows,status:pass?'pass':'fail',...state});
      if(i===1&&[390,1280].includes(width)){
        const name=`__OUTPUT__/z16-${path.slice(1)}-tabs-${width}-${theme}.png`;
        await page.locator('.fp-stand').screenshot({path:name,animations:'disabled'});out.screenshots.push(name);
      }
    }
    if(path==='/zuqiu'&&width===1280&&theme==='light'){
      await tabs.nth(1).click();
      const click=page.waitForResponse(r=>r.request().isNavigationRequest()&&r.url().includes('/xijia/jifen'),{timeout:6000});
      await page.locator('#fp-stand-more').click();const target=await click;
      out.journey={from:'/zuqiu',tab:pool[1].name,url:page.url(),status:target.status()};
    }
  }
  out.passed=out.states.length===64&&out.states.every(x=>x.status==='pass')&&
    out.journey?.url==='__BASE__/xijia/jifen'&&out.journey.status===200;
  return out;
}
