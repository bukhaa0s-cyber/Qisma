#!/usr/bin/env python3
"""Tests for: (1) PayPal batch save flips status only, (2) closed-month refusal keeps the modal & data.
usage: qisma_test2.py /path/to/qisma.html
"""
import json, sys, copy
from playwright.sync_api import sync_playwright

path = sys.argv[1]

def U(id, name, owner, mgmt, myown, maint=0, rooms=1, fx='off', clean=0, laundry=0, cleanBy='owner', laundryBy='owner',
      mohPct=0, mohBase='mgmt', wa='off', phone=''):
    return dict(id=id, name=name, owner=owner, rooms=rooms, mgmtPct=mgmt, myOwnPct=myown, cleanFee=clean, cleanBy=cleanBy,
                laundryFee=laundry, laundryBy=laundryBy, maintPct=maint, maintBy='owner', suppliesPct=0, suppliesBy='owner',
                fxMode=fx, ownerPhone=phone, waAuto=wa, airbnb='', booking='', gathern='', maps='', notes='',
                mohPct=mohPct, mohBase=mohBase)

units = [
    U('u_homey', 'Homey Inn', 'مالك١', .15, 1.0, fx='mine', clean=25, laundry=25, mohPct=.15, mohBase='mynet', wa='on', phone='966500000000'),
    U('u_oapt', 'Olive Apt', 'مالك٢', .35, 0, maint=.09, fx='shared', clean=50, laundry=30, cleanBy='mgr', mohPct=.5, mohBase='mgmt'),
    U('u_waha', 'Waha Grand', 'مالك٣', .20, 0, fx='off', clean=40, laundry=20, mohPct=.5, mohBase='mgmt'),
]

def B(id, unit, plat, ci, co, **kw):
    d = dict(id=id, unitId=unit, apt='', platform=plat, ref='R' + id, checkin=ci, checkout=co, gross='', commission='', net=100, fx='',
             clean=0, laundry=0, deposit='', depositKept='', commVat=True, cashBy='', cashWho='', autoNet=True,
             status='قيد التحصيل', notes='ملاحظة ' + id, cxFee=False, zzz='extra-' + id)
    d.update(kw)
    return d

PEND = 'قيد التحصيل'; DONE = 'مُحصّل'; CANC = 'ملغي'
bookings = [
    B('f_in1',        'u_homey', 'Airbnb',  '2026-09-03', '2026-09-05', net=295.83, clean=25, laundry=25, deposit=100),   # flips
    B('f_edge_from',  'u_waha',  'Airbnb',  '2026-09-01', '2026-09-02', net=129.84),                                    # flips (boundary)
    B('f_edge_to',    'u_oapt',  'Airbnb',  '2026-09-15', '2026-09-17', net=410.5, clean=50, laundry=30),              # flips (boundary)
    B('f_pp_booking', 'u_homey', 'Booking', '2026-09-10', '2026-09-11', net=120, cxFee=True, payVia='paypal'),          # flips (PayPal)
    B('s_before',     'u_homey', 'Airbnb',  '2026-08-31', '2026-09-02', net=210),                                       # stays
    B('s_after',      'u_homey', 'Airbnb',  '2026-09-16', '2026-09-18', net=220),                                       # stays
    B('s_gathern',    'u_oapt',  'Gathern', '2026-09-05', '2026-09-06', net=300, clean=50, laundry=30),                 # stays (not PayPal)
    B('s_booking',    'u_homey', 'Booking', '2026-09-06', '2026-09-08', gross=900, commission=100, net=''),             # stays (not PayPal)
    B('s_cancel',     'u_homey', 'Airbnb',  '2026-09-07', '2026-09-08', net=150, status=CANC),                          # stays
    B('s_paid',       'u_homey', 'Airbnb',  '2026-09-08', '2026-09-09', net=160, status=DONE),                          # stays
    B('s_contract',   'u_oapt',  'Airbnb',  '2026-09-09', '2026-09-10', net=500, contractId='ct1'),                     # stays (contract guard)
    B('o_oct',        'u_homey', 'Airbnb',  '2026-10-07', '2026-10-11', net=488.55, status=DONE),                       # unrelated
]
seed = dict(units=units, bookings=bookings, expenses=[], ownerTx=[], payouts={}, mohPaid={}, transfers={}, commPaid={},
            comm=dict(Airbnb=.17, Booking=.15, Gathern=.33, Google=0, **{'مباشر': 0, 'تمديد': 0, 'تعويض': 0, 'شهري': 0, 'أخرى': .15}),
            target={}, claims=[], batches=[], partners=[], pagr=[], recurring=[], closes={})

EXPECT_FLIP = {'f_in1', 'f_edge_from', 'f_edge_to', 'f_pp_booking'}
res = {'errors': [], 'checks': []}

def check(name, ok, detail=''):
    res['checks'].append(dict(name=name, ok=bool(ok), detail=str(detail)))
    print(('PASS ' if ok else 'FAIL ') + name + (('  -> ' + str(detail)[:600]) if (detail and not ok) else ''))

CALC_ALL = """()=>{ clearCaches(); const ids=S.bookings.map(b=>b.id).sort();
  const per=S.bookings.slice().sort((a,b)=>a.id<b.id?-1:1).map(b=>[b.id,calc(b,unitById(b.unitId))]);
  const st={}; ['u_homey','u_oapt','u_waha'].forEach(u=>{ st[u]=JSON.parse(JSON.stringify(stmtDataLive(u,'2026-08-01','2026-10-31'),(k,v)=>k==='b'?v&&v.id:v)); });  // rows embed the booking object itself (its status label differs by design) -> compare by id + all numbers
  return JSON.stringify({per,st}); }"""

def boot(pg_ctx_seed):
    pass

with sync_playwright() as p:
    br = p.chromium.launch()

    def new_page(seed_obj):
        ctx = br.new_context(locale='ar-SA', viewport={'width': 1280, 'height': 900})
        ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file:') else r.abort())
        ctx.add_init_script("try{localStorage.setItem('qisma.v2'," + json.dumps(json.dumps(seed_obj)) + ");}catch(e){}")
        pg = ctx.new_page()
        pg.on('pageerror', lambda e: res['errors'].append('pageerror: ' + str(e)))
        pg.goto('file://' + path)
        pg.wait_for_timeout(700)
        pg.evaluate("()=>{ authState='in'; render(); auditReset(); }")
        pg.wait_for_timeout(200)
        return pg

    # ══════════ 1) PayPal batch save: status-only flip ══════════
    pg = new_page(seed)
    before = pg.evaluate("()=>JSON.parse(JSON.stringify(S.bookings))")
    check('seed loaded', len(before) == len(bookings), len(before))
    check('just opening the app leaves every booking byte-identical to the stored data', before == bookings,
          [(a['id']) for a, b in zip(before, bookings) if a != b])

    pg.evaluate("()=>{ modal={t:'p',data:{date:'2026-09-16',from:'2026-09-01',to:'2026-09-15',sar:'',usd:'',note:''}}; render(); }")
    note_txt = pg.evaluate("()=>document.querySelector('.modal').innerText")
    check('batch modal explains the status flip', 'الحالة بس' in note_txt, note_txt[-300:])
    pg.fill('[data-t=sar]', '1500')
    pg.fill('[data-t=usd]', '400')
    pg.click('[data-act=saveM]')
    pg.wait_for_timeout(300)

    after = pg.evaluate("()=>JSON.parse(JSON.stringify(S.bookings))")
    check('no booking added or removed', [b['id'] for b in before] == [b['id'] for b in after])
    A = {b['id']: b for b in after}
    flipped_ok, frozen_ok, bad = True, True, []
    for b in before:
        a = A[b['id']]
        if b['id'] in EXPECT_FLIP:
            exp = dict(b); exp['status'] = DONE
            if a != exp: flipped_ok = False; bad.append((b['id'], 'flip-mismatch', a))
        else:
            if a != b: frozen_ok = False; bad.append((b['id'], 'changed', a))
    check('eligible PayPal bookings: ONLY status changed (every other field identical, incl. unknown fields)', flipped_ok, bad)
    check('non-eligible bookings: completely untouched (deep equal)', frozen_ok, bad)
    check('flipped set == expected set', {b['id'] for b in after if b['status'] == DONE and b['id'] in EXPECT_FLIP} == EXPECT_FLIP)
    check('cancelled booking stays ملغي; paid stays مُحصّل; Gathern/Booking/contract stay قيد التحصيل',
          A['s_cancel']['status'] == CANC and A['s_paid']['status'] == DONE and A['s_gathern']['status'] == PEND
          and A['s_booking']['status'] == PEND and A['s_contract']['status'] == PEND)
    check('boundary dates (from/to) are included; day outside is not',
          A['f_edge_from']['status'] == DONE and A['f_edge_to']['status'] == DONE
          and A['s_before']['status'] == PEND and A['s_after']['status'] == PEND)
    msg = pg.evaluate("()=>msg")
    check('toast tells how many flipped (4)', '4' in msg and 'مُحصّل' in msg, msg)
    check('batch saved', pg.evaluate("()=>S.batches.length") == 1)

    # money must be identical with statuses un-flipped vs flipped
    post = pg.evaluate(CALC_ALL)
    pg.evaluate("(st)=>{ window.__keepB=S.bookings; S.bookings=S.bookings.map(b=>Object.assign({},b,{status:st[b.id]})); }",
                {b['id']: b['status'] for b in before})
    pre = pg.evaluate(CALC_ALL)
    pg.evaluate("()=>{ S.bookings=window.__keepB; clearCaches(); }")
    check('ALL money figures (per-booking calc + owner statements) identical before/after the flip', pre == post)

    # audit log recorded status-only changes
    audit = pg.evaluate("()=>{ try{ return JSON.parse(localStorage.getItem(AUD_Q)||'[]'); }catch(e){ return null; } }")
    st_only = False
    if audit:
        edits = [e for e in audit if e.get('coll') == 'bookings' and e.get('op') == 'edit']
        st_only = len(edits) == 4 and all(list(e['changes'].keys()) == ['status'] for e in edits)
    check('audit log: 4 booking edits, each changing only «status»', st_only, audit if not st_only else '')

    # editing the batch later never reverts statuses; deleting it neither
    pg.evaluate("""()=>{ const bt=S.batches[0]; modal={t:'p',data:Object.assign({},bt,{to:'2026-09-02'})}; render(); }""")
    pg.click('[data-act=saveM]'); pg.wait_for_timeout(250)
    st_after_edit = pg.evaluate("()=>S.bookings.filter(b=>b.status==='مُحصّل').map(b=>b.id).sort()")
    check('shrinking the batch period does NOT revert earlier flips', set(EXPECT_FLIP) <= set(st_after_edit), st_after_edit)
    pg.evaluate("()=>{ S.batches=[]; commit(); }")
    st_after_del = pg.evaluate("()=>S.bookings.filter(b=>b.status==='مُحصّل').map(b=>b.id).sort()")
    check('deleting the batch does NOT revert statuses', set(EXPECT_FLIP) <= set(st_after_del), st_after_del)

    # ══════════ 2) closed month: refusal keeps the modal & data, no phantom side effects ══════════
    seed2 = copy.deepcopy(seed)
    seed2['closes'] = {'2026-09': {'at': 1, 'by': 't', 'units': {}}}
    pg2 = new_page(seed2)
    pg2.evaluate("()=>{ window.__wa=0; window.open=function(){ window.__wa++; return null; }; }")
    base_b = pg2.evaluate("()=>JSON.parse(JSON.stringify(S.bookings))")

    # (a) new booking in the closed month
    pg2.evaluate("()=>{ modal={t:'b',data:Object.assign({},BLANK_B)}; render(); }")
    pg2.select_option('[data-b=unitId]', 'u_homey')
    pg2.evaluate("()=>{ const d=modal.data; d.checkin='2026-09-20'; d.checkout='2026-09-22'; render(); }")
    pg2.fill('[data-b=net]', '333.33')
    pg2.evaluate("()=>{ readModal(); ui.advB=true; render(); }")
    pg2.fill('[data-b=ref]', 'CLOSEDTEST1')
    pg2.fill('[data-b=notes]', 'مكتوب لازم يبقى')
    pg2.click('[data-act=saveM]'); pg2.wait_for_timeout(300)
    s = pg2.evaluate("""()=>({open:!!modal, t:modal&&modal.t, id:modal&&modal.data&&modal.data.id, net:(document.querySelector('[data-b=net]')||{}).value,
        ref:(document.querySelector('[data-b=ref]')||{}).value, notes:(document.querySelector('[data-b=notes]')||{}).value,
        ci:(document.querySelector('[data-b=checkin]')||{}).value, mm:(document.querySelector('.modal #mmsg')||{}).textContent,
        n:S.bookings.length, wa:window.__wa})""")
    check('closed month: save refused, modal STAYS open', s['open'] and s['t'] == 'b', s)
    check('closed month: typed net/ref/notes are kept', s['net'] == '333.33' and s['ref'] == 'CLOSEDTEST1' and s['notes'] == 'مكتوب لازم يبقى', s)
    check('closed month: refusal message shown inside the modal', s['mm'] and 'مقفل' in s['mm'], s)
    check('closed month: draft has NO id (so the next save still adds it)', not s['id'], s)
    check('closed month: nothing saved (bookings deep-equal to before)', pg2.evaluate("()=>JSON.parse(JSON.stringify(S.bookings))") == base_b, s)
    check('closed month: no WhatsApp window opened for an unsaved booking', s['wa'] == 0, s)
    # now move it to an open month and save: must be added exactly once, WhatsApp opens once
    pg2.evaluate("()=>{ readModal(); modal.data.checkin='2026-11-20'; modal.data.checkout='2026-11-22'; render(); }")
    pg2.click('[data-act=saveM]'); pg2.wait_for_timeout(300)
    r = pg2.evaluate("()=>({cnt:S.bookings.filter(b=>b.ref==='CLOSEDTEST1').length, wa:window.__wa, open:!!modal, b:S.bookings.find(b=>b.ref==='CLOSEDTEST1')})")
    check('after moving to an open month the booking saves exactly once', r['cnt'] == 1 and not r['open'], r)
    check('WhatsApp helper fires once for the saved booking', r['wa'] == 1, r)
    check('saved booking kept the typed values', r['b'] and abs(float(r['b']['net']) - 333.33) < 1e-9 and r['b']['notes'] == 'مكتوب لازم يبقى', r)
    now_b = pg2.evaluate("()=>JSON.parse(JSON.stringify(S.bookings))")
    ids0 = {b['id'] for b in base_b}
    check('all older bookings untouched (deep-equal) after the refused + accepted saves', [b for b in now_b if b['id'] in ids0] == base_b)

    # (b) edit an existing booking inside the closed month (change the amount)
    orig = pg2.evaluate("()=>JSON.parse(JSON.stringify(S.bookings.find(b=>b.id==='s_paid')))")
    pg2.evaluate("()=>{ const b=S.bookings.find(x=>x.id==='s_paid'); modal={t:'b',data:Object.assign({},b)}; render(); }")
    pg2.fill('[data-b=net]', '999')
    pg2.click('[data-act=saveM]'); pg2.wait_for_timeout(300)
    e = pg2.evaluate("()=>({open:!!modal, net:(document.querySelector('[data-b=net]')||{}).value, id:modal&&modal.data&&modal.data.id, cur:JSON.parse(JSON.stringify(S.bookings.find(b=>b.id==='s_paid')))})")
    check('closed month edit: refused, modal open with the typed amount', e['open'] and e['net'] == '999' and e['id'] == 's_paid', e)
    check('closed month edit: stored booking is UNCHANGED', e['cur'] == orig, e['cur'])
    pg2.evaluate("()=>{ modal=null; render(); }")

    # (c) PayPal batch touching the closed month: refused, nothing flipped, form kept
    snap = pg2.evaluate("()=>JSON.parse(JSON.stringify(S.bookings))")
    pg2.evaluate("()=>{ modal={t:'p',data:{date:'2026-09-16',from:'2026-09-01',to:'2026-09-15',sar:'',usd:'',note:''}}; render(); }")
    pg2.fill('[data-t=sar]', '1500')
    pg2.click('[data-act=saveM]'); pg2.wait_for_timeout(300)
    c = pg2.evaluate("()=>({open:!!modal, t:modal&&modal.t, sar:(document.querySelector('[data-t=sar]')||{}).value, nb:S.batches.length, id:modal&&modal.data&&modal.data.id,"
                     "bk:JSON.parse(JSON.stringify(S.bookings))})")
    check('closed month batch: refused, modal stays with typed amount, no id', c['open'] and c['t'] == 'p' and c['sar'] == '1500' and not c['id'], c)
    check('closed month batch: no batch saved and NO booking status flipped', c['nb'] == 0 and c['bk'] == snap)

    fatal = [x for x in res['errors'] if x.startswith('pageerror')]
    check('no uncaught page errors', not fatal, fatal[:3])
    br.close()

res['pass'] = sum(1 for c in res['checks'] if c['ok'])
res['fail'] = sum(1 for c in res['checks'] if not c['ok'])
print('\nSUMMARY: %d pass, %d fail' % (res['pass'], res['fail']))
sys.exit(1 if res['fail'] else 0)
