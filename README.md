# ✍️ AIライティングツール

Python + Streamlit + Gemini API で作った、個人用のAIライティングツールです。

## 機能

| ツール | できること |
| --- | --- |
| 📝 ブログ記事 | テーマ・読者・トーン・文字数を指定して記事を作成（構成だけも可） |
| ✉️ メール返信 | 受信メールを貼り付けて、相手との関係に合わせた返信案を作成 |
| 📋 要約 | 箇条書き・3行まとめなどの形式で要約。TODOやキーワードの抽出も可 |
| ✏️ 校正・リライト | 誤字脱字チェック、フォーマル／カジュアル化、短縮・膨らませ |
| 🌐 翻訳 | 7言語に対応。意訳・直訳などのスタイルを選べる |
| 📣 SNS投稿 | X・Instagram などに合わせた投稿文を複数パターン作成 |
| 💡 タイトル・キャッチコピー | タイトルやコピーの案を大量に出し、おすすめを提案 |
| 🪄 フリー入力 | 自由に指示して文章を作成 |

共通機能:
- 生成結果のストリーミング表示、文字数カウント、コピー、Markdownダウンロード
- **手直し**: 「もっと短く」「丁寧に」「別の案」などのボタンや自由な指示で、結果をその場で書き直し（「1つ戻す」で元に戻せる）
- **ファイル読み込み**: 要約・校正・翻訳では txt / md / pdf / docx を読み込める
- **履歴の保存**: `history.json` に最新100件まで保存され、再起動しても残る
- モデル・創造性（temperature）の切り替え

## セットアップ

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

`.env.example` をコピーして `.env` を作り、[Google AI Studio](https://aistudio.google.com/apikey) で取得したAPIキーを書きます。

```
GEMINI_API_KEY=あなたのAPIキー
```

（`.env` がなくても、画面のサイドバーからキーを入力できます）

## 起動

```bash
streamlit run app.py
```

## ファイル構成

```
app.py              画面（サイドバー・生成ボタン・結果表示・履歴）
tools.py            各ツールの入力フォームとプロンプト
gemini_client.py    Gemini API の呼び出し（会話形式で送信）
file_loader.py      アップロードファイルからのテキスト抽出
history_store.py    履歴の保存（history.json）
.streamlit/config.toml  テーマ設定（ダーク）
```

## ツールの追加方法

`tools.py` に入力フォームを描画して `Prompt` を返す関数を書き、`TOOLS` リストに `Tool(...)` を1行追加するだけで、サイドバーに表示されます。
