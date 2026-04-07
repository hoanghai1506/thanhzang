import streamlit as st
import sqlite3
import random
import time
import pandas as pd
from gtts import gTTS
from pypinyin import pinyin, Style
from deep_translator import GoogleTranslator
from io import BytesIO
import base64
import json
import uuid
import streamlit.components.v1 as components

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Thanh Giang cố lên", page_icon="🌸", layout="centered")
st.markdown("""
    <style>
    .stApp { background-color: #FFF0F5; }
    h1, h2, h3 { color: #FF69B4; font-family: 'Arial', sans-serif; text-align: center;}
    .word-card { background-color: white; padding: 30px; border-radius: 20px; box-shadow: 0px 4px 15px rgba(0,0,0,0.1); text-align: center; margin-bottom: 20px;}
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1>✿ Thanh Giang cố lên ✿</h1>", unsafe_allow_html=True)

def init_db():
    conn = sqlite3.connect('chinese_web.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS vocab 
                    (id INTEGER PRIMARY KEY, hanzi TEXT, pinyin TEXT, meaning TEXT)''')
    conn.commit(); conn.close()
init_db()

# --- HÀM CACHE ÂM THANH (GIẢI QUYẾT TẬN GỐC VẤN ĐỀ LAG) ---
@st.cache_data(show_spinner=False)
def get_cached_audio_b64(text):
    try:
        tts = gTTS(text=text, lang='zh-cn')
        fp = BytesIO()
        tts.write_to_fp(fp)
        return base64.b64encode(fp.getvalue()).decode()
    except:
        return ""

# --- HÀM PHÁT ÂM (SỬ DỤNG CACHE) ---
def render_audio(text, auto_play_on_desktop=True):
    b64 = get_cached_audio_b64(text)
    if not b64: return
    
    uid = str(uuid.uuid4()).replace("-", "")
    html = f"""
    <div style="text-align: center; margin-top: 10px;">
        <audio id="audio_{uid}" src="data:audio/mp3;base64,{b64}"></audio>
        <button onclick="document.getElementById('audio_{uid}').play()" 
                style="background-color: #FF69B4; color: white; border: none; padding: 12px 30px; border-radius: 50px; font-size: 18px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%;">
            🔊 BẤM ĐỂ NGHE LẠI
        </button>
        <script>
            if("{str(auto_play_on_desktop).lower()}" === "true") {{
                document.getElementById('audio_{uid}').play().catch(e => console.log('Chờ người dùng bấm (iOS)'));
            }}
        </script>
    </div>
    """
    components.html(html, height=75)

# --- BỘ NHỚ TRẠNG THÁI ---
if 'selected_ids' not in st.session_state: st.session_state.selected_ids = []
if 'flash_word' not in st.session_state: st.session_state.flash_word = None
if 'quiz_word' not in st.session_state: st.session_state.quiz_word = None
if 'quiz_options' not in st.session_state: st.session_state.quiz_options = []
if 'edit_id' not in st.session_state: st.session_state.edit_id = None

t_add, t_manage, t_shadow, t_flash, t_quiz = st.tabs(["📝 Thêm", "📚 Quản Lý", "🗣 Luyện Nói", "🎴 Flashcard", "🎯 Trắc Nghiệm"])

# ==========================================
# TAB 1: THÊM TỪ
# ==========================================
with t_add:
    st.markdown("<h3>TRA CỨU VÀ THÊM TỪ THỦ CÔNG</h3>", unsafe_allow_html=True)
    hz_input = st.text_input("Nhập chữ Hán (vd: 老师):", key="in_hz")
    if st.button("Tra cứu tự động ✧", use_container_width=True):
        if hz_input:
            st.session_state.temp_py = " ".join([i[0] for i in pinyin(hz_input, style=Style.TONE)])
            try: st.session_state.temp_mean = GoogleTranslator(source='zh-CN', target='vi').translate(hz_input)
            except: st.session_state.temp_mean = "Lỗi mạng"
            st.rerun()

    py_input = st.text_input("Pinyin:", value=st.session_state.get('temp_py', ''))
    m_input = st.text_input("Nghĩa tiếng Việt:", value=st.session_state.get('temp_mean', ''))
    
    if st.button("Lưu Vào Kho", use_container_width=True):
        if hz_input and py_input and m_input:
            conn = sqlite3.connect('chinese_web.db')
            conn.execute("INSERT INTO vocab (hanzi, pinyin, meaning) VALUES (?, ?, ?)", (hz_input, py_input, m_input))
            conn.commit(); conn.close()
            st.session_state.temp_py = ""; st.session_state.temp_mean = ""
            st.success("Đã lưu thành công!")
            time.sleep(1); st.rerun()

    st.divider()
    
    # THÊM HÀNG LOẠT TỪ EXCEL
    st.markdown("<h3>THÊM HÀNG LOẠT TỪ EXCEL</h3>", unsafe_allow_html=True)
    st.info("App sẽ chỉ đọc Cột 1 (Chữ Hán) và TỰ ĐỘNG tra cứu Pinyin + Nghĩa cho bạn.")
    
    uploaded_file = st.file_uploader("Kéo thả file Excel/CSV vào đây", type=["xlsx", "csv"])
    
    if uploaded_file is not None:
        if st.button("🚀 Bắt đầu nạp & Tự động dịch", use_container_width=True):
            try:
                if uploaded_file.name.endswith('.csv'): df = pd.read_csv(uploaded_file)
                else: df = pd.read_excel(uploaded_file)
                
                conn = sqlite3.connect('chinese_web.db')
                cursor = conn.cursor()
                success_count = 0
                total_rows = len(df)
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for index, row in df.iterrows():
                    hz = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                    if hz:
                        py = " ".join([i[0] for i in pinyin(hz, style=Style.TONE)])
                        try: mn = GoogleTranslator(source='zh-CN', target='vi').translate(hz)
                        except: mn = "Lỗi mạng"
                        cursor.execute("INSERT INTO vocab (hanzi, pinyin, meaning) VALUES (?, ?, ?)", (hz, py, mn))
                        success_count += 1
                    
                    progress_percent = int(((index + 1) / total_rows) * 100)
                    progress_bar.progress(progress_percent)
                    status_text.text(f"Đang xử lý: {index + 1}/{total_rows} từ ({progress_percent}%)")
                        
                conn.commit(); conn.close()
                st.success(f"Tuyệt vời! Đã nạp thành công {success_count} từ vựng. 🌸")
                time.sleep(2); st.rerun()
            except Exception as e:
                st.error(f"Có lỗi xảy ra. Chi tiết: {e}")

# ==========================================
# TAB 2: QUẢN LÝ
# ==========================================
with t_manage:
    st.markdown("<h3>KHO TỪ VỰNG</h3>", unsafe_allow_html=True)
    
    conn = sqlite3.connect('chinese_web.db')
    total_words = conn.execute("SELECT COUNT(*) FROM vocab").fetchone()[0]
    st.info(f"📚 Tổng số từ vựng hiện có trong kho: **{total_words}** từ")
    
    search_term = st.text_input("🔍 Tìm kiếm từ vựng (Nhập Hán tự, Pinyin hoặc Nghĩa):", "")
    
    if search_term:
        query = "SELECT * FROM vocab WHERE hanzi LIKE ? OR pinyin LIKE ? OR meaning LIKE ?"
        params = (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%")
        rows = conn.execute(query, params).fetchall()
    else:
        rows = conn.execute("SELECT * FROM vocab").fetchall()
        
    conn.close()

    if not rows: st.warning("Không tìm thấy từ vựng nào phù hợp!")
    
    for r in rows:
        c1, c2, c3, c4, c5 = st.columns([0.5, 3.5, 1, 1, 1])
        is_checked = c1.checkbox("", key=f"chk_{r[0]}", value=(r[0] in st.session_state.selected_ids))
        if is_checked and r[0] not in st.session_state.selected_ids: st.session_state.selected_ids.append(r[0])
        elif not is_checked and r[0] in st.session_state.selected_ids: st.session_state.selected_ids.remove(r[0])
            
        c2.write(f"**{r[1]}** [{r[2]}] - {r[3]}")
        
        if c3.button("🔊", key=f"play_{r[0]}"): render_audio(r[1], auto_play_on_desktop=True)
        if c4.button("Sửa", key=f"edit_{r[0]}"): st.session_state.edit_id = r[0]
        if c5.button("Xóa", key=f"del_{r[0]}"):
            conn = sqlite3.connect('chinese_web.db')
            conn.execute("DELETE FROM vocab WHERE id=?", (r[0],))
            conn.commit(); conn.close(); st.rerun()

        if st.session_state.edit_id == r[0]:
            new_mean = st.text_input("Nhập nghĩa mới:", value=r[3], key=f"new_m_{r[0]}")
            if st.button("Lưu thay đổi", key=f"save_{r[0]}"):
                conn = sqlite3.connect('chinese_web.db')
                conn.execute("UPDATE vocab SET meaning=? WHERE id=?", (new_mean, r[0]))
                conn.commit(); conn.close()
                st.session_state.edit_id = None; st.rerun()
        st.divider()

# ==========================================
# TAB 3: LUYỆN NÓI (SHADOWING)
# ==========================================
with t_shadow:
    st.markdown("<h3>LUYỆN NÓI (SHADOWING)</h3>", unsafe_allow_html=True)
    if not st.session_state.selected_ids:
        st.warning("Hãy sang tab Quản Lý và chọn ít nhất 1 từ nhé!")
    else:
        conn = sqlite3.connect('chinese_web.db')
        ids_str = ','.join(map(str, st.session_state.selected_ids))
        shadow_words = conn.execute(f"SELECT * FROM vocab WHERE id IN ({ids_str})").fetchall()
        conn.close()

        playlist = []
        for w in shadow_words:
            # SỬ DỤNG HÀM CACHE ĐỂ KHÔNG BỊ CHẬM KHI TẠO DANH SÁCH
            b64 = get_cached_audio_b64(w[1]) 
            playlist.append({"hanzi": w[1], "pinyin": w[2], "mean": w[3], "audio": b64})
        
        js_playlist = json.dumps(playlist)
        
        html_player = f"""
        <div style="text-align: center; background: white; padding: 30px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); font-family: sans-serif;">
            <h1 id="p_hanzi" style="font-size: 60px; color: #FF69B4; margin-bottom: 10px;">Sẵn sàng!</h1>
            <h3 id="p_pinyin" style="color: #34495e; margin: 5px 0;"></h3>
            <p id="p_mean" style="color: gray; font-style: italic; font-size: 18px; margin-bottom: 20px;"></p>

            <div style="display: flex; justify-content: center; gap: 15px; margin-top: 20px;">
                <button id="btn_play" onclick="startPlay()" style="background: #27ae60; color: white; border: none; padding: 15px; border-radius: 10px; font-size: 18px; font-weight: bold; width: 100%;">▶ BẮT ĐẦU</button>
                <button id="btn_stop" onclick="stopPlay()" style="background: #e74c3c; color: white; border: none; padding: 15px; border-radius: 10px; font-size: 18px; font-weight: bold; width: 100%; display: none;">■ DỪNG LẠI</button>
            </div>
        </div>
        
        <script>
            const playlist = {js_playlist};
            let idx = 0;
            let isPlaying = false;
            let audioCtx = null;
            let currentSource = null;
            let timeoutId = null;

            async function startPlay() {{
                if(isPlaying) return;
                isPlaying = true;
                document.getElementById('btn_play').style.display = 'none';
                document.getElementById('btn_stop').style.display = 'inline-block';
                
                if(!audioCtx) {{ audioCtx = new (window.AudioContext || window.webkitAudioContext)(); }}
                if(audioCtx.state === 'suspended') audioCtx.resume();
                playLoop();
            }}

            function stopPlay() {{
                isPlaying = false;
                if(currentSource) currentSource.stop();
                clearTimeout(timeoutId);
                document.getElementById('btn_play').style.display = 'inline-block';
                document.getElementById('btn_stop').style.display = 'none';
                document.getElementById('btn_play').innerText = "▶ PHÁT TIẾP";
            }}

            async function playLoop() {{
                if(!isPlaying) return;
                if(idx >= playlist.length) {{
                    document.getElementById('p_hanzi').innerText = "Hoàn thành! 🌸";
                    document.getElementById('p_pinyin').innerText = "";
                    document.getElementById('p_mean').innerText = "";
                    stopPlay();
                    document.getElementById('btn_play').innerText = "▶ LẶP LẠI";
                    idx = 0;
                    return;
                }}

                let word = playlist[idx];
                document.getElementById('p_hanzi').innerText = word.hanzi;
                document.getElementById('p_pinyin').innerText = word.pinyin;
                document.getElementById('p_mean').innerText = word.mean;

                try {{
                    let binaryString = window.atob(word.audio);
                    let len = binaryString.length;
                    let bytes = new Uint8Array(len);
                    for (let i = 0; i < len; i++) bytes[i] = binaryString.charCodeAt(i);
                    
                    let audioBuffer = await audioCtx.decodeAudioData(bytes.buffer);
                    currentSource = audioCtx.createBufferSource();
                    currentSource.buffer = audioBuffer;
                    currentSource.connect(audioCtx.destination);
                    currentSource.start();

                    currentSource.onended = () => {{
                        if(!isPlaying) return;
                        timeoutId = setTimeout(() => {{ idx++; playLoop(); }}, 3500);
                    }};
                }} catch(e) {{ idx++; playLoop(); }}
            }}
        </script>
        """
        components.html(html_player, height=350)

# ==========================================
# TAB 4: FLASHCARD
# ==========================================
with t_flash:
    st.markdown("<h3>FLASHCARD LẬT THẺ</h3>", unsafe_allow_html=True)
    if not st.session_state.selected_ids:
        st.warning("Hãy chọn từ ở tab Quản lý trước!")
    else:
        if st.button("Rút thẻ mới ➔", use_container_width=True):
            conn = sqlite3.connect('chinese_web.db')
            ids_str = ','.join(map(str, st.session_state.selected_ids))
            st.session_state.flash_word = random.choice(conn.execute(f"SELECT * FROM vocab WHERE id IN ({ids_str})").fetchall())
            conn.close()
            st.session_state.show_flash_ans = False

        if st.session_state.flash_word:
            w = st.session_state.flash_word
            st.markdown(f"<div class='word-card'><h1 style='font-size: 80px;'>{w[1]}</h1></div>", unsafe_allow_html=True)
            render_audio(w[1], auto_play_on_desktop=True)
            
            if st.button("👁 Xem Pinyin & Nghĩa", use_container_width=True):
                st.session_state.show_flash_ans = True
                
            if st.session_state.get('show_flash_ans', False):
                st.markdown(f"<div class='word-card'><h3>{w[2]}</h3><p>{w[3]}</p></div>", unsafe_allow_html=True)

# ==========================================
# TAB 5: TRẮC NGHIỆM
# ==========================================
with t_quiz:
    st.markdown("<h3>TRẮC NGHIỆM PHẢN XẠ</h3>", unsafe_allow_html=True)
    if not st.session_state.selected_ids:
        st.warning("Hãy chọn từ ở tab Quản lý để làm test nhé!")
    else:
        def generate_quiz():
            conn = sqlite3.connect('chinese_web.db')
            ids_str = ','.join(map(str, st.session_state.selected_ids))
            sel_words = conn.execute(f"SELECT * FROM vocab WHERE id IN ({ids_str})").fetchall()
            all_means = [r[0] for r in conn.execute("SELECT meaning FROM vocab").fetchall()]
            conn.close()
            
            st.session_state.quiz_word = random.choice(sel_words)
            correct = st.session_state.quiz_word[3]
            distractors = random.sample([m for m in all_means if m != correct], min(3, len(all_means)-1)) if len(all_means)>1 else ["-", "-", "-"]
            opts = distractors + [correct]
            random.shuffle(opts)
            st.session_state.quiz_options = opts

        if st.button("Câu hỏi mới ➔", use_container_width=True) or st.session_state.quiz_word is None:
            generate_quiz()

        if st.session_state.quiz_word:
            q_word = st.session_state.quiz_word
            st.markdown(f"<div class='word-card'><h1 style='font-size: 60px;'>{q_word[1]}</h1></div>", unsafe_allow_html=True)
            
            render_audio(q_word[1], auto_play_on_desktop=True)
            
            st.write("Chọn đáp án đúng:")
            opts = st.session_state.quiz_options
            
            for i in range(4):
                if st.button(opts[i], key=f"ans_{i}", use_container_width=True):
                    if opts[i] == q_word[3]:
                        st.balloons()
                        st.success("Chính xác! 🌸")
                        time.sleep(1.5)
                        generate_quiz()
                        st.rerun()
                    else:
                        st.error(f"Sai rồi! Đáp án là: {q_word[3]}")