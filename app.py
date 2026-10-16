import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import time
import streamlit as st

from config import settings
from core.agent import LiteratureAgent
from sources import ArxivSource, PubMedSource, SemanticScholarSource

st.set_page_config(page_title="文献智能检索 Agent", page_icon="📚", layout="wide")

st.title("📚 文献智能检索 Agent")
st.caption("Planner → Retrieve → Rerank → Read → Reflect → Synthesize  |  LLM via opencode")

# ---------- 侧边栏 ----------
with st.sidebar:
    st.header("配置")
    question = st.text_area("研究问题", value="", height=100,
                            placeholder="e.g. What are recent approaches to "
                            "retrieval-augmented generation for long-context LLMs?")
    max_rounds = st.slider("最大反思轮数", 1, 3, settings.max_reflect_rounds)
    k_per_src = st.number_input("每源候选数", 3, 15, settings.top_k_per_source)
    final_k = st.number_input("最终 Top-K", 5, 20, settings.final_top_k)

    st.divider()
    st.subheader("数据源")
    use_arxiv = st.checkbox("arXiv", True)
    use_pubmed = st.checkbox("PubMed", True)
    use_s2 = st.checkbox("Semantic Scholar", True)

    st.divider()
    st.caption(f"LLM: `{settings.llm_model}`")
    run_btn = st.button("🚀 开始检索", type="primary", disabled=not question)

# ---------- 主区 ----------
if "state" not in st.session_state:
    st.session_state.state = None
if "timeline" not in st.session_state:
    st.session_state.timeline = []

EXAMPLES = [
    "What are recent approaches to retrieval-augmented generation for long-context LLMs?",
    "How does fine-tuning affect hallucination in large language models?",
    "What methods improve chain-of-thought reasoning in medical QA?",
]


def stage_detail(d: dict, stage: str) -> str:
    if stage == "planner":
        return f"{len(d.get('subqueries', []))} 子查询"
    if stage == "retrieve":
        return f"+{d.get('new', 0)} 篇"
    if stage == "reranker":
        return f"Top-{len(d.get('top', []))}"
    if stage == "reader":
        return f"{d.get('notes', 0)} 笔记"
    if stage == "reflector":
        return "充分" if d.get("sufficient") else "不足"
    if stage == "synthesizer":
        return f"{d.get('length', 0)} 字符"
    return ""

if not run_btn and st.session_state.state is None:
    st.markdown("### 示例问题")
    for ex in EXAMPLES:
        if st.button(ex, key=ex):
            st.session_state.pending_question = ex
            st.rerun()
    st.stop()

if run_btn:
    st.session_state.timeline = []
    st.session_state.state = None

    srcs = []
    if use_arxiv: srcs.append(ArxivSource())
    if use_pubmed: srcs.append(PubMedSource())
    if use_s2: srcs.append(SemanticScholarSource())
    if not srcs:
        st.error("请至少选择一个数据源")
        st.stop()

    settings.max_reflect_rounds = max_rounds
    settings.top_k_per_source = k_per_src
    settings.final_top_k = final_k

    agent = LiteratureAgent(sources=srcs, settings=settings)
    t0 = time.time()

    with st.status("🔍 Agent 运行中...", expanded=True) as status:
        def on_step(event):
            stage = event["stage"]
            st.session_state.timeline.append(event)
            if event.get("status") == "start":
                st.write(f"⏳ **{stage}** ...")
            else:
                d = event.get("data", {})
                if stage == "planner":
                    sqs = d.get("subqueries", [])
                    st.write(f"✅ **planner** — 拆解出 {len(sqs)} 个子查询")
                    for sq in sqs:
                        st.write(f"   • `{sq['text']}` → {sq['sources']}")
                elif stage == "retrieve":
                    st.write(f"✅ **retrieve** (R{d.get('round',1)}) — "
                             f"新增 {d.get('new',0)} / 共 {d.get('total',0)} 篇")
                elif stage == "reranker":
                    top = d.get("top", [])
                    st.write(f"✅ **reranker** — 保留 Top-{len(top)}")
                elif stage == "reader":
                    st.write(f"✅ **reader** — 生成 {d.get('notes',0)} 条笔记")
                elif stage == "reflector":
                    suf = d.get("sufficient")
                    st.write(f"✅ **reflector** — 证据{'充分' if suf else '不足'}"
                             f" | gaps: {len(d.get('gaps',[]))}"
                             f" | conflicts: {len(d.get('conflicts',[]))}")
                elif stage == "synthesizer":
                    st.write(f"✅ **synthesizer** — 输出 {d.get('length',0)} 字符")

        try:
            state = agent.run(question, on_step=on_step)
            st.session_state.state = state
            elapsed = time.time() - t0
            status.update(label=f"✅ 完成 ({elapsed:.1f}s)", state="complete")
        except Exception as e:
            status.update(label=f"❌ 出错: {e}", state="error")
            st.error(e)
            st.stop()

state = st.session_state.state
if state is None:
    st.stop()

# ---------- 结果展示 ----------
tab_timeline, tab_papers, tab_review = st.tabs(
    ["📜 时间线", "📄 论文", "📝 综述"]
)

with tab_timeline:
    for ev in st.session_state.timeline:
        if ev.get("status") == "start":
            continue
        stage = ev["stage"]
        d = ev.get("data", {})
        with st.expander(f"{stage} — {stage_detail(d, stage)}", expanded=False):
            st.json(d, expanded=False)

with tab_papers:
    if not state.papers:
        st.info("未检索到论文")
    else:
        display = state.scored if state.scored else state.papers
        cols = st.columns(3)
        for i, item in enumerate(display):
            if hasattr(item, "paper"):
                p, score, reason = item.paper, item.score, item.reason
            else:
                p, score, reason = item, 0, ""
            with cols[i % 3]:
                badge = f" `score={score}`" if score else ""
                st.markdown(f"**[{p.source}]** `[{p.paper_id}]`{badge}")
                st.markdown(f"**{p.title}**")
                st.caption(f"{', '.join(p.authors[:4])}  |  {p.year or '?'}")
                if p.url:
                    st.markdown(f"[link]({p.url})")
                if reason:
                    st.caption(reason)
                with st.expander("摘要"):
                    st.write(p.abstract[:500])

with tab_review:
    if state.final_output:
        st.markdown(state.final_output)
    else:
        st.info("无综述输出")
