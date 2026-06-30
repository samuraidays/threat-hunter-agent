#!/usr/bin/env python3
"""OpenSearch への接続例（SSH 経由で _msearch を叩く）。

★ これは「データ源につなぐ道具」の一例です。
   あなたの環境（別のログ基盤・DB・API・CSV など）に合わせて、この1ファイルを
   書き換えてください。hunt_agent.py 側は run_msearch() を呼ぶだけなので、
   ここを差し替えれば残りはそのまま動きます。

接続先は環境変数で設定します（ハードコードしない）:
  OPENSEARCH_SSH_HOST   SSH 先ホスト（~/.ssh/config のエイリアス等）。必須
  OPENSEARCH_PASSWORD   OpenSearch のパスワード。必須
  OPENSEARCH_USER       OpenSearch ユーザー（既定: admin）
  OPENSEARCH_HOSTPORT   リモート側の OpenSearch ホスト:ポート（既定: localhost:9200）
  OPENSEARCH_INDEX      既定インデックス（既定: logs-*）
  MSEARCH_TIMEOUT       タイムアウト秒（既定: 120）

Usage:
  python3 msearch.py '{"q1": <opensearch_query>, "q2": <opensearch_query>}'
"""
from __future__ import annotations

import json
import os
import subprocess
import sys


def _require(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        raise ValueError(f"環境変数 {name} が未設定です")
    return val


def run_msearch(named_queries: dict, index: str | None = None, timeout: int | None = None) -> dict:
    """名前付きクエリをまとめて OpenSearch に投げ、名前付きの結果を返す。

    named_queries: {"name": opensearch_query_dict, ...}
    戻り値:        {"name": opensearch_response_dict, ...}
    """
    ssh_host = _require("OPENSEARCH_SSH_HOST")
    password = _require("OPENSEARCH_PASSWORD")
    user = os.environ.get("OPENSEARCH_USER", "admin")
    hostport = os.environ.get("OPENSEARCH_HOSTPORT", "localhost:9200")
    host = hostport.split(":")[0]
    index = index or os.environ.get("OPENSEARCH_INDEX", "logs-*")
    _timeout = timeout if timeout is not None else int(os.environ.get("MSEARCH_TIMEOUT", "120"))

    # _msearch 形式（ndjson）に組み立て
    lines = []
    for query in named_queries.values():
        lines.append("{}")
        lines.append(json.dumps(query, separators=(",", ":")))
    body = "\n".join(lines) + "\n"

    # パスワードは stdin の先頭行で渡し、リモート側で netrc tmpfile に書き出す。
    # curl の引数・プロセスリストにパスワードが露出しないようにするため。
    ssh_script = (
        "read -r _PW; "
        "_NETRC=$(mktemp); "
        'trap "rm -f $_NETRC" EXIT; '
        f'printf "machine {host} login {user} password %s\\n" "$_PW" > "$_NETRC"; '
        'chmod 600 "$_NETRC"; '
        f'curl -s -k --netrc-file "$_NETRC" "https://{hostport}/{index}/_msearch" '
        '-H "Content-Type: application/x-ndjson" --data-binary @-'
    )
    proc = subprocess.run(
        ["ssh", ssh_host, ssh_script],
        input=password + "\n" + body,
        capture_output=True,
        text=True,
        timeout=_timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"SSH/curl エラー: {proc.stderr}")

    resp = json.loads(proc.stdout)
    if "error" in resp:
        raise RuntimeError(f"OpenSearch エラー: {resp['error']}")

    names = list(named_queries.keys())
    return {names[i]: resp["responses"][i] for i in range(len(names))}


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run_msearch(json.loads(raw)), ensure_ascii=False, indent=2))
