"""AIライティングツール（Streamlit + Gemini API）

起動: streamlit run app.py
"""

import os
import re
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

import history_store
from gemini_client import Message, friendly_error, list_text_models, stream_generate
from tools import TOOLS, Tool

load_dotenv()

DEFAULT_MODEL = "gemini-3.8-flash"
CUSTOM_MODEL = "その他（手入力）"


@st.cache_data(ttl=3600, show_spinner=False)
def available_models(api_key: str) -> list[str]:
    """API から使えるモデル一覧を取得する（1時間キャッシュ）。取得できなければ既定モデルだけ。"""
    try:
        models = list_text_models(api_key) if api_key else []
    except Exception:  # キーの誤り・通信エラーなど（生成時にエラー内容を表示する）
        models = []
    if DEFAULT_MODEL in models:
        models.remove(DEFAULT_MODEL)
    return [DEFAULT_MODEL] + models

# 生成結果をワンクリックで手直しするためのボタン（表示名: AI への指示）
QUICK_REFINES = {
    "✂️ もっと短く": "今の文章を、要点を残したままもっと短く簡潔にしてください。",
    "📖 もっと詳しく": "今の文章を、具体例や補足を加えてもっと詳しくしてください。",
    "🎩 丁寧に": "今の文章を、より丁寧でフォーマルな表現に書き直してください。",
    "😊 カジュアルに": "今の文章を、親しみやすいカジュアルな表現に書き直してください。",
    "🔄 別の案": "同じ条件で、今とは切り口や表現を変えた別の案を作成してください。",
}

st.set_page_config(page_title="AIライティングツール", page_icon="✍️", layout="wide")

if "results" not in st.session_state:
    # ツールごとの最新の生成結果: {"system": システムプロンプト, "messages": [(role, text), ...]}
    # messages の最後が表示中の文章。手直しするたびに [指示, 結果] が後ろに増えていく。
    st.session_state.results = {}
if "history" not in st.session_state:
    st.session_state.history = history_store.load()  # これまでの生成結果（新しい順）


# ---------------------------------------------------------------------------
# サイドバー
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("✍️ AIライティング")

    tool: Tool = st.radio(
        "ツール",
        TOOLS,
        format_func=lambda t: f"{t.icon} {t.label}",
        label_visibility="collapsed",
    )

    st.divider()
    with st.expander("⚙️ 設定", expanded=not os.getenv("GEMINI_API_KEY")):
        api_key = os.getenv("GEMINI_API_KEY", "")
        if api_key:
            st.caption("✅ APIキーは .env から読み込み済み")
        else:
            api_key = st.text_input(
                "Gemini APIキー",
                type="password",
                help="https://aistudio.google.com/apikey で取得できます。.env に書いておくと毎回の入力が不要です。",
            )

        model = st.selectbox(
            "モデル",
            available_models(api_key) + [CUSTOM_MODEL],
            help="APIキーを設定すると、使えるモデルの一覧を自動で取得します。",
        )
        if model == CUSTOM_MODEL:
            model = st.text_input("モデル名", placeholder=f"例: {DEFAULT_MODEL}")

        temperature = st.slider(
            "創造性（temperature）",
            min_value=0.0,
            max_value=2.0,
            value=0.7,
            step=0.1,
            help="低いほど安定した文章、高いほど自由で多様な文章になります。",
        )

    if st.session_state.history:
        st.divider()
        st.subheader("🕘 履歴")
        st.caption(f"history.json に保存（最新{history_store.MAX_ITEMS}件まで）")
        for item in st.session_state.history[:20]:
            with st.expander(f"{item['icon']} {item['label']}｜{item['time']}"):
                st.markdown(safe_markdown(item["text"]))
        if st.button("履歴をすべて削除", width="stretch"):
            st.session_state.history = []
            history_store.clear()
            st.rerun()


# ---------------------------------------------------------------------------
# 生成処理（新規作成・手直しの両方で使う）
# ---------------------------------------------------------------------------
def generate(tool: Tool, system: str, messages: list[Message], history_label: str) -> None:
    """会話を Gemini に送ってその場に表示し、成功したら結果と履歴を保存して画面を更新する。"""
    if not api_key:
        st.error("Gemini APIキーを設定してください（サイドバーの「⚙️ 設定」）。")
        return
    if not model:
        st.error("モデル名を入力してください。")
        return

    def notify_retry(attempt: int, wait: float) -> None:
        st.toast(f"⏳ モデルが混み合っています。{wait:g}秒後に再試行します（{attempt}回目）")

    try:
        with st.spinner("生成中..."):
            text = st.write_stream(
                stream_generate(api_key, model, system, messages, temperature, on_retry=notify_retry)
            )
    except Exception as e:  # APIキーの誤り・モデル名の誤り・混雑・通信エラーなど
        st.error(f"生成に失敗しました。{friendly_error(e)}")
        return

    if not isinstance(text, str) or not text.strip():
        st.warning("結果が空でした。入力内容を変えてもう一度お試しください。")
        return

    st.session_state.results[tool.key] = {
        "system": system,
        "messages": messages + [("model", text)],
    }
    st.session_state.history.insert(
        0,
        {
            "icon": tool.icon,
            "label": history_label,
            "time": datetime.now().strftime("%m/%d %H:%M"),
            "text": text,
        },
    )
    try:
        history_store.save(st.session_state.history)
    except OSError as e:
        st.toast(f"履歴の保存に失敗しました: {e}")
    st.rerun()


# Markdown の画像記法 ![代替テキスト](URL)
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")


def safe_markdown(text: str) -> str:
    """Markdown の画像を、自動で読み込まれないリンク表記に置き換える。

    AI の出力に外部画像が埋め込まれると、表示した瞬間に URL へ通信が発生し、
    文書の内容を外部に送られる恐れがある（受信メールや PDF に仕込まれた指示による）。
    """
    return _MD_IMAGE.sub(lambda m: f"[画像: {m.group(1) or '無題'}]({m.group(2)})", text)


def count_chars(text: str) -> str:
    no_space = len(re.sub(r"\s", "", text))
    return f"{len(text):,}文字（空白・改行を除くと {no_space:,}文字）"


# ---------------------------------------------------------------------------
# メイン画面
# ---------------------------------------------------------------------------
st.header(f"{tool.icon} {tool.label}")
st.caption(tool.description)

prompt = tool.render()

if st.button("✨ 生成する", type="primary", width="stretch"):
    missing = [name for name, value in prompt.required.items() if not value or not value.strip()]
    if missing:
        st.error(f"「{'」「'.join(missing)}」を入力してください。")
    else:
        st.divider()
        st.subheader("生成結果")
        generate(tool, prompt.system, [("user", prompt.user)], tool.label)

result = st.session_state.results.get(tool.key)
if result:
    messages: list[Message] = result["messages"]
    text = messages[-1][1]
    revisions = (len(messages) - 2) // 2  # 手直しした回数

    st.divider()
    head, undo, clear = st.columns([4, 1, 1])
    head.subheader("生成結果" + (f"（手直し {revisions}回目）" if revisions else ""))
    if revisions and undo.button("↩️ 1つ戻す", width="stretch", help="手直し前の文章に戻します"):
        result["messages"] = messages[:-2]
        st.rerun()
    if clear.button("🗑 消去", width="stretch"):
        del st.session_state.results[tool.key]
        st.rerun()

    with st.container(border=True):
        st.markdown(safe_markdown(text))
    st.caption(f"📏 {count_chars(text)}")

    col1, col2 = st.columns(2)
    with col1:
        with st.expander("📋 コピー用テキスト"):
            st.code(text, language=None, wrap_lines=True)
    with col2:
        st.download_button(
            "⬇️ Markdownでダウンロード",
            data=text,
            file_name=f"{tool.key}_{datetime.now():%Y%m%d_%H%M%S}.md",
            mime="text/markdown",
            width="stretch",
        )

    # --- 手直し -------------------------------------------------------------
    st.markdown("##### 🔧 この結果を手直しする")
    instruction = None
    for col, (label, quick) in zip(st.columns(len(QUICK_REFINES)), QUICK_REFINES.items()):
        if col.button(label, width="stretch"):
            instruction, short = quick, label
    with st.form("refine_form", clear_on_submit=True, border=False):
        field, submit = st.columns([5, 1], vertical_alignment="bottom")
        custom = field.text_input(
            "修正の指示",
            placeholder="例: 結論を最初に書いて / 箇条書きをやめて / 300字以内に",
        )
        if submit.form_submit_button("修正する", width="stretch") and custom.strip():
            instruction, short = custom.strip(), custom.strip()

    if instruction:
        st.subheader("手直し結果")
        generate(
            tool,
            result["system"],
            messages + [("user", instruction)],
            f"{tool.label}（{short[:15]}）",
        )
