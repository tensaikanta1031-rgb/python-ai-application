"""アップロードされたファイルからテキストを取り出すモジュール。"""

from io import BytesIO

SUPPORTED_TYPES = ["txt", "md", "pdf", "docx"]
MAX_CHARS = 200_000  # これより長い文章は、トークンの大量消費を防ぐため読み込まない


def extract_text(name: str, data: bytes) -> str:
    """ファイル名の拡張子に応じてテキストを取り出す。読めない・長すぎる場合は ValueError。"""
    text = _extract(name, data)
    if len(text) > MAX_CHARS:
        raise ValueError(f"文章が長すぎます（{len(text):,}文字）。{MAX_CHARS:,}文字以内のファイルにしてください。")
    return text


def _extract(name: str, data: bytes) -> str:
    ext = name.rsplit(".", 1)[-1].lower()

    if ext in ("txt", "md"):
        for encoding in ("utf-8-sig", "cp932"):  # Windows のメモ帳で保存した Shift_JIS にも対応
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("文字コードを判別できませんでした（UTF-8 か Shift_JIS で保存してください）。")

    if ext == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if not text:
            raise ValueError("PDF から文字を取り出せませんでした（画像だけの PDF は読めません）。")
        return text

    if ext == "docx":
        from docx import Document

        doc = Document(BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)

    raise ValueError(f"対応していない形式です: .{ext}")
