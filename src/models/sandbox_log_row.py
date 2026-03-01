from dataclasses import dataclass
import orjson

@dataclass
class SandboxLogRow:
    timestamp: int
    sandbox_log: str
    lambda_log: str

    def __init__(self, timestamp: int, sandbox_log: str, lambda_log: str):
        self.timestamp = timestamp
        self.sandbox_log = sandbox_log
        self.lambda_log = lambda_log

    def with_offset(self, timestamp_offset: int) -> "SandboxLogRow":
        return SandboxLogRow(
            self.timestamp + timestamp_offset,
            self.sandbox_log,
            self.lambda_log.replace(f"[[{self.timestamp},", f"[[{self.timestamp + timestamp_offset},"),
        )

    def __str__(self) -> str:
        return orjson.dumps(
            {
                "sandboxLog": self.sandbox_log,
                "lambdaLog": self.lambda_log,
                "timestamp": self.timestamp,
            },
            option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_INDENT_2,
        ).decode("utf-8")