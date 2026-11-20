"""各ライティングツールの入力フォームとプロンプトを定義するモジュール。

ツールを追加するときは、入力フォームを描画して Prompt を返す関数を書き、
TOOLS に Tool を1つ追加するだけでよい。
"""

from collections.abc import Callable
from dataclasses import dataclass

import streamlit as st

from file_loader import SUPPORTED_TYPES, extract_text

BASE_SYSTEM = (
    "あなたはプロの日本語ライターです。"
    "指示に正確に従い、自然で読みやすい文章を書いてください。"
    "前置きや「承知しました」などの返事は書かず、成果物だけを出力してください。"
    "見出しや箇条書きが必要な場合は Markdown を使ってください。"
)


@dataclass
class Prompt:
    system: str
    user: str
    # 空だと生成できない入力（未入力ならエラー表示する）
    required: dict[str, str]


@dataclass
class Tool:
    key: str
    label: str
    icon: str
    description: str
    render: Callable[[], Prompt]


def _line(label: str, value: str) -> str:
    """値が入っている項目だけをプロンプトに含める。"""
    return f"- {label}: {value}\n" if value and value.strip() else ""


def _text_or_file(label: str, key: str, height: int = 220, placeholder: str = "") -> str:
    """文章の貼り付け欄と、ファイル読み込みを切り替えられる入力欄。入力された文章を返す。"""
    source = st.radio(
        f"{label}の入力方法",
        ["貼り付け", "ファイルから読み込む"],
        horizontal=True,
        key=f"{key}_source",
        label_visibility="collapsed",
    )
    if source == "貼り付け":
        return st.text_area(f"{label} *", height=height, placeholder=placeholder, key=f"{key}_text")

    uploaded = st.file_uploader(
        f"{label} *（{' / '.join(SUPPORTED_TYPES)}）",
        type=SUPPORTED_TYPES,
        key=f"{key}_file",
    )
    if uploaded is None:
        return ""
    try:
        text = extract_text(uploaded.name, uploaded.getvalue())
    except Exception as e:  # 壊れたファイル・未対応の文字コードなど
        st.error(f"ファイルを読み込めませんでした: {e}")
        return ""
    with st.expander(f"📎 {uploaded.name}（{len(text):,}文字）の内容を確認"):
        st.text(text[:3000] + ("\n…（以下省略）" if len(text) > 3000 else ""))
    return text


# ---------------------------------------------------------------------------
# ブログ記事
# ---------------------------------------------------------------------------
def render_blog() -> Prompt:
    topic = st.text_input("記事のテーマ *", placeholder="例: 初心者向けのPython学習ロードマップ")
    keywords = st.text_input("含めたいキーワード", placeholder="例: Python, 独学, 挫折しない")
    col1, col2 = st.columns(2)
    with col1:
        audience = st.text_input("想定読者", placeholder="例: プログラミング未経験の社会人")
        tone = st.selectbox("トーン", ["親しみやすい", "丁寧・ですます調", "専門的", "カジュアル", "熱量高め"])
    with col2:
        length = st.select_slider("文字数の目安", options=[800, 1500, 2500, 4000, 6000], value=2500)
        structure = st.selectbox("出力内容", ["記事本文（完成版）", "見出し構成のみ", "構成＋導入文"])
    notes = st.text_area("その他の要望", placeholder="例: 体験談風に、最後にまとめを入れて", height=80)

    user = (
        "以下の条件でブログ記事を作成してください。\n"
        f"{_line('テーマ', topic)}{_line('キーワード', keywords)}{_line('想定読者', audience)}"
        f"{_line('トーン', tone)}{_line('文字数の目安', f'約{length}字')}"
        f"{_line('出力内容', structure)}{_line('その他の要望', notes)}\n"
        "記事の冒頭にタイトル案を1つ付け、H2・H3 見出しで構成してください。"
        "SEO を意識しつつ、読者が最後まで読みたくなる流れにしてください。"
    )
    return Prompt(BASE_SYSTEM, user, {"記事のテーマ": topic})


# ---------------------------------------------------------------------------
# メール返信
# ---------------------------------------------------------------------------
def render_email() -> Prompt:
    received = st.text_area("受信したメール *", height=180, placeholder="返信したいメールの本文を貼り付けてください")
    points = st.text_area("返信で伝えたいこと", height=80, placeholder="例: 日程はOK、資料は来週送ると伝えたい")
    col1, col2, col3 = st.columns(3)
    with col1:
        relation = st.selectbox("相手との関係", ["取引先・顧客", "上司", "同僚", "友人・知人", "初対面の人"])
    with col2:
        tone = st.selectbox("トーン", ["丁寧", "とても丁寧（かしこまった）", "フレンドリー", "簡潔"])
    with col3:
        count = st.number_input("返信案の数", min_value=1, max_value=3, value=1)
    sender = st.text_input("自分の名前（署名用）", placeholder="例: 山田")

    user = (
        "以下のメールへの返信文を作成してください。\n\n"
        f"【受信メール】\n{received}\n\n"
        "【条件】\n"
        f"{_line('伝えたいこと', points)}{_line('相手との関係', relation)}"
        f"{_line('トーン', tone)}{_line('署名に使う名前', sender)}"
        f"- 返信案を{count}パターン作成（複数の場合は「案1」「案2」のように見出しを付ける）\n"
        "- 件名（Re: を含む）も付けてください\n"
        "- 伝えたいことが空の場合は、受信メールの内容から自然な返信を考えてください"
    )
    return Prompt(BASE_SYSTEM, user, {"受信したメール": received})


# ---------------------------------------------------------------------------
# 要約
# ---------------------------------------------------------------------------
def render_summary() -> Prompt:
    text = _text_or_file("要約したい文章", "summary", height=250, placeholder="記事・議事録・論文などを貼り付けてください")
    col1, col2 = st.columns(2)
    with col1:
        style = st.selectbox("要約の形式", ["箇条書き", "3行まとめ", "段落（文章）", "見出し付きレポート"])
    with col2:
        length = st.selectbox("長さ", ["短く（要点のみ）", "標準", "詳しく"])
    extras = st.multiselect("追加で出力するもの", ["重要キーワード", "アクションアイテム（TODO）", "一言でいうと", "疑問点・注意点"])

    user = (
        "以下の文章を要約してください。\n"
        f"{_line('形式', style)}{_line('長さ', length)}"
        f"{_line('追加で出力するもの', '、'.join(extras))}\n"
        "原文にない情報は加えないでください。\n\n"
        f"【文章】\n{text}"
    )
    return Prompt(BASE_SYSTEM, user, {"要約したい文章": text})


# ---------------------------------------------------------------------------
# 校正・リライト
# ---------------------------------------------------------------------------
REWRITE_MODES = {
    "誤字脱字・文法チェック": "誤字脱字・文法ミス・表記ゆれを修正してください。修正後の文章の後に、主な修正点を箇条書きで示してください。",
    "読みやすく整える": "意味を変えずに、読みやすく自然な文章に書き直してください。",
    "フォーマルにする": "ビジネスでも使える丁寧でフォーマルな文章に書き直してください。",
    "カジュアルにする": "親しみやすいカジュアルな文章に書き直してください。",
    "短くする": "要点を残したまま、できるだけ短く簡潔に書き直してください。",
    "詳しく膨らませる": "内容を補足・具体化して、より詳しい文章に膨らませてください。",
}


def render_rewrite() -> Prompt:
    text = _text_or_file("元の文章", "rewrite")
    mode = st.radio("どうしたいですか？", list(REWRITE_MODES), horizontal=True)
    notes = st.text_input("その他の要望", placeholder="例: 箇条書きは使わないで")

    user = f"{REWRITE_MODES[mode]}\n{_line('その他の要望', notes)}\n【元の文章】\n{text}"
    return Prompt(BASE_SYSTEM, user, {"元の文章": text})


# ---------------------------------------------------------------------------
# 翻訳
# ---------------------------------------------------------------------------
def render_translate() -> Prompt:
    text = _text_or_file("翻訳したい文章", "translate")
    col1, col2 = st.columns(2)
    with col1:
        target = st.selectbox("翻訳先の言語", ["英語", "日本語", "中国語（簡体字）", "韓国語", "スペイン語", "フランス語", "ドイツ語"])
    with col2:
        style = st.selectbox("スタイル", ["自然な意訳", "原文に忠実な直訳", "ビジネス向け", "カジュアル"])
    explain = st.checkbox("ポイントとなる表現の解説も付ける")

    user = (
        f"以下の文章を{target}に翻訳してください。\n"
        f"{_line('スタイル', style)}"
        + ("- 翻訳の後に、訳し方のポイントとなる表現を日本語で簡単に解説してください\n" if explain else "")
        + f"\n【文章】\n{text}"
    )
    return Prompt(BASE_SYSTEM, user, {"翻訳したい文章": text})


# ---------------------------------------------------------------------------
# SNS投稿
# ---------------------------------------------------------------------------
def render_sns() -> Prompt:
    content = st.text_area("投稿したい内容 *", height=120, placeholder="例: 新しいブログ記事を公開した。Pythonの独学方法について")
    col1, col2, col3 = st.columns(3)
    with col1:
        platform = st.selectbox("プラットフォーム", ["X（旧Twitter）", "Instagram", "Threads", "LinkedIn", "Facebook"])
    with col2:
        tone = st.selectbox("トーン", ["カジュアル", "丁寧", "エモーショナル", "ユーモア", "ビジネス"])
    with col3:
        count = st.number_input("案の数", min_value=1, max_value=5, value=3)
    hashtags = st.checkbox("ハッシュタグを付ける", value=True)
    emoji = st.checkbox("絵文字を使う", value=True)

    user = (
        f"{platform}向けの投稿文を{count}パターン作成してください。\n"
        f"{_line('内容', content)}{_line('トーン', tone)}"
        f"- ハッシュタグ: {'付ける' if hashtags else '付けない'}\n"
        f"- 絵文字: {'使う' if emoji else '使わない'}\n"
        "- プラットフォームの文字数制限や文化に合わせてください（X は140字程度）\n"
        "- 各案に「案1」「案2」のような見出しを付けてください"
    )
    return Prompt(BASE_SYSTEM, user, {"投稿したい内容": content})


# ---------------------------------------------------------------------------
# タイトル・キャッチコピー
# ---------------------------------------------------------------------------
def render_copy() -> Prompt:
    content = st.text_area("対象の内容 *", height=120, placeholder="例: 30代向けの時短レシピをまとめたブログ記事")
    col1, col2 = st.columns(2)
    with col1:
        purpose = st.selectbox("用途", ["ブログ記事タイトル", "YouTube動画タイトル", "キャッチコピー", "メール件名", "商品名・サービス名"])
    with col2:
        count = st.number_input("案の数", min_value=3, max_value=20, value=10)
    tone = st.text_input("雰囲気・方向性", placeholder="例: 数字を入れて具体的に、思わずクリックしたくなる")

    user = (
        f"{purpose}の案を{count}個考えてください。\n"
        f"{_line('対象の内容', content)}{_line('雰囲気・方向性', tone)}"
        "- 番号付きリストで出力し、各案の後に短く狙いを添えてください\n"
        "- 最後に一番おすすめの案とその理由を書いてください"
    )
    return Prompt(BASE_SYSTEM, user, {"対象の内容": content})


# ---------------------------------------------------------------------------
# 自由入力
# ---------------------------------------------------------------------------
def render_free() -> Prompt:
    instruction = st.text_area(
        "指示 *",
        height=200,
        placeholder="例: 退職する先輩へのメッセージを200字で書いて",
    )
    return Prompt(BASE_SYSTEM, instruction, {"指示": instruction})


TOOLS: list[Tool] = [
    Tool("blog", "ブログ記事", "📝", "テーマを入れるだけで、見出し付きのブログ記事を作成します。", render_blog),
    Tool("email", "メール返信", "✉️", "受け取ったメールに合わせた返信文を考えます。", render_email),
    Tool("summary", "要約", "📋", "長い文章を、目的に合った形式で要約します。", render_summary),
    Tool("rewrite", "校正・リライト", "✏️", "誤字脱字のチェックや、トーンの変更・言い換えを行います。", render_rewrite),
    Tool("translate", "翻訳", "🌐", "自然な表現で多言語に翻訳します。", render_translate),
    Tool("sns", "SNS投稿", "📣", "各SNSに合わせた投稿文を作成します。", render_sns),
    Tool("copy", "タイトル・キャッチコピー", "💡", "クリックしたくなるタイトルやコピーを大量に考えます。", render_copy),
    Tool("free", "フリー入力", "🪄", "決まった型にとらわれず、自由に指示して文章を作ります。", render_free),
]
