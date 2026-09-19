"""Check whether the mobile APP banner covers a focused home-page link."""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

from core import ROOT, save_json


PROBE = """() => {
  const banner = document.querySelector('.bottom-downloadapp');
  const candidates = [...document.querySelectorAll('a[href]')].filter(a => {
    const r = a.getBoundingClientRect();
    return r.width > 20 && r.height > 10 &&
      !a.closest('header, footer, .bottom-downloadapp, [inert], [aria-hidden="true"]') &&
      a.tabIndex >= 0 &&
      getComputedStyle(a).visibility === 'visible';
  });
  const documentTop = a => a.getBoundingClientRect().top + scrollY;
  const link = candidates.find(a => documentTop(a) > 1200) ||
    candidates.reverse().find(a => documentTop(a) > 600);
  if (!banner || !link || getComputedStyle(banner).display === 'none') {
    return {status: 'blocked', reason: 'visible banner or in-content link missing'};
  }
  document.documentElement.style.scrollBehavior = 'auto';
  link.scrollIntoView({block: 'end'});
  link.focus();
  const a = link.getBoundingClientRect(), b = banner.getBoundingClientRect();
  const focused = document.activeElement === link;
  const covered = a.bottom > b.top && a.top < b.bottom && a.right > b.left && a.left < b.right;
  const overflow = document.documentElement.scrollWidth > innerWidth + 2;
  return {
    status: !focused || covered || overflow ? 'fail' : 'pass',
    href: link.getAttribute('href'), focused,
    banner_top: b.top, link_bottom: a.bottom, covered, page_overflow: overflow,
    scroll_padding_bottom: getComputedStyle(document.documentElement).scrollPaddingBottom
  };
}"""


def main(output):
    target = (ROOT / output).resolve()
    if not target.is_relative_to(ROOT / 'runs'):
        raise ValueError('Evidence must stay under external runs/')
    records = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for number in range(1, 18):
                for width in (320, 390):
                    context = browser.new_context(
                        viewport={'width': width, 'height': 900}, is_mobile=True, has_touch=True,
                        user_agent=('Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 '
                                    '(KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36'))
                    page = context.new_page()
                    try:
                        response = page.goto(f'http://127.0.0.1:{6300 + number}/',
                                             wait_until='domcontentloaded', timeout=15000)
                        if number == 9:
                            page.locator('#z9-entry-enter').click(timeout=3000)
                            page.wait_for_function(
                                "document.documentElement.getAttribute('data-z9-entry') === 'skip'",
                                timeout=3000)
                        page.wait_for_timeout(150)
                        result = page.evaluate(PROBE)
                        result['http_status'] = response.status if response else None
                    except Exception as error:
                        result = {'status': 'blocked', 'reason': type(error).__name__}
                    records.append({'template': f'z{number}', 'width': width, **result})
                    context.close()
        finally:
            browser.close()
    save_json(target, records)
    counts = {status: sum(r['status'] == status for r in records)
              for status in ('pass', 'fail', 'blocked')}
    print(counts)
    if counts['fail'] or counts['blocked']:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    main(parser.parse_args().output)
