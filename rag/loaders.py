"""多格式文档加载：PDF / DOCX / TXT / Markdown → 逐页（段）纯文本

设计要点：
- PDF 用 pypdf 逐页提取，随后做中文归一化（PDF 提取常在汉字间插入空格）；
- DOCX 用标准库 zipfile 解析 word/document.xml，无需额外依赖；
- 统一输出 PageContent 列表，页码从 1 开始，供切片与引用溯源使用。
"""

import io
import re
import zipfile
from functools import lru_cache
from pathlib import Path

from .schemas import PageContent

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}

# 中文字符区间，用于空格清理
_CJK_RE = re.compile(r"([\u4e00-\u9fff\u3400-\u4dbf])\s+(?=[\u4e00-\u9fff\u3400-\u4dbf])")


def normalize_text(text: str) -> str:
    """中文文本归一化：去掉汉字之间的无意义空格、合并连续空白"""
    text = _CJK_RE.sub(r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@lru_cache(maxsize=1)
def _load_stopwords() -> frozenset[str]:
    """中文停用词表（精简版，内嵌避免外部文件依赖）"""
    words = """的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自 己 这
    那 它 吧 被 把 从 与 们 但 等 到 这么 什么 那么 可以 这个 那个 我们 你们 他们 因此 如果 因为 所以
    或者 虽然 但是 而且 以及 对于 根据 通过 进行 可能 需要 应该 就是 还是 只是 已经 一些 一定"""
    return frozenset(words.split())


def load_document(data: bytes, filename: str) -> list[PageContent]:
    """按文件后缀分发到对应解析器，返回逐页文本"""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"不支持的文件类型 {suffix}，支持：{sorted(SUPPORTED_SUFFIXES)}")

    if suffix == ".pdf":
        pages = _load_pdf(data)
    elif suffix == ".docx":
        pages = _load_docx(data)
    else:  # txt / md 整体作为一"页"
        pages = [PageContent(page=1, text=_decode_text(data))]

    if not any(p.text for p in pages):
        raise ValueError("文件内容为空或无法解析出文本")
    return pages


# ── PDF ──

def _load_pdf(data: bytes) -> list[PageContent]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(PageContent(page=i, text=normalize_text(text)))
    return pages


# ── DOCX ──

_W_TEXT_RE = re.compile(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", re.IGNORECASE)
_W_PARA_RE = re.compile(r"<w:p[ >]")


def _load_docx(data: bytes) -> list[PageContent]:
    """解析 DOCX：每个 <w:p> 段落一行，每 40 段视为一"页"便于引用定位"""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")

    paragraphs: list[str] = []
    # 逐段扫描，段落边界按 <w:p ...> 出现位置切分
    pos = 0
    for match in _W_PARA_RE.finditer(xml):
        seg = xml[pos:match.start()]
        pos = match.start()
        paragraphs.append("".join(_W_TEXT_RE.findall(seg)))
    paragraphs.append("".join(_W_TEXT_RE.findall(xml[pos:])))

    lines = [normalize_text(p) for p in paragraphs if normalize_text(p)]
    page_size = 40
    pages = [
        PageContent(page=i // page_size + 1, text="\n".join(chunk))
        for i, chunk in enumerate(
            [lines[i:i + page_size] for i in range(0, len(lines), page_size)]
        )
    ]
    return pages


# ── TXT / MD ──

def _decode_text(data: bytes) -> str:
    for enc in ("utf-8", "gb18030", "utf-16"):
        try:
            return normalize_text(data.decode(enc))
        except (UnicodeDecodeError, LookupError):
            continue
    return normalize_text(data.decode("utf-8", errors="replace"))
