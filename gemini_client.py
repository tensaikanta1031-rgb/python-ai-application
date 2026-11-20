"""Gemini API との通信をまとめたモジュール。"""

import time
from collections.abc import Callable, Iterator

from google import genai
from google.genai import errors, types

# 会話の1発言: ("user" または "model", 本文)
Message = tuple[str, str]

# 一時的なエラー（混雑・サーバー側の不調）は、この秒数ずつ待って自動でやり直す
RETRYABLE_CODES = {500, 503, 504}
RETRY_WAITS = [2, 5, 10]

# 文章生成に向かないモデル（画像生成・音声・埋め込みなど）を一覧から除くための目印
_NON_TEXT_HINTS = ("image", "tts", "audio", "live", "embedding", "computer-use", "transcribe", "robotics")


def list_text_models(api_key: str) -> list[str]:
    """この API キーで使える、文章生成用の Gemini モデル名を新しそうな順で返す。"""
    client = genai.Client(api_key=api_key)
    names = []
    for m in client.models.list():
        name = (m.name or "").removeprefix("models/")
        actions = m.supported_actions or []
        if (
            name.startswith("gemini-")
            and "generateContent" in actions
            and not any(hint in name for hint in _NON_TEXT_HINTS)
        ):
            names.append(name)
    return sorted(set(names), reverse=True)


def stream_generate(
    api_key: str,
    model: str,
    system_prompt: str,
    messages: list[Message],
    temperature: float = 0.7,
    on_retry: Callable[[int, float], None] | None = None,
) -> Iterator[str]:
    """Gemini に会話を送り、生成されたテキストを少しずつ返す。

    messages は古い順の会話。最後は "user" の発言にする。
    （例: [依頼, 生成結果, 修正指示] と渡すと、生成結果を踏まえて書き直してくれる）
    混雑（503）などの一時的なエラーは自動でやり直し、そのたびに on_retry(回数, 待ち秒数) を呼ぶ。
    """
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
    )
    contents = [
        types.Content(role=role, parts=[types.Part.from_text(text=text)])
        for role, text in messages
    ]

    for attempt in range(len(RETRY_WAITS) + 1):
        started = False
        try:
            for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            ):
                if chunk.text:
                    started = True
                    yield chunk.text
            return
        except errors.APIError as e:
            # 混雑などの一時的なエラーで、まだ1文字も出力していなければ少し待ってやり直す。
            # （途中まで出力した後にやり直すと文章が重複するので、その場合はやり直さない）
            if started or e.code not in RETRYABLE_CODES or attempt == len(RETRY_WAITS):
                raise
            if on_retry:
                on_retry(attempt + 1, RETRY_WAITS[attempt])
            time.sleep(RETRY_WAITS[attempt])


def friendly_error(e: Exception) -> str:
    """API のエラーを、次に何をすればよいか分かる日本語のメッセージにする。"""
    code = getattr(e, "code", None)
    messages = {
        400: "リクエストが不正です。APIキーの形式や入力内容を確認してください。",
        401: "APIキーが正しくありません。サイドバーの「⚙️ 設定」か .env のキーを確認してください。",
        403: "このAPIキーではこのモデルを使えません。キーの権限か、別のモデルを確認してください。",
        404: "このモデルは使えません（提供終了・名前の誤りなど）。サイドバーで別のモデルを選んでください。",
        429: "利用上限（無料枠のリクエスト数など）に達しました。しばらく待つか、別のモデルを選んでください。",
        500: "Gemini 側で一時的なエラーが起きました。少し待ってからもう一度お試しください。",
        503: "モデルが混み合っていて応答できませんでした。少し待つか、サイドバーで別のモデルを選んでください。",
        504: "応答に時間がかかりすぎました。入力を短くするか、もう一度お試しください。",
    }
    hint = messages.get(code, "通信エラーなどで生成できませんでした。")
    return f"{hint}\n\n詳細: {e}"
