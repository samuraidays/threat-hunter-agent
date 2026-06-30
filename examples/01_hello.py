import anthropic

client = anthropic.Anthropic()          # ① 環境変数 ANTHROPIC_API_KEY を自動で読む

resp = client.messages.create(          # ② Claude に1回リクエスト
    model="claude-haiku-4-5",           #   学習中は安いHaikuで。本番はopus-4-8に上げる
    max_tokens=200,                     #   返答の最大トークン（上限。足りないと途中で切れる）
    messages=[                          #   会話履歴。今回は1ターンだけ
        {"role": "user", "content": "あなたは何ができる？1文で。"}
    ],
)

print(resp.content[0].text)             # ③ 返答はブロックの配列。最初のテキストを表示