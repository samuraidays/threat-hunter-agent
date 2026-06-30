# threat-hunter-agent

フレームワークを使わず、Anthropic の Python SDK だけで作った**自律型脅威ハンティングAIエージェント**。

ざっくりした任務（例:「直近1日のログを調べて、気になる攻撃を深掘りしてまとめて」）を渡すと、
エージェントが**自分で検索クエリを組み立て → 実行 → 結果を読んで次の仮説を立てる**、を繰り返し、
発見した脅威を構造化データ（JSON）と文章レポート（Markdown）で出力します。

> このコードは記事「**【AI SOC構築 #0】自律AIエージェント開発入門 — フレームワークを使わず、仕組みから作る**」の完成物です。
> 仕組みの解説（LLM＋道具＋ループ、手動ループ→`tool_runner` での自動化など）は記事を参照してください。
> 記事リンク: （公開後にここへ）

## 仕組み（3つだけ）

エージェントの正体は **LLM ＋ 道具（tools）＋ ループ** だけです。

- **`opensearch_search`** … ログを検索する道具（エージェントの「目」）
- **`record_finding`** … 確認できた脅威を1件ずつ構造化記録する道具（「成果物」）
- **`tool_runner`** … 「道具を使う → 結果を返す → 次の手を決める」を、終わりまで自動で回すループ

## 必要なもの

- Python 3.10+
- Anthropic API キー（[console.anthropic.com](https://console.anthropic.com) で発行・従量課金）
- 検索対象のデータ源（このリポジトリは OpenSearch を SSH 経由で叩く例。**自分の環境に合わせて差し替え可**）

## セットアップ

```bash
git clone https://github.com/<your-name>/threat-hunter-agent.git
cd threat-hunter-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY='sk-ant-...'
```

データ源（OpenSearch）への接続は環境変数で設定します（`msearch.py` 参照）:

```bash
export OPENSEARCH_SSH_HOST='your-ssh-host'   # ~/.ssh/config のエイリアス等
export OPENSEARCH_PASSWORD='...'
# 任意: OPENSEARCH_USER / OPENSEARCH_HOSTPORT / OPENSEARCH_INDEX
```

## 使い方

```bash
python hunt_agent.py --days 1      # 直近1日
python hunt_agent.py --days 7      # 直近7日
```

実行すると、エージェントが自律的に調査を進め、最後に2つのファイルが残ります:

- `report_YYYY-MM-DD.md` … 文章のレポート
- `findings_YYYY-MM-DD.json` … 構造化された発見（深刻度・根拠・推奨アクション）

## 自分のデータ源に差し替える

このエージェントの肝は「**道具はただの関数**」という点です。
`msearch.py` の `run_msearch()`（実際にデータを取りに行く部分）を、あなたの環境の
ログ検索・データベース・API・CSV などに書き換えれば、エージェント本体（`hunt_agent.py`）は
そのまま動きます。`hunt_agent.py` の `SYSTEM`（システムプロンプト）に書いた
フィールド名や手順も、自分のデータに合わせて調整してください。

## ファイル構成

```
hunt_agent.py     エージェント本体（2つの道具 + tool_runner + 保存）
msearch.py        データ源への接続例（OpenSearch over SSH）。差し替え可
examples/         記事の各ステップの最小コード（学習用）
  01_hello.py        SDK で1往復
  02_manual_loop.py  道具呼び出しのループを手作業で1周
  03_tool_runner.py  @beta_tool + tool_runner で自動化
```

## 注意

- **AIは間違えることがあります。** 出力は必ず元データで確かめ、最終判断は人間が持ってください。
- API は従量課金です。`hunt_agent.py` には反復回数の上限（既定40ターン）を入れていますが、
  対象期間やモデルによってコストは変わります。

## ライセンス

MIT
