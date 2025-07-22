#!/usr/bin/env python3
import json, base64, hashlib, time, sys, re, os, shutil, asyncio, aiohttp, threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import nacl.signing
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import hmac
import ssl
import signal

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
    print(f"\033[{y};{x}H", end='', flush=True)
    return input()

async def ainp(x, y):
    print(f"\033[{y};{x}H", end='', flush=True)
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
        wallet_path = os.path.expanduser("~/.octra/wallet.json")
        if not os.path.exists(wallet_path):
            wallet_path = "wallet.json"
        
        with open(wallet_path, 'r') as f:
            d = json.load(f)
        
        priv = d.get('priv')
        addr = d.get('addr')
        rpc = d.get('rpc', 'http://localhost:8080')
        
        if not priv or not addr:
            return False
            
        if not rpc.startswith('https://') and 'localhost' not in rpc:
            print(f"{c['R']}⚠️  WARNING: Using insecure HTTP connection!{c['r']}")
            time.sleep(2)
            
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

def derive_encryption_key(privkey_b64):
    privkey_bytes = base64.b64decode(privkey_b64)
    salt = b"octra_encrypted_balance_v2"
    return hashlib.sha256(salt + privkey_bytes).digest()[:32]

def encrypt_client_balance(balance, privkey_b64):
    key = derive_encryption_key(privkey_b64)
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    plaintext = str(balance).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return "v2|" + base64.b64encode(nonce + ciphertext).decode()

def decrypt_client_balance(encrypted_data, privkey_b64):
    if encrypted_data == "0" or not encrypted_data:
        return 0
    
    if not encrypted_data.startswith("v2|"):
        privkey_bytes = base64.b64decode(privkey_b64)
        salt = b"octra_encrypted_balance_v1"
        key = hashlib.sha256(salt + privkey_bytes).digest() + hashlib.sha256(privkey_bytes + salt).digest()
        key = key[:32]
        
        try:
            data = base64.b64decode(encrypted_data)
            if len(data) < 32:
                return 0
            
            nonce = data[:16]
            tag = data[16:32]
            encrypted = data[32:]
            
            expected_tag = hashlib.sha256(nonce + encrypted + key).digest()[:16]
            if not hmac.compare_digest(tag, expected_tag):
                return 0
            
            decrypted = bytearray()
            key_hash = hashlib.sha256(key + nonce).digest()
            for i, byte in enumerate(encrypted):
                decrypted.append(byte ^ key_hash[i % 32])
            
            return int(decrypted.decode())
        except:
            return 0
    
    try:
        b64_data = encrypted_data[3:]
        raw = base64.b64decode(b64_data)
        
        if len(raw) < 28:
            return 0
        
        nonce = raw[:12]
        ciphertext = raw[12:]
        
        key = derive_encryption_key(privkey_b64)
        aesgcm = AESGCM(key)
        
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return int(plaintext.decode())
    except:
        return 0

def derive_shared_secret_for_claim(my_privkey_b64, ephemeral_pubkey_b64):
    sk = nacl.signing.SigningKey(base64.b64decode(my_privkey_b64))
    my_pubkey_bytes = sk.verify_key.encode()
    eph_pub_bytes = base64.b64decode(ephemeral_pubkey_b64)
    
    if eph_pub_bytes < my_pubkey_bytes:
        smaller, larger = eph_pub_bytes, my_pubkey_bytes
    else:
        smaller, larger = my_pubkey_bytes, eph_pub_bytes
    
    combined = smaller + larger
    round1 = hashlib.sha256(combined).digest()
    round2 = hashlib.sha256(round1 + b"OCTRA_SYMMETRIC_V1").digest()
    return round2[:32]

def decrypt_private_amount(encrypted_data, shared_secret):
    if not encrypted_data or not encrypted_data.startswith("v2|"):
        return None
    
    try:
        raw = base64.b64decode(encrypted_data[3:])
        if len(raw) < 28:
            return None
        
        nonce = raw[:12]
        ciphertext = raw[12:]
        
        aesgcm = AESGCM(shared_secret)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return int(plaintext.decode())
    except:
        return None

async def req(m, p, d=None, t=10):
    global session
    if not session:
        ssl_context = ssl.create_default_context()
        connector = aiohttp.TCPConnector(ssl=ssl_context, force_close=True)
        session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=t),
            connector=connector,
            json_serialize=json.dumps
        )
    try:
        url = f"{rpc}{p}"
        
        kwargs = {}
        if m == 'POST' and d:
            kwargs['json'] = d
        
        async with getattr(session, m.lower())(url, **kwargs) as resp:
            text = await resp.text()
            
            try:
                j = json.loads(text) if text.strip() else None
            except:
                j = None
            
            return resp.status, text, j
    except asyncio.TimeoutError:
        return 0, "timeout", None
    except Exception as e:
        return 0, str(e), None

async def req_private(path, method='GET', data=None):
    headers = {"X-Private-Key": priv}
    try:
        url = f"{rpc}{path}"
        
        kwargs = {'headers': headers}
        if method == 'POST' and data:
            kwargs['json'] = data
            
        async with getattr(session, method.lower())(url, **kwargs) as resp:
            text = await resp.text()
            
            if resp.status == 200:
                try:
                    return True, json.loads(text) if text.strip() else {}
                except:
                    return False, {"error": "Invalid JSON response"}
            else:
                return False, {"error": f"HTTP {resp.status}"}
                
    except Exception as e:
        return False, {"error": str(e)}

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

async def get_encrypted_balance():
    ok, result = await req_private(f"/view_encrypted_balance/{addr}")
    
    if ok:
        try:
            return {
                "public": float(result.get("public_balance", "0").split()[0]),
                "public_raw": int(result.get("public_balance_raw", "0")),
                "encrypted": float(result.get("encrypted_balance", "0").split()[0]),
                "encrypted_raw": int(result.get("encrypted_balance_raw", "0")),
                "total": float(result.get("total_balance", "0").split()[0])
            }
        except:
            return None
    else:
        return None

async def encrypt_balance(amount):
    enc_data = await get_encrypted_balance()
    if not enc_data:
        return False, {"error": "cannot get balance"}
    
    current_encrypted_raw = enc_data['encrypted_raw']
    new_encrypted_raw = current_encrypted_raw + int(amount * μ)
    
    encrypted_value = encrypt_client_balance(new_encrypted_raw, priv)
    
    data = {
        "address": addr,
        "amount": str(int(amount * μ)),
        "private_key": priv,
        "encrypted_data": encrypted_value
    }
    
    s, t, j = await req('POST', '/encrypt_balance', data)
    if s == 200:
        return True, j
    else:
        return False, {"error": j.get("error", t) if j else t}

async def decrypt_balance(amount):
    enc_data = await get_encrypted_balance()
    if not enc_data:
        return False, {"error": "cannot get balance"}
    
    current_encrypted_raw = enc_data['encrypted_raw']
    if current_encrypted_raw < int(amount * μ):
        return False, {"error": "insufficient encrypted balance"}
    
    new_encrypted_raw = current_encrypted_raw - int(amount * μ)
    
    encrypted_value = encrypt_client_balance(new_encrypted_raw, priv)
    
    data = {
        "address": addr,
        "amount": str(int(amount * μ)),
        "private_key": priv,
        "encrypted_data": encrypted_value
    }
    
    s, t, j = await req('POST', '/decrypt_balance', data)
    if s == 200:
        return True, j
    else:
        return False, {"error": j.get("error", t) if j else t}

async def get_address_info(address):
    s, t, j = await req('GET', f'/address/{address}')
    if s == 200:
        return j
    return None

async def get_public_key(address):
    s, t, j = await req('GET', f'/public_key/{address}')
    if s == 200:
        return j.get("public_key")
    return None

async def create_private_transfer(to_addr, amount):
    addr_info = await get_address_info(to_addr)
    if not addr_info or not addr_info.get("has_public_key"):
        return False, {"error": "Recipient has no public key"}
    
    to_public_key = await get_public_key(to_addr)
    if not to_public_key:
        return False, {"error": "Cannot get recipient public key"}
    
    data = {
        "from": addr,
        "to": to_addr,
        "amount": str(int(amount * μ)),
        "from_private_key": priv,
        "to_public_key": to_public_key
    }
    
    s, t, j = await req('POST', '/private_transfer', data)
    if s == 200:
        return True, j
    else:
        return False, {"error": j.get("error", t) if j else t}

async def get_pending_transfers():
    ok, result = await req_private(f"/pending_private_transfers?address={addr}")
    
    if ok:
        transfers = result.get("pending_transfers", [])
        return transfers
    else:
        return []

async def claim_private_transfer(transfer_id):
    data = {
        "recipient_address": addr,
        "private_key": priv,
        "transfer_id": transfer_id
    }
    
    s, t, j = await req('POST', '/claim_private_transfer', data)
    if s == 200:
        return True, j
    else:
        return False, {"error": j.get("error", t) if j else t}

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
        "timestamp": time.time()
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
    at(x + 11, y + 5, pub[:40] + "...", c['w'])
    
    try:
        enc_data = await get_encrypted_balance()
        if enc_data:
            at(x + 2, y + 6, "encrypted:", c['c'])
            at(x + 13, y + 6, f"{enc_data['encrypted']:.6f} oct", c['B'] + c['y'])
            
            pending = await get_pending_transfers()
            if pending:
                at(x + 2, y + 7, "claimable:", c['c'])
                at(x + 13, y + 7, f"{len(pending)} transfers", c['B'] + c['g'])
    except:
        pass
    
    _, _, j = await req('GET', '/staging', 2)
    sc = len([tx for tx in j.get('staged_transactions', []) if tx.get('from') == addr]) if j else 0
    at(x + 2, y + 8, "staging:", c['c'])
    at(x + 11, y + 8, f"{sc} pending" if sc else "none", c['y'] if sc else c['w'])
    at(x + 1, y + 9, "─" * (w - 2), c['w'])
    
    at(x + 2, y + 10, "recent transactions:", c['B'] + c['c'])
    if not h:
        at(x + 2, y + 12, "no transactions yet", c['y'])
    else:
        at(x + 2, y + 12, "time     type  amount      address", c['c'])
        at(x + 2, y + 13, "─" * (w - 4), c['w'])
        seen_hashes = set()
        display_count = 0
        sorted_h = sorted(h, key=lambda x: x['time'], reverse=True)
        for tx in sorted_h:
            if tx['hash'] in seen_hashes:
                continue
            seen_hashes.add(tx['hash'])
            if display_count >= min(len(h), hb - 17):
                break
            is_pending = not tx.get('epoch')
            time_color = c['y'] if is_pending else c['w']
            at(x + 2, y + 14 + display_count, tx['time'].strftime('%H:%M:%S'), time_color)
            at(x + 11, y + 14 + display_count, " in" if tx['type'] == 'in' else "out", c['g'] if tx['type'] == 'in' else c['R'])
            at(x + 16, y + 14 + display_count, f"{float(tx['amt']):>10.6f}", c['w'])
            at(x + 28, y + 14 + display_count, str(tx.get('to', '---')), c['y'])
            if tx.get('msg'):
                at(x + 77, y + 14 + display_count, "msg", c['c'])
            status_text = "pen" if is_pending else f"e{tx.get('epoch', 0)}"
            status_color = c['y'] + c['B'] if is_pending else c['c']
            at(x + w - 6, y + 14 + display_count, status_text, status_color)
            display_count += 1

def menu(x, y, w, h):
    box(x, y, w, h, "commands")
    at(x + 2, y + 2, "[1] send tx", c['w'])
    at(x + 2, y + 3, "[2] refresh", c['w'])
    at(x + 2, y + 4, "[3] multi send", c['w'])
    at(x + 2, y + 5, "[4] encrypt balance", c['w'])
    at(x + 2, y + 6, "[5] decrypt balance", c['w'])
    at(x + 2, y + 7, "[6] private transfer", c['w'])
    at(x + 2, y + 8, "[7] claim transfers", c['w'])
    at(x + 2, y + 9, "[8] mass claim transfers", c['w'])
    at(x + 2, y + 10, "[9] export keys", c['w'])
    at(x + 2, y + 11, "[0] clear hist", c['w'])
    at(x + 2, y + 12, "[x] exit", c['w'])
    at(x + 2, y + h - 2, "command: ", c['B'] + c['y'])

async def scr():
    cr = sz()
    cls()
    fill()
    t = f" octra client v0.1.0 (private) │ {datetime.now().strftime('%H:%M:%S')} "
    at((cr[0] - len(t)) // 2, 1, t, c['B'] + c['w'])
    
    sidebar_w = 28
    menu(2, 3, sidebar_w, 15)
    
    info_y = 19
    box(2, info_y, sidebar_w, 11)
    at(4, info_y + 2, "testnet environment.", c['y'])
    at(4, info_y + 3, "actively updated.", c['y'])
    at(4, info_y + 4, "monitor changes!", c['y'])
    at(4, info_y + 5, "", c['y'])
    at(4, info_y + 6, "private transactions", c['g'])
    at(4, info_y + 7, "enabled", c['g'])
    at(4, info_y + 8, "", c['y'])
    at(4, info_y + 9, "tokens: no value", c['R'])
    
    explorer_x = sidebar_w + 4
    explorer_w = cr[0] - explorer_x - 2
    await expl(explorer_x, 3, explorer_w, cr[1] - 6)
    
    at(2, cr[1] - 1, " " * (cr[0] - 4), c['bg'])
    at(2, cr[1] - 1, "ready", c['bgg'] + c['w'])
    return await ainp(12, 16)

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

async def encrypt_balance_ui():
    cr = sz()
    cls()
    fill()
    w, hb = 70, 20
    x = (cr[0] - w) // 2
    y = (cr[1] - hb) // 2
    
    box(x, y, w, hb, "encrypt balance")
    
    _, pub_bal = await st()
    enc_data = await get_encrypted_balance()
    
    if not enc_data:
        at(x + 2, y + 10, "cannot get encrypted balance info", c['R'])
        await awaitkey()
        return
    
    at(x + 2, y + 2, "public balance:", c['c'])
    at(x + 20, y + 2, f"{pub_bal:.6f} oct", c['w'])
    
    at(x + 2, y + 3, "encrypted:", c['c'])
    at(x + 20, y + 3, f"{enc_data['encrypted']:.6f} oct", c['y'])
    
    at(x + 2, y + 4, "total:", c['c'])
    at(x + 20, y + 4, f"{enc_data['total']:.6f} oct", c['g'])
    
    at(x + 2, y + 6, "─" * (w - 4), c['w'])
    
    max_encrypt = enc_data['public_raw'] / μ - 1.0
    if max_encrypt <= 0:
        at(x + 2, y + 8, "insufficient public balance (need > 1 oct for fees)", c['R'])
        await awaitkey()
        return
    
    at(x + 2, y + 7, f"max encryptable: {max_encrypt:.6f} oct", c['y'])
    
    at(x + 2, y + 9, "amount to encrypt:", c['y'])
    amount = await ainp(x + 21, y + 9)
    
    if not amount or not re.match(r"^\d+(\.\d+)?$", amount) or float(amount) <= 0:
        return
    
    amount = float(amount)
    if amount > max_encrypt:
        at(x + 2, y + 11, f"amount too large (max: {max_encrypt:.6f})", c['R'])
        await awaitkey()
        return
    
    at(x + 2, y + 11, f"encrypt {amount:.6f} oct? [y/n]:", c['B'] + c['y'])
    if (await ainp(x + 30, y + 11)).strip().lower() != 'y':
        return
    
    spin_task = asyncio.create_task(spin_animation(x + 2, y + 14, "encrypting balance"))
    
    ok, result = await encrypt_balance(amount)
    
    spin_task.cancel()
    try:
        await spin_task
    except asyncio.CancelledError:
        pass
    
    if ok:
        at(x + 2, y + 14, "✓ encryption submitted!", c['bgg'] + c['w'])
        at(x + 2, y + 15, f"tx hash: {result.get('tx_hash', 'unknown')[:50]}...", c['g'])
        at(x + 2, y + 16, f"will process in next epoch", c['g'])
    else:
        at(x + 2, y + 14, f"✗ error: {result.get('error', 'unknown')}", c['bgr'] + c['w'])
    
    await awaitkey()

async def decrypt_balance_ui():
    cr = sz()
    cls()
    fill()
    w, hb = 70, 20
    x = (cr[0] - w) // 2
    y = (cr[1] - hb) // 2
    
    box(x, y, w, hb, "decrypt balance")
    
    _, pub_bal = await st()
    enc_data = await get_encrypted_balance()
    
    if not enc_data:
        at(x + 2, y + 10, "cannot get encrypted balance info", c['R'])
        await awaitkey()
        return
    
    at(x + 2, y + 2, "public balance:", c['c'])
    at(x + 20, y + 2, f"{pub_bal:.6f} oct", c['w'])
    
    at(x + 2, y + 3, "encrypted:", c['c'])
    at(x + 20, y + 3, f"{enc_data['encrypted']:.6f} oct", c['y'])
    
    at(x + 2, y + 4, "total:", c['c'])
    at(x + 20, y + 4, f"{enc_data['total']:.6f} oct", c['g'])
    
    at(x + 2, y + 6, "─" * (w - 4), c['w'])
    
    if enc_data['encrypted_raw'] == 0:
        at(x + 2, y + 8, "no encrypted balance to decrypt", c['R'])
        await awaitkey()
        return
    
    max_decrypt = enc_data['encrypted_raw'] / μ
    at(x + 2, y + 7, f"max decryptable: {max_decrypt:.6f} oct", c['y'])
    
    at(x + 2, y + 9, "amount to decrypt:", c['y'])
    amount = await ainp(x + 21, y + 9)
    
    if not amount or not re.match(r"^\d+(\.\d+)?$", amount) or float(amount) <= 0:
        return
    
    amount = float(amount)
    if amount > max_decrypt:
        at(x + 2, y + 11, f"amount too large (max: {max_decrypt:.6f})", c['R'])
        await awaitkey()
        return
    
    at(x + 2, y + 11, f"decrypt {amount:.6f} oct? [y/n]:", c['B'] + c['y'])
    if (await ainp(x + 30, y + 11)).strip().lower() != 'y':
        return
    
    spin_task = asyncio.create_task(spin_animation(x + 2, y + 14, "decrypting balance"))
    
    ok, result = await decrypt_balance(amount)
    
    spin_task.cancel()
    try:
        await spin_task
    except asyncio.CancelledError:
        pass
    
    if ok:
        at(x + 2, y + 14, "✓ decryption submitted!", c['bgg'] + c['w'])
        at(x + 2, y + 15, f"tx hash: {result.get('tx_hash', 'unknown')[:50]}...", c['g'])
        at(x + 2, y + 16, f"will process in next epoch", c['g'])
    else:
        at(x + 2, y + 14, f"✗ error: {result.get('error', 'unknown')}", c['bgr'] + c['w'])
    
    await awaitkey()

async def private_transfer_ui():
    cr = sz()
    cls()
    fill()
    w, hb = 80, 25
    x = (cr[0] - w) // 2
    y = (cr[1] - hb) // 2
    
    box(x, y, w, hb, "private transfer")
    
    enc_data = await get_encrypted_balance()
    if not enc_data or enc_data['encrypted_raw'] == 0:
        at(x + 2, y + 10, "no encrypted balance available", c['R'])
        at(x + 2, y + 11, "encrypt some balance first", c['y'])
        await awaitkey()
        return
    
    at(x + 2, y + 2, f"encrypted balance: {enc_data['encrypted']:.6f} oct", c['g'])
    at(x + 2, y + 3, "─" * (w - 4), c['w'])
    
    at(x + 2, y + 5, "recipient address:", c['y'])
    to_addr = await ainp(x + 2, y + 6)
    
    if not to_addr or not b58.match(to_addr):
        at(x + 2, y + 12, "invalid address", c['R'])
        await awaitkey()
        return
    
    if to_addr == addr:
        at(x + 2, y + 12, "cannot send to yourself", c['R'])
        await awaitkey()
        return
    
    spin_task = asyncio.create_task(spin_animation(x + 2, y + 8, "checking recipient"))
    
    addr_info = await get_address_info(to_addr)
    
    spin_task.cancel()
    try:
        await spin_task
    except asyncio.CancelledError:
        pass
    
    if not addr_info:
        at(x + 2, y + 12, "recipient address not found on blockchain", c['R'])
        await awaitkey()
        return
    
    if not addr_info.get('has_public_key'):
        at(x + 2, y + 12, "recipient has no public key", c['R'])
        at(x + 2, y + 13, "they need to make a transaction first", c['y'])
        await awaitkey()
        return
    
    at(x + 2, y + 8, f"recipient balance: {addr_info.get('balance', 'unknown')}", c['c'])
    
    at(x + 2, y + 10, "amount:", c['y'])
    amount = await ainp(x + 10, y + 10)
    
    if not amount or not re.match(r"^\d+(\.\d+)?$", amount) or float(amount) <= 0:
        return
    
    amount = float(amount)
    if amount > enc_data['encrypted'] :
        at(x + 2, y + 14, f"insufficient encrypted balance", c['R'])
        await awaitkey()
        return
    
    at(x + 2, y + 12, "─" * (w - 4), c['w'])
    at(x + 2, y + 13, f"send {amount:.6f} oct privately to", c['B'])
    at(x + 2, y + 14, to_addr, c['y'])
    at(x + 2, y + 16, "[y]es / [n]o:", c['B'] + c['y'])
    
    if (await ainp(x + 15, y + 16)).strip().lower() != 'y':
        return
    
    spin_task = asyncio.create_task(spin_animation(x + 2, y + 18, "creating private transfer"))
    
    ok, result = await create_private_transfer(to_addr, amount)
    
    spin_task.cancel()
    try:
        await spin_task
    except asyncio.CancelledError:
        pass
    
    if ok:
        at(x + 2, y + 18, "✓ private transfer submitted!", c['bgg'] + c['w'])
        at(x + 2, y + 19, f"tx hash: {result.get('tx_hash', 'unknown')[:50]}...", c['g'])
        at(x + 2, y + 20, f"recipient can claim in next epoch", c['g'])
        at(x + 2, y + 21, f"ephemeral key: {result.get('ephemeral_key', 'unknown')[:40]}...", c['c'])
    else:
        at(x + 2, y + 18, f"✗ error: {result.get('error', 'unknown')[:w-10]}", c['bgr'] + c['w'])
    
    await awaitkey()

async def claim_transfers_ui():
    cr = sz()
    cls()
    fill()
    w, hb = 85, cr[1] - 4
    x = (cr[0] - w) // 2
    y = 2
    
    box(x, y, w, hb, "claim private transfers")
    
    spin_task = asyncio.create_task(spin_animation(x + 2, y + 2, "loading pending transfers"))
    
    transfers = await get_pending_transfers()
    
    spin_task.cancel()
    try:
        await spin_task
    except asyncio.CancelledError:
        pass
    
    if not transfers:
        at(x + 2, y + 10, "no pending transfers", c['y'])
        await awaitkey()
        return
    
    at(x + 2, y + 2, f"found {len(transfers)} claimable transfers:", c['B'] + c['g'])
    at(x + 2, y + 4, "#   FROM                AMOUNT         EPOCH   ID", c['c'])
    at(x + 2, y + 5, "─" * (w - 4), c['w'])
    
    display_y = y + 6
    max_display = min(len(transfers), hb - 12)
    
    for i, t in enumerate(transfers[:max_display]):
        amount_str = "[encrypted]"
        amount_color = c['y']
        
        if t.get('encrypted_data') and t.get('ephemeral_key'):
            try:
                shared = derive_shared_secret_for_claim(priv, t['ephemeral_key'])
                amt = decrypt_private_amount(t['encrypted_data'], shared)
                if amt:
                    amount_str = f"{amt/μ:.6f} OCT"
                    amount_color = c['g']
            except:
                pass
        
        at(x + 2, display_y + i, f"[{i+1}]", c['c'])
        at(x + 8, display_y + i, t['sender'][:20] + "...", c['w'])
        at(x + 32, display_y + i, amount_str, amount_color)
        at(x + 48, display_y + i, f"ep{t.get('epoch_id', '?')}", c['c'])
        at(x + 58, display_y + i, f"#{t.get('id', '?')}", c['y'])
    
    if len(transfers) > max_display:
        at(x + 2, display_y + max_display + 1, f"... and {len(transfers) - max_display} more", c['y'])
    
    at(x + 2, y + hb - 6, "─" * (w - 4), c['w'])
    at(x + 2, y + hb - 5, "enter number to claim (0 to cancel):", c['y'])
    choice = await ainp(x + 40, y + hb - 5)
    
    if not choice or choice == '0':
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(transfers):
            transfer = transfers[idx]
            transfer_id = transfer['id']
            
            spin_task = asyncio.create_task(spin_animation(x + 2, y + hb - 3, f"claiming transfer #{transfer_id}"))
            
            ok, result = await claim_private_transfer(transfer_id)
            
            spin_task.cancel()
            try:
                await spin_task
            except asyncio.CancelledError:
                pass
            
            if ok:
                at(x + 2, y + hb - 3, f"✓ claimed {result.get('amount', 'unknown')}!", c['bgg'] + c['w'])
                at(x + 2, y + hb - 2, "your encrypted balance has been updated", c['g'])
            else:
                error_msg = result.get('error', 'unknown error')
                at(x + 2, y + hb - 3, f"✗ error: {error_msg[:w-10]}", c['bgr'] + c['w'])
        else:
            at(x + 2, y + hb - 3, "invalid selection", c['R'])
    except ValueError:
        at(x + 2, y + hb - 3, "invalid number", c['R'])
    except Exception:
        at(x + 2, y + hb - 3, f"error occurred", c['R'])
    
    await awaitkey()

async def mass_claim_transfers_ui():
    cr = sz()
    cls()
    fill()
    w, hb = 85, cr[1] - 4
    x = (cr[0] - w) // 2
    y = 2
    
    box(x, y, w, hb, "mass claim private transfers")
    
    spin_task = asyncio.create_task(spin_animation(x + 2, y + 2, "loading pending transfers"))
    
    transfers = await get_pending_transfers()
    
    spin_task.cancel()
    try:
        await spin_task
    except asyncio.CancelledError:
        pass
    
    if not transfers:
        at(x + 2, y + 10, "no pending transfers", c['y'])
        await awaitkey()
        return
    
    at(x + 2, y + 2, f"found {len(transfers)} claimable transfers:", c['B'] + c['g'])
    at(x + 2, y + 4, "#   FROM                AMOUNT         EPOCH   ID", c['c'])
    at(x + 2, y + 5, "─" * (w - 4), c['w'])
    
    display_y = y + 6
    max_display = min(len(transfers), hb - 16)
    total_amount = 0
    
    for i, t in enumerate(transfers[:max_display]):
        amount_str = "[encrypted]"
        amount_color = c['y']
        amount_val = 0
        
        if t.get('encrypted_data') and t.get('ephemeral_key'):
            try:
                shared = derive_shared_secret_for_claim(priv, t['ephemeral_key'])
                amt = decrypt_private_amount(t['encrypted_data'], shared)
                if amt:
                    amount_val = amt / μ
                    amount_str = f"{amount_val:.6f} OCT"
                    amount_color = c['g']
                    total_amount += amount_val
            except:
                pass
        
        at(x + 2, display_y + i, f"[{i+1}]", c['c'])
        at(x + 8, display_y + i, t['sender'][:20] + "...", c['w'])
        at(x + 32, display_y + i, amount_str, amount_color)
        at(x + 48, display_y + i, f"ep{t.get('epoch_id', '?')}", c['c'])
        at(x + 58, display_y + i, f"#{t.get('id', '?')}", c['y'])
    
    if len(transfers) > max_display:
        at(x + 2, display_y + max_display + 1, f"... and {len(transfers) - max_display} more", c['y'])
    
    at(x + 2, y + hb - 10, "─" * (w - 4), c['w'])
    at(x + 2, y + hb - 9, f"total claimable: ~{total_amount:.6f} OCT", c['B'] + c['g'])
    at(x + 2, y + hb - 8, f"will claim all {len(transfers)} transfers", c['y'])
    
    at(x + 2, y + hb - 6, "proceed with mass claim? [y/n]:", c['B'] + c['y'])
    choice = await ainp(x + 33, y + hb - 6)
    
    if choice.strip().lower() != 'y':
        return
    
    # Start mass claiming
    at(x + 2, y + hb - 4, "claiming transfers...", c['c'])
    
    success_count = 0
    failed_count = 0
    batch_size = 3  # Process in smaller batches to avoid overwhelming the server
    
    for i in range(0, len(transfers), batch_size):
        batch = transfers[i:i + batch_size]
        batch_tasks = []
        
        for transfer in batch:
            transfer_id = transfer['id']
            batch_tasks.append(claim_private_transfer(transfer_id))
        
        # Process batch
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        for j, (transfer, result) in enumerate(zip(batch, batch_results)):
            current_idx = i + j + 1
            transfer_id = transfer['id']
            
            at(x + 2, y + hb - 4, f"[{current_idx}/{len(transfers)}] claiming #{transfer_id}...", c['c'])
            
            if isinstance(result, Exception):
                failed_count += 1
                at(x + 55, y + hb - 4, "✗ error", c['R'])
            else:
                ok, claim_result = result
                if ok:
                    success_count += 1
                    at(x + 55, y + hb - 4, "✓ ok   ", c['g'])
                else:
                    failed_count += 1
                    at(x + 55, y + hb - 4, "✗ fail ", c['R'])
            
            await asyncio.sleep(0.1)  # Small delay between claims
        
        # Small delay between batches
        if i + batch_size < len(transfers):
            await asyncio.sleep(0.5)
    
    # Show final results
    at(x + 2, y + hb - 4, " " * (w - 4), c['bg'])
    if failed_count == 0:
        at(x + 2, y + hb - 4, f"✓ mass claim completed!", c['bgg'] + c['w'])
        at(x + 2, y + hb - 3, f"successfully claimed {success_count} transfers", c['g'])
    else:
        at(x + 2, y + hb - 4, f"mass claim finished with errors", c['bgr'] + c['w'])
        at(x + 2, y + hb - 3, f"success: {success_count}, failed: {failed_count}", c['y'])
    
    at(x + 2, y + hb - 2, "your encrypted balance has been updated", c['g'])
    
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
        os.umask(0o077)
        with open(fn, 'w') as f:
            json.dump(wallet_data, f, indent=2)
        os.chmod(fn, 0o600)
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

def signal_handler(sig, frame):
    stop_flag.set()
    if session:
        asyncio.create_task(session.close())
    sys.exit(0)

async def main():
    global session
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
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
                await encrypt_balance_ui()
            elif cmd == '5':
                await decrypt_balance_ui()
            elif cmd == '6':
                await private_transfer_ui()
            elif cmd == '7':
                await claim_transfers_ui()
            elif cmd == '8':
                await mass_claim_transfers_ui()
            elif cmd == '9':
                await exp()
            elif cmd == '0':
                h.clear()
                lh = 0
            elif cmd in ['x', 'q', '']:
                break
    except Exception:
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
    except KeyboardInterrupt:
        pass
    except Exception:
        pass
    finally:
        cls()
        print(f"{c['r']}")
        os._exit(0)
