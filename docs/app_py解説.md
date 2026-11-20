# 「AIライティングツール」の app.py を読み解く ― Streamlit アプリの“司令塔”のしくみ

`app.py` はこのアプリの**司令塔**です。画面を組み立て、ボタンが押されたら Gemini に頼み、結果を見せて保存します。この記事では、約230行のコードを上から順に読んでいきます。

---

## まず大前提:Streamlit は「毎回、上から全部やり直す」

`app.py` を読む前に、**Streamlit の一番大事なルール**を押さえておきましょう。

> **ボタンを押す・文字を入力するなど、画面で何か操作するたびに、`app.py` は1行目から最後まで丸ごと実行し直される。**

普通のプログラムは上から下へ1回実行したら終わりです。Streamlit では、操作のたびにそれが何度も繰り返されます。そのため、次の2つの決まりがあります。

- 普通の変数は、実行し直すたびに消えてしまいます。
- 残しておきたいデータは、**`st.session_state`**(セッションステート)という特別な入れ物にしまいます。

このルールを知っていると、このあとのコードがぐっと読みやすくなります。

---

## ① 準備:部品を集める(1〜21行目)

```python
import streamlit as st
from dotenv import load_dotenv

import history_store
from gemini_client import Message, friendly_error, list_text_models, stream_generate
from tools import TOOLS, Tool

load_dotenv()
```

ここでは、ほかのファイルから「部品」を借りてきています。このアプリは**役割ごとにファイルが分かれている**のが特徴です。

| ファイル | 役割 | たとえると |
|---|---|---|
| `app.py` | 画面全体の進行役 | 司令塔 |
| `tools.py` | 各ツール(ブログ・メール等)の入力欄とAIへの指示文 | 料理のレシピ集 |
| `gemini_client.py` | Gemini API とのやりとり | 電話係 |
| `history_store.py` | 履歴をファイルに保存 | 記録係 |

`load_dotenv()` は、`.env` ファイルに書いた `GEMINI_API_KEY=...` を読み込む命令です。これでAPIキーをコードに直接書かずに済みます。

```python
DEFAULT_MODEL = "gemini-3.8-flash"
```

最初に選ばれているAIモデルの名前です。2.5 Flash が使えなくなったので、このモデルに変えました。

---

## ② 使えるモデルを取ってくる(23〜32行目)

```python
@st.cache_data(ttl=3600, show_spinner=False)
def available_models(api_key: str) -> list[str]:
    try:
        models = list_text_models(api_key) if api_key else []
    except Exception:
        models = []
    ...
    return [DEFAULT_MODEL] + models
```

Gemini に「このAPIキーで使えるモデルを教えて」と問い合わせて、モデルの一覧を作る関数です。

注目してほしいのは、1行目の **`@st.cache_data(ttl=3600)`** です。Streamlit は操作のたびに全体を実行し直すので、このままだとボタンを押すたびに Gemini へ問い合わせることになり、無駄です。そこで「**一度取った結果を1時間(3600秒)覚えておいて使い回す**」ように指定しています。

`try / except` の部分は、キーが間違っているなどで取得に失敗したときの備えです。アプリを止めずに、既定のモデルだけを並べます。

---

## ③ 手直しボタンの定義(34〜41行目)

```python
QUICK_REFINES = {
    "✂️ もっと短く": "今の文章を、要点を残したままもっと短く簡潔にしてください。",
    "🎩 丁寧に": "今の文章を、より丁寧でフォーマルな表現に書き直してください。",
    ...
}
```

**左側がボタンに表示される文字**、**右側がそのボタンを押したときAIに送る指示**です。このように辞書(`{ キー: 値 }`)にまとめておけば、ボタンを増やしたいときも1行足すだけで済みます。

---

## ④ 記憶の入れ物を用意する(43〜50行目)

```python
if "results" not in st.session_state:
    st.session_state.results = {}
if "history" not in st.session_state:
    st.session_state.history = history_store.load()
```

冒頭で説明した `st.session_state` の出番です。

- `if "results" not in ...` は「**まだ入れ物がない(=初回の実行)ときだけ作る**」という意味です。2回目以降の実行では作り直さないので、中身が消えません。
- `results` には、ツールごとの最新の生成結果を入れます。
- `history` には、これまでの履歴を入れます。起動時に `history.json` から読み込むので、アプリを再起動しても履歴が残ります。

---

## ⑤ サイドバーを作る(56〜105行目)

`with st.sidebar:` の中に書いたものは、画面の左側に並びます。

### ツールの選択

```python
tool: Tool = st.radio("ツール", TOOLS, format_func=lambda t: f"{t.icon} {t.label}", ...)
```

`tools.py` にある `TOOLS`(ツールの一覧)を、ラジオボタンとして並べています。`format_func` で「📝 ブログ記事」のように、アイコンと名前を組み合わせて表示しています。選ばれたツールは変数 `tool` に入ります。

### 設定欄

```python
api_key = os.getenv("GEMINI_API_KEY", "")
if api_key:
    st.caption("✅ APIキーは .env から読み込み済み")
else:
    api_key = st.text_input("Gemini APIキー", type="password", ...)
```

`.env` にキーがあればそれを使い、なければ入力欄を出します。`type="password"` を指定しているので、入力した文字は「●●●」で隠れます。

そのあとに、モデルを選ぶ欄と「創造性(temperature)」のスライダーが続きます。temperature は、**低いほど無難で安定した文章、高いほど自由で意外性のある文章**になる設定です。

### 履歴の表示

```python
for item in st.session_state.history[:20]:
    with st.expander(f"{item['icon']} {item['label']}｜{item['time']}"):
        st.markdown(item["text"])
```

新しい順に20件まで、開け閉めできる箱(`expander`)に入れて表示します。

---

## ⑥ アプリの心臓部:`generate()` 関数(111〜153行目)

**AIに文章を書かせる処理は、すべてこの関数を通ります。** 新しく生成するときも、手直しするときも同じ関数です。中身は次の4ステップに分かれています。

### ステップ1:事前チェック

```python
if not api_key:
    st.error("Gemini APIキーを設定してください…")
    return
```

APIキーやモデル名がなければ、エラーを表示してここで終わります(`return`)。

### ステップ2:AIに頼んで、少しずつ表示する

```python
text = st.write_stream(
    stream_generate(api_key, model, system, messages, temperature, on_retry=notify_retry)
)
```

ここがいちばん面白いところです。`stream_generate` は、Gemini から**文章を少しずつ受け取る**関数です。`st.write_stream` は、受け取った分を**その場でどんどん画面に表示**し、最後に全文を返します。ChatGPT のように文字がスラスラ出てくる演出は、この組み合わせで実現しています。

`on_retry=notify_retry` は、混雑エラー(503)で自動的にやり直すときに「⏳ 混み合っています」と知らせるための仕組みです。

### ステップ3:失敗したとき

```python
except Exception as e:
    st.error(f"生成に失敗しました。{friendly_error(e)}")
```

`friendly_error` は、英語のエラーを「モデルが混み合っています。少し待つか…」のような、わかりやすい日本語に変える関数です。

### ステップ4:成功したら保存して画面を描き直す

```python
st.session_state.results[tool.key] = {
    "system": system,
    "messages": messages + [("model", text)],
}
st.session_state.history.insert(0, {...})
history_store.save(st.session_state.history)
st.rerun()
```

- 結果を `results` に保存します。
- 履歴の先頭に追加し(`insert(0, ...)`)、ファイルにも保存します。
- 最後の **`st.rerun()`** は「今すぐ上から実行し直して」という命令です。実行し直すと、保存した結果が下の「結果表示エリア」に表示されます。

### 💡 `messages` は「会話の記録」

`messages` は、次のような**会話の記録**になっています。

```
[("user",  "Pythonのブログ記事を書いて"),     ← 最初の依頼
 ("model", "# Python入門 …"),               ← AIの返事
 ("user",  "もっと短くして"),                ← 手直しの指示
 ("model", "# Python入門(短縮版) …")]       ← AIの返事
```

会話をまるごと送るので、AIは「さっき自分が書いた文章を、短くすればいいんだな」と理解できます。**手直し機能は、この仕組みのおかげで成り立っています。**

---

## ⑦ メイン画面:入力と生成ボタン(164〜176行目)

```python
st.header(f"{tool.icon} {tool.label}")
prompt = tool.render()

if st.button("✨ 生成する", type="primary", width="stretch"):
    missing = [name for name, value in prompt.required.items() if not value or not value.strip()]
    if missing:
        st.error(...)
    else:
        generate(tool, prompt.system, [("user", prompt.user)], tool.label)
```

1. **`tool.render()`** で、選ばれたツールの入力欄を表示します。入力欄の中身は `tools.py` に書いてあります。`render()` は、入力内容をもとに組み立てた「AIへの指示文(`prompt`)」を返します。
2. **`st.button(...)`** は、押された回の実行でだけ `True` になります。
3. 必須の項目(`required`)が空なら、エラーを出します。
4. 問題がなければ `generate()` を呼びます。

ここで大事なのは、`app.py` が**ブログやメールなど、個別のツールの中身をまったく知らない**ことです。`app.py` は「`render()` を呼べば指示文が返ってくる」ことだけを知っています。そのため、**ツールを増やすときは `tools.py` を書き足すだけでよく、`app.py` は一切変更しなくて済みます。**

---

## ⑧ 結果を表示する(178〜209行目)

```python
result = st.session_state.results.get(tool.key)
if result:
    messages = result["messages"]
    text = messages[-1][1]                 # 会話の最後 = 最新の文章
    revisions = (len(messages) - 2) // 2   # 手直しした回数
```

- `messages[-1]` は会話の最後の発言、つまり最新の文章です。`[1]` で、そのうちの本文を取り出しています。
- 手直しした回数は、会話の長さから計算しています。最初の依頼と返事で2つ、手直しするたびに2つずつ増えるので、`(長さ - 2) ÷ 2` で回数がわかります。

このあとに、次の部品が並びます。

| 部品 | 中身 |
|---|---|
| `↩️ 1つ戻す` | `messages[:-2]` で最後の2つ(指示と返事)を消して、1つ前の状態に戻す |
| `🗑 消去` | 結果そのものを削除する |
| 枠つきの本文 | `st.markdown` で見出しなどを整えて表示する |
| 📏 文字数 | `count_chars()` で、空白を含む文字数と含まない文字数を表示する |
| コピー・ダウンロード | `st.code` でコピーボタン付きの欄を出し、`st.download_button` で .md ファイルとして保存できるようにする |

---

## ⑨ 手直し機能(211〜233行目)

```python
instruction = None
for col, (label, quick) in zip(st.columns(len(QUICK_REFINES)), QUICK_REFINES.items()):
    if col.button(label, width="stretch"):
        instruction, short = quick, label
```

③で定義した `QUICK_REFINES` の数だけ列(`columns`)を作り、ボタンを横に並べています。押されたボタンがあれば、その指示を `instruction` に入れます。

```python
with st.form("refine_form", clear_on_submit=True, border=False):
    custom = field.text_input("修正の指示", ...)
    if submit.form_submit_button("修正する") and custom.strip():
        instruction, short = custom.strip(), custom.strip()
```

自由に指示を書ける入力欄です。`st.form` で囲んでいるのには理由があります。普通の入力欄は1文字打つたびにアプリ全体が実行し直されることがありますが、フォームにすると**「修正する」ボタンを押したときだけ**送信されます。`clear_on_submit=True` は、送信したあとに入力欄を空にする指定です。

```python
if instruction:
    generate(tool, result["system"], messages + [("user", instruction)], ...)
```

最後に、**これまでの会話に新しい指示を1つ足して**、⑥の `generate()` に渡します。新しく生成するときと同じ関数を使い回しているので、コードがすっきりしています。

---

## まとめ:ボタンを押してから結果が出るまで

「✨ 生成する」を押したときの流れを、最初から最後まで追うと次のようになります。

```
ボタンを押す
  ↓ app.py が上から実行し直される
st.button(...) が True になる
  ↓
tool.render() が作った指示文を generate() に渡す
  ↓
stream_generate() が Gemini に送り、文章を少しずつ受け取って表示する
  ↓
結果を session_state と history.json に保存する
  ↓
st.rerun() で、もう一度上から実行し直す
  ↓
「結果表示エリア」が session_state から文章を取り出して表示する
```

### この記事のポイント

1. **Streamlit は操作のたびに上から全部やり直す。** 残したいデータは `st.session_state` に入れる。
2. **役割ごとにファイルを分けている。** `app.py` は進行役に徹し、ツールの中身は `tools.py`、AIとの通信は `gemini_client.py` が担当する。
3. **会話の記録(`messages`)を送ることで、AIは前の文章を踏まえて手直しできる。**
4. **`generate()` を新しい生成と手直しの両方で使い回して、同じ処理を2回書かずに済ませている。**

---

次は `tools.py` を読むと、ブログやメールなど、各ツールの指示文がどう組み立てられているかがわかります。
