#!/usr/bin/env python3
import json, base64, hashlib, time, sys, re, random, string, os, shutil, asyncio, aiohttp, threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import nacl.signing

c = {'r': '\033[0m', 'b': '\033[34m', 'c': '\033[36m', 'g': '\033[32m', 'y': '\033[33m', 'R': '\033[31m', 'B': '\033[1m', 'bg': '\033[44m', 'bgr': '\033[41m', 'bgg': '\033[42m', 'w': '\033[37m'}

priv, addr, rpc = None, None, None
sk, pub = None, None
b58 = re.compile(r"^oct[1-9A-HJ-NP-Za-km-z]{44}$")
μ = 1_000_000
h = []
cb, cn, lu, lh = None, None, 0, 0
session = None
executor = ThreadPoolExecutor(max_workers=1)
stop_flag = threading.Event()
spinner_frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
spinner_idx = 0

def cls():
    os.system('cls' if os.name == 'nt' else 'clear')

def sz():
    return shutil.get_terminal_size((80, 25))

def at(x, y, t, cl=''):
    print(f"\033[{y};{x}H{c['bg']}{cl}{t}{c['bg']}", end='')

def inp(x, y):
    print(f"\033[{y};{x}H{c['bg']}{c['B']}{c['w']}", end='', flush=True)
    return input()

async def ainp(x, y):
    print(f"\033[{y};{x}H{c['bg']}{c['B']}{c['w']}", end='', flush=True)
    try:
        return await asyncio.get_event_loop().run_in_executor(executor, input)
    except:
        stop_flag.set()
        return ''

def wait():
    cr = sz()
    msg = "press enter to continue..."
    msg_len = len(msg)
    y_pos = cr[1] - 2
    x_pos = max(2, (cr[0] - msg_len) // 2)
    at(x_pos, y_pos, msg, c['y'])
    print(f"\033[{y_pos};{x_pos + msg_len}H", end='', flush=True)
    input()

async def awaitkey():
    cr = sz()
    msg = "press enter to continue..."
    msg_len = len(msg)
    y_pos = cr[1] - 2
    x_pos = max(2, (cr[0] - msg_len) // 2)
    at(x_pos, y_pos, msg, c['y'])
    print(f"\033[{y_pos};{x_pos + msg_len}H{c['bg']}", end='', flush=True)
    try:
        await asyncio.get_event_loop().run_in_executor(executor, input)
    except:
        stop_flag.set()

def ld():
    global priv, addr, rpc, sk, pub
    try:
        with open('wallet.json', 'r') as f:
            d = json.load(f)
        priv = d.get('priv')
        addr = d.get('addr')
        rpc = d.get('rpc', 'https://octra.network')
        sk = nacl.signing.SigningKey(base64.b64decode(priv))
        pub = base64.b64encode(sk.verify_key.encode()).decode()
        return True
    except:
        return False

def fill():
    cr = sz()
    print(f"{c['bg']}", end='')
    for _ in range(cr[1]):
        print(" " * cr[0])
    print("\033[H", end='')

def box(x, y, w, h, t=""):
    print(f"\033[{y};{x}H{c['bg']}{c['w']}┌{'─' * (w - 2)}┐{c['bg']}")
    if t:
        print(f"\033[{y};{x}H{c['bg']}{c['w']}┤ {c['B']}{t} {c['w']}├{c['bg']}")
    for i in range(1, h - 1):
        print(f"\033[{y + i};{x}H{c['bg']}{c['w']}│{' ' * (w - 2)}│{c['bg']}")
    print(f"\033[{y + h - 1};{x}H{c['bg']}{c['w']}└{'─' * (w - 2)}┘{c['bg']}")

async def spin_animation(x, y, msg):
    global spinner_idx
    try:
        while True:
            at(x, y, f"{c['c']}{spinner_frames[spinner_idx]} {msg}", c['c'])
            spinner_idx = (spinner_idx + 1) % len(spinner_frames)
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        at(x, y, " " * (len(msg) + 3), "")

async def req(m, p, d=None, t=10):
    global session
    if not session:
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=t))
    try:
        url = f"{rpc}{p}"
        async with getattr(session, m.lower())(url, json=d if m == 'POST' else None) as resp:
            text = await resp.text()
            try:
                j = json.loads(text) if text else None
            except:
                j = None
            return resp.status, text, j
    except asyncio.TimeoutError:
        return 0, "timeout", None
    except Exception as e:
        return 0, str(e), None

async def st():
    global cb, cn, lu
    now = time.time()
    if cb is not None and (now - lu) < 30:
        return cn, cb
    
    results = await asyncio.gather(
        req('GET', f'/balance/{addr}'),
        req('GET', '/staging', 5),
        return_exceptions=True
    )
    
    s, t, j = results[0] if not isinstance(results[0], Exception) else (0, str(results[0]), None)
    s2, _, j2 = results[1] if not isinstance(results[1], Exception) else (0, None, None)
    
    if s == 200 and j:
        cn = int(j.get('nonce', 0))
        cb = float(j.get('balance', 0))
        lu = now
        if s2 == 200 and j2:
            our = [tx for tx in j2.get('staged_transactions', []) if tx.get('from') == addr]
            if our:
                cn = max(cn, max(int(tx.get('nonce', 0)) for tx in our))
    elif s == 404:
        cn, cb, lu = 0, 0.0, now
    elif s == 200 and t and not j:
        try:
            parts = t.strip().split()
            if len(parts) >= 2:
                cb = float(parts[0]) if parts[0].replace('.', '').isdigit() else 0.0
                cn = int(parts[1]) if parts[1].isdigit() else 0
                lu = now
            else:
                cn, cb = None, None
        except:
            cn, cb = None, None
    return cn, cb

async def gh():
    global h, lh
    now = time.time()
    if now - lh < 60 and h:
        return
    s, t, j = await req('GET', f'/address/{addr}?limit=20')
    if s != 200 or (not j and not t):
        return
    
    if j and 'recent_transactions' in j:
        tx_hashes = [ref["hash"] for ref in j.get('recent_transactions', [])]
        tx_results = await asyncio.gather(*[req('GET', f'/tx/{hash}', 5) for hash in tx_hashes], return_exceptions=True)
        
        existing_hashes = {tx['hash'] for tx in h}
        nh = []
        
        for i, (ref, result) in enumerate(zip(j.get('recent_transactions', []), tx_results)):
            if isinstance(result, Exception):
                continue
            s2, _, j2 = result
            if s2 == 200 and j2 and 'parsed_tx' in j2:
                p = j2['parsed_tx']
                tx_hash = ref['hash']
                
                if tx_hash in existing_hashes:
                    continue
                
                ii = p.get('to') == addr
                ar = p.get('amount_raw', p.get('amount', '0'))
                a = float(ar) if '.' in str(ar) else int(ar) / μ
                msg = None
                if 'data' in j2:
                    try:
                        data = json.loads(j2['data'])
                        msg = data.get('message')
                    except:
                        pass
                nh.append({
                    'time': datetime.fromtimestamp(p.get('timestamp', 0)),
                    'hash': tx_hash,
                    'amt': a,
                    'to': p.get('to') if not ii else p.get('from'),
                    'type': 'in' if ii else 'out',
                    'ok': True,
                    'nonce': p.get('nonce', 0),
                    'epoch': ref.get('epoch', 0),
                    'msg': msg
                })
        
        oh = datetime.now() - timedelta(hours=1)
        h[:] = sorted(nh + [tx for tx in h if tx.get('time', datetime.now()) > oh], key=lambda x: x['time'], reverse=True)[:50]
        lh = now
    elif s == 404 or (s == 200 and t and 'no transactions' in t.lower()):
        h.clear()
        lh = now

def mk(to, a, n, msg=None):
    tx = {
        "from": addr,
        "to_": to,
        "amount": str(int(a * μ)),
        "nonce": int(n),
        "ou": "1" if a < 1000 else "3",
        "timestamp": time.time() + random.random() * 0.01
    }
    if msg:
        tx["message"] = msg
    bl = json.dumps({k: v for k, v in tx.items() if k != "message"}, separators=(",", ":"))
    sig = base64.b64encode(sk.sign(bl.encode()).signature).decode()
    tx.update(signature=sig, public_key=pub)
    return tx, hashlib.sha256(bl.encode()).hexdigest()

async def snd(tx):
    t0 = time.time()
    s, t, j = await req('POST', '/send-tx', tx)
    dt = time.time() - t0
    if s == 200:
        if j and j.get('status') == 'accepted':
            return True, j.get('tx_hash', ''), dt, j
        elif t.lower().startswith('ok'):
            return True, t.split()[-1], dt, None
    return False, json.dumps(j) if j else t, dt, j

async def expl(x, y, w, hb):
    box(x, y, w, hb, "wallet explorer")
    n, b = await st()
    await gh()
    at(x + 2, y + 2, "address:", c['c'])
    at(x + 11, y + 2, addr, c['w'])
    at(x + 2, y + 3, "balance:", c['c'])
    at(x + 11, y + 3, f"{b:.6f} oct" if b is not None else "---", c['B'] + c['g'] if b else c['w'])
    at(x + 2, y + 4, "nonce:  ", c['c'])
    at(x + 11, y + 4, str(n) if n is not None else "---", c['w'])
    at(x + 2, y + 5, "public: ", c['c'])
    at(x + 11, y + 5, pub, c['w'])
    _, _, j = await req('GET', '/staging', 2)
    sc = len([tx for tx in j.get('staged_transactions', []) if tx.get('from') == addr]) if j else 0
    at(x + 2, y + 6, "staging:", c['c'])
    at(x + 11, y + 6, f"{sc} pending" if sc else "none", c['y'] if sc else c['w'])
    at(x + 1, y + 7, "─" * (w - 2), c['w'])
    
    at(x + 2, y + 8, "recent transactions:", c['B'] + c['c'])
    if not h:
        at(x + 2, y + 10, "no transactions yet", c['y'])
    else:
        at(x + 2, y + 10, "time     type  amount      address", c['c'])
        at(x + 2, y + 11, "─" * (w - 4), c['w'])
        seen_hashes = set()
        display_count = 0
        sorted_h = sorted(h, key=lambda x: x['time'], reverse=True)
        for tx in sorted_h:
            if tx['hash'] in seen_hashes:
                continue
            seen_hashes.add(tx['hash'])
            if display_count >= min(len(h), hb - 15):
                break
            is_pending = not tx.get('epoch')
            time_color = c['y'] if is_pending else c['w']
            at(x + 2, y + 12 + display_count, tx['time'].strftime('%H:%M:%S'), time_color)
            at(x + 11, y + 12 + display_count, " in" if tx['type'] == 'in' else "out", c['g'] if tx['type'] == 'in' else c['R'])
            at(x + 16, y + 12 + display_count, f"{float(tx['amt']):>10.6f}", c['w'])
            at(x + 28, y + 12 + display_count, str(tx.get('to', '---')), c['y'])
            if tx.get('msg'):
                at(x + 77, y + 12 + display_count, "msg", c['c'])
            status_text = "pen" if is_pending else f"e{tx.get('epoch', 0)}"
            status_color = c['y'] + c['B'] if is_pending else c['c']
            at(x + w - 6, y + 12 + display_count, status_text, status_color)
            display_count += 1

def menu(x, y, w, h):
    box(x, y, w, h, "commands")
    at(x + 2, y + 3, "[1] send tx", c['w'])
    at(x + 2, y + 5, "[2] refresh balance", c['w'])
    at(x + 2, y + 7, "[3] multi send", c['w'])
    at(x + 2, y + 9, "[4] export keys", c['w'])
    at(x + 2, y + 11, "[5] clear hist", c['w'])
    at(x + 2, y + 13, "[6] auto multi send", c['w'])  # New option
    at(x + 2, y + 15, "[0] exit", c['w'])
    at(x + 2, y + h - 2, "command: ", c['B'] + c['y'])

async def scr():
    cr = sz()
    cls()
    fill()
    t = f" octra pre-client v0.0.13 (dev) │ {datetime.now().strftime('%H:%M:%S')} "
    at((cr[0] - len(t)) // 2, 1, t, c['B'] + c['w'])
    
    sidebar_w = 28
    menu(2, 3, sidebar_w, 17)
    
    info_y = 21
    box(2, info_y, sidebar_w, 9)
    at(4, info_y + 2, "testnet environment.", c['y'])
    at(4, info_y + 3, "actively updated.", c['y'])
    at(4, info_y + 4, "monitor changes!", c['y'])
    at(4, info_y + 5, "", c['y'])
    at(4, info_y + 6, "testnet tokens have", c['y'])
    at(4, info_y + 7, "no commercial value.", c['y'])
    
    explorer_x = sidebar_w + 4
    explorer_w = cr[0] - explorer_x - 2
    await expl(explorer_x, 3, explorer_w, cr[1] - 6)
    
    at(2, cr[1] - 1, " " * (cr[0] - 4), c['bg'])
    at(2, cr[1] - 1, "ready", c['bgg'] + c['w'])
    return await ainp(13, 18)

async def tx():
    cr = sz()
    cls()
    fill()
    w, hb = 85, 26
    x = (cr[0] - w) // 2
    y = (cr[1] - hb) // 2
    box(x, y, w, hb, "send transaction")
    at(x + 2, y + 2, "to address: (or [esc] to cancel)", c['y'])
    at(x + 2, y + 3, "─" * (w - 4), c['w'])
    to = await ainp(x + 2, y + 4)
    if not to or to.lower() == 'esc':
        return
    if not b58.match(to):
        at(x + 2, y + 14, "invalid address!", c['bgr'] + c['w'])
        at(x + 2, y + 15, "press enter to go back...", c['y'])
        await ainp(x + 2, y + 16)
        return
    at(x + 2, y + 5, f"to: {to}", c['g'])
    at(x + 2, y + 7, "amount: (or [esc] to cancel)", c['y'])
    at(x + 2, y + 8, "─" * (w - 4), c['w'])
    a = await ainp(x + 2, y + 9)
    if not a or a.lower() == 'esc':
        return
    if not re.match(r"^\d+(\.\d+)?$", a) or float(a) <= 0:
        at(x + 2, y + 14, "invalid amount!", c['bgr'] + c['w'])
        at(x + 2, y + 15, "press enter to go back...", c['y'])
        await ainp(x + 2, y + 16)
        return
    a = float(a)
    at(x + 2, y + 10, f"amount: {a:.6f} oct", c['g'])
    at(x + 2, y + 12, "message (optional, max 1024): (or enter to skip)", c['y'])
    at(x + 2, y + 13, "─" * (w - 4), c['w'])
    msg = await ainp(x + 2, y + 14)
    if not msg:
        msg = None
    elif len(msg) > 1024:
        msg = msg[:1024]
        at(x + 2, y + 15, "message truncated to 1024 chars", c['y'])
    
    global lu
    lu = 0
    n, b = await st()
    if n is None:
        at(x + 2, y + 17, "failed to get nonce!", c['bgr'] + c['w'])
        at(x + 2, y + 18, "press enter to go back...", c['y'])
        await ainp(x + 2, y + 19)
        return
    if not b or b < a:
        at(x + 2, y + 17, f"insufficient balance ({b:.6f} < {a})", c['bgr'] + c['w'])
        at(x + 2, y + 18, "press enter to go back...", c['y'])
        await ainp(x + 2, y + 19)
        return
    at(x + 2, y + 16, "─" * (w - 4), c['w'])
    at(x + 2, y + 17, f"send {a:.6f} oct", c['B'] + c['g'])
    at(x + 2, y + 18, f"to:  {to}", c['g'])
    if msg:
        at(x + 2, y + 19, f"msg: {msg[:50]}{'...' if len(msg) > 50 else ''}", c['c'])
    at(x + 2, y + 20, f"fee: {'0.001' if a < 1000 else '0.003'} oct (nonce: {n + 1})", c['y'])
    at(x + 2, y + 21, "[y]es / [n]o: ", c['B'] + c['y'])
    if (await ainp(x + 16, y + 21)).strip().lower() != 'y':
        return
    
    spin_task = asyncio.create_task(spin_animation(x + 2, y + 22, "sending transaction"))
    
    t, _ = mk(to, a, n + 1, msg)
    ok, hs, dt, r = await snd(t)
    
    spin_task.cancel()
    try:
        await spin_task
    except asyncio.CancelledError:
        pass
    
    if ok:
        for i in range(17, 25):
            at(x + 2, y + i, " " * (w - 4), c['bg'])
        at(x + 2, y + 20, f"✓ transaction accepted!", c['bgg'] + c['w'])
        at(x + 2, y + 21, f"hash: {hs[:64]}...", c['g'])
        at(x + 2, y + 22, f"      {hs[64:]}", c['g'])
        at(x + 2, y + 23, f"time: {dt:.2f}s", c['w'])
        if r and 'pool_info' in r:
            at(x + 2, y + 24, f"pool: {r['pool_info'].get('total_pool_size', 0)} txs pending", c['y'])
        h.append({
            'time': datetime.now(),
            'hash': hs,
            'amt': a,
            'to': to,
            'type': 'out',
            'ok': True,
            'msg': msg
        })
        lu = 0
    else:
        at(x + 2, y + 20, f"✗ transaction failed!", c['bgr'] + c['w'])
        at(x + 2, y + 21, f"error: {str(hs)[:w - 10]}", c['R'])
    await awaitkey()

async def multi():
    cr = sz()
    cls()
    fill()
    w, hb = 70, cr[1] - 4
    x = (cr[0] - w) // 2
    y = 2
    box(x, y, w, hb, "multi send")
    at(x + 2, y + 2, "enter recipients (address amount), empty line to finish:", c['y'])
    at(x + 2, y + 3, "type [esc] to cancel", c['c'])
    at(x + 2, y + 4, "─" * (w - 4), c['w'])
    rcp = []
    tot = 0
    ly = y + 5
    while ly < y + hb - 8:
        at(x + 2, ly, f"[{len(rcp) + 1}] ", c['c'])
        l = await ainp(x + 7, ly)
        if l.lower() == 'esc':
            return
        if not l:
            break
        p = l.split()
        if len(p) == 2 and b58.match(p[0]) and re.match(r"^\d+(\.\d+)?$", p[1]) and float(p[1]) > 0:
            a = float(p[1])
            rcp.append((p[0], a))
            tot += a
            at(x + 50, ly, f"+{a:.6f}", c['g'])
            ly += 1
        else:
            at(x + 50, ly, "invalid!", c['R'])
    if not rcp:
        return
    at(x + 2, y + hb - 7, "─" * (w - 4), c['w'])
    at(x + 2, y + hb - 6, f"total: {tot:.6f} oct to {len(rcp)} addresses", c['B'] + c['y'])
    global lu
    lu = 0
    n, b = await st()
    if n is None:
        at(x + 2, y + hb - 5, "failed to get nonce!", c['bgr'] + c['w'])
        at(x + 2, y + hb - 4, "press enter to go back...", c['y'])
        await ainp(x + 2, y + hb - 3)
        return
    if not b or b < tot:
        at(x + 2, y + hb - 5, f"insufficient balance! ({b:.6f} < {tot})", c['bgr'] + c['w'])
        at(x + 2, y + hb - 4, "press enter to go back...", c['y'])
        await ainp(x + 2, y + hb - 3)
        return
    at(x + 2, y + hb - 5, f"send all? [y/n] (starting nonce: {n + 1}): ", c['y'])
    if (await ainp(x + 48, y + hb - 5)).strip().lower() != 'y':
        return
    
    spin_task = asyncio.create_task(spin_animation(x + 2, y + hb - 3, "sending transactions"))
    
    batch_size = 5
    batches = [rcp[i:i+batch_size] for i in range(0, len(rcp), batch_size)]
    s_total, f_total = 0, 0
    
    for batch_idx, batch in enumerate(batches):
        tasks = []
        for i, (to, a) in enumerate(batch):
            idx = batch_idx * batch_size + i
            at(x + 2, y + hb - 2, f"[{idx + 1}/{len(rcp)}] preparing batch...", c['c'])
            t, _ = mk(to, a, n + 1 + idx)
            tasks.append(snd(t))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, (result, (to, a)) in enumerate(zip(results, batch)):
            idx = batch_idx * batch_size + i
            if isinstance(result, Exception):
                f_total += 1
                at(x + 55, y + hb - 2, "✗ fail ", c['R'])
            else:
                ok, hs, _, _ = result
                if ok:
                    s_total += 1
                    at(x + 55, y + hb - 2, "✓ ok   ", c['g'])
                    h.append({
                        'time': datetime.now(),
                        'hash': hs,
                        'amt': a,
                        'to': to,
                        'type': 'out',
                        'ok': True
                    })
                else:
                    f_total += 1
                    at(x + 55, y + hb - 2, "✗ fail ", c['R'])
            at(x + 2, y + hb - 2, f"[{idx + 1}/{len(rcp)}] {a:.6f} to {to[:20]}...", c['c'])
            await asyncio.sleep(0.05)
    
    spin_task.cancel()
    try:
        await spin_task
    except asyncio.CancelledError:
        pass
    
    lu = 0
    at(x + 2, y + hb - 2, " " * 65, c['bg'])
    at(x + 2, y + hb - 2, f"completed: {s_total} success, {f_total} failed", c['bgg'] + c['w'] if f_total == 0 else c['bgr'] + c['w'])
    await awaitkey()

async def exp():
    cr = sz()
    cls()
    fill()
    w, hb = 70, 15
    x = (cr[0] - w) // 2
    y = (cr[1] - hb) // 2
    box(x, y, w, hb, "export keys")
    
    at(x + 2, y + 2, "current wallet info:", c['c'])
    at(x + 2, y + 4, "address:", c['c'])
    at(x + 11, y + 4, addr[:32] + "...", c['w'])
    at(x + 2, y + 5, "balance:", c['c'])
    n, b = await st()
    at(x + 11, y + 5, f"{b:.6f} oct" if b is not None else "---", c['g'])
    
    at(x + 2, y + 7, "export options:", c['y'])
    at(x + 2, y + 8, "[1] show private key", c['w'])
    at(x + 2, y + 9, "[2] save full wallet to file", c['w'])
    at(x + 2, y + 10, "[3] copy address to clipboard", c['w'])
    at(x + 2, y + 11, "[0] cancel", c['w'])
    at(x + 2, y + 13, "choice: ", c['B'] + c['y'])
    
    choice = await ainp(x + 10, y + 13)
    choice = choice.strip()
    
    if choice == '1':
        at(x + 2, y + 7, " " * (w - 4), c['bg'])
        at(x + 2, y + 8, " " * (w - 4), c['bg'])
        at(x + 2, y + 9, " " * (w - 4), c['bg'])
        at(x + 2, y + 10, " " * (w - 4), c['bg'])
        at(x + 2, y + 11, " " * (w - 4), c['bg'])
        at(x + 2, y + 13, " " * (w - 4), c['bg'])
        
        at(x + 2, y + 7, "private key (keep secret!):", c['R'])
        at(x + 2, y + 8, priv[:32], c['R'])
        at(x + 2, y + 9, priv[32:], c['R'])
        at(x + 2, y + 11, "public key:", c['g'])
        at(x + 2, y + 12, pub[:44] + "...", c['g'])
        await awaitkey()
        
    elif choice == '2':
        fn = f"octra_wallet_{int(time.time())}.json"
        wallet_data = {
            'priv': priv,
            'addr': addr,
            'rpc': rpc
        }
        with open(fn, 'w') as f:
            json.dump(wallet_data, f, indent=2)
        at(x + 2, y + 7, " " * (w - 4), c['bg'])
        at(x + 2, y + 8, " " * (w - 4), c['bg'])
        at(x + 2, y + 9, " " * (w - 4), c['bg'])
        at(x + 2, y + 10, " " * (w - 4), c['bg'])
        at(x + 2, y + 11, " " * (w - 4), c['bg'])
        at(x + 2, y + 13, " " * (w - 4), c['bg'])
        at(x + 2, y + 9, f"saved to {fn}", c['g'])
        at(x + 2, y + 11, "file contains private key - keep safe!", c['R'])
        await awaitkey()
        
    elif choice == '3':
        try:
            import pyperclip
            pyperclip.copy(addr)
            at(x + 2, y + 7, " " * (w - 4), c['bg'])
            at(x + 2, y + 9, "address copied to clipboard!", c['g'])
        except:
            at(x + 2, y + 7, " " * (w - 4), c['bg'])
            at(x + 2, y + 9, "clipboard not available", c['R'])
        at(x + 2, y + 11, " " * (w - 4), c['bg'])
        await awaitkey()

async def auto_multi():
    """Automated multi-send function that sends 0.05 OCT to 5 addresses every minute"""
    
    # Predefined recipients
    recipients = [
        ("octCTzLvKrxPXNGyWZeBAiEiE8UN7DXe2eGJVgdPYimKog5", 0.05),
        ("octEggobi1U8AjJUPUye6P5nN7YwPUvohzJAf5TLeJTjWeU", 0.05),
        ("octGHPkxysJ4vStwSH8nenokGACabo8vqjwFSWZMLG78DSt", 0.05),
        ("oct6ofsKuhbFADd5yVxtJrCKFv6ZhWsYcneD5aHUGyq5CTo", 0.05),
        ("octJBwmZNUjnffikWPYa2BmicP1x98JoSML6LMR3XScHgk7", 0.05)
    ]
    
    cr = sz()
    cls()
    fill()
    w, hb = 70, cr[1] - 4
    x = (cr[0] - w) // 2
    y = 2
    
    box(x, y, w, hb, "automated multi send")
    
    # Display configuration
    at(x + 2, y + 2, "automated multi-send configuration:", c['B'] + c['y'])
    at(x + 2, y + 3, "─" * (w - 4), c['w'])
    at(x + 2, y + 4, f"recipients: {len(recipients)} addresses", c['c'])
    at(x + 2, y + 5, f"amount per address: 0.05 OCT", c['c'])
    at(x + 2, y + 6, f"total per cycle: {len(recipients) * 0.05:.2f} OCT", c['c'])
    at(x + 2, y + 7, f"interval: 60 seconds", c['c'])
    at(x + 2, y + 8, "─" * (w - 4), c['w'])
    
    # Check initial balance
    global lu
    lu = 0
    n, b = await st()
    total_needed = len(recipients) * 0.05
    
    if n is None:
        at(x + 2, y + 10, "failed to get wallet status!", c['bgr'] + c['w'])
        at(x + 2, y + 11, "press enter to go back...", c['y'])
        await ainp(x + 2, y + 12)
        return
        
    if not b or b < total_needed:
        at(x + 2, y + 10, f"insufficient balance! need {total_needed:.2f}, have {b:.6f}", c['bgr'] + c['w'])
        at(x + 2, y + 11, "press enter to go back...", c['y'])
        await ainp(x + 2, y + 12)
        return
    
    at(x + 2, y + 10, f"current balance: {b:.6f} OCT", c['g'])
    at(x + 2, y + 11, f"estimated cycles: {int(b / total_needed)}", c['c'])
    at(x + 2, y + 13, "start automated sending? [y/n]: ", c['B'] + c['y'])
    
    if (await ainp(x + 35, y + 13)).strip().lower() != 'y':
        return
    
    # Clear screen for automation display
    cls()
    fill()
    box(x, y, w, hb, "automated multi send - running")
    
    at(x + 2, y + 2, "status: running automated multi-send", c['bgg'] + c['w'])
    at(x + 2, y + 3, "press ctrl+c to stop", c['y'])
    at(x + 2, y + 4, "─" * (w - 4), c['w'])
    
    cycle_count = 0
    total_sent = 0
    total_success = 0
    total_failed = 0
    
    try:
        while True:
            cycle_count += 1
            cycle_start = time.time()
            
            # Update display
            at(x + 2, y + 6, f"cycle: {cycle_count}", c['c'])
            at(x + 2, y + 7, f"time: {datetime.now().strftime('%H:%M:%S')}", c['c'])
            
            # Get current nonce and balance
            lu = 0
            n, b = await st()
            
            if n is None:
                at(x + 2, y + 9, "failed to get nonce - retrying...", c['R'])
                await asyncio.sleep(5)
                continue
                
            if not b or b < total_needed:
                at(x + 2, y + 9, f"insufficient balance: {b:.6f} < {total_needed}", c['bgr'] + c['w'])
                at(x + 2, y + 10, "stopping automation...", c['y'])
                break
            
            at(x + 2, y + 8, f"balance: {b:.6f} OCT", c['g'])
            at(x + 2, y + 9, "sending batch...", c['c'])
            
            # Prepare and send transactions
            spin_task = asyncio.create_task(spin_animation(x + 2, y + 11, f"sending cycle {cycle_count}"))
            
            batch_size = 5
            batches = [recipients[i:i+batch_size] for i in range(0, len(recipients), batch_size)]
            cycle_success, cycle_failed = 0, 0
            
            for batch_idx, batch in enumerate(batches):
                tasks = []
                for i, (to, a) in enumerate(batch):
                    idx = batch_idx * batch_size + i
                    t, _ = mk(to, a, n + 1 + idx)
                    tasks.append(snd(t))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, (result, (to, a)) in enumerate(zip(results, batch)):
                    if isinstance(result, Exception):
                        cycle_failed += 1
                    else:
                        ok, hs, _, _ = result
                        if ok:
                            cycle_success += 1
                            h.append({
                                'time': datetime.now(),
                                'hash': hs,
                                'amt': a,
                                'to': to,
                                'type': 'out',
                                'ok': True
                            })
                        else:
                            cycle_failed += 1
            
            spin_task.cancel()
            try:
                await spin_task
            except asyncio.CancelledError:
                pass
            
            # Update totals
            total_success += cycle_success
            total_failed += cycle_failed
            total_sent += cycle_success * 0.05
            
            # Display results
            at(x + 2, y + 11, " " * (w - 4), c['bg'])
            at(x + 2, y + 11, f"cycle {cycle_count}: {cycle_success} success, {cycle_failed} failed", 
               c['bgg'] + c['w'] if cycle_failed == 0 else c['bgr'] + c['w'])
            at(x + 2, y + 12, f"totals: {total_success} sent, {total_sent:.2f} OCT", c['c'])
            
            # Wait for next cycle (60 seconds total)
            elapsed = time.time() - cycle_start
            wait_time = max(0, 60 - elapsed)
            
            if wait_time > 0:
                for remaining in range(int(wait_time), 0, -1):
                    at(x + 2, y + 13, f"next cycle in: {remaining}s    ", c['y'])
                    await asyncio.sleep(1)
            
            lu = 0  # Force balance refresh
            
    except KeyboardInterrupt:
        at(x + 2, y + 15, "automation stopped by user", c['y'])
    except Exception as e:
        at(x + 2, y + 15, f"error: {str(e)[:50]}", c['R'])
    
    at(x + 2, y + 16, f"final stats: {total_success} transactions, {total_sent:.2f} OCT sent", c['g'])
    await awaitkey()

async def main():
    global session
    
    if not ld():
        sys.exit("[!] wallet.json error")
    if not addr:
        sys.exit("[!] wallet.json not configured")
    
    try:
        await st()
        await gh()
        
        while not stop_flag.is_set():
            cmd = await scr()
            if cmd == '1':
                await tx()
            elif cmd == '2':
                global lu, lh
                lu = lh = 0
                await st()
                await gh()
            elif cmd == '3':
                await multi()
            elif cmd == '4':
                await exp()
            elif cmd == '5':
                h.clear()
                lh = 0
            elif cmd == '6':  # New command handler
                await auto_multi()
            elif cmd in ['0', 'q', '']:
                break
    except:
        pass
    finally:
        if session:
            await session.close()
        executor.shutdown(wait=False)

if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", category=ResourceWarning)
    
    try:
        asyncio.run(main())
    except:
        pass
    finally:
        cls()
        print(f"{c['r']}")
        os._exit(0)