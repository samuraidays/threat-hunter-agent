import anthropic
from anthropic import beta_tool          # ← 新しい import

client = anthropic.Anthropic()

@beta_tool                               # ← これだけで関数が「道具」になる
def get_weather(city: str) -> str:
    """指定した都市の現在の天気を返す。天気を聞かれたら必ずこれを使う。

    Args:
        city: 都市名（例: 東京）
    """
    return f"{city}は晴れ、22度。"

runner = client.beta.messages.tool_runner(   # ← ループを自動で回す
    model="claude-haiku-4-5",
    max_tokens=300,
    tools=[get_weather],                     # 関数をそのまま渡す
    messages=[{"role": "user", "content": "東京の天気は？"}],
)

for message in runner:                       # 1ターンごとに message が返る
    for block in message.content:
        if block.type == "text":
            print("[Claude]", block.text)
        elif block.type == "tool_use":
            print("[道具]", block.name, block.input)