async (page) => {
  const out={policy:'2.2',template:'z16',states:[],negative_controls:{},screenshots:[]};
  const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  const cases=[['team_info','/yingchao/teams/teaminfo-10012.html','#tab-fixture'],['team_match_list','/yingchao/teams/10012.html','.z16-league-page']];
  const visibleRows=root=>[...root.querySelectorAll('.match-item[data-league]')].filter(x=>x.getClientRects().length&&getComputedStyle(x).display!=='none').map(x=>x.dataset.matchid);
  const geometry=(index=0)=>{
    const row=[...document.querySelectorAll('.match_box .match-item')].filter(x=>x.querySelector('.home .left img')&&x.getClientRects().length)[index];
    if(!row)return {pass:false,reason:'related row missing'};
    const sels=['.home .left img','.home .left .text','.score','.away .right img','.away .right .text'];
    const nodes=sels.map(s=>row.querySelector('.info_center '+s));
    if(nodes.some(x=>!x))return {pass:false,reason:'component part missing'};
    const rects=nodes.map(x=>x.getBoundingClientRect());const box=row.getBoundingClientRect();
    const within=rects.every(r=>r.width>0&&r.height>0&&r.left>=box.left-2&&r.right<=box.right+2&&r.top>=box.top-2&&r.bottom<=box.bottom+2);
    const overlaps=rects.some((a,i)=>rects.slice(i+1).some(b=>Math.min(a.right,b.right)-Math.max(a.left,b.left)>2&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>2));
    // z16's existing desktop five-column contract, NOT a universal logo alignment rule.
    const centers=rects.map(r=>(r.top+r.bottom)/2);
    const topology=innerWidth>960?Math.max(...centers)-Math.min(...centers)<=2:
      rects[0].bottom<=rects[1].top+2&&rects[3].bottom<=rects[4].top+2&&
      Math.max(rects[0].right,rects[1].right)<=rects[2].left+2&&
      Math.min(rects[3].left,rects[4].left)>=rects[2].right-2;
    return {pass:within&&!overlaps&&topology,within,overlaps,topology,centers,rects:rects.map(r=>({x:r.x,y:r.y,width:r.width,height:r.height})),pageOverflow:document.documentElement.scrollWidth>innerWidth+2};
  };
  const measureRows=async()=>{
    const count=await page.evaluate(()=>[...document.querySelectorAll('.match_box .match-item')].filter(x=>x.querySelector('.home .left img')&&x.getClientRects().length).length);
    const rows=[];for(let i=0;i<count;i++)rows.push(await page.evaluate(geometry,i));
    return rows;
  };
  for(const width of [320,360,390,768,959,960,961,1280,1920])for(const theme of ['light','dark']){
    await page.setViewportSize({width,height:900});
    for(const [kind,path,selector] of cases){
      await page.goto('http://127.0.0.1:6316'+path+'?regression='+Date.now(),{waitUntil:'domcontentloaded'});
      await page.evaluate(t=>document.documentElement.setAttribute('data-theme',t),theme);
      if(kind==='team_info')await page.locator('[data-tab="matches"]').click();
      const root=page.locator(selector);
      const rows=await root.locator('.match-item[data-league]').evaluateAll(xs=>xs.map(x=>({id:x.dataset.matchid,league:x.dataset.league,location:x.dataset.location})));
      const leagues=await root.locator('[data-filter-league]').evaluateAll(xs=>xs.map(x=>x.dataset.filterLeague));
      const state={page:kind,width,theme,environment:'real_app',checks:[],status:'pass'};
      if(rows.length<2||leagues.length<2||new Set(rows.map(x=>x.location)).size<2){state.status='blocked';state.reason='sample lacks distinct leagues/home-away';out.states.push(state);continue;}
      for(const league of leagues)for(const location of ['all','home','away']){
        await root.getByRole('button',{name:league==='all'?'全部':league,exact:true}).click();
        await root.locator('.location-filters label').filter({has:page.locator('input[value="'+location+'"]')}).click();
        const expected=rows.filter(x=>(league==='all'||x.league===league)&&(location==='all'||x.location===location)).map(x=>x.id);
        const actual=await root.evaluate(visibleRows);
        const empty=await root.locator('.z16-filter-empty').isVisible();
        const groupErrors=await root.locator('[data-date-mod]').evaluateAll(xs=>xs.filter(x=>{
          const any=[...x.querySelectorAll('.match-item')].some(r=>r.style.display!=='none');
          return (getComputedStyle(x).display!=='none')!==any;
        }).length);
        const pass=same(actual,expected)&&empty===(expected.length===0)&&groupErrors===0;
        state.checks.push({rule_id:'FILTER-RESULT-SET',league,location,expected,actual,empty,groupErrors,pass});
        if(!pass)state.status='fail';
        if(kind==='team_info'&&width===1280&&theme==='light'&&league!=='all'&&location==='home'&&expected.length&&expected.length<rows.length){
          if(out.negative_controls.filter_detected===undefined){
            await root.locator('.match-item[data-league]').evaluateAll(xs=>xs.forEach(x=>{if(x.style.display==='none')x.style.setProperty('display','none');}));
            out.negative_controls.filter_detected=!same(await root.evaluate(visibleRows),expected);
            await root.locator('[data-filter-league="all"]').click();
            await root.getByRole('button',{name:league,exact:true}).click();
          }
        }
      }
      await root.locator('[data-filter-league="all"]').click();
      await root.locator('.location-filters label').filter({has:page.locator('input[value="all"]')}).click();
      state.reset=same(await root.evaluate(visibleRows),rows.map(x=>x.id));
      if(!state.reset)state.status='fail';
      state.layout_rows=await measureRows();
      if(!state.layout_rows.length||state.layout_rows.some(x=>!x.pass||x.pageOverflow))state.status='fail';
      if([390,1280].includes(width)){
        const path='runs/z16-leo-regression-20260919/'+kind+'-'+width+'-'+theme+'.png';
        await root.locator('.z16-filter-bar').screenshot({path});out.screenshots.push(path);
      }
      out.states.push(state);
    }
    await page.goto('http://127.0.0.1:6316/ajia/4539770.html?regression='+Date.now(),{waitUntil:'domcontentloaded'});
    await page.evaluate(t=>document.documentElement.setAttribute('data-theme',t),theme);
    const row=page.locator('.match_box .match-item').filter({has:page.locator('.home .left img')}).first();
    await row.scrollIntoViewIfNeeded();
    const actual=await measureRows();
    out.states.push({page:'detail_related',width,theme,environment:'real_app',rule_id:'LAYOUT-INTEGRITY',status:actual.length&&actual.every(x=>x.pass&&!x.pageOverflow)?'pass':'fail',rows:actual});
    if(width===1280&&theme==='light'){
      const old=await page.addStyleTag({content:'.match-item .info_center .home .left > img,.match-item .info_center .home .left > .text,.match-item .info_center > .score,.match-item .info_center .away .right > img,.match-item .info_center .away .right > .text{grid-row:auto!important}'});
      out.negative_controls.layout_detected=!(await page.evaluate(geometry)).pass;
      await old.evaluate(x=>x.remove());
    }
    if(width===390&&theme==='light'){
      const old=await page.addStyleTag({content:'html body.z16-body .match_box .match-item .info_center .home .left,html body.z16-body .match_box .match-item .info_center .away .right{grid-column:auto!important;grid-row:auto!important}html body.z16-body .match_box .match-item .info_center>.score{grid-column:3!important;grid-row:auto!important}'});
      out.negative_controls.mobile_layout_detected=!(await page.evaluate(geometry)).pass;
      await old.evaluate(x=>x.remove());
    }
    if([390,1280].includes(width)){
      const path='runs/z16-leo-regression-20260919/related-'+width+'-'+theme+'.png';
      await row.screenshot({path});out.screenshots.push(path);
    }
    const saved=await row.evaluate(x=>x.innerHTML);
    for(const fixture of ['zero','three_digits','long_names','missing_logo','failed_logo']){
      await row.evaluate((x,kind)=>{
        if(kind==='zero')x.querySelector('.score .fenge').textContent='0-0';
        if(kind==='three_digits')x.querySelector('.score .fenge').textContent='123-118';
        if(kind==='long_names'){x.querySelector('.home .text').textContent='很长的中文球队名称用于边界验证';x.querySelector('.away .text').textContent='LongUnbrokenEnglishTeamNameForLayout';}
        if(kind==='missing_logo')x.querySelectorAll('img').forEach(i=>{i.removeAttribute('src');i.removeAttribute('data-original');});
        if(kind==='failed_logo')x.querySelectorAll('img').forEach(i=>{i.removeAttribute('data-original');i.src='data:image/png;base64,invalid';});
      },fixture);
      const result=await page.evaluate(geometry);
      out.states.push({page:'detail_related',width,theme,environment:'fixture',data_state:fixture,rule_id:'LAYOUT-INTEGRITY',status:result.pass&&!result.pageOverflow?'pass':'fail',...result});
      await row.evaluate((x,html)=>x.innerHTML=html,saved);
    }
  }
  out.counts={};for(const s of out.states)out.counts[s.status]=(out.counts[s.status]||0)+1;
  out.passed=!out.counts.fail&&!out.counts.blocked&&Object.values(out.negative_controls).length===3&&Object.values(out.negative_controls).every(Boolean);
  return out;
}
