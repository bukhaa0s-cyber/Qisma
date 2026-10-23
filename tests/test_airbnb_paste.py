#!/usr/bin/env python3
"""Paste-Airbnb-email + visible booking-ref tests. usage: qisma_test3.py qisma.html fixtures_dir"""
import json, sys, os
from playwright.sync_api import sync_playwright
path, fx = sys.argv[1], sys.argv[2]
res = []
def check(name, ok, detail=''):
    res.append(ok); print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)[:500]) if not ok else ''))

def U(id, name, airbnb='', clean=0, laundry=0):
    return dict(id=id, name=name, owner='x', rooms=1, mgmtPct=.15, myOwnPct=1, cleanFee=clean, cleanBy='owner', laundryFee=laundry,
                laundryBy='owner', maintPct=0, maintBy='owner', suppliesPct=0, suppliesBy='owner', fxMode='off', ownerPhone='',
                waAuto='off', airbnb=airbnb, booking='', gathern='', maps='', notes='')
units = [U('u_homey', 'Homey Inn', clean=25, laundry=25), U('u_shiraa', "Al Shira'a"), U('u_fam', 'Olive Apt', airbnb='https://www.airbnb.com/rooms/222222222222222222')]
old = [dict(id='o1', unitId='u_homey', apt='', platform='Airbnb', ref='HMOLD00001', checkin='2026-10-01', checkout='2026-10-03', gross='', commission='',
            net=200, fx='', clean=25, laundry=25, deposit='', depositKept='', commVat=True, cashBy='', cashWho='', autoNet=True, status='مُحصّل', notes='', cxFee=False)]
seed = dict(units=units, bookings=old, expenses=[], ownerTx=[], payouts={}, mohPaid={}, transfers={}, commPaid={},
            comm=dict(Airbnb=.17, Booking=.15, Gathern=.33), target={}, claims=[], batches=[], partners=[], pagr=[], recurring=[], closes={})
T = {k: open(os.path.join(fx, k + '.txt'), encoding='utf-8').read() for k in ('e1', 'e2', 'e3')}
errs = []
with sync_playwright() as p:
    br = p.chromium.launch(); ctx = br.new_context(locale='ar-SA', viewport={'width': 1280, 'height': 900})
    ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file:') else r.abort())
    ctx.add_init_script("try{localStorage.setItem('qisma.v2'," + json.dumps(json.dumps(seed)) + ");}catch(e){}")
    pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('file://' + path); pg.wait_for_timeout(700); pg.evaluate("()=>{ authState='in'; render(); auditReset(); }")
    P = lambda k: pg.evaluate("(t)=>parseAirbnbEmail(t,S.units,'2026-10-23')", T[k])
    r1 = P('e1')
    check('e1 (raw email): ref/dates/net/unit/notes', r1['ref'] == 'HMTEST0001' and r1['checkin'] == '2026-10-23' and r1['checkout'] == '2026-10-25'
          and r1['net'] == 230.09 and r1['unitId'] == 'u_homey' and r1['guests'] == '2 بالغين + رضيع' and r1['guest'] == 'ضيف تجريبي' and not r1['miss'], r1)
    r2 = P('e2')
    check('e2 (Gmail copy, mixed case, tabs): ref/dates/net + Abhur unit + apt 217', r2['ref'] == 'HMTEST0002' and r2['checkin'] == '2026-09-01'
          and r2['checkout'] == '2026-09-02' and r2['net'] == 124.91 and r2['unitId'] == 'u_shiraa' and r2['apt'] == '217', r2)
    r3 = P('e3')
    check('e3: year rollover Dec->Jan + thousands separator + unknown listing -> unit missing', r3['checkin'] == '2026-12-30' and r3['checkout'] == '2027-01-02'
          and r3['net'] == 1457.35 and r3['unitId'] == '' and 'الوحدة' in r3['miss'] and r3['guests'] == '2 بالغين + 2 أطفال', r3)
    r4 = pg.evaluate("()=>parseAirbnbEmail('hello world',S.units,'2026-10-23')")
    check('garbage text -> nothing filled', not r4['ref'] and not r4['checkin'] and r4['net'] == '', r4)
    r5 = pg.evaluate("(t)=>parseAirbnbEmail(t,S.units,'2026-10-23')", T['e1'].replace('230.09', '٢٣٠٫٠٩').replace('Oct 25', 'Oct ٢٥'))
    check('Arabic-Indic digits in dates are understood', r5['checkout'] == '2026-10-25', r5)

    # ---- UI: ref visible up-front for Airbnb / Booking, in "extra" for others ----
    pg.evaluate("()=>{ ui.advB=false; modal={t:'b',data:Object.assign({},BLANK_B)}; render(); }")
    check('Airbnb: ref field visible without opening extra options', pg.evaluate("()=>!!document.querySelector('[data-b=ref]')"))
    pg.select_option('[data-b=platform]', 'Booking'); pg.wait_for_timeout(80)
    check('Booking: ref field visible', pg.evaluate("()=>!!document.querySelector('[data-b=ref]')"))
    pg.select_option('[data-b=platform]', 'Gathern'); pg.wait_for_timeout(80)
    check('Gathern: ref stays inside extra options (optional)', pg.evaluate("()=>!document.querySelector('[data-b=ref]')"))
    pg.evaluate("()=>{ ui.advB=true; render(); }")
    check('Gathern + extra open: one ref field', pg.evaluate("()=>document.querySelectorAll('[data-b=ref]').length") == 1)
    pg.evaluate("()=>{ ui.advB=true; modal={t:'b',data:Object.assign({},BLANK_B)}; render(); }")
    check('Airbnb + extra open: still exactly one ref field (no duplicate)', pg.evaluate("()=>document.querySelectorAll('[data-b=ref]').length") == 1)
    pg.evaluate("()=>{ ui.advB=false; modal=null; render(); }")

    # ---- UI: paste flow end-to-end, nothing saved until Save ----
    before = pg.evaluate("()=>JSON.parse(JSON.stringify(S.bookings))")
    pg.evaluate("()=>{ ui.advB=false; ui.pasteB=false; modal={t:'b',data:Object.assign({},BLANK_B)}; render(); }")
    pg.click('[data-act=pasteTog]'); pg.wait_for_timeout(80)
    pg.fill('#pasteTxt', T['e1'])
    pg.evaluate("()=>render()")  # background re-render must keep pasted text
    check('pasted text survives a background re-render', pg.evaluate("()=>document.getElementById('pasteTxt').value.length") > 100)
    pg.click('[data-act=pasteFill]'); pg.wait_for_timeout(150)
    d = pg.evaluate("()=>({d:modal.data, ref:document.querySelector('[data-b=ref]').value, net:document.querySelector('[data-b=net]').value, n:S.bookings.length})")
    check('form filled from email (unit, dates, net, ref, cleaning from unit, status)', d['d']['unitId'] == 'u_homey' and d['d']['checkin'] == '2026-10-23'
          and d['ref'] == 'HMTEST0001' and d['net'] == '230.09' and d['d']['clean'] == 25 and d['d']['status'] == 'قيد التحصيل', d)
    check('filling does NOT save anything', d['n'] == len(before) and pg.evaluate("()=>JSON.parse(JSON.stringify(S.bookings))") == before)
    pg.click('[data-act=saveM]'); pg.wait_for_timeout(250)
    after = pg.evaluate("()=>JSON.parse(JSON.stringify(S.bookings))")
    nb = [b for b in after if b['ref'] == 'HMTEST0001']
    check('saved once after pressing Save', len(nb) == 1 and len(after) == len(before) + 1, nb)
    check('existing booking untouched', [b for b in after if b['id'] == 'o1'] == before)
    if nb:
        check('saved values', nb[0]['net'] == 230.09 and nb[0]['checkout'] == '2026-10-25' and 'رضيع' in nb[0]['notes'], nb[0])
    learned = pg.evaluate("()=>JSON.parse(localStorage.getItem('qisma.abTitles')||'{}')")
    check('listing title learned -> unit on this device', learned.get('cozy retreat with a private entrance') == 'u_homey', learned)
    # pasting the same email again -> duplicate-ref dialog, not a silent double
    pg.evaluate("()=>{ modal={t:'b',data:Object.assign({},BLANK_B)}; ui.pasteB=true; ui.pasteTxt=''; render(); }")
    pg.fill('#pasteTxt', T['e1']); pg.click('[data-act=pasteFill]'); pg.wait_for_timeout(100)
    pg.click('[data-act=saveM]'); pg.wait_for_timeout(200)
    check('same email twice -> duplicate warning, still one booking', pg.evaluate("()=>!!dialog && S.bookings.filter(b=>b.ref==='HMTEST0001').length===1"))
    check('no page errors', not errs, errs[:3])
    br.close()
print('\nSUMMARY: %d pass, %d fail' % (sum(res), len(res) - sum(res)))
sys.exit(0 if all(res) else 1)
