async (page) => {
  const result = { page: page.url(), viewport: 390 };
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(180);
  const enterGate = async () => {
    const gate = page.locator('#z9-entry-enter, #z10-entry-enter').filter({ visible: true }).first();
    if (await gate.count()) { await gate.click(); return true; }
    return false;
  };
  result.entryGate = await enterGate().catch(() => false);
  const toggle = page.locator('button[aria-controls][aria-label*="菜单"], button[aria-controls][aria-label*="导航"], button[aria-controls][aria-label*="侧边栏"], .mobilemenu[aria-expanded], [data-z7-more]')
    .filter({ visible: true }).first();
  if (await toggle.count()) {
    try {
      const before = await toggle.getAttribute('aria-expanded');
      await toggle.click();
      const after = await toggle.getAttribute('aria-expanded');
      const template = await page.locator('body').getAttribute('data-template');
      if (template) await page.screenshot({ path: `${template}-mobile-menu-open.png`, animations: 'disabled' });
      await page.keyboard.press('Escape');
      if (template) await page.screenshot({ path: `${template}-mobile-menu-closed.png`, animations: 'disabled' });
      result.navigation = { before, after, closed: await toggle.getAttribute('aria-expanded') };
    } catch (e) { result.navigation = { error: String(e).slice(0, 100) }; }
  } else result.navigation = { status: 'needs_review', reason: 'No visible expanded navigation control' };

  const theme = page.locator('[data-theme-toggle], [data-z13-theme-toggle], [data-z1-theme]')
    .filter({ visible: true }).first();
  if (await theme.count()) {
    try {
      const before = await page.locator('html').getAttribute('data-theme');
      const backgroundBefore = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
      await theme.click();
      const after = await page.locator('html').getAttribute('data-theme');
      const backgroundAfter = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('load');
      result.theme = { before, after, persisted: await page.locator('html').getAttribute('data-theme'),
        backgroundBefore, backgroundAfter };
      await enterGate().catch(() => false);
      const themeTemplate = await page.locator('body').getAttribute('data-template');
      const menuAfterTheme = page.locator('button[aria-controls][aria-label*="菜单"], button[aria-controls][aria-label*="导航"]').filter({ visible: true }).first();
      if (themeTemplate && await menuAfterTheme.count()) {
        await menuAfterTheme.click();
        await page.screenshot({ path: `${themeTemplate}-mobile-menu-${after}.png`, animations: 'disabled' });
        await page.keyboard.press('Escape');
      }
    } catch (e) { result.theme = { error: String(e).slice(0, 700) }; }
  } else result.theme = { status: 'needs_review', reason: 'No visible theme control' };

  if (await page.locator('body').getAttribute('data-template') === 'z7') {
    const dots = page.locator('[data-z7-hero-dot]');
    if (await dots.count() > 1) {
      await dots.nth(1).click();
      result.hero = { title: await page.locator('.z7-dash-hero__title').innerText(),
        href: await page.locator('.z7-dash-hero__cta').getAttribute('href') };
      await page.screenshot({ path: 'z7-hero-next.png', animations: 'disabled' });
    }
  }

  try {
    await page.evaluate(() => {
      const root = document.documentElement;
      const previous = root.style.scrollBehavior;
      root.style.scrollBehavior = 'auto';
      scrollTo(0, document.body.scrollHeight);
      root.style.scrollBehavior = previous;
    });
    await page.waitForFunction(() => scrollY > 320, null, { timeout: 2000 }).catch(() => {});
    await page.waitForTimeout(120);
    const scrollBefore = await page.evaluate(() => scrollY);
    const top = page.locator('#scroll-to-top, .z1-back-top').filter({ visible: true }).first();
    if (await top.count()) {
      await top.click();
      await page.waitForFunction(() => scrollY < 2, null, { timeout: 4000 }).catch(() => {});
      result.gotoTop = { scrollBefore, scrollAfter: await page.evaluate(() => scrollY) };
    } else result.gotoTop = { status: 'needs_review', reason: 'No visible top control',
      scrollBefore, button: await page.locator('#scroll-to-top').evaluateAll((items) => items.map((item) => ({
        className: item.className, display: getComputedStyle(item).display,
        visibility: getComputedStyle(item).visibility, opacity: getComputedStyle(item).opacity,
        rect: item.getBoundingClientRect().toJSON()
      }))) };
  } catch (e) { result.gotoTop = { error: String(e).slice(0, 100) }; }

  let search = page.locator('form[action="/search"] input[name="q"]').filter({ visible: true }).first();
  if (!(await search.count())) {
    const openSearch = page.locator('#mobile-search-icon, button[aria-label="打开搜索"]')
      .filter({ visible: true }).first();
    if (await openSearch.count()) await openSearch.click().catch(() => {});
    search = page.locator('form[action="/search"] input[name="q"]').filter({ visible: true }).first();
  }
  if (await search.count()) {
    try {
      await search.fill('英超');
      await Promise.all([page.waitForURL(/\/search\?q=/, { timeout: 10000 }), search.press('Enter')]);
      await page.waitForLoadState('load');
      const title = await page.title();
      result.search = { url: page.url(), serverError: title.includes('Werkzeug Debugger'),
        headingCount: await page.locator('h1').count(), resultLinks: await page.locator('main a[href]').count(),
        themeAfterNavigation: await page.locator('html').getAttribute('data-theme') };
      result.search.themeMaintained = !result.theme.persisted || result.search.themeAfterNavigation === result.theme.persisted;
      let submit = page.locator('form[action="/search"] button[type="submit"]').filter({ visible: true }).first();
      let nextInput = page.locator('form[action="/search"] input[name="q"]').filter({ visible: true }).first();
      if (!(await submit.count()) || !(await nextInput.count())) {
        const reopen = page.locator('#mobile-search-icon, button[aria-label="打开搜索"]').filter({ visible: true }).first();
        if (await reopen.count()) await reopen.click().catch(() => {});
        submit = page.locator('form[action="/search"] button[type="submit"]').filter({ visible: true }).first();
        nextInput = page.locator('form[action="/search"] input[name="q"]').filter({ visible: true }).first();
      }
      if (await submit.count() && await nextInput.count()) {
        await nextInput.fill('nba');
        await Promise.all([page.waitForURL(/\/search\?q=nba/, { timeout: 10000 }), submit.click()]);
        await page.waitForLoadState('load');
        result.search.buttonUrl = page.url();
      } else result.search.button = 'needs_review';
      let specialInput = page.locator('form[action="/search"] input[name="q"]').filter({ visible: true }).first();
      if (!(await specialInput.count())) {
        const reopen = page.locator('#mobile-search-icon, button[aria-label="打开搜索"]').filter({ visible: true }).first();
        if (await reopen.count()) await reopen.click().catch(() => {});
        specialInput = page.locator('form[action="/search"] input[name="q"]').filter({ visible: true }).first();
      }
      if (await specialInput.count()) {
        await specialInput.fill('不存在+?');
        await Promise.all([page.waitForURL(/\/search\?q=%/, { timeout: 10000 }), specialInput.press('Enter')]);
        await page.waitForLoadState('load');
        result.search.specialUrl = page.url();
        result.search.specialServerError = (await page.title()).includes('Werkzeug Debugger');
      }
    } catch (e) { result.search = { error: String(e).slice(0, 100) }; }
  } else result.search = { status: 'needs_review', reason: 'No visible site search input' };
  return result;
}
