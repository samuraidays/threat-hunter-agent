import anthropic

client = anthropic.Anthropic()

tools = [
    {
        "name": "get_weather",
        "description": "指定した都市の現在の天気を返す。天気を聞かれたら必ずこれを使うこと。",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "都市名（例: 東京）"},
            },
            "required": ["city"],
        },
    }
]

def get_weather(city):
    return f"{city}は晴れ、22度。"

messages = [{"role": "user", "content": "東京の天気は？"}]

resp = client.messages.create(model="claude-haiku-4-5", max_tokens=300, tools=tools, messages=messages)

# ① モデルの返答を「そのまま」履歴に積む（text も tool_use も全部）
messages.append({"role": "assistant", "content": resp.content})

# ② tool_use ブロックを取り出して、自分の関数を実行
for block in resp.content:
    if block.type == "tool_use":
        result = get_weather(**block.input)        # input={'city':'東京'} を渡す
        # ③ 結果を tool_result として user メッセージで返す
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": block.id,            # ← ②で来たIDと一致させる（必須）
                "content": result,
            }],
        })

# ④ もう一度呼ぶ → モデルは結果を見て最終回答する
resp2 = client.messages.create(model="claude-haiku-4-5", max_tokens=300, tools=tools, messages=messages)
print("stop_reason:", resp2.stop_reason)
print(resp2.content[0].text)