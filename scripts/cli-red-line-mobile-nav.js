async (page) => {
  // 红线门槛 · 手机端导航（政策 2.5）：在每一种页面类型的样例页上，390 宽，点汉堡按钮后必须是"当前页上盖出来的抽屉/浮层"——
  // 地址不变、不开新标签、出现一块盖住页面的导航层（里面的链接点得到）、能关掉。任何一条不满足都是 fail，不是 needs_review。
  const base=__BASE__, paths=__PATHS__, folder=__OUTPUT__, name=__NAME__;
  const out={results:[],screenshots:[]};
  const short=e=>String(e).slice(0,200);
  const KNOWN='[data-nav-toggle],[data-z7-more],.z1-mobile-menu,.z2-mobile-menu,.z3-mobile-menu,.z4-rail-toggle,.z5-rail-toggle,.z6-rail-toggle,.z8-nav-toggle,.z9-mobile-menu-toggle,.z10-mobile-menu-toggle,.z11-mobile-menu-toggle,.z12-mobile-menu-toggle,.z13-nav-toggle,.z14-mobile-menu-toggle,.z15-mobile-menu-toggle,.z16-mobile-menu-toggle,.z17-mobile-menu-toggle';
  // 页面里找汉堡按钮：先认已知选择器，再按通用特征（顶部区域、可见、名字像菜单/导航，排除主题、搜索、返回顶部）
  const findToggle=()=>page.evaluate(known=>{
    const vis=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>=20&&r.height>=20&&s.visibility!=='hidden'&&s.display!=='none'&&parseFloat(s.opacity||'1')>0.05&&r.bottom>0&&r.top<260&&r.right>0&&r.left<innerWidth;};
    const mark=el=>{el.setAttribute('data-redline-toggle','1');return true;};
    document.querySelectorAll('[data-redline-toggle]').forEach(e=>e.removeAttribute('data-redline-toggle'));
    for(const el of document.querySelectorAll(known))if(vis(el))return mark(el);
    const like=/menu|nav|hamburger|burger|drawer|sidebar|rail|toggle|菜单|导航|更多/i, not=/theme|dark|light|moon|sun|search|top|close|lang|login|download|app/i;
    const cands=[...document.querySelectorAll('button,[role=button],a,div,span,label,i')].filter(el=>{
      if(!vis(el))return false;
      const sig=[el.className&&el.className.baseVal!==undefined?el.className.baseVal:el.className,el.id,el.getAttribute('aria-label'),el.getAttribute('aria-controls'),el.getAttribute('title'),el.getAttribute('data-target'),(el.textContent||'').trim().slice(0,6)].join(' ');
      if(!like.test(sig)||not.test(sig))return false;
      const r=el.getBoundingClientRect();return r.width<=160&&r.height<=90;
    }).sort((a,b)=>(b.hasAttribute('aria-expanded')-a.hasAttribute('aria-expanded'))||((b.tagName==='BUTTON')-(a.tagName==='BUTTON'))||(a.getBoundingClientRect().width*a.getBoundingClientRect().height-b.getBoundingClientRect().width*b.getBoundingClientRect().height));
    return cands.length?mark(cands[0]):false;
  },KNOWN);
  // 当前盖在页面上的层：fixed/absolute/sticky、面积够大、里面至少 3 个可见链接
  const layers=()=>page.evaluate(()=>{
    const vw=innerWidth,vh=innerHeight,res=[];
    for(const el of document.querySelectorAll('body *')){
      const s=getComputedStyle(el);
      if(!/fixed|absolute|sticky/.test(s.position)||s.display==='none'||s.visibility==='hidden'||parseFloat(s.opacity||'1')<0.05)continue;
      const r=el.getBoundingClientRect();
      const w=Math.min(r.right,vw)-Math.max(r.left,0),h=Math.min(r.bottom,vh)-Math.max(r.top,0);
      if(w<180||h<vh*0.3||w*h<vw*vh*0.22)continue;
      const links=[...el.querySelectorAll('a[href]')].filter(a=>{const q=a.getBoundingClientRect();return q.width>8&&q.height>8&&q.bottom>0&&q.top<vh&&q.right>0&&q.left<vw;});
      if(links.length<3)continue;
      const first=links[0].getBoundingClientRect(),hit=document.elementFromPoint(first.left+first.width/2,first.top+first.height/2);
      if(!el.hasAttribute('data-redline-layer'))el.setAttribute('data-redline-layer',String(res.length+1)+'-'+Math.random().toString(36).slice(2,7));
      res.push({id:el.getAttribute('data-redline-layer'),tag:el.tagName.toLowerCase(),cls:String(el.className&&el.className.baseVal!==undefined?el.className.baseVal:el.className).slice(0,80),rect:[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)],links:links.length,
        firstLinkHit:!!hit&&(hit===links[0]||links[0].contains(hit)||hit.contains(links[0])),firstHref:links[0].getAttribute('href')});
    }
    return res;
  });
  const gone=id=>page.evaluate(id=>{const el=document.querySelector('[data-redline-layer="'+id+'"]');if(!el)return true;const s=getComputedStyle(el),r=el.getBoundingClientRect();
    return s.display==='none'||s.visibility==='hidden'||parseFloat(s.opacity||'1')<0.05||r.right<=2||r.left>=innerWidth-2||r.bottom<=2||r.top>=innerHeight-2||r.width<40||r.height<40;},id);
  await page.setViewportSize({width:390,height:844});
  let shots=0;
  for(const item of paths){
    const rec={path:item.path,page_types:item.types,width:390,status:'fail',reasons:[]};
    try{
      const response=await page.goto(base+item.path,{waitUntil:'domcontentloaded',timeout:30000});
      await page.waitForLoadState('load',{timeout:8000}).catch(()=>{});
      rec.http=response?response.status():null;
      if(rec.http!==200){rec.status='blocked';rec.reasons.push('样例页本身不是 200');out.results.push(rec);continue;}
      // 手机首页是"进入大厅"入口页的模板：入口页本身没有站内导航，记为入口页；进大厅后的页面照常检查
      const gateBtn=page.locator('[id$="-entry-enter"]').filter({visible:true}).first();
      if(await gateBtn.count()){rec.entry_page=true;await gateBtn.click({timeout:3000}).catch(()=>{});await page.waitForLoadState('domcontentloaded',{timeout:8000}).catch(()=>{});await page.waitForTimeout(300);}
      const urlBefore=page.url().split('#')[0], pagesBefore=page.context().pages().length;
      const before=new Set((await layers()).map(x=>x.id));
      if(!await findToggle()){rec.reasons.push('390 宽下找不到手机端菜单按钮（汉堡按钮）');out.results.push(rec);continue;}
      const toggle=page.locator('[data-redline-toggle="1"]').first();
      rec.toggle=await toggle.evaluate(el=>({tag:el.tagName.toLowerCase(),cls:String(el.className&&el.className.baseVal!==undefined?el.className.baseVal:el.className).slice(0,80),text:(el.textContent||'').trim().slice(0,12),href:el.getAttribute('href'),target:el.getAttribute('target')}));
      await toggle.click({timeout:4000});
      await page.waitForTimeout(550);
      const pagesAfter=page.context().pages().length, urlAfter=page.url().split('#')[0];
      if(pagesAfter!==pagesBefore){rec.reasons.push('点菜单后开了新标签页');for(const p of page.context().pages().slice(pagesBefore))await p.close().catch(()=>{});}
      if(urlAfter!==urlBefore){rec.reasons.push('点菜单后跳到了新页面：'+urlAfter.replace(base,''));out.results.push(rec);continue;}
      const opened=(await layers()).filter(x=>!before.has(x.id));
      if(!opened.length){rec.reasons.push('点菜单后没有出现盖在页面上的导航层（抽屉/浮层）');
        if(shots<3){const f=`${folder}/${name}-mobile-nav-fail-${++shots}.png`;await page.screenshot({path:f,animations:'disabled'}).catch(()=>{});out.screenshots.push(f);}
        out.results.push(rec);continue;}
      const layer=opened.sort((a,b)=>b.links-a.links)[0];rec.layer={cls:layer.cls,rect:layer.rect,links:layer.links};
      if(!layer.firstLinkHit)rec.reasons.push('抽屉里的链接被别的东西盖住，点不到');
      // Leo 2026-09-21："點一下菜單就會跳出新的頁面"——当时的菜单是一整屏不透明的面板，地址没变但看起来就是新页面。
      // 抽屉 / 浮层要只盖住一部分，其余地方是半透明遮罩或原页面：取左中、右中、下方三个点，全都落在不透明的菜单面板上就不合格
      rec.coverage=await page.evaluate(id=>{
        const layer=document.querySelector('[data-redline-layer="'+id+'"]');if(!layer)return null;
        const alpha=el=>{const m=getComputedStyle(el).backgroundColor.match(/rgba?\(([^)]+)\)/);if(!m)return 0;const p=m[1].split(',').map(Number);return p.length>3?p[3]:1;};
        // 这个点上菜单本身有多不透明：从点到的元素一路往上到菜单层，把每一层的背景不透明度叠起来（1 - Π(1 - a)）
        const pts=[[innerWidth*0.08,innerHeight*0.5],[innerWidth*0.92,innerHeight*0.5],[innerWidth*0.5,innerHeight*0.93]];
        return pts.map(([x,y])=>{const hit=document.elementFromPoint(x,y);const at={x:Math.round(x),y:Math.round(y)};
          if(!hit||!(layer===hit||layer.contains(hit)))return {...at,menu:false};
          let clear=1;for(let n=hit;n;n=n.parentElement){clear*=1-alpha(n);if(n===layer)break;}
          return {...at,menu:true,alpha:Math.round((1-clear)*100)/100};});
      },layer.id);
      if(rec.coverage&&rec.coverage.every(p=>p.menu&&p.alpha>=0.95))rec.reasons.push('菜单是一整屏不透明的面板，看起来就像跳到了新页面（要的是侧边抽屉或浮层：只盖住一部分，背后页面半透明变暗还能看见）');
      rec.scroll_locked=await page.evaluate(()=>{const b=getComputedStyle(document.body),h=getComputedStyle(document.documentElement);return /hidden|clip/.test(b.overflowY)||/hidden|clip/.test(h.overflowY)||b.position==='fixed';});
      if(shots<1&&!rec.reasons.length){const f=`${folder}/${name}-mobile-nav-open.png`;await page.screenshot({path:f,animations:'disabled'}).catch(()=>{});out.screenshots.push(f);shots++;}
      // 关闭：Esc → 点抽屉外面 → 再点一次按钮 / 关闭按钮，任一种能关掉即可
      let closedBy=null;
      await page.keyboard.press('Escape');await page.waitForTimeout(350);
      if(await gone(layer.id))closedBy='esc';
      if(!closedBy){const [l,t,w,h]=layer.rect;const x=l+w<380?Math.min(385,l+w+20):l>10?Math.max(4,l-10):null;
        if(x!==null){await page.mouse.click(x,Math.min(800,t+Math.max(40,h/2)));await page.waitForTimeout(350);if(await gone(layer.id))closedBy='outside';}}
      if(!closedBy){const close=page.locator('[data-redline-layer="'+layer.id+'"] [aria-label*="关闭"],[data-redline-layer="'+layer.id+'"] [class*="close"],[data-redline-layer="'+layer.id+'"] [data-close]').filter({visible:true}).first();
        if(await close.count()){await close.click({timeout:2500}).catch(()=>{});await page.waitForTimeout(350);if(await gone(layer.id))closedBy='close-button';}}
      if(!closedBy){await toggle.click({timeout:2500}).catch(()=>{});await page.waitForTimeout(350);if(await gone(layer.id))closedBy='toggle';}
      rec.closed_by=closedBy;
      if(!closedBy)rec.reasons.push('抽屉打开后关不掉（Esc、点外面、关闭按钮、再点菜单都不行）');
      if(page.url().split('#')[0]!==urlBefore)rec.reasons.push('关闭菜单的过程中页面跳走了：'+page.url().replace(base,''));
      rec.status=rec.reasons.length?'fail':'pass';
    }catch(error){rec.status='blocked';rec.reasons.push(short(error));}
    out.results.push(rec);
  }
  return out;
}
