import assert from 'node:assert/strict';

/** Verify painted colors, not just the html attribute or theme icon. */
export async function verifyPortalTheme(page, mode) {
  const result = await page.evaluate(() => {
    const visible = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
    const parse = value => {
      const numbers = value.match(/[\d.]+/g)?.map(Number) || [0,0,0,0];
      return [numbers[0],numbers[1],numbers[2],numbers.length === 4 ? numbers[3] : 1];
    };
    const over = (front, back) => [...front.slice(0,3).map((v, i) => v * front[3] + back[i] * (1-front[3])),1];
    const luminance = color => {
      const channels = color.slice(0,3).map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
      return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
    };
    const background = element => {
      const ancestors = [];
      for (let node=element;node;node=node.parentElement) ancestors.unshift(node);
      return ancestors.reduce((paint, el) => over(parse(getComputedStyle(el).backgroundColor), paint), [255,255,255,1]);
    };
    const surfaces = [...document.querySelectorAll('html, body, .portal-shell, .portal-header, .panel, .pet-card, .field-input, .staff-sidebar, thead, tbody, .popover-panel, .hero-copy-card, .spotlight-card, .spotlight-details, .latest-pets-section, .journey-step, .workspace-links')].filter(visible).map(el => ({
      tag: el.tagName, classes: el.className, bg: getComputedStyle(el).backgroundColor,
      brightness: parse(getComputedStyle(el).backgroundColor).slice(0,3).reduce((a,b) => a+b,0) / 3,
      alpha: parse(getComputedStyle(el).backgroundColor)[3],
    }));
    const fonts = [...document.querySelectorAll('body,h1,h2,h3,h4,.font-display,.field-input,.btn')].filter(visible).map(el => getComputedStyle(el).fontFamily);
    const contrast = [...document.querySelectorAll('h1,h2,h3,h4,.hero-description,.hero-eyebrow,.hero-care-note p,.section-label,.field-label,.field-input,.photo-placeholder-caption,.adopter-nav-link,.pet-card p,.pet-availability,.spotlight-details p,.portal-header a,.portal-header button')].filter(visible).filter(el => !el.disabled).map(el => {
      const style = getComputedStyle(el), bg = background(el), fg = over(parse(style.color), bg);
      const first = luminance(fg), second = luminance(bg);
      const size = parseFloat(style.fontSize), weight = parseInt(style.fontWeight);
      const iconOnly = (el.tagName === 'BUTTON' || el.tagName === 'A') && !el.textContent.trim();
      return { tag: el.tagName, classes: el.className, text: el.textContent.trim().slice(0,60), foreground: style.color, background: bg, ratio: (Math.max(first,second)+.05)/(Math.min(first,second)+.05), required: size >= 24 || size >= 18.66 && weight >= 700 || iconOnly ? 3 : 4.5 };
    });
    return { mode: document.documentElement.dataset.theme, surfaces, fonts, contrast };
  });
  assert.equal(result.mode, mode);
  assert.ok(result.surfaces.length >= 3, 'Visible theme surfaces required');
  for (const surface of result.surfaces.filter(surface => surface.alpha > 0)) {
    assert.ok(mode === 'dark' ? surface.brightness < 105 : surface.brightness > 205 && surface.brightness <= 248, `${mode} surface: ${JSON.stringify(surface)}`);
  }
  assert.equal(new Set(result.fonts).size, 1, `Mixed font families: ${JSON.stringify([...new Set(result.fonts)])}`);
  for (const text of result.contrast) assert.ok(text.ratio >= text.required, `${mode} contrast: ${JSON.stringify(text)}`);
  return { surfaces: result.surfaces.length, textChecks: result.contrast.length };
}
