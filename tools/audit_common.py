"""Shared helpers for the site audits.

Everything here exists because of a bug one of these checks let through once.
Read the notes before changing any of it.
"""
import glob
import os
import sys

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 404.html links its assets from "/" so it renders unstyled over file://.
# It is excluded on purpose; check it on the live site instead.
SKIP = {'404.html'}


def pages(root=SITE):
    return sorted(
        os.path.basename(p) for p in glob.glob(os.path.join(root, '*.html'))
        if os.path.basename(p) not in SKIP
    )


def url(page, root=SITE):
    return 'file://' + os.path.join(root, page)


def find_chromium():
    """Locate a Chromium binary.

    Playwright's default resolution asks for the exact build its Python package
    was pinned to, which is often not the build that is actually installed.
    So: honour CHROMIUM_PATH, else let Playwright try, else go looking.
    """
    if os.environ.get('CHROMIUM_PATH'):
        return os.environ['CHROMIUM_PATH']
    roots = [os.environ.get('PLAYWRIGHT_BROWSERS_PATH', ''),
             os.path.expanduser('~/.cache/ms-playwright')]
    for root in filter(None, roots):
        for pat in ('chromium-*/chrome-linux/chrome',
                    'chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium',
                    'chrome-linux/chrome'):
            hits = sorted(glob.glob(os.path.join(root, pat)))
            if hits:
                return hits[-1]
    return None


def launch(pw):
    """Chromium, however it happens to be installed here."""
    try:
        return pw.chromium.launch()
    except Exception:
        exe = find_chromium()
        if not exe:
            sys.exit('Chromium not found. Set CHROMIUM_PATH, or run: playwright install chromium')
        return pw.chromium.launch(executable_path=exe)


def prepare(page, theme=None, open_details=False):
    """Put the page in a measurable state.

    Three things bite if you skip them:

    1. motion.css holds `.reveal` at opacity 0 until an IntersectionObserver
       adds `.is-visible`. Without stripping that, everything below the fold
       measures as invisible and the audit silently passes.
    2. CSS colour transitions are still mid-flight right after a theme switch,
       so computed colours come back as intermediate values. Two identical runs
       once disagreed on 384 findings. Disabling transitions makes it
       deterministic.
    3. `<details>` bodies are display:none until opened, so accordion content
       is never measured unless you ask for it.
    """
    page.add_style_tag(content='*,*::before,*::after{transition:none!important;animation:none!important}')
    if theme:
        page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", theme)
    page.evaluate("""() => {
      document.documentElement.classList.remove('has-motion');
      document.querySelectorAll('.reveal,.reveal-item,.reveal-group')
              .forEach(e => e.classList.add('is-visible'));
      document.querySelectorAll('.thread-svg').forEach(e => e.classList.add('in-view'));
    }""")
    if open_details:
        page.evaluate("() => document.querySelectorAll('details').forEach(d => d.open = true)")
    page.wait_for_timeout(200)


# --- Colour maths, shared by the contrast checks --------------------------
# Kept as a JS string because it has to run in the page, against computed
# styles, rather than against what the stylesheet says.
COLOUR_JS = r"""
  function srgb(v){v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);}
  function lum(c){return 0.2126*srgb(c[0])+0.7152*srgb(c[1])+0.0722*srgb(c[2]);}
  function parse(c){const p=c.match(/[\d.]+/g).map(Number);return {rgb:p.slice(0,3),a:p.length>3?p[3]:1};}
  function hex(c){return '#'+c.map(v=>Math.round(v).toString(16).padStart(2,'0')).join('');}
  // Walk up compositing translucent layers. Returns null over a gradient,
  // which cannot be reduced to one colour: those are reported as unmeasured
  // rather than guessed at.
  function bgStack(el){
    let n=el, L=[];
    while(n){
      const st=getComputedStyle(n);
      if(st.backgroundImage && st.backgroundImage!=='none') return null;
      const p=parse(st.backgroundColor);
      if(p.a>0) L.push(p);
      if(p.a===1) break;
      n=n.parentElement;
    }
    let o=[255,255,255];
    for(let i=L.length-1;i>=0;i--){const x=L[i];o=[0,1,2].map(k=>x.rgb[k]*x.a+o[k]*(1-x.a));}
    return o;
  }
  function ratio(a,b){const f=lum(a),g=lum(b);const[hi,lo]=f>g?[f,g]:[g,f];
    return +((hi+0.05)/(lo+0.05)).toFixed(2);}
  // WCAG 1.4.3: 3:1 for large text (>=24px, or >=18.66px bold), else 4.5:1.
  function threshold(cs){
    const px=parseFloat(cs.fontSize), bold=parseInt(cs.fontWeight)>=700;
    return (px>=24 || (px>=18.66 && bold)) ? 3 : 4.5;
  }
  // opacity fades the text toward its backdrop, so fold it in before measuring.
  function foreground(el, bg){
    const cs=getComputedStyle(el), op=parseFloat(cs.opacity);
    let fg=parse(cs.color).rgb;
    if(op<1) fg=[0,1,2].map(k=>fg[k]*op+bg[k]*(1-op));
    return fg;
  }
  function label(el){
    let s = el.tagName.toLowerCase();
    if (typeof el.className === 'string' && el.className.trim())
      s += '.' + el.className.trim().split(/\s+/)
            .filter(c => !/^(reveal|reveal-item|reveal-group|is-visible|in-view)$/.test(c))
            .join('.');
    return s;
  }
"""


def report(title, findings, detail=lambda f: str(f)):
    """Print a section and return 1 if it failed, for the exit code."""
    print(f'\n{title}')
    if not findings:
        print('  PASS')
        return 0
    for f in findings:
        print('  ' + detail(f))
    print(f'  FAIL ({len(findings)})')
    return 1


def main_guard():
    if not os.path.isdir(SITE) or not pages():
        sys.exit(f'no pages found under {SITE}')
