async (page) => {
  const browser = page.context().browser();
  if (!browser) throw new Error('CLI browser handle unavailable; use existing Python runner and record limitation');
  const context = await browser.newContext({javaScriptEnabled:false, viewport:{width:390,height:900}});
  try {
    const probe = await context.newPage();
    const response = await probe.goto('http://127.0.0.1:5855/',{waitUntil:'domcontentloaded'});
    if (!response || response.status() >= 500) throw new Error('Server failure; debugger HTML not retained');
    const html = await probe.content();
    const summary = await probe.evaluate(() => ({title:document.title, text:document.body.innerText.slice(0,1000),links:document.querySelectorAll('a[href]').length}));
    await probe.screenshot({path:'cli-nojs-390.png',fullPage:true,animations:'disabled'});
    return {kind:'nojs_dom',html,summary,screenshot:'cli-nojs-390.png'};
  } finally {await context.close();}
}
