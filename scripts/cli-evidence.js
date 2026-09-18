async (page) => {
  await page.goto('http://127.0.0.1:5855/', {waitUntil: 'domcontentloaded'});
  await page.locator('body').waitFor();
  await page.setViewportSize({width: 390, height: 900});
  const responseDom = await page.content();
  const metrics = await page.evaluate(() => ({
    viewport: innerWidth, width: document.documentElement.scrollWidth,
    title: document.title, h1: [...document.querySelectorAll('h1')].map(x=>x.textContent),
    forms: [...document.forms].map(x=>({action:x.getAttribute('action'),method:x.getAttribute('method')})),
    scripts: [...document.scripts].map(x=>x.getAttribute('src')).filter(Boolean)
  }));
  await page.screenshot({path:'cli-dom-390.png', fullPage:true, animations:'disabled'});
  return {kind:'rendered_dom', html:responseDom, metrics, screenshot:'cli-dom-390.png'};
}
