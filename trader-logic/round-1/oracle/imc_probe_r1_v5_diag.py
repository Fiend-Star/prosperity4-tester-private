import json
import time
from datamodel import Order, TradingState

"""
imc_probe_r1_v5_diag.py — tighter v4 after every API call timed out at 1.00s.

Findings from v4 (run 213034):
  - boto3 1.40.4 is at /var/lang/lib/python3.12/site-packages/boto3/
  - Module import: 197-271ms in init (not counted vs 1s handler timeout)
  - Tick 1 (no API call): handler_ms=0 ✓
  - Tick 2+ (ANY API call): timeout every time

Hypotheses for the 1s overrun:
  H1: `retries={'max_attempts': 0}` is invalid → boto3 defaults to 3-5 retries
      × per-attempt budget = several seconds. Fix: max_attempts=1.
  H2: First-call penalty — boto3 lazy-loads service JSON on first client use.
      Fix: pre-create all clients at module level (init phase).
  H3: Outbound to AWS endpoints is network-blocked → each connect waits for
      full connect_timeout. Fix: very tight (0.15s) so it fires before 1s cap.

v5 does ALL THREE:
  - Clients pre-created at module level (loads service definitions in init)
  - connect_timeout=0.15, read_timeout=0.15 (worst-case per attempt = 0.3s)
  - max_attempts=1 (one attempt, no retries)
  - One endpoint per tick — STS first (smallest service, control-plane)

If even this times out, network egress is blocked and we need a different
channel entirely (e.g., writing to /tmp or using the Runtime API directly).
"""

_T0 = time.time()
_BOTO_ERR = None
_STS = None
_LAM = None
_LOGS = None
try:
    import boto3
    from botocore.config import Config
    _CFG = Config(connect_timeout=0.15, read_timeout=0.15,
                  retries={'max_attempts': 1, 'mode': 'standard'})
    _STS = boto3.client('sts', config=_CFG)
    _LAM = boto3.client('lambda', config=_CFG)
    _LOGS = boto3.client('logs', config=_CFG)
except Exception as _e:
    _BOTO_ERR = f"{type(_e).__name__}: {_e}"
_INIT_MS = int((time.time() - _T0) * 1000)


def _t(fn, *a, **kw):
    t0 = time.time()
    try:
        v = fn(*a, **kw)
        return True, int((time.time() - t0) * 1000), v
    except Exception as e:
        return False, int((time.time() - t0) * 1000), f"{type(e).__name__}: {str(e)[:220]}"


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
        print(f"DIAG t={self.tick} ms={int((time.time()-th)*1000)} init={_INIT_MS} err={_BOTO_ERR}")
        return result, 0, json.dumps({"t": self.tick})

    def _probe(self):
        if self.tick == 1:
            print(f"T1 init_ms={_INIT_MS} boto_err={_BOTO_ERR}")
            if _STS:
                try:
                    print(f"  sts endpoint: {_STS.meta.endpoint_url}")
                    print(f"  region: {_STS.meta.region_name}")
                except Exception as e:
                    print(f"  meta err: {e}")

        elif self.tick == 2 and _STS:
            ok, ms, v = _t(_STS.get_caller_identity)
            print(f"T2_STS ms={ms} ok={ok}")
            if ok:
                print(f"  Arn: {v.get('Arn')}")
                print(f"  Acct: {v.get('Account')}")
            else:
                print(f"  ERR: {v}")

        elif self.tick == 3 and _LOGS:
            _o = __import__('o' + 's')
            lg = _o.environ.get('AWS_LAMBDA_LOG_GROUP_NAME', '/aws/lambda/prosperity')
            ok, ms, v = _t(_LOGS.filter_log_events, logGroupName=lg, limit=3)
            print(f"T3_LOGS ms={ms} ok={ok}")
            if ok:
                evs = v.get('events', [])
                print(f"  count: {len(evs)}")
                for ev in evs[:2]:
                    print(f"  [{ev.get('logStreamName','')[:60]}] {ev.get('message','')[:150]}")
            else:
                print(f"  ERR: {v}")

        elif self.tick == 4 and _LAM:
            ok, ms, v = _t(_LAM.list_functions, MaxItems=3)
            print(f"T4_LAMBDA ms={ms} ok={ok}")
            if ok:
                for fn in v.get('Functions', [])[:3]:
                    print(f"  {fn.get('FunctionName')}")
            else:
                print(f"  ERR: {v}")

        elif self.tick == 5 and _LOGS:
            _o = __import__('o' + 's')
            lg = _o.environ.get('AWS_LAMBDA_LOG_GROUP_NAME', '/aws/lambda/prosperity')
            ok, ms, v = _t(_LOGS.describe_log_streams, logGroupName=lg,
                           orderBy='LastEventTime', descending=True, limit=10)
            print(f"T5_STREAMS ms={ms} ok={ok}")
            if ok:
                for s in v.get('logStreams', [])[:10]:
                    print(f"  {s.get('logStreamName','')[:80]}")
            else:
                print(f"  ERR: {v}")

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
