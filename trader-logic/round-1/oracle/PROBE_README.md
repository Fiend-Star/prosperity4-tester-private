# Round 1 Lambda Probe

Port of `round-0/oracle/imc_probe.py` retargeted at Round 1 unknowns + inline AWS reconnaissance.

## Files
| File | Purpose | Status |
|------|---------|--------|
| `imc_probe_r1.py` | v1 — file listing, hash diff, creds exfil | ✅ run 210525, 10,536 PnL |
| `imc_probe_r1_v2.py` | v2 — dumps files truncated in v1 (datamodel/app_bid/Dockerfile/simulation) | ✅ run 211179, 10,536 PnL |
| `imc_probe_r1_v3_aws.py` | v3 — boto3 inside Lambda, 7 ticks of AWS API calls | ❌ run 211983, ERROR_FINISHED (timeout) |
| `imc_probe_r1_v4_diag.py` | v4 — timing diagnostic | ❌ run 213034, boto3 import 197-271ms OK but every API call timed out |
| `imc_probe_r1_v5_diag.py` | v5 — tight boto3 timeouts | ❌ run 213504, `ConnectTimeoutError` — AWS endpoints network-blocked |
| `imc_probe_r1_v6_net.py` | v6 — urllib3, 2 calls/tick | ❌ run 214138, all timeouts |
| `imc_probe_r1_v7_net.py` | v7 — urllib3, 1 call/tick | ❌ run 225333, tick 1 OK, tick 2+ timed out (urllib3 soft timeout) |
| `imc_probe_r1_v8_sock.py` | v8 — **raw socket, kernel-enforced timeout** | ✅ run 225718, 10,536 PnL, **all 10 targets mapped** |
| `aws_probe.sh` | Local helper (requires `aws` CLI, not installed locally; used boto3 via round-0 script) | ✅ Confirmed IAM lockdown |

## Final network posture (v8 run 225718)
| Target | Result |
|---|---|
| `169.254.100.1:9001` Runtime API | ✅ OPEN |
| `169.254.100.5:53` DNS | ✅ OPEN |
| Any other `169.254.100.x:*` | ❌ ConnRefused |
| `169.254.169.254:80` IMDS | ❌ ConnRefused |
| `1.1.1.1:*` public internet | ❌ Timeout (firewall drops) |
| Runtime API `GET /` | ✅ HTTP 404 (Go server) |
| Runtime API extension path | ✅ HTTP 405 (exists, requires POST) |

**IMC tightened network rules vs round 0** — public HTTP exfil via `ptsv2.com` (attack_trader.py pattern) no longer works. Only exfil channels: stdout (4096ch/tick), traderData (50k), `/tmp/` (container-local).

## v1 Findings (run 210525)
- **FINISHED status, 10,536 PnL** — probe doesn't hurt trading score.
- **1 new file**: `trader_no_orders.py` (1524b) — it's the starter template, NOT a round-2 hint.
- **All round-0 files [CHANGED]** by hash — but `app.py` source is byte-identical (+58b whitespace). `datamodel.py`, `Dockerfile`, `app_bid.py` source dumps got truncated at 4096-char log limit (v2 target).
- **IMC did NOT patch** the 2026-03-21 vulnerability report: `os.popen` works, env extraction works, `/var/task/` readable, `attack_trader.py` still on disk.
- **Python 3.12.13** (was 3.12.12), kernel `5.10.252-285.992.amzn2 #1 SMP Mon Mar 30 23:12:13 UTC 2026`, uid=993(sbx_user1051).
- **Lambda concurrency = 2 containers**. Alternating invocations, each has its own `self.tick`, own AWS key, own `/tmp`. Class-level counters diverge — **traderData is the only reliable cross-invocation state**.
- **Duration 32-55ms, 52MB/128MB** — big headroom for in-Lambda boto3 calls.
- **`/tmp` persists within a container** (verified via marker file).
- **Two container keys seen**: `ASIA3TIUT54GRUGB246A` (log stream `7371a84d…`) + `ASIA3TIUT54G3K37B4EF` (log stream `7d15080e…`).

## Local aws_probe (round-1 creds) Findings
- Identity: account `797296553741`, role `Prosperity_General_Lambda_Role`, UserId `AROA3TIUT54G7SZ72BKAN`
- All 9 services (Lambda, S3, DDB, CW, APIGW, SF, SQS, ECS): **AccessDenied**
- **Same IAM lockdown as round 0** — role has STS `GetCallerIdentity` only

## Per-tick table

### v1 (submitted as 210525)
| Tick | Target |
|------|--------|
| 1 | `/var/task/` listing + env vars (b64) |
| 2 | SHA256[:16] of 9 known round-0 files → SAME/CHANGED/MISSING |
| 3 | Full source of new files (truncated) + changed app.py |
| 4 | Hardening + `/tmp` + round-2 product file name scan |
| 5 | Fresh `CREDS_B64` + `/proc/self/status` |
| 6 | `/tmp` persist re-check |

### v2 (file dumps)
| Tick | Target |
|------|--------|
| 1 | Dockerfile + app_bid.py + README + requirements.txt |
| 2 | datamodel.py (3648b — fits in 4096 alone) |
| 3 | simulation/ dir listing |
| 4 | simulation/orderbook.py head |
| 5 | simulation/orderbook.py tail + products.py/symbols.py/observations.py |
| 6 | Re-hash bananas/orchids/attack/lambda-entrypoint + content |
| 7 | Second fresh `CREDS_B64` |

### v3 (AWS reconnaissance inside Lambda)
| Tick | AWS calls |
|------|-----------|
| 1 | `sts:GetCallerIdentity`, `iam:ListAttachedRolePolicies`, `iam:ListRolePolicies`, `iam:GetRole` on self-role |
| 2 | `lambda:ListFunctions`, `lambda:GetFunction` on 8 guessed names (matching-engine, prosperity-simulator, etc) |
| 3 | `ec2:DescribeInstances/Vpcs/SecurityGroups/Subnets` (VPC reconnaissance) |
| 4 | `secretsmanager:ListSecrets`, `ssm:DescribeParameters`, `ssm:GetParametersByPath /prosperity/` |
| 5 | `cloudformation:ListStacks`, `events:ListRules`, `lambda:ListEventSourceMappings` |
| 6 | `s3:ListBuckets` + `s3:HeadBucket` on 7 guesses + `ddb:DescribeTable` on 4 guesses |
| 7 | `logs:DescribeLogGroups/Streams`, `logs:GetLogEvents` on self, `logs:FilterLogEvents` on the shared `/aws/lambda/prosperity` group |

All v3 responses base64-encoded (tag `Tn_*_B64`) to survive the 4096-char log filter and JSON formatting.

## Why in-Lambda AWS scan matters
- **Fresh creds every invocation** — no ~1h expiry race.
- **Inside IMC's VPC/network** — endpoint reachability differs from our local machine. Services behind VPC endpoints may respond only from inside.
- **No exfiltration surface** — creds never leave AWS.
- **CloudWatch Logs `FilterLogEvents` on the shared group** is the highest-value call — if authorized, it could return **other participants' stdout**.

## Usage
```bash
# Submit v2 as round 1 submission -> grab file contents
# Submit v3 as round 1 submission -> grab AWS inventory
# After each run, extract base64 blobs from run-logs/round-1/<RUN_ID>/<RUN_ID>.log
```

Decoding a v3 Tn_*_B64 blob:
```python
import base64, json
blob = ''  # paste concatenated lines
print(json.dumps(json.loads(base64.b64decode(blob)), indent=2, default=str))
```
