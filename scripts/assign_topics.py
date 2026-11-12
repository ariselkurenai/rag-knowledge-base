"""示例案例分归专题：把 docs/sizheng 的案例归入两个种子专题

用法：python scripts/assign_topics.py
可重复运行（幂等）：按文件名匹配活动案例，专题名从 topics 表按名称解析，
不存在的案例跳过，归属已正确的无操作。适用于已入库但未归属的案例。

映射关系：
- 理想信念与人生价值：张桂梅 / 民法典好人条款 / 十八洞村精准扶贫
                        / 黄文秀脱贫攻坚 / 张富清深藏功名
- 科技强国与绿色发展：塞罕坝 / 嫦娥探月 / 高质量发展 / 南仁东天眼 / 库布其治沙
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from rag.database import SessionLocal, Topic  # noqa: E402
from rag.pipeline import get_pipeline  # noqa: E402

# 示例文件名（docs/sizheng）→ 专题名称
SAMPLE_TOPIC_MAP = {
    "理想信念与人生价值": [
        "01-zhangguimi-huaping-nvgao.md",
        "02-minfadian-haoren-tiaokuan.md",
        "05-shibadong-cun-jingzhun-fupin.md",
        "07-huangwenxiu-tuopin-yongpan-shengming.docx",
        "08-zhangfuqing-shencang-gongming-chuxin.docx",
    ],
    "科技强国与绿色发展": [
        "03-saihanba-linhai.md",
        "04-chang-e-tan-yue.md",
        "06-gaozhiliang-fazhan-xingeju.md",
        "09-nanrendong-zhongguo-tianyan.docx",
        "10-kubuqi-shamo-zhili.docx",
    ],
}


def main() -> None:
    db = SessionLocal()
    try:
        topics = {t.name: t.id for t in db.scalars(select(Topic)).all()}
        missing = [n for n in SAMPLE_TOPIC_MAP if n not in topics]
        if missing:
            print(f"⚠️ 专题不存在（先运行 scripts/init_db.py）：{missing}")
            return
    finally:
        db.close()

    registry = get_pipeline().registry
    docs = {d.filename: d for d in registry.list_active()}
    assigned = 0
    for topic_name, filenames in SAMPLE_TOPIC_MAP.items():
        for fn in filenames:
            doc = docs.get(fn)
            if not doc:
                print(f"⏭ 未入库，跳过：{fn}")
                continue
            if doc.topic_id == topics[topic_name]:
                print(f"✓ 已归属：{fn} → {topic_name}")
                continue
            if registry.set_topic(doc.doc_id, topics[topic_name]):
                assigned += 1
                print(f"✅ {fn} → {topic_name}")
            else:
                print(f"❌ 归属失败：{fn}")
    print(f"\n📊 本次新归属 {assigned} 个案例")


if __name__ == "__main__":
    main()
