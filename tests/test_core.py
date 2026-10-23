#!/usr/bin/env python3
"""Qisma headless smoke/regression harness.
usage: qisma_test.py /path/to/qisma.html [--json out.json]
Loads the app offline in headless Chromium with a synthetic dataset, then:
  1. boot check (no page errors)
  2. renders every screen
  3. money-engine invariants over all bookings
  4. new-booking modal behaviour (default status per platform)
  5. save flow through the real UI
"""
import json, sys, re
from playwright.sync_api import sync_playwright

path = sys.argv[1]
out_json = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None

def U(id, name, owner, mgmt, myown, maint=0, rooms=1, fx='off', clean=0, laundry=0, cleanBy='owner', laundryBy='owner',
      mohPct=0, mohBase='mgmt'):
    return dict(id=id, name=name, owner=owner, rooms=rooms, mgmtPct=mgmt, myOwnPct=myown, cleanFee=clean, cleanBy=cleanBy,
                laundryFee=laundry, laundryBy=laundryBy, maintPct=maint, maintBy='owner', suppliesPct=0, suppliesBy='owner',
                fxMode=fx, ownerPhone='', waAuto='off', airbnb='', booking='', gathern='', maps='', notes='',
                mohPct=mohPct, mohBase=mohBase)

units = [
    U('u_homey', 'Homey Inn', 'مالك١', .15, 1.0, fx='mine', clean=25, laundry=25, mohPct=.15, mohBase='mynet'),
    U('u_ostudio', 'Olive Studio', 'مالك٢', 0, .5, maint=.09, fx='shared', clean=25, laundry=25, mohPct=1.0, mohBase='mynet'),
    U('u_oapt', 'Olive Apt', 'مالك٢', .35, 0, maint=.09, fx='shared', clean=50, laundry=30, cleanBy='mgr', mohPct=.5, mohBase='mgmt'),
    U('u_waha', 'Waha Grand', 'مالك٣', .20, 0, fx='off', clean=40, laundry=20, mohPct=.5, mohBase='mgmt'),
    U('u_shiraa', 'أبحر هومز', 'مالك٤', .15, 0, rooms=9, fx='off', mohPct=.5, mohBase='mgmt'),
]

def B(id, unit, plat, ci, co, **kw):
    d = dict(id=id, unitId=unit, apt='', platform=plat, ref='R' + id, checkin=ci, checkout=co, gross='', commission='', net='', fx='',
             clean=0, laundry=0, deposit='', depositKept='', commVat=True, cashBy='', cashWho='', autoNet=True,
             status='مُحصّل', notes='', cxFee=False)
    d.update(kw)
    return d

bookings = [
    B('a1', 'u_homey', 'Airbnb', '2026-09-03', '2026-09-05', net=295.83, clean=25, laundry=25),
    B('a2', 'u_homey', 'Airbnb', '2026-10-07', '2026-10-11', net=488.55, clean=25, laundry=25),
    B('a3', 'u_waha', 'Airbnb', '2026-10-02', '2026-10-03', net=129.84, status='قيد التحصيل'),
    B('b1', 'u_homey', 'Booking', '2026-10-15', '2026-10-20', gross=1200, commission=215.73, net='', clean=25, laundry=25,
      deposit=300, status='قيد التحصيل'),
    B('b2', 'u_oapt', 'Booking', '2026-09-10', '2026-09-13', gross=1990.80, commission=259.67, clean=50, laundry=30),
    B('g1', 'u_ostudio', 'Gathern', '2026-09-20', '2026-09-22', net=400, clean=25, laundry=25),
    B('d1', 'u_oapt', 'مباشر', '2026-08-01', '2026-08-04', net=900, clean=50, laundry=30, cashBy='me'),
    B('c1', 'u_shiraa', 'Airbnb', '2026-09-01', '2026-09-03', net=350, apt='217'),
    B('x1', 'u_homey', 'Airbnb', '2026-08-10', '2026-08-12', net=300, status='ملغي'),
    B('k1', 'u_homey', 'Booking', '2026-09-25', '2026-09-26', gross=0, commission=0, net=120, cxFee=True, payVia='paypal'),
]
batches = [{'id': 'bt1', 'from': '2026-09-01', 'to': '2026-09-15', 'date': '2026-09-16', 'usd': 500, 'sar': 1880.0}]
seed = dict(units=units, bookings=bookings, expenses=[], ownerTx=[], payouts={}, mohPaid={}, transfers={}, commPaid={},
            comm=dict(Airbnb=.17, Booking=.15, Gathern=.33, Google=0, **{'مباشر': 0, 'تمديد': 0, 'تعويض': 0, 'شهري': 0, 'أخرى': .15}),
            target={}, claims=[], batches=batches, partners=[], pagr=[], recurring=[])

res = {'errors': [], 'checks': []}

def check(name, ok, detail=''):
    res['checks'].append(dict(name=name, ok=bool(ok), detail=str(detail)))
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)) if (detail and not ok) else ''))

with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(locale='ar-SA', viewport={'width': 1280, 'height': 900})
    ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file:') else r.abort())
    ctx.add_init_script("try{localStorage.setItem('qisma.v2'," + json.dumps(json.dumps(seed)) + ");}catch(e){}")
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: res['errors'].append('pageerror: ' + str(e)))
    pg.on('console', lambda m: res['errors'].append('console.error: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'net::ERR' not in m.text else None)
    pg.goto('file://' + path)
    pg.wait_for_timeout(800)
    # open the app for testing: pretend signed-in without Firebase
    pg.evaluate("()=>{ try{ authState='in'; render(); }catch(e){ window.__bootErr=String(e); } }")
    pg.wait_for_timeout(300)
    check('boot: no uncaught errors', not [e for e in res['errors'] if e.startswith('pageerror')], res['errors'][:3])
    nb = pg.evaluate("()=>S.bookings.length")
    check('boot: seeded bookings loaded', nb == len(bookings), nb)

    # 2. every screen renders
    views = pg.evaluate("()=>NAVFLAT.map(x=>x[0])")
    for v in views:
        r = pg.evaluate("(v)=>{ try{ view=v; render(); return {ok:true,len:document.body.innerText.length}; }catch(e){ return {ok:false,err:String(e)}; } }", v)
        check('render screen: ' + v, r.get('ok') and r.get('len', 0) > 50, r)
    pg.evaluate("()=>{ view='dash'; render(); }")

    # 3. engine invariants
    inv = pg.evaluate("""()=>{
      const bad=[]; const T=0.011;
      S.bookings.forEach(b=>{ const u=unitById(b.unitId); const r=calc(b,u);
        const sum=r.ownerNet+r.myNet+r.moh+r.costs;
        if(Math.abs(sum-r.base)>T) bad.push({id:b.id,why:'split!=base',sum,base:r.base});
        if([r.base,r.myNet,r.ownerNet,r.moh,r.mgmtFee].some(x=>!isFinite(x))) bad.push({id:b.id,why:'NaN/Inf'});
      });
      return bad; }""")
    check('engine: owner+mine+partners+costs == income for every booking', not inv, inv)
    booking_ok = pg.evaluate("""()=>{ const b=S.bookings.find(x=>x.id==='b2'); return {net:netOf(b), comm:commDue(b)}; }""")
    # gross 1990.80, commission 259.67 + 15% = 298.62 -> net 1692.18
    check('engine: Booking autoNet = gross - commission*1.15', abs(booking_ok['net'] - round(1990.80 - 259.67 * 1.15, 2)) < 0.011, booking_ok)
    # fx for the batch (Homey = mine)
    fxv = pg.evaluate("()=>{ const b=S.bookings.find(x=>x.id==='a1'); return {fx:effFx(b,unitById(b.unitId)), bt:batchFor(b)&&batchFor(b).id}; }")
    check('engine: Airbnb booking inside a withdrawal batch picks it up', fxv['bt'] == 'bt1', fxv)
    issues = pg.evaluate("()=>bookingIssues().map(x=>({id:x.b.id,p:x.p.map(y=>y.lvl+':'+y.msg)}))")
    res['seed_issues'] = issues

    # 4. new-booking modal behaviour
    def open_modal():
        pg.evaluate("()=>{ modal={t:'b',data:Object.assign({},BLANK_B)}; render(); }")
    open_modal()
    st = pg.evaluate("()=>document.querySelector('[data-b=status]').value")
    plat = pg.evaluate("()=>document.querySelector('[data-b=platform]').value")
    res['default_status_airbnb'] = st
    check('new booking: platform defaults to Airbnb', plat == 'Airbnb', plat)
    check('new booking: Airbnb default status = قيد التحصيل', st == 'قيد التحصيل', st)

    pg.select_option('[data-b=platform]', 'Booking')
    pg.wait_for_timeout(100)
    st2 = pg.evaluate("()=>document.querySelector('[data-b=status]').value")
    check('new booking: switching to Booking -> مُحصّل', st2 == 'مُحصّل', st2)
    pg.select_option('[data-b=platform]', 'Airbnb')
    pg.wait_for_timeout(100)
    st3 = pg.evaluate("()=>document.querySelector('[data-b=status]').value")
    check('new booking: switching back to Airbnb -> قيد التحصيل', st3 == 'قيد التحصيل', st3)
    # manual choice must stick
    pg.select_option('[data-b=status]', 'مُحصّل')
    pg.select_option('[data-b=platform]', 'Gathern')
    pg.select_option('[data-b=platform]', 'Airbnb')
    pg.wait_for_timeout(100)
    st4 = pg.evaluate("()=>document.querySelector('[data-b=status]').value")
    check('new booking: manual status choice survives platform changes', st4 == 'مُحصّل', st4)

    # 5. full save through the UI (Airbnb, new)
    open_modal()
    pg.select_option('[data-b=unitId]', 'u_homey')
    pg.wait_for_timeout(100)
    pg.evaluate("()=>{ const d=modal.data; d.checkin='2026-11-01'; d.checkout='2026-11-03'; render(); }")
    pg.fill('[data-b=net]', '230.09')
    pg.evaluate("()=>{ readModal(); ui.advB=true; render(); }")
    pg.fill('[data-b=ref]', 'TESTAIR001')
    before = pg.evaluate("()=>S.bookings.length")
    pg.click('[data-act=saveM]')
    pg.wait_for_timeout(300)
    saved = pg.evaluate("()=>S.bookings.filter(b=>b.ref==='TESTAIR001')")
    check('save: new Airbnb booking saved via UI', len(saved) == 1, saved)
    if saved:
        s = saved[0]
        check('save: saved Airbnb booking status = قيد التحصيل (untouched default)', s['status'] == 'قيد التحصيل', s['status'])
        check('save: net stored as number 230.09', abs(float(s['net']) - 230.09) < 1e-9, s['net'])
        check('save: unit cleaning/laundry prefilled from unit', s['clean'] == 25 and s['laundry'] == 25, (s['clean'], s['laundry']))
    check('save: booking count +1', pg.evaluate("()=>S.bookings.length") == before + 1)

    # editing an old booking must not change its status
    pg.evaluate("()=>{ const b=S.bookings.find(x=>x.id==='a2'); modal={t:'b',data:Object.assign({},b)}; render(); }")
    es = pg.evaluate("()=>document.querySelector('[data-b=status]').value")
    check('edit: old Airbnb booking keeps its مُحصّل status in the form', es == 'مُحصّل', es)
    pg.evaluate("()=>{ modal=null; render(); }")

    # missing booking ref for Airbnb is blocked
    open_modal()
    pg.select_option('[data-b=unitId]', 'u_homey')
    pg.evaluate("()=>{ const d=modal.data; d.checkin='2026-11-10'; d.checkout='2026-11-12'; render(); }")
    pg.fill('[data-b=net]', '100')
    b0 = pg.evaluate("()=>S.bookings.length")
    pg.click('[data-act=saveM]')
    pg.wait_for_timeout(200)
    check('save: Airbnb without booking ref is refused', pg.evaluate("()=>S.bookings.length") == b0)
    pg.evaluate("()=>{ modal=null; render(); }")

    # aging alert
    al = pg.evaluate("""()=>{ const t=today(); return agingLists().recv.map(x=>x.b.id); }""")
    res['aging_recv_ids'] = al

    # ---- refused save must be visible, must reveal the hidden ref field, and must not lose typing ----
    open_modal()
    pg.select_option('[data-b=unitId]', 'u_homey')
    pg.evaluate("()=>{ const d=modal.data; d.checkin='2026-12-01'; d.checkout='2026-12-03'; render(); }")
    pg.fill('[data-b=net]', '230.09')
    pg.click('[data-act=saveM]')           # no ref -> refused
    pg.wait_for_timeout(250)
    vis = pg.evaluate("""()=>{ const m=document.querySelector('.modal #mmsg'); return {text:m?m.textContent:null, open:!!modal,
       refExists:!!document.querySelector('[data-b=ref]'), focused:document.activeElement&&document.activeElement.dataset&&document.activeElement.dataset.b,
       net:document.querySelector('[data-b=net]')?document.querySelector('[data-b=net]').value:null}; }""")
    check('refused save: message is shown INSIDE the modal', vis['text'] and 'رقم الحجز' in vis['text'], vis)
    check('refused save: hidden booking-ref field is opened and focused', vis['refExists'] and vis['focused'] == 'ref', vis)
    check('refused save: already-typed net is kept', vis['net'] == '230.09', vis)
    # typing after the message + a background re-render must not wipe anything
    pg.fill('[data-b=ref]', 'KEEPME1')
    pg.fill('[data-b=notes]', 'ملاحظة تجريبية')
    pg.evaluate("()=>{ render(); }")       # what a cloud snapshot / timer does
    kept = pg.evaluate("()=>({ref:document.querySelector('[data-b=ref]').value, notes:document.querySelector('[data-b=notes]').value, net:document.querySelector('[data-b=net]').value})")
    check('background re-render keeps typed ref/notes/net', kept == {'ref': 'KEEPME1', 'notes': 'ملاحظة تجريبية', 'net': '230.09'}, kept)
    pg.wait_for_timeout(5300)              # the message auto-clears after 5s
    after = pg.evaluate("()=>({open:!!modal, ref:(document.querySelector('[data-b=ref]')||{}).value, msgGone:!document.getElementById('mmsg')})")
    check('message auto-clear does not re-render/wipe the open modal', after['open'] and after['ref'] == 'KEEPME1' and after['msgGone'], after)
    pg.click('[data-act=saveM]')
    pg.wait_for_timeout(250)
    check('after fixing the ref the booking saves', pg.evaluate("()=>S.bookings.some(b=>b.ref==='KEEPME1')"))
    pg.evaluate("()=>{ modal=null; render(); }")

    # aging alert rules (relative dates so the test never goes stale)
    ag = pg.evaluate("""()=>{
      const t=today(); const mk=(id,plat,coDaysAgo,extra)=>Object.assign({id:id,unitId:'u_waha',apt:'',platform:plat,ref:'T'+id,
        checkin:addD(t,-coDaysAgo-2),checkout:addD(t,-coDaysAgo),gross:'',commission:'',net:100,fx:'',clean:0,laundry:0,deposit:'',
        depositKept:'',commVat:true,cashBy:'',cashWho:'',autoNet:true,status:'قيد التحصيل',notes:'',cxFee:false},extra||{});
      const saveB=S.bookings, saveBt=S.batches;
      S.bookings=[ mk('p20','Airbnb',20), mk('p40','Airbnb',40), mk('g20','Gathern',20), mk('g5','Gathern',5),
                   mk('pcov','Airbnb',60) ];
      // a withdrawal batch that covers pcov's check-in
      S.batches=[{id:'btx',from:addD(t,-64),to:addD(t,-58),date:addD(t,-50),usd:50,sar:190}];
      clearCaches();
      const ids=agingLists().recv.map(x=>x.b.id).sort();
      S.bookings=saveB; S.batches=saveBt; clearCaches();
      return ids; }""")
    check('aging: Airbnb 20d old, no withdrawal yet -> NOT flagged', 'p20' not in ag, ag)
    check('aging: Airbnb 40d old, no withdrawal -> flagged', 'p40' in ag, ag)
    check('aging: Airbnb 60d old but covered by a PayPal withdrawal -> NOT flagged', 'pcov' not in ag, ag)
    check('aging: non-PayPal (Gathern) 20d old -> still flagged (14d rule unchanged)', 'g20' in ag, ag)
    check('aging: non-PayPal 5d old -> not flagged', 'g5' not in ag, ag)

    fatal = [e for e in res['errors'] if e.startswith('pageerror')]
    check('no uncaught page errors during the whole run', not fatal, fatal[:3])
    br.close()

res['pass'] = sum(1 for c in res['checks'] if c['ok'])
res['fail'] = sum(1 for c in res['checks'] if not c['ok'])
print('\nSUMMARY: %d pass, %d fail' % (res['pass'], res['fail']))
print('seed issues:', json.dumps(res.get('seed_issues'), ensure_ascii=False))
print('default status airbnb:', res.get('default_status_airbnb'), '| aging recv:', res.get('aging_recv_ids'))
if res['errors']:
    print('console/page errors:', res['errors'][:8])
if out_json:
    json.dump(res, open(out_json, 'w'), ensure_ascii=False, indent=1)
sys.exit(1 if res['fail'] else 0)
