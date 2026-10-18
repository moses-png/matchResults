"""
BetPawa favourite-bet bot  (Selenium, Python, headless)

Flow:  events list -> open card -> read stats + odds -> click favourite odd -> back -> next card.
Stops when the combined odds of the picks added reach TARGET_ODDS (within ODDS_TOLERANCE).
At the end it reads the betslip booking code and saves everything to picks.csv / booking_code.txt.

Nothing here depends on ids, classes or data-test-id. Everything is found by VISIBLE TEXT
(market titles such as "Double Chance | Full Time", outcome labels such as "1X" / "Over 1.5",
stat labels such as "Win Probability") plus basic page structure. If a market is missing on
an event (corners, 1UP, Over 1.5 ...) it is simply skipped for that event.

It only adds a selection to the betslip. It never places a bet.

    pip install selenium
    python bet_bot_selenium.py
"""
import csv
import re
import time

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ----------------------------------------------------------------------------- settings
LIST_URL = "https://www.betpawa.ug/events?categoryId=2&marketId=1X2"
BASE_URL = "https://www.betpawa.ug"
MAX_EVENTS = None          # how many cards to process (None = all, needed for the odds target)
CLICK_PICK = True          # False = analyse only (dry run)
HEADLESS = True            # True = no browser window

TARGET_ODDS = 20.0         # stop when combined odds reach this (None = no limit)
ODDS_TOLERANCE = 0.10      # 10%: stops at >= 18.0, never goes above 22.0

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

CFG = {
    "minProb": 0.55,            # ignore bets we think are less likely than this
    "minOdds": 1.20,            # ignore bets paying less than this
    "requirePositiveEV": False, # True = only click when probability x odds > 1
    "modelWeight": 0.6,         # weight of the Poisson model vs raw stats percentages
    # Market titles as shown on the page. Add aliases if BetPawa ever renames one.
    "markets": {
        "ft":   ["1X2 | Full Time"],
        "dc":   ["Double Chance | Full Time"],
        "up":   ["1X2 1UP | Full Time"],
        "ou":   ["Over/Under | Full Time"],
        "btts": ["Both Teams To Score | Full Time"],
        "corn": ["Corner Count 1X2 | Full Time"],
    },
}

# ------------------------------------------------------------------ in-page analysis (JS)
# Runs inside the event page. Returns the analysis and tags the chosen odds button with
# data-bp-pick="1" so Selenium can do a real click on it.
ANALYSE_JS = r"""
(cfg) => {
  const num = t => { const v = parseFloat(String(t).replace('%','')); return isNaN(v) ? NaN : v; };
  const ok = v => typeof v === 'number' && !isNaN(v);
  const mean = a => { a = a.filter(ok); return a.length ? a.reduce((s,x)=>s+x,0)/a.length : NaN; };
  const norm = s => String(s).replace(/\s+/g,' ').replace(/\s*\|\s*/g,' | ').trim().toLowerCase();

  /* ---------- visible text tokens (used for the stats widgets) ---------- */
  function getTokens() {
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, { acceptNode(n) {
      const p = n.parentElement;
      if (!p || /^(SCRIPT|STYLE|NOSCRIPT)$/.test(p.tagName)) return NodeFilter.FILTER_REJECT;
      return n.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT; }});
    const raw = []; while (w.nextNode()) raw.push(w.currentNode.nodeValue.trim());
    const t = []; for (const x of raw) { if (x === '%' && t.length) t[t.length-1] += '%'; else t.push(x); }
    return t;
  }
  function numbersAfter(t, label, from, count) {
    const i = t.indexOf(label, from); if (i < 0) return [];
    const out = [];
    for (let j = i+1; j < t.length && out.length < count; j++) {
      const v = num(t[j]);
      if (ok(v)) out.push(v); else if (/^[A-Za-z]/.test(t[j]) && t[j] !== 'League') break;
    }
    return out;
  }
  function parseStats(t) {
    const wp = t.indexOf('Win Probability'), pm = t.indexOf('Previous meetings');
    if (wp < 0) return null;
    const S = {};
    const seg = t.slice(wp, pm > wp ? pm : wp + 25);
    const pcts = seg.filter(x => /^\d+(\.\d+)?%$/.test(x)); const di = seg.indexOf('Draw');
    S.win = { home: num(pcts[0]), draw: di > 0 ? num(seg[di-1]) : NaN, away: num(pcts[pcts.length-1]) };
    const av = Math.max(t.indexOf('Goals Scored'), 0);
    S.avg = {
      goals: numbersAfter(t,'Goals Scored',av,1)[0], leagueGoals: numbersAfter(t,'Goals Scored',av,2)[1],
      btts: numbersAfter(t,'BTTS',av,1)[0], over15: numbersAfter(t,'over 1.5',av,1)[0],
      corners: numbersAfter(t,'Corners',av,3) };                       // [total, home, away]
    const mp = []; t.forEach((x,i) => { if (x === 'MP') mp.push(num(t[i-1])); });
    S.mp = mp.slice(0,2);
    const labels = ['Matches played','Win%','Total Goals','AVG goals scored','AVG goals conceded',
      'Both teams scored','over 1.5','over 2.5','HT Over 0.5','HT Over 1.5','Yellow cards','Total cards'];
    const T = { t1:{}, t2:{} }; let from = Math.max(t.indexOf('Matches played')-1, 0);
    for (const L of labels) {
      const i = t.indexOf(L, from+1); if (i < 0) continue; from = i;
      T.t1[L] = { ctx: num(t[i-3]), all: num(t[i-1]) };
      T.t2[L] = { ctx: num(t[i+1]), all: num(t[i+3]) };
    }
    S.team = T; return S;
  }

  /* ---------- maths ---------- */
  function pmfArr(l, n=16) { const a=[Math.exp(-l)]; for (let k=1;k<=n;k++) a.push(a[k-1]*l/k); return a; }
  function fitLambdas(pH,pD,pA,total) {
    let best={e:Infinity,lh:1.3,la:1.1}; const cache=new Map();
    const g = x => { const k=Math.round(x*1000); if(!cache.has(k)) cache.set(k,pmfArr(x)); return cache.get(k); };
    for (let lh=0.15; lh<=3.6; lh+=0.025) for (let la=0.15; la<=3.6; la+=0.025) {
      const a=g(lh), b=g(la); let h=0,d=0,w=0;
      for (let i=0;i<a.length;i++) for (let j=0;j<b.length;j++) { const p=a[i]*b[j]; if(i>j)h+=p; else if(i===j)d+=p; else w+=p; }
      const s=h+d+w; h/=s; d/=s; w/=s;
      let e=(h-pH)**2+(d-pD)**2+(w-pA)**2; if (ok(total)) e+=0.01*(lh+la-total)**2;
      if (e<best.e) best={e,lh,la};
    }
    return best;
  }
  function pOneUp(lh,la,home) {            // P(team leads at some moment of the match)
    const L=lh+la, p=home?lh/L:la/L, K=16, pm=pmfArr(L,K);
    let dist=new Array(2*K+3).fill(0); dist[K+1]=1; let ab=0, tot=0;
    for (let n=1;n<=K;n++) { const nd=new Array(dist.length).fill(0);
      for (let d=-n+1; d<=0; d++) { const m=dist[d+K+1]; if(!m) continue;
        if (d===0) ab+=m*p; else nd[d+1+K+1]+=m*p; nd[d-1+K+1]+=m*(1-p); }
      dist=nd; tot+=pm[n]*ab; }
    return tot;
  }
  function pMoreCorners(mh,ma,homeSide) {
    const a=pmfArr(mh,30), b=pmfArr(ma,30); let win=0,tot=0;
    for (let i=0;i<a.length;i++) for (let j=0;j<b.length;j++) { const p=a[i]*b[j]; tot+=p; if(homeSide?i>j:j>i) win+=p; }
    return win/tot;
  }

  /* ---------- odds, found by visible text ---------- */
  const leaves = new Map();            // normalised text -> elements that contain only that text
  for (const e of document.body.querySelectorAll('*')) {
    if (e.children.length || /^(SCRIPT|STYLE|NOSCRIPT)$/i.test(e.tagName)) continue;
    const t = norm(e.textContent); if (!t) continue;
    if (!leaves.has(t)) leaves.set(t, []); leaves.get(t).push(e);
  }
  function oddBtn(b) {                 // odds button = first child is the label, last child is the price
    const k = b.children; if (k.length < 2) return null;
    const label = k[0].textContent.trim(), last = k[k.length-1].textContent.trim();
    if (!label || !/^\d+(\.\d+)?$/.test(last)) return null;
    return { label, odds: parseFloat(last), btn: b };
  }
  function firstText(box) {            // first non-empty text inside a container
    for (const e of box.querySelectorAll('*')) if (!e.children.length && norm(e.textContent)) return norm(e.textContent);
    return '';
  }
  function findOdd(titles, label) {
    for (const title of titles) for (const el of (leaves.get(norm(title)) || [])) {
      let a = el;
      for (let up = 0; up < 8 && a.parentElement; up++) {
        a = a.parentElement;
        const bs = [...a.querySelectorAll('button')].map(oddBtn).filter(Boolean);
        if (bs.length >= 2) {
          // a real market box STARTS with its title; combo-bet cards etc. that merely mention it do not
          if (firstText(a) !== norm(title)) break;
          const hit = bs.find(x => norm(x.label) === norm(label)); if (hit) return hit; break;
        }
      }
    }
    return null;
  }

  /* ---------- analysis ---------- */
  const M = cfg.markets;
  const names = (document.title.match(/Bet on (.+?) - (.+?) \|/) || []).slice(1);
  const H = names[0] || 'Home', A = names[1] || 'Away';
  const S = parseStats(getTokens());
  let mode = 'stats', pH, pD, pA;
  if (S && ok(S.win.home) && ok(S.win.draw) && ok(S.win.away)) {
    const s = S.win.home + S.win.draw + S.win.away; pH = S.win.home/s; pD = S.win.draw/s; pA = S.win.away/s;
  } else {                              // no stats widget: fall back to the bookmaker's own 1X2 (margin removed)
    const o1 = findOdd(M.ft,'1'), oX = findOdd(M.ft,'X'), o2 = findOdd(M.ft,'2');
    if (!o1 || !oX || !o2) return { error: 'no stats and no 1X2 market found' };
    const q = [1/o1.odds, 1/oX.odds, 1/o2.odds], s = q[0]+q[1]+q[2];
    pH = q[0]/s; pD = q[1]/s; pA = q[2]/s; mode = 'odds-only';
  }

  let totalTarget = NaN, trust = 0, sOver15 = NaN, sBtts = NaN, cH = NaN, cA = NaN, smallSample = false;
  if (S && S.team && S.team.t1) {
    const t1 = S.team.t1, t2 = S.team.t2;
    const mix = x => !x ? NaN : ok(x.ctx) && ok(x.all) ? (x.ctx+x.all)/2 : ok(x.ctx) ? x.ctx : x.all;
    const sH = mean([mix(t1['AVG goals scored']), mix(t2['AVG goals conceded'])]);
    const sA = mean([mix(t2['AVG goals scored']), mix(t1['AVG goals conceded'])]);
    const n = Math.min(...S.mp.filter(ok), 99);
    smallSample = n < 10; trust = n < 99 ? n/(n+10) : 0.5;
    const stat = ok(sH) && ok(sA) ? sH+sA : S.avg.goals;
    const lg = ok(S.avg.leagueGoals) && S.avg.leagueGoals > 1.5 && S.avg.leagueGoals < 4 ? S.avg.leagueGoals : NaN;
    totalTarget = ok(stat) && ok(lg) ? trust*stat + (1-trust)*lg : (ok(stat) ? stat : lg);
    sOver15 = mean([S.avg.over15, t1['over 1.5'] && t1['over 1.5'].ctx, t2['over 1.5'] && t2['over 1.5'].ctx]) / 100;
    sBtts = mean([S.avg.btts, t1['Both teams scored'] && t1['Both teams scored'].ctx,
                  t2['Both teams scored'] && t2['Both teams scored'].ctx]) / 100;
    cH = S.avg.corners[1]; cA = S.avg.corners[2];
  }
  const fit = fitLambdas(pH,pD,pA,totalTarget), lh = fit.lh, la = fit.la, L = lh+la;
  const wS = (1 - cfg.modelWeight) * trust, blend = (m,s) => ok(s) ? (1-wS)*m + wS*s : m;
  const pOver15 = blend(1 - Math.exp(-L)*(1+L), sOver15);
  const pBtts = blend((1-Math.exp(-lh))*(1-Math.exp(-la)), sBtts);
  const haveCorners = ok(cH) && ok(cA);

  const cand = [
    { key:'FT 1',     m:M.ft,   lb:'1',        p:pH,        name:H+' to win' },
    { key:'FT 2',     m:M.ft,   lb:'2',        p:pA,        name:A+' to win' },
    { key:'DC 1X',    m:M.dc,   lb:'1X',       p:pH+pD,     name:H+' or draw' },
    { key:'DC 12',    m:M.dc,   lb:'12',       p:pH+pA,     name:'No draw (12)' },
    { key:'DC X2',    m:M.dc,   lb:'X2',       p:pD+pA,     name:A+' or draw' },
    { key:'1UP 1',    m:M.up,   lb:'1',        p:pOneUp(lh,la,true),  name:H+' 1UP' },
    { key:'1UP 2',    m:M.up,   lb:'2',        p:pOneUp(lh,la,false), name:A+' 1UP' },
    { key:'Over 1.5', m:M.ou,   lb:'Over 1.5', p:pOver15,   name:'Over 1.5 goals' },
    { key:'BTTS Yes', m:M.btts, lb:'Yes',      p:pBtts,     name:'Both teams to score' },
    { key:'BTTS No',  m:M.btts, lb:'No',       p:1-pBtts,   name:'Not both teams score' },
  ];
  if (haveCorners) cand.push(
    { key:'Corners 1', m:M.corn, lb:'1', p:pMoreCorners(cH,cA,true),  name:H+' more corners' },
    { key:'Corners 2', m:M.corn, lb:'2', p:pMoreCorners(cH,cA,false), name:A+' more corners' });

  const missing = [];
  for (const c of cand) {
    const o = findOdd(c.m, c.lb);
    if (!o) { missing.push(c.key); c.odds = NaN; continue; }
    c.odds = o.odds; c.btn = o.btn; c.fair = 1/c.p; c.ev = c.p*c.odds - 1;
  }
  const live = cand.filter(c => ok(c.odds));
  let pool = live.filter(c => c.p >= cfg.minProb && c.odds >= cfg.minOdds);
  if (cfg.requirePositiveEV) pool = pool.filter(c => c.ev > 0);
  if (ok(cfg.maxOdds)) pool = pool.filter(c => c.odds <= cfg.maxOdds);   // room left under the odds target
  pool.sort((a,b) => b.ev - a.ev || b.p - a.p);
  const pick = pool[0] || null;

  document.querySelectorAll('[data-bp-pick]').forEach(e => e.removeAttribute('data-bp-pick'));
  let already = false;
  if (pick) { pick.btn.setAttribute('data-bp-pick','1'); already = pick.btn.getAttribute('aria-pressed') === 'true'; }
  const out = c => ({ key:c.key, name:c.name, p:+c.p.toFixed(3), odds:c.odds, ev:+c.ev.toFixed(3) });
  return { home:H, away:A, mode, smallSample, lh:+lh.toFixed(2), la:+la.toFixed(2),
           probs:[+pH.toFixed(3), +pD.toFixed(3), +pA.toFixed(3)], missing,
           pick: pick ? Object.assign(out(pick), { already }) : null,
           table: live.sort((a,b) => b.ev - a.ev).map(out) };
}
"""

# Collects the hrefs of event cards currently rendered (found via the visible '1X2 | Full Time' label)
COLLECT_JS = """
const out = [];
for (const e of document.body.querySelectorAll('*')) {
  if (e.children.length || e.textContent.trim() !== '1X2 | Full Time') continue;
  const a = e.closest('a[href*="/event/"]'); if (a) out.push(a.getAttribute('href'));
}
return out;
"""

# Scrolls the page and the last card into view so the list loads more matches
SCROLL_JS = """
window.scrollBy(0, 3000);
const cards = document.querySelectorAll('a[href*="/event/"]');
if (cards.length) cards[cards.length - 1].scrollIntoView({block: 'end'});
"""


# ---------------------------------------------------------------------------- helpers
def make_driver():
    opts = Options()
    if HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1280,720")      # desktop layout, even without a screen
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument(f"--user-agent={USER_AGENT}")   # headless Chrome otherwise says "HeadlessChrome"
    opts.page_load_strategy = "eager"                 # don't wait for every image / tracker
    return webdriver.Chrome(options=opts)


def xp(text):
    """XPath for the INNERMOST element whose whole visible text is exactly `text`."""
    return (f'//*[normalize-space(.)="{text}"]'
            f'[not(*[normalize-space(.)="{text}"])]')


def wait_text(driver, text, timeout):
    """Wait until an element with exactly this text exists in the page."""
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xp(text))))


def find_visible(driver, text, timeout):
    """Wait for the first DISPLAYED element with exactly this text."""
    def _find(d):
        for e in d.find_elements(By.XPATH, xp(text)):
            try:
                if e.is_displayed():
                    return e
            except StaleElementReferenceException:
                pass
        return False
    return WebDriverWait(driver, timeout).until(_find)


def js_click(driver, el):
    driver.execute_script("arguments[0].click();", el)


def safe_click(driver, el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    try:
        el.click()
    except (ElementClickInterceptedException, ElementNotInteractableException):
        js_click(driver, el)


def run_analysis(driver, cfg):
    # ANALYSE_JS is an arrow function; call it with the config as its argument
    return driver.execute_script("return (" + ANALYSE_JS + ")(arguments[0]);", cfg)


# ---------------------------------------------------------------------------- bot steps
def collect_event_hrefs(driver):
    """Hrefs of every event card on the list. Scrolls until no new cards appear."""
    seen, last = [], -1
    for _ in range(25):
        for h in driver.execute_script(COLLECT_JS):
            if h not in seen:
                seen.append(h)
        if len(seen) == last:
            break
        last = len(seen)
        driver.execute_script(SCROLL_JS)
        time.sleep(0.8)
    driver.execute_script("window.scrollTo(0, 0);")
    return seen


def wait_event_ready(driver):
    wait_text(driver, "1X2 | Full Time", 20)
    try:                                                 # stats load a bit later than the odds
        wait_text(driver, "Win Probability", 7)
    except TimeoutException:
        try:                                             # maybe the stats panel is collapsed
            safe_click(driver, find_visible(driver, "Statistics", 2))
            wait_text(driver, "Win Probability", 4)
        except TimeoutException:
            pass                                         # analysis falls back to odds-only


def open_card(driver, href):
    """SPA-navigate to the event by clicking its card (keeps the betslip), fall back to get()."""
    link = None
    for _ in range(12):
        found = driver.find_elements(By.CSS_SELECTOR, f'a[href="{href}"]')
        if found:
            link = found[0]
            break
        driver.execute_script(SCROLL_JS)
        time.sleep(0.6)
    if link is None:
        return False
    # click the anchor itself so we never hit an odds button inside the card
    js_click(driver, link)
    try:
        WebDriverWait(driver, 8).until(EC.url_contains("/event/"))
    except TimeoutException:
        driver.get(BASE_URL + href)
    return True


def analyse_and_click(driver, total=1.0):
    cfg = dict(CFG)
    if TARGET_ODDS:
        # biggest odds we can still add without overshooting the target
        cfg["maxOdds"] = TARGET_ODDS * (1 + ODDS_TOLERANCE) / total
    res = run_analysis(driver, cfg)
    res["taken"] = False
    if res.get("error"):
        print("   skip:", res["error"])
        return res
    p = res["pick"]
    print(f"   {res['home']} vs {res['away']}   [{res['mode']}]  exp.goals {res['lh']}-{res['la']}")
    if res["missing"]:
        print("   missing markets:", ", ".join(res["missing"]))
    for r in res["table"][:5]:
        print(f"     {r['key']:<9} p={r['p']*100:4.0f}%  odds={r['odds']:<6}  value={r['ev']*100:+4.0f}%")
    if not p:
        print("   -> no bet passes the filters")
        return res
    print(f"   -> PICK {p['name']} @ {p['odds']}  (p={p['p']*100:.0f}%, value {p['ev']*100:+.0f}%)")
    if p["already"]:
        print("      already in betslip")
    elif CLICK_PICK:
        btn = driver.find_element(By.CSS_SELECTOR, '[data-bp-pick="1"]')
        safe_click(driver, btn)
        time.sleep(0.7)
        print("      clicked")
    res["taken"] = True          # counts toward the total (also in dry-run mode)
    return res


CODE_RE = re.compile(r"\b[A-Z0-9]{5,}\b")
CODE_BUTTON_XPATH = ('//*[normalize-space(text())="Booking Code:"]'
                     '/following-sibling::button[1]')


def dump_debug(driver, name):
    """Save a screenshot and the page HTML so you can see what the bot saw."""
    try:
        driver.save_screenshot(name + ".png")
        with open(name + ".html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"   debug files saved: {name}.png and {name}.html")
    except Exception as e:
        print("   could not save debug files:", repr(e)[:100])


def open_booking_popup(driver):
    """Click 'Booking Code' and wait for the popup. Tries a normal, a JS, then a mouse click."""
    for method in ("normal", "js", "mouse"):
        try:
            trigger = find_visible(driver, "Booking Code", 10)
            if method == "normal":
                safe_click(driver, trigger)
            elif method == "js":
                js_click(driver, trigger)
            else:
                ActionChains(driver).move_to_element(trigger).pause(0.3).click().perform()
            find_visible(driver, "Share your betslip", 6)
            return True
        except (TimeoutException, StaleElementReferenceException):
            print(f"   popup did not open with a {method} click")
    return False


def get_booking_code(driver):
    """Click Booking Code, wait for the popup, then read the code. Returns None if not found."""
    # step 1: the Booking Code control
    try:
        find_visible(driver, "Booking Code", 10)
    except TimeoutException:
        print("Step 1 failed: no visible 'Booking Code' control on the page.")
        dump_debug(driver, "debug_no_trigger")
        return None

    # step 2: click it and wait for the popup
    if not open_booking_popup(driver):
        print("Step 2 failed: the 'Share your betslip' popup never appeared after clicking.")
        dump_debug(driver, "debug_no_popup")
        return None

    # step 3: read the code from the popup (keeps retrying until it is filled in)
    def read_code(d):
        try:
            btn = d.find_element(By.XPATH, CODE_BUTTON_XPATH)
            raw = (btn.text or btn.get_attribute("textContent") or "").strip()
            m = CODE_RE.search(raw)
            if m:
                return m.group(0)
        except (NoSuchElementException, StaleElementReferenceException):
            pass
        body = d.execute_script("return document.body.innerText;") or ""
        m = re.search(r"Booking Code:\s*([A-Z0-9]{5,})", body)
        return m.group(1) if m else False

    try:
        return WebDriverWait(driver, 10).until(read_code)
    except TimeoutException:
        print("Step 3 failed: the popup is open but the code could not be read.")
        dump_debug(driver, "debug_no_code")
        return None


def main():
    results = []
    driver = make_driver()
    try:
        driver.get(LIST_URL)
        wait_text(driver, "1X2 | Full Time", 30)

        hrefs = collect_event_hrefs(driver)
        if MAX_EVENTS:
            hrefs = hrefs[:MAX_EVENTS]
        print(f"{len(hrefs)} events found")

        total = 1.0
        for n, href in enumerate(hrefs, 1):
            # stop conditions
            if TARGET_ODDS:
                if total >= TARGET_ODDS * (1 - ODDS_TOLERANCE):
                    print(f"\nTarget reached: total odds {total:.2f}")
                    break
                if total * CFG["minOdds"] > TARGET_ODDS * (1 + ODDS_TOLERANCE):
                    print(f"\nNo room left for another pick: total odds {total:.2f}")
                    break

            print(f"\n[{n}/{len(hrefs)}] {href}   (total odds so far: {total:.2f})")
            try:
                if not open_card(driver, href):
                    print("   card not found, skipping")
                    continue
                wait_event_ready(driver)
                res = analyse_and_click(driver, total)
                p = (res or {}).get("pick") or {}
                if res.get("taken"):
                    total *= p["odds"]
                    print(f"   total odds now: {total:.2f}")
                results.append({"href": href, "match": f"{res.get('home')} vs {res.get('away')}",
                                "pick": p.get("name", "") if res.get("taken") else "",
                                "odds": p.get("odds", "") if res.get("taken") else "",
                                "prob": p.get("p", ""), "value": p.get("ev", ""),
                                "mode": res.get("mode", ""), "total_odds": round(total, 2)})
            except Exception as e:                       # one bad event must not stop the loop
                print("   error:", repr(e)[:200])
            # back to the list
            try:
                driver.back()
                wait_text(driver, "1X2 | Full Time", 15)
            except TimeoutException:
                driver.get(LIST_URL)
                wait_text(driver, "1X2 | Full Time", 30)

        print(f"\nFinal total odds: {total:.2f}")

        if results:
            if any(r["pick"] for r in results):
                booking_code = get_booking_code(driver)
                if booking_code:
                    print("Booking code:", booking_code)
                    with open("booking_code.txt", "w", encoding="utf-8") as f:
                        f.write(booking_code + "\n")
                else:
                    print("Booking code unavailable.")
            else:
                print("No picks were added, so there is no booking code.")

            with open("picks.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
                w.writeheader()
                w.writerows(results)
            print("saved picks.csv")
    finally:
        if not HEADLESS:
            input("\nDone. Press Enter to close the browser...")
        driver.quit()


if __name__ == "__main__":
    main()
