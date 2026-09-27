(cfg) => {
  // Detects ad-like regions on the current page. Read-only: never mutates the DOM.
  // Returns {scroll, viewport, dpr, regions:[...]} as a JSON-serialisable object.
  const AD_HOSTS = (cfg && cfg.adHosts) || [];
  const MARKER = (cfg && cfg.markerAttr) || 'data-research-ad-id';
  const MAX_SCAN = 6000;
  const TOKEN_RE = /(^|[\s_\-])(ad|ads|adv|advert|advertisement|adslot|adunit|adbox|adbanner|adcontainer|sponsor|sponsored|promoted|dfp|gpt-ad|native-ad|ad-slot|ad-unit|ad-container|ad-wrapper|banner-ad)([\s_\-]|$)/i;
  const LABEL_RE = /^\s*(ad|ads|advertisement|advertisements|sponsored|sponsored content|promoted|paid content|anzeige|publicité|publicidad|patrocinado|werbung)\s*[:·•]?\s*$/i;
  const TRACKER_PATH_RE = /\/(aclk|adclick|pagead\/|clickserve|ad\.doubleclick|click\?|ck\.php)/i;
  const KNOWN_SELECTORS = [
    'ins.adsbygoogle', '[id^="google_ads_iframe"]', '[id^="div-gpt-ad"]', '[data-google-query-id]',
    '[data-ad-slot]', '[data-ad-client]', '[data-ad-unit]', '[data-adunit]', '[data-ad]',
    'amp-ad', 'amp-embed', '[id^="taboola-"]', '.trc_related_container', '.OUTBRAIN',
    '[aria-label="Advertisement" i]', '[aria-label="Sponsored" i]', '[aria-label="Ad" i]'
  ];

  const hostOf = (u) => { try { return new URL(u, location.href).hostname.toLowerCase(); } catch (e) { return ''; } };
  const isAdHost = (h) => !!h && AD_HOSTS.some((d) => h === d || h.endsWith('.' + d));
  const vw = window.innerWidth, vh = window.innerHeight;
  const sx = window.scrollX, sy = window.scrollY;

  const cssPath = (el) => {
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 8) {
      let part = node.tagName.toLowerCase();
      if (node.id && /^[A-Za-z][\w\-]*$/.test(node.id)) { parts.unshift(part + '#' + node.id); break; }
      const parent = node.parentElement;
      if (parent) {
        const same = Array.from(parent.children).filter((c) => c.tagName === node.tagName);
        if (same.length > 1) part += ':nth-of-type(' + (same.indexOf(node) + 1) + ')';
      }
      parts.unshift(part);
      node = parent;
    }
    return parts.join(' > ');
  };

  const found = new Map();
  const add = (el, reason, confidence) => {
    if (!el || el.nodeType !== 1) return;
    const r = el.getBoundingClientRect();
    const hasMarker = el.hasAttribute(MARKER);
    if (!hasMarker && (r.width < 10 || r.height < 10)) return;
    let e = found.get(el);
    if (!e) { e = { el, reasons: new Set(), confidence: 0 }; found.set(el, e); }
    e.reasons.add(reason);
    e.confidence = Math.max(e.confidence, confidence);
  };

  // 1. Researcher-controlled markers (ground-truth ad slots on test/controlled pages).
  document.querySelectorAll('[' + MARKER + ']').forEach((el) => add(el, 'research_marker', 1.0));

  // 2. Well-known ad container conventions.
  KNOWN_SELECTORS.forEach((s) => {
    try { document.querySelectorAll(s).forEach((el) => add(el, 'known_selector:' + s, 0.85)); } catch (e) {}
  });

  // 3. Iframes served from ad hosts, or named like ad slots.
  document.querySelectorAll('iframe').forEach((f) => {
    const h = hostOf(f.src || '');
    if (isAdHost(h)) add(f, 'ad_iframe_host:' + h, 0.9);
    else if (TOKEN_RE.test((f.id || '') + ' ' + (f.name || '') + ' ' + (f.title || ''))) add(f, 'ad_iframe_name', 0.6);
  });

  // 4. Links that go to ad hosts / click trackers.
  document.querySelectorAll('a[href]').forEach((a) => {
    const h = hostOf(a.href);
    if (isAdHost(h)) add(a, 'ad_link_host:' + h, 0.8);
    else if (TRACKER_PATH_RE.test(a.href)) add(a, 'ad_click_tracker_path', 0.7);
  });

  // 5. Class / id naming conventions (weaker signal; require a reasonably sized box).
  const named = document.querySelectorAll('[id],[class]');
  for (let i = 0; i < named.length && i < MAX_SCAN; i++) {
    const el = named[i];
    const label = (el.id || '') + ' ' + (el.getAttribute('class') || '');
    if (!TOKEN_RE.test(label)) continue;
    const r = el.getBoundingClientRect();
    if (r.width >= 50 && r.height >= 30) add(el, 'ad_token_name', 0.5);
  }

  // 6. Disclosure labels ("Sponsored", "Advertisement") -> nearest sizeable ancestor.
  const leaves = document.querySelectorAll('span,div,p,small,label,figcaption,a,strong,em,b,i');
  for (let i = 0; i < leaves.length && i < MAX_SCAN; i++) {
    const el = leaves[i];
    if (el.childElementCount > 0) continue;
    const txt = (el.textContent || '').trim();
    if (!txt || txt.length > 30 || !LABEL_RE.test(txt)) continue;
    let anc = el.parentElement;
    for (let d = 0; anc && d < 6; d++, anc = anc.parentElement) {
      const r = anc.getBoundingClientRect();
      if (r.width >= 120 && r.height >= 60) { add(anc, 'disclosure_label:' + txt.toLowerCase(), 0.7); break; }
    }
  }

  // Merge: drop regions nested inside another region, folding their reasons upward.
  const entries = Array.from(found.values());
  const kept = entries.filter((e) => !entries.some((o) => o !== e && o.el.contains(e.el)));
  entries.forEach((e) => {
    if (kept.includes(e)) return;
    const outer = kept.find((k) => k.el.contains(e.el));
    if (outer) { e.reasons.forEach((r) => outer.reasons.add(r)); outer.confidence = Math.max(outer.confidence, e.confidence); }
  });

  const regions = kept.map((e) => {
    const el = e.el;
    const r = el.getBoundingClientRect();
    const markerEl = el.hasAttribute(MARKER) ? el : el.querySelector('[' + MARKER + ']');
    const links = Array.from(el.tagName === 'A' ? [el] : el.querySelectorAll('a[href]')).slice(0, 5).map((a) => a.href);
    const iframes = Array.from(el.tagName === 'IFRAME' ? [el] : el.querySelectorAll('iframe')).slice(0, 3).map((f) => f.src || '');
    const imgs = Array.from(el.querySelectorAll('img')).slice(0, 3).map((im) => ({ src: im.currentSrc || im.src, alt: im.alt || '' }));
    const visibleArea = Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0)) * Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0));
    const area = Math.max(1, r.width * r.height);
    return {
      marker_id: markerEl ? markerEl.getAttribute(MARKER) : null,
      selector: cssPath(el),
      tag: el.tagName.toLowerCase(),
      reasons: Array.from(e.reasons),
      confidence: e.confidence,
      text: (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 400),
      links, iframes, images: imgs,
      viewport_rect: { x: r.left, y: r.top, width: r.width, height: r.height },
      page_rect: { x: r.left + sx, y: r.top + sy, width: r.width, height: r.height },
      visible_fraction: Math.round((visibleArea / area) * 100) / 100,
    };
  });

  return {
    url: location.href,
    scroll: { x: sx, y: sy },
    viewport: { width: vw, height: vh },
    dpr: window.devicePixelRatio || 1,
    regions,
  };
}
