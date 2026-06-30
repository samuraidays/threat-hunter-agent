#!/usr/bin/env python3
"""自律型脅威ハンティングエージェント (Claude Agent SDK / anthropic Python SDK)

エージェント = LLM + 道具(tools) + ループ。
- opensearch_search: wazuh-alerts-* に OpenSearch クエリを投げる道具（目）
- record_finding:    確認できた脅威を構造化記録する道具（成果物）
tool_runner が「クエリ→結果→次の手」のループを自動で回す。

使い方: python hunt_agent.py --days 1
前提:  ANTHROPIC_API_KEY 環境変数 / OpenSearch に接続できること（msearch.py を自分の環境に合わせて設定）/ msearch.py が同ディレクトリにある
"""
import argparse
import datetime
import json

import anthropic
from anthropic import beta_tool

from msearch import run_msearch          # OpenSearch への接続（自分のデータ源に合わせて差し替える）

client = anthropic.Anthropic()           # ANTHROPIC_API_KEY を環境変数から自動取得

# 確認できた脅威を貯めるリスト（record_finding が追記する）
findings = []


# ───────────────────────── 道具1: データを取る ─────────────────────────
@beta_tool
def opensearch_search(query: str) -> str:
    """wazuh-alerts-* に OpenSearch のクエリを投げ、結果(JSON)を返す。脅威ハンティングのデータ取得に使う。
    集計は size:0 を推奨。集計対象フィールドには .keyword を付ける（例 data.honeypot_source.keyword）。

    Args:
        query: OpenSearchクエリ本体のJSON文字列。例 '{"size":0,"aggs":{...}}'
    """
    try:
        q = json.loads(query)                      # モデルが書いた文字列を dict に
    except Exception as e:
        return f"ERROR: queryが有効なJSONではありません: {e}"
    try:
        res = run_msearch({"q": q})                # 単体テストで動かしたあの関数
    except Exception as e:
        return f"ERROR: クエリ実行失敗: {e}"
    out = json.dumps(res["q"], ensure_ascii=False)
    if len(out) > 8000:                            # 結果が巨大だと文脈を圧迫するので上限
        out = out[:8000] + "\n...[切り詰め。size:0の集計で絞って]"
    return out


# ───────────────────────── 道具2: 発見を記録する ─────────────────────────
@beta_tool
def record_finding(severity: str, title: str, evidence: str, recommendation: str) -> str:
    """確認できた脅威を1件記録する。調査で裏取りできたものだけ記録すること。

    Args:
        severity: CRITICAL / HIGH / MEDIUM のいずれか
        title: 脅威の簡潔な名前
        evidence: 根拠となる具体値（IP・件数・abuse_score・ユーザー名 等）
        recommendation: 推奨アクション（読者が何をすべきか）
    """
    findings.append({
        "severity": severity, "title": title,
        "evidence": evidence, "recommendation": recommendation,
    })
    return f"記録しました（現在 {len(findings)}件）"


# ───────────────────────── システムプロンプト（人格・ルール・手順）─────────────────────────
SYSTEM = """あなたはT-POT+Wazuh環境のCTIアナリストです。ハニーポットの実攻撃データに対し、能動的な脅威ハンティングを行います。

# 道具
- opensearch_search(query): wazuh-alerts-* にOpenSearchクエリを投げて結果を得る。集計は size:0 を使う。
- record_finding(...): 確認できた脅威を1件記録する。

# 重要ルール
- 集計に使うフィールドは必ず .keyword を付ける（例: data.src_ip.keyword, data.honeypot_source.keyword）。数値/boolフィールド(rule.level, data.enrichment.abuse_score)は不要。
- tanner の攻撃元IPは data.src_ip ではなく data.peer.ip。
- 自分の監視インフラ自身のIP（誤検知の元）があれば、必ず除外する（bool の must_not で）。
- 主要フィールド: data.src_ip, data.honeypot_source, data.enrichment.abuse_score(数値,0-100), GeoLocation.country_name, rule.level(数値,0-15), rule.description

# 進め方
1. まず全体像を掴む（source別件数、件数の多いIP 等）
2. 異常・外れ値・気になるIPを見つけたら、追加クエリで深掘りする
3. 確認できた脅威は record_finding で1件ずつ記録する
4. 最後に「発見した脅威・注目IP・推奨アクション」を日本語でまとめる
複数回クエリを投げ、能動的に深掘りすること。"""


# ───────────────────────── 実行 ─────────────────────────
def main():
    parser = argparse.ArgumentParser(description="自律型脅威ハンティングエージェント")
    parser.add_argument("--days", type=int, default=1, help="対象日数（直近N日）")
    args = parser.parse_args()

    runner = client.beta.messages.tool_runner(
        model="claude-opus-4-8",                   # 実クエリを書く頭脳。賢いモデルに
        max_tokens=8000,
        system=SYSTEM,
        tools=[opensearch_search, record_finding], # 2つの道具を渡す
        messages=[{"role": "user", "content":
            f"直近{args.days}日(now-{args.days}d/d 〜 now/d)を脅威ハンティングして。"
            "まず全体像を掴み、気になるIPやパターンを複数クエリで深掘りし、"
            "確認できた脅威は record_finding で記録してから、最後にまとめて。"}],
    )

    final_text = ""
    for i, message in enumerate(runner):           # tool_runner が①〜④ループを自動で回す
        if i > 40:                                 # 暴走防止（万一ループが止まらない場合）
            print("反復上限に到達、停止します")
            break
        msg_text = "".join(b.text for b in message.content if b.type == "text")
        if msg_text.strip():
            print("[Claude]", msg_text)
            final_text = msg_text                  # 最後の実質テキスト＝最終レポート
        for block in message.content:
            if block.type == "tool_use":
                print("[道具]", block.name)

    # 成果物をファイルに保存
    date = datetime.date.today().isoformat()
    with open(f"report_{date}.md", "w", encoding="utf-8") as f:
        f.write(final_text)
    with open(f"findings_{date}.json", "w", encoding="utf-8") as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)
    print(f"\n保存しました: report_{date}.md / findings_{date}.json")


if __name__ == "__main__":
    main()