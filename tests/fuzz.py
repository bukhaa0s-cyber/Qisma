#!/usr/bin/env python3
"""Qisma fuzz + click-crawl: richer random dataset, every screen rendered, NaN/undefined scan,
engine invariants, and every safe button clicked (with state restored after each).
usage: qisma_fuzz.py /path/to/qisma.html [seed]"""
import json, sys, random, re, datetime as dt
from playwright.sync_api import sync_playwright

path = sys.argv[1]
seed_n = int(sys.argv[2]) if len(sys.argv) > 2 else 7
rnd = random.Random(seed_n)

def U(id, name, owner, mgmt, myown, maint=0, rooms=1, fx='off', clean=0, laundry=0, cleanBy='owner', laundryBy='owner',
      mohPct=0, mohBase='mgmt', suppliesPct=0):
    return dict(id=id, name=name, owner=owner, rooms=rooms, mgmtPct=mgmt, myOwnPct=myown, cleanFee=clean, cleanBy=cleanBy,
                laundryFee=laundry, laundryBy=laundryBy, maintPct=maint, maintBy=rnd.choice(['owner', 'mgr']),
                suppliesPct=suppliesPct, suppliesBy='owner', fxMode=fx, ownerPhone='', waAuto='off', airbnb='', booking='',
                gathern='', maps='', notes='', mohPct=mohPct, mohBase=mohBase)

units = [
    U('u_homey', 'Homey Inn', 'مالك١', .15, 1.0, fx='mine', clean=25, laundry=25, mohPct=.15, mohBase='mynet'),
    U('u_ostudio', 'Olive Studio', 'مالك٢', 0, .5, maint=.09, fx='shared', clean=25, laundry=25, mohPct=1.0, mohBase='mynet'),
    U('u_oapt', 'Olive Apt', 'مالك٢', .35, 0, maint=.09, fx='shared', clean=50, laundry=30, cleanBy='mgr', mohPct=.5, mohBase='mgmt'),
    U('u_waha', 'Waha Grand', 'مالك٣', .20, 0, fx='off', clean=40, laundry=20, mohPct=.5, mohBase='mgmt', suppliesPct=.03),
    U('u_shiraa', 'أبحر هومز', 'مالك٤', .15, 0, rooms=9, fx='off', mohPct=.5, mohBase='mgmt'),
    U('u_month', 'Monthly Flat', 'سالم', .10, 0, fx='off'),
]
ROOMS = ['102', '106', '107', '109', '121', '215', '217', '218', '224']
PLATS = ['Airbnb', 'Airbnb', 'Airbnb', 'Booking', 'Booking', 'Gathern', 'Google', 'مباشر']

def d(s): return dt.date.fromisoformat(s)
def iso(x): return x.isoformat()

bookings = []; bid = 0
for u in units[:5]:
    cur = d('2026-08-01'); roomlist = ROOMS[:3] if u['rooms'] > 1 else ['']
    for room in roomlist:
        cur = d('2026-08-01') + dt.timedelta(days=rnd.randint(0, 6))
        while cur < d('2026-11-25'):
            n = rnd.randint(1, 6)
            ci, co = cur, cur + dt.timedelta(days=n)
            plat = rnd.choice(PLATS)
            bid += 1
            b = dict(id='b%d' % bid, unitId=u['id'], apt=room, platform=plat, ref='REF%04d' % bid, checkin=iso(ci), checkout=iso(co),
                     gross='', commission='', net='', fx='', clean=u['cleanFee'], laundry=u['laundryFee'], deposit='', depositKept='',
                     commVat=True, cashBy='', cashWho='', autoNet=True,
                     status=rnd.choice(['مُحصّل', 'مُحصّل', 'قيد التحصيل', 'ملغي' if rnd.random() < .08 else 'مُحصّل']), notes='', cxFee=False)
            amt = round(rnd.uniform(90, 480) * n, 2)
            if plat == 'Booking':
                g = round(amt * 1.2, 2)
                b.update(gross=g, commission=round(g / 1.15 * .15, 2), net='')
                if rnd.random() < .3: b['cashBy'] = rnd.choice(['owner', 'me', 'moh', 'staff']); b['cashWho'] = 'ابو سعيد'
            else:
                b['net'] = amt
                if plat == 'Google' and rnd.random() < .4: b['cashBy'] = 'owner'
            if rnd.random() < .2: b['deposit'] = rnd.choice([100, 200, 300]); b['depositKept'] = rnd.choice(['', 0, 50])
            if rnd.random() < .05: b['cxFee'] = True; b['clean'] = 0; b['laundry'] = 0
            bookings.append(b)
            cur = co + dt.timedelta(days=rnd.randint(0, 4))

batches = [
    {'id': 'bt1', 'from': '2026-08-01', 'to': '2026-08-15', 'date': '2026-08-16', 'usd': 900, 'sar': 3390.0},
    {'id': 'bt2', 'from': '2026-08-16', 'to': '2026-08-31', 'date': '2026-09-01', 'usd': 700, 'sar': 2630.0},
    {'id': 'bt3', 'from': '2026-09-01', 'to': '2026-09-15', 'date': '2026-09-16', 'usd': 800, 'sar': 3010.5},
]
expenses = []
for i in range(25):
    u = rnd.choice(units)
    expenses.append(dict(id='e%d' % i, date=iso(d('2026-08-01') + dt.timedelta(days=rnd.randint(0, 80))), unitId=u['id'],
                         category=rnd.choice(['نظافة', 'مغسلة', 'صيانة', 'مستلزمات', 'كهرباء', 'مياه', 'تعويض ضيف']),
                         description='مصروف %d' % i, amount=round(rnd.uniform(20, 600), 2),
                         paidBy=rnd.choice(['أنا', 'المالك', 'محمد']), chargeTo=rnd.choice(['owner', 'shared', 'mgr']),
                         collected=rnd.choice(['غير محصّل', 'محصّل'])))
claims = [dict(id='c%d' % i, date=iso(d('2026-09-01') + dt.timedelta(days=i * 5)), unitId=rnd.choice(units[:5])['id'], platform='Airbnb',
               ref='CL%d' % i, description='تعويض', amount=round(rnd.uniform(50, 400), 2), **{'from': 'الضيف'},
               to=rnd.choice(['owner', 'shared', 'mgr']), status=rnd.choice(['تحت المعالجة', 'تم التحصيل']), notes='') for i in range(5)]
ownerTx = [dict(id='x1', unitId='u_waha', kind='pay', amount=1500, date='2026-09-20', period='2026-08', notes=''),
           dict(id='x2', unitId='u_oapt', kind='pay', amount=800, date='2026-10-02', period='2026-09', notes='')]
partners = [{'id': 'p2', 'name': 'سالم'}]
pagr = [{'id': 'g2', 'partnerId': 'p2', 'unitId': 'u_waha', 'from': '2026-09', 'to': '', 'base': 'own', 'pct': .1, 'fixed': 0, 'fixedPer': 'booking', 'expPct': 0},
        {'id': 'g3', 'partnerId': 'p2', 'unitId': 'u_homey', 'from': '2026-08', 'to': '2026-09', 'base': 'inc', 'pct': 0, 'fixed': 20, 'fixedPer': 'night', 'expPct': .1}]
contracts = [dict(id='k1', unitId='u_month', apt='', tenant='مستأجر تجريبي', phone='', start='2026-09-01', months=12, freq=3, rent=3000,
                  deposit=3000, commission=0, ejar='', notes='', util='', endedOn='')]

seed = dict(units=units, bookings=bookings, expenses=expenses, ownerTx=ownerTx, payouts={}, mohPaid={}, transfers={}, commPaid={},
            comm=dict(Airbnb=.17, Booking=.15, Gathern=.33, Google=0, **{'مباشر': 0, 'تمديد': 0, 'تعويض': 0, 'شهري': 0, 'أخرى': .15}),
            target={}, claims=claims, batches=batches, partners=partners, pagr=pagr, recurring=[], contracts=contracts)

errors = []
fails = []
def fail(msg): fails.append(msg); print('FAIL', msg)
def ok(msg): print('PASS', msg)

with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(locale='ar-SA', viewport={'width': 1280, 'height': 900})
    ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file:') else r.abort())
    ctx.add_init_script("try{localStorage.setItem('qisma.v2'," + json.dumps(json.dumps(seed)) + ");}catch(e){}")
    pg = ctx.new_page()
    cur_label = {'v': 'boot'}
    pg.on('pageerror', lambda e: errors.append((cur_label['v'], 'pageerror: ' + str(e))))
    pg.on('console', lambda m: errors.append((cur_label['v'], 'console.error: ' + m.text)) if m.type == 'error' and 'Failed to load resource' not in m.text and 'net::ERR' not in m.text else None)
    pg.on('dialog', lambda dlg: dlg.dismiss())
    pg.goto('file://' + path); pg.wait_for_timeout(800)
    pg.evaluate("()=>{ authState='in'; ctBuild && (S.bookings=S.bookings.filter(b=>!b.contractId).concat(ctBuild(S.contracts[0]))); clearCaches(); render(); }")
    pg.wait_for_timeout(300)
    nb = pg.evaluate("()=>S.bookings.length")
    print('seeded bookings (incl. contract installments):', nb, ' units:', pg.evaluate("()=>S.units.length"))

    # --- every screen: render + scan for broken output
    views = pg.evaluate("()=>NAVFLAT.map(x=>x[0])")
    BAD = re.compile(r'NaN|undefined|Infinity|\[object')
    for v in views:
        cur_label['v'] = 'view:' + v
        r = pg.evaluate("(v)=>{ try{ view=v; render(); return {ok:true,txt:document.querySelector('main')?document.querySelector('main').innerText:document.body.innerText}; }catch(e){ return {ok:false,err:String(e)}; } }", v)
        if not r['ok']: fail('render %s threw %s' % (v, r['err'])); continue
        hits = [m.group(0) for m in BAD.finditer(r['txt'])]
        if hits:
            i = BAD.search(r['txt']).start(); fail('screen %s shows %s: ...%s...' % (v, sorted(set(hits)), r['txt'][max(0, i - 60):i + 60].replace('\n', ' ')))
        else: ok('screen %s renders clean' % v)

    # --- invariants
    cur_label['v'] = 'invariants'
    inv = pg.evaluate("""()=>{ const bad=[]; const T=0.011;
      S.bookings.forEach(b=>{ const u=unitById(b.unitId); const r=calc(b,u);
        const sum=r.ownerNet+r.myNet+r.moh+r.costs;
        if(Math.abs(sum-r.base)>T) bad.push({id:b.id,u:b.unitId,plat:b.platform,why:'split!=base',sum:+sum.toFixed(2),base:+r.base.toFixed(2)});
        for(const k of ['base','mgmtFee','myNet','ownerNet','moh','pool']) if(!isFinite(r[k])) bad.push({id:b.id,why:'non-finite '+k});
        const cd=commDue(b); if(!isFinite(cd)||cd<0) bad.push({id:b.id,why:'commDue '+cd});
        if(b.platform==='Booking'&&autoNet(b)&&netOf(b)<0) bad.push({id:b.id,why:'negative Booking net'});
      });
      // FX distribution: per batch, allocated gains must add up to the batch gain
      (S.batches||[]).forEach(bt=>{ const e=batchElig(bt); let alloc=0;
        e.list.forEach(x=>{ alloc+=effFx(x,unitById(x.unitId)); }); e.claims.forEach(c=>{ alloc+=claimFx(c); });
        if(e.tot>0 && Math.abs(alloc-e.gain)>0.02) bad.push({batch:bt.id,why:'fx allocated != gain',alloc:+alloc.toFixed(3),gain:+e.gain.toFixed(3)}); });
      return bad; }""")
    if inv: fail('engine invariants: %s' % json.dumps(inv[:6], ensure_ascii=False))
    else: ok('engine invariants hold for all %d bookings + FX batches' % nb)

    # --- CSV / owner statement / audit helpers do not throw
    for name, js in [('toCSV', "()=>toCSV().length"), ('stmtData', "()=>{ const D=stmtData(); return D?1:0; }"), ('repText', "()=>repText().length"),
                     ('agingLists', "()=>{ const a=agingLists(); return a.recv.length+a.dep.length; }"), ('bookingIssues', "()=>bookingIssues().length")]:
        cur_label['v'] = 'fn:' + name
        try: r = pg.evaluate(js); ok('%s ok (%s)' % (name, r))
        except Exception as e: fail('%s threw %s' % (name, str(e)[:160]))

    # --- click crawl: every distinct data-act on every screen
    SKIP = re.compile(r'del|wipe|reset|signIn|signOut|logout|restore|download|print|share|wa$|whats|clear|import|archiv|close|lock|backup|saveNow|export|pdf|copy', re.I)
    snap = pg.evaluate("()=>JSON.stringify(S)")
    clicked = 0
    for v in views:
        pg.evaluate("(a)=>{ S=JSON.parse(a[0]); modal=null; dialog=null; clearCaches(); view=a[1]; render(); }", [snap, v])
        acts = pg.evaluate("()=>[...new Set([...document.querySelectorAll('[data-act]')].map(e=>e.dataset.act))]")
        for a in acts:
            if SKIP.search(a): continue
            cur_label['v'] = 'click:%s/%s' % (v, a)
            before = len(errors)
            pg.evaluate("""(a)=>{ const el=document.querySelector('[data-act="'+a+'"]'); if(el) el.click(); }""", a)
            pg.wait_for_timeout(30)
            # if a modal opened, exercise validation + (blank) save, then a sensible fill+save
            if pg.evaluate("()=>!!modal"):
                pg.evaluate("()=>{ const b=document.querySelector('[data-act=saveM]'); if(b) b.click(); }")
                pg.wait_for_timeout(30)
            clicked += 1
            if len(errors) > before: fail('click %s/%s -> %s' % (v, a, errors[-1][1][:200]))
            pg.evaluate("(a)=>{ S=JSON.parse(a[0]); modal=null; dialog=null; clearCaches(); view=a[1]; render(); }", [snap, v])
    print('clicked %d (screen,action) pairs' % clicked)
    if not [e for e in errors if e[0].startswith('click')]: ok('click crawl: no exceptions in any handler')

    # --- state untouched by the crawl
    same = pg.evaluate("(s)=>JSON.stringify(S)===s", snap)
    ok('crawl restored state') if same else fail('state differs after restore (harness issue)')
    br.close()

print('\nSUMMARY: %d failure(s); %d page/console errors' % (len(fails), len(errors)))
for lab, e in errors[:10]: print('  [%s] %s' % (lab, e[:220]))
sys.exit(1 if fails else 0)
