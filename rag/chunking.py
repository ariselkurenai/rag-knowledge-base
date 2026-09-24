"""文本切片：中文感知的递归切分 + 碎片合并

相比固定窗口切分：
- 优先在段落、句号、分号等自然边界断开，保持语义完整；
- 小于 min_chunk_size 的碎片并入相邻块，避免产生无检索价值的碎块；
- 每个块记录来源页码，供答案引用溯源。
"""

import re

from .config import settings
from .schemas import Chunk, PageContent

# 递归分隔符：从粗到细
_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]


def _split_by_separators(text: str, separators: list[str]) -> list[str]:
    """按分隔符层级递归切分，直到每段不超过 chunk_size"""
    if len(text) <= settings.chunk_size or not separators:
        return [text] if text.strip() else []

    sep, rest = separators[0], separators[1:]
    if sep == "":
        # 兜底：硬切
        return [text[i:i + settings.chunk_size]
                for i in range(0, len(text), settings.chunk_size - settings.chunk_overlap)]

    parts = [p for p in text.split(sep) if p.strip()]
    if len(parts) <= 1:
        return _split_by_separators(text, rest)

    result: list[str] = []
    for part in parts:
        if len(part) <= settings.chunk_size:
            result.append(part)
        else:
            result.extend(_split_by_separators(part, rest))
    return result


def _merge_with_overlap(pieces: list[str]) -> list[str]:
    """把切出的段落按 chunk_size 聚合为块，并加入 overlap（头部回看）"""
    chunks: list[str] = []
    buffer = ""

    def _overlap_head(text: str) -> str:
        back = min(settings.chunk_overlap, len(text))
        return text[-back:]

    for piece in pieces:
        if buffer and len(buffer) + len(piece) + 1 > settings.chunk_size:
            chunks.append(buffer.strip())
            buffer = _overlap_head(buffer) + piece
        else:
            buffer = f"{buffer}{'。' if buffer and not buffer.endswith(('。', '！', '？', '\n')) else ''}{piece}" \
                if buffer else piece
    if buffer.strip():
        chunks.append(buffer.strip())
    return chunks


def _merge_tiny(chunks: list[str]) -> list[str]:
    """把过短的块并入前一块"""
    if not chunks:
        return []
    merged = [chunks[0]]
    for c in chunks[1:]:
        if len(merged[-1]) < settings.min_chunk_size or len(c) < settings.min_chunk_size:
            merged[-1] = merged[-1] + c
        else:
            merged.append(c)
    return merged


def split_pages(pages: list[PageContent], doc_id: str, filename: str) -> list[Chunk]:
    """逐页切分并合并碎片，输出带元数据的 Chunk 列表"""
    chunks: list[Chunk] = []
    for page in pages:
        pieces = _split_by_separators(page.text, _SEPARATORS)
        page_chunks = _merge_tiny(_merge_with_overlap(pieces))
        for idx, content in enumerate(page_chunks):
            if not content.strip():
                continue
            chunks.append(Chunk(
                chunk_id=f"{doc_id}:{len(chunks)}",
                doc_id=doc_id,
                filename=filename,
                page=page.page,
                chunk_index=len(chunks),
                content=content,
            ))
    return chunks


def chunk_stats(chunks: list[Chunk]) -> dict:
    """切片统计（入库返回 & 论文数据集描述用）"""
    lengths = [len(c.content) for c in chunks]
    return {
        "chunks": len(chunks),
        "min_len": min(lengths) if lengths else 0,
        "max_len": max(lengths) if lengths else 0,
        "avg_len": round(sum(lengths) / len(lengths), 1) if lengths else 0,
    }


_CITATION_RE = re.compile(r"\[(\d+)\]")


def parse_citations(answer: str) -> set[int]:
    """解析答案正文中出现的引用编号 [n]"""
    return {int(m) for m in _CITATION_RE.findall(answer)}
