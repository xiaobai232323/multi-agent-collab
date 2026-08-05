#!/usr/bin/env python3
"""多模型协作 — DeepSeek + 千问"""

import os, sys, json, shutil, platform, uuid, re, logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import streamlit as st
from usage_tracker import tracker

_log = logging.getLogger("multi_agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if platform.system() == "Windows":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

def _env(k):
    v = os.getenv(k)
    if v: return v
    if platform.system() == "Windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as r:
                v, _ = winreg.QueryValueEx(r, k)
                if v: os.environ[k] = v; return v
        except FileNotFoundError: pass
    return ""

BASE = Path(__file__).parent
HD = BASE / "history"; HD.mkdir(parents=True, exist_ok=True)
UP = BASE / "uploads"; UP.mkdir(parents=True, exist_ok=True)

def _safe_id(name: str) -> str:
    """消毒会话 ID，防止路径遍历"""
    s = re.sub(r"[^0-9A-Za-z _-]", "_", name.strip())[:64]
    return s or "default"

@st.cache_resource
def init_ds():
    from openai import OpenAI
    return OpenAI(api_key=_env("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com/v1")

@st.cache_resource
def init_qw():
    import dashscope
    dashscope.api_key = _env("DASHSCOPE_API_KEY")

def ds_ask(msgs):
    if tracker.warning_level() == "critical":
        raise RuntimeError("预算已达上限，已阻止 API 调用。请在侧栏调整预算设置。")
    try:
        r = init_ds().chat.completions.create(model="deepseek-chat", messages=msgs, temperature=0.7, max_tokens=4096, timeout=60)
        tracker.record("deepseek-chat", r.usage.prompt_tokens, r.usage.completion_tokens)
        return r.choices[0].message.content
    except RuntimeError: raise
    except Exception as e:
        msg = str(e)
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            raise RuntimeError("DeepSeek 请求超时，请重试")
        if "rate" in msg.lower() or "429" in msg:
            raise RuntimeError("DeepSeek 请求过于频繁，请稍后重试")
        if "auth" in msg.lower() or "401" in msg or "403" in msg:
            raise RuntimeError("DeepSeek API Key 无效，请检查环境变量 DEEPSEEK_API_KEY")
        raise RuntimeError(f"DeepSeek 调用失败: {msg[:200]}")

def qw_ask(msgs):
    if tracker.warning_level() == "critical":
        raise RuntimeError("预算已达上限，已阻止 API 调用。请在侧栏调整预算设置。")
    from dashscope import Generation
    try:
        r = Generation.call(model="qwen-max", messages=msgs, result_format="message")
        if r.status_code == 200:
            u = r.usage; tracker.record("qwen-max", u.input_tokens, u.output_tokens)
            return r.output.choices[0].message.content
        code = getattr(r, 'status_code', '?')
        if code == 429: raise RuntimeError("千问请求过于频繁，请稍后重试")
        if code in (401, 403): raise RuntimeError("千问 API Key 无效，请检查环境变量 DASHSCOPE_API_KEY")
        raise RuntimeError(f"千问调用失败 (code={code}): {r.message}")
    except RuntimeError: raise
    except Exception as e:
        raise RuntimeError(f"千问网络错误: {e}")

def qw_see(img, prompt):
    if tracker.warning_level() == "critical":
        raise RuntimeError("预算已达上限，已阻止 API 调用。请在侧栏调整预算设置。")
    from dashscope import MultiModalConversation
    p = str(Path(img).resolve())
    if not os.path.exists(p): return "图片不存在"
    try:
        r = MultiModalConversation.call(model="qwen-vl-max", messages=[{
            "role": "user", "content": [{"image": f"file://{p}"}, {"text": prompt or "请详细描述这张图片"}]
        }])
        if r.status_code == 200:
            u = r.usage; tracker.record("qwen-vl-max", u.input_tokens, u.output_tokens, image_count=1)
            c = r.output.choices[0].message.content
            return "".join(i.get("text","") if isinstance(i,dict) else str(i) for i in c) if isinstance(c,list) else c
        code = getattr(r, 'status_code', '?')
        if code == 429: raise RuntimeError("千问视觉请求过于频繁，请稍后重试")
        raise RuntimeError(f"千问视觉调用失败 (code={code}): {r.message}")
    except RuntimeError: raise
    except Exception as e:
        raise RuntimeError(f"千问视觉网络错误: {e}")

def list_sessions():
    ss = []
    for f in sorted(HD.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            d = json.loads(f.read_text("utf-8"))
            ss.append({"id":f.stem,"title":d.get("title",f.stem),"time":d.get("updated",""),"n":len(d.get("messages",[]))})
        except: pass
    return ss or [{"id":"default","title":"默认会话","time":"","n":0}]

def load_msgs(sid):
    f = HD / f"{_safe_id(sid)}.json"
    return json.loads(f.read_text("utf-8")).get("messages",[]) if f.exists() else []

def save_msgs(sid, title, msgs):
    safe = _safe_id(sid)
    tmp = HD / f"{safe}.json.tmp"
    tmp.write_text(json.dumps(
        {"title":title,"updated":datetime.now().strftime("%m-%d %H:%M"),"messages":msgs},
        ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(HD / f"{safe}.json")  # 原子替换，防止并发写损坏

def del_session(sid):
    (HD / f"{_safe_id(sid)}.json").unlink(missing_ok=True)

def _h(msgs):
    return [{"role":m["role"],"content":m["content"]} for m in msgs]

def run_review(msg, prev):
    msgs = _h(prev) + [{"role":"user","content":msg}]
    # 并行调用两模型，减少等待时间
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(ds_ask, msgs)
        f2 = ex.submit(qw_ask, msgs)
        a1 = f1.result(timeout=120)
        a2 = f2.result(timeout=120)
    # 审查也可并行
    with ThreadPoolExecutor(max_workers=2) as ex:
        f3 = ex.submit(ds_ask, [{"role":"system","content":"严苛审稿，从准确性/完整性/逻辑性/可读性评分指正。"},{"role":"user","content":f"审查:\n{a2}"}])
        f4 = ex.submit(qw_ask, [{"role":"system","content":"严苛审稿，从准确性/完整性/逻辑性/可读性评分指正。"},{"role":"user","content":f"审查:\n{a1}"}])
        r1 = f3.result(timeout=120)
        r2 = f4.result(timeout=120)
    f = ds_ask([{"role":"system","content":"综合两份回答和审查意见，输出最优答案。"},{"role":"user","content":f"DeepSeek:\n{a1}\n\n千问:\n{a2}\n\nDS审千问:\n{r1}\n\n千问审DS:\n{r2}"}])
    return f"### 🤖 DeepSeek\n\n{a1}\n\n---\n\n### 🧠 千问\n\n{a2}\n\n---\n\n### 🔍 DeepSeek 审查千问\n\n{r1}\n\n### 🔍 千问审查 DeepSeek\n\n{r2}\n\n---\n\n### ⭐ 综合最优\n\n{f}"

def run_relay(msg, img, prev):
    desc = qw_see(img, msg or "请详细描述这张图片")
    reason = ds_ask([{"role":"system","content":"基于视觉描述深度分析。"},{"role":"user","content":f"视觉描述:\n'''\n{desc}\n'''\n\n用户问题:{msg or '请分析'}"}])
    return f"### 👁️ 千问视觉分析\n\n{desc}\n\n---\n\n### 🧠 DeepSeek 深度推理\n\n{reason}"

def run_debate(msg, prev):
    log = []
    s = ds_ask([{"role":"system","content":"辩论:陈述观点。"},{"role":"user","content":msg}])
    log.append(("DeepSeek",s)); consensus = None
    for r in range(1,4):
        txt = "\n\n".join(f"[{n}]:{t}" for n,t in log)
        qr = qw_ask([{"role":"system","content":"辩论:指正、承认、补充。"},{"role":"user","content":f"{txt}\n\n回应:"}])
        log.append(("千问",qr))
        ck = qw_ask([{"role":"system","content":"判断是否一致。是->CONSENSUS:结论，否->DISAGREE:分歧"},{"role":"user","content":"\n".join(f"[{n}]:{t[:200]}" for n,t in log)}])
        if ck.startswith("CONSENSUS:"): consensus = ck.replace("CONSENSUS:","").strip(); break
        dr = ds_ask([{"role":"system","content":"辩论:回应质疑，推进收敛。"},{"role":"user","content":f"{txt}\n\n回应:"}])
        log.append(("DeepSeek",dr))
    if not consensus: consensus = ds_ask([{"role":"system","content":"综合辩论给结论。"},{"role":"user","content":"\n\n".join(f"[{n}]:{t}" for n,t in log)}])
    return f"### ⚔️ 辩论\n\n" + "\n\n".join(f"**{n}**:{t[:150]}..." for n,t in log) + f"\n\n---\n\n### 📋 结论\n\n{consensus}"

# ════════════════════════════════════════
st.set_page_config(page_title="多模型协作", page_icon="🤝", layout="wide")

if "sid" not in st.session_state:
    st.session_state.sid = "default"

init_qw()

with st.sidebar:
    st.markdown("## 🤝 多模型协作")
    st.caption("DeepSeek + 千问")

    st.divider()
    st.subheader("💬 会话")
    sessions = list_sessions()
    sids = [s["id"] for s in sessions]
    idx = sids.index(st.session_state.sid) if st.session_state.sid in sids else 0
    sel = st.selectbox("历史", sids, index=idx, label_visibility="collapsed")

    c1, c2 = st.columns(2)
    with c1: new_name = st.text_input("新会话", placeholder="名称...", label_visibility="collapsed")
    with c2:
        if st.button("➕ 新建", use_container_width=True):
            if new_name.strip():
                sid = _safe_id(new_name.strip())
                save_msgs(sid, new_name.strip(), [])
                st.session_state.sid = sid
                st.rerun()

    c3, c4 = st.columns(2)
    with c3:
        if st.button("🗑 删除", use_container_width=True, type="secondary"):
            if st.session_state.sid != "default":
                del_session(st.session_state.sid)
                st.session_state.sid = "default"
                st.rerun()
    with c4:
        if st.button("↺ 清空", use_container_width=True):
            save_msgs(st.session_state.sid, "清空", [])
            st.rerun()

    if sel != st.session_state.sid:
        st.session_state.sid = sel
        st.rerun()

    st.divider()
    st.subheader("⚙️ 模式")
    mode = st.radio("mode", ["🔍 交叉审查（推荐）","🏃 接力看图","⚔️ 辩论","🤖 仅 DeepSeek","🧠 仅千问"], label_visibility="collapsed")
    mode_map = {"🔍 交叉审查（推荐）":"review","🏃 接力看图":"relay","⚔️ 辩论":"debate","🤖 仅 DeepSeek":"deepseek","🧠 仅千问":"qwen"}
    cm = mode_map[mode]

    st.divider()
    st.subheader("🖼️ 图片")
    upf = st.file_uploader("拖拽图片", type=["png","jpg","jpeg","gif","webp","bmp"], label_visibility="collapsed")
    img_path = None
    if upf:
        if upf.size > 10 * 1024 * 1024:
            st.error("图片过大，请上传 10MB 以内的文件")
        else:
            suffix = Path(upf.name).suffix or ".png"
            safe = f"{uuid.uuid4().hex}{suffix}"
            tmp = UP / (safe + ".tmp")
            tmp.write_bytes(upf.getvalue())
            tmp.replace(UP / safe)  # 原子写入
            img_path = str(UP / safe)
            st.caption(f"📎 {upf.name}")

    st.divider()
    st.subheader("💰 用量")
    td = tracker.today(); md = tracker.month(); b = tracker.budget()
    mpct = (md["cost"]/b["monthly"]*100) if b["monthly"]>0 else 0
    wl = tracker.warning_level()

    if wl == "critical":
        st.error(f"⚠️ 已达预算上限！今日 ¥{td['cost']:.3f}")
    elif wl == "warn":
        st.warning(f"⚡ 已用 {mpct:.0f}%，接近预算")

    st.metric("本月花费", f"¥{md['cost']:.3f}", f"{mpct:.0f}% / ¥{b['monthly']:.0f}")
    st.metric("今日花费", f"¥{td['cost']:.3f}")
    st.metric("本月调用", f"{md['calls']} 次")

    with st.expander("⚙️ 预算设置"):
        nm = st.number_input("月预算 (元)", min_value=1.0, max_value=500.0, value=b["monthly"], step=1.0)
        nw = st.slider("预警百分比", min_value=50, max_value=100, value=b["warning_pct"], step=5)
        nd = st.number_input("日限额 (元)", min_value=0.5, max_value=100.0, value=b.get("daily_limit",2.0), step=0.5)
        if st.button("💾 保存设置", use_container_width=True):
            tracker.prices["budget"] = {"monthly":nm,"warning_pct":nw,"daily_limit":nd}
            from usage_tracker import _save_json, BUDGET_FILE
            _save_json(BUDGET_FILE, tracker.prices)
            st.success("已保存！")
            st.rerun()

    with st.expander("📋 最近调用"):
        for c in tracker.recent_calls(5):
            ct = c["time"][11:19]
            st.caption(f"{ct} | {c['model']} | ¥{c['cost']:.4f} | {c['input_tokens']}+{c['output_tokens']}tk")

# ── 主区域 ──
st.title("🤝 多模型协作")

for m in load_msgs(st.session_state.sid):
    if m["role"] == "user":
        with st.chat_message("user"): st.write(m["content"])
    else:
        with st.chat_message("assistant"):
            tag = m.get("metadata",{}).get("model","")
            if tag: st.caption(f"[{tag}]")
            st.markdown(m["content"])

prompt = st.chat_input("输入消息... (Enter 发送)")

if prompt:
    with st.chat_message("user"):
        disp = prompt
        if img_path: disp += f"\n\n📎 {Path(img_path).name}"
        st.write(disp)

    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            msgs = load_msgs(st.session_state.sid)
            prev = msgs
            msgs.append({"role":"user","content":prompt + (f"\n📎 {Path(img_path).name}" if img_path else "")})

            try:
                if cm == "review": ans = run_review(prompt, prev); tag = "交叉审查"
                elif cm == "relay": ans = run_relay(prompt, img_path or "", prev); tag = "接力协作"
                elif cm == "debate": ans = run_debate(prompt, prev); tag = "辩论"
                elif cm == "deepseek": ans = ds_ask(_h(prev)+[{"role":"user","content":prompt}]); tag = "DeepSeek"
                elif cm == "qwen":
                    if img_path: ans = qw_see(img_path, prompt); tag = "千问视觉"
                    else: ans = qw_ask(_h(prev)+[{"role":"user","content":prompt}]); tag = "千问"
                else: ans = run_review(prompt, prev); tag = "交叉审查"
                st.caption(f"[{tag}]")
                st.markdown(ans)
            except Exception as e:
                err_id = uuid.uuid4().hex[:8]
                _log.exception("Unhandled error id=%s", err_id)
                st.error(f"服务异常（错误 ID: {err_id}），请稍后重试")
                ans = f"系统错误 [{err_id}]"; tag = "error"

        msgs.append({"role":"assistant","content":ans,"metadata":{"model":tag}})
        save_msgs(st.session_state.sid, msgs[0]["content"][:30] if msgs else "新对话", msgs)
