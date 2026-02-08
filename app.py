import streamlit as st
import os
import tempfile
import datetime
import time
import google.generativeai as genai
from pydub import AudioSegment

# ページ設定
st.set_page_config(page_title="AI議事録Pro", page_icon="📝")

st.title("📝 AI統合レポート作成ツール")
st.caption("自動圧縮機能搭載：重いファイルもサクサク処理します")

# --- セッションステート初期化 ---
if "report_text" not in st.session_state:
    st.session_state.report_text = None

# --- サイドバー：設定 ---
with st.sidebar:
    st.header("🔑 設定")
    gemini_key = st.text_input("Gemini API Key", type="password")
    
    st.divider()
    report_type = st.radio("📄 レポートの種類", ["会議・打ち合わせ", "講演会・セミナー", "相談会・ヒアリング"])
    
    st.divider()
    selected_model = st.selectbox("使用モデル", ["gemini-1.5-flash", "gemini-1.5-pro"], index=0)
    
    if st.button("🗑️ リセット"):
        st.session_state.report_text = None
        st.rerun()

# --- 音声圧縮関数 ---
def compress_audio(input_path):
    """音声をモノラル・32kbpsに圧縮して一時保存する"""
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1)  # モノラル化
    audio = audio.set_frame_rate(16000)  # サンプリングレート低減
    
    compressed_path = input_path.replace(".", "_comp.") + "mp3"
    audio.export(compressed_path, format="mp3", bitrate="32k")
    return compressed_path

# --- メイン処理 ---
uploaded_files = st.file_uploader("音声ファイルをアップロード", type=["mp3", "m4a", "wav"], accept_multiple_files=True)

if uploaded_files and gemini_key:
    uploaded_files.sort(key=lambda x: x.name)
    
    if st.button("🚀 レポート作成を開始"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(selected_model)
        
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        content_to_send = [f"あなたは優秀な専門家です。音声を統合しレポートを作成してください。日付: {today_str}"]
        
        temp_files_to_delete = []
        g_files_to_delete = []

        try:
            for i, uploaded_file in enumerate(uploaded_files):
                # 1. 一時保存
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    raw_path = tmp.name
                    temp_files_to_delete.append(raw_path)

                # 2. 自動圧縮実行
                status_text.text(f"圧縮中... {uploaded_file.name}")
                comp_path = compress_audio(raw_path)
                temp_files_to_delete.append(comp_path)

                # 3. Googleへ転送
                status_text.text(f"転送中... {uploaded_file.name}")
                g_file = genai.upload_file(path=comp_path)
                
                while g_file.state.name == "PROCESSING":
                    time.sleep(2)
                    g_file = genai.get_file(g_file.name)
                
                content_to_send.append(g_file)
                g_files_to_delete.append(g_file)
                progress_bar.progress(((i + 1) / len(uploaded_files)) * 0.4)

            # 4. レポート生成
            status_text.text("🧠 AIがレポートを執筆中...")
            response = model.generate_content(content_to_send)
            st.session_state.report_text = response.text
            progress_bar.progress(100)
            status_text.success("完了しました！")
            
        except Exception as e:
            st.error(f"エラー: {e}")
        
        finally:
            # 5. 後片付け
            for gf in g_files_to_delete:
                genai.delete_file(gf.name)
            for tf in temp_files_to_delete:
                if os.path.exists(tf):
                    os.remove(tf)

# --- 結果表示 ---
if st.session_state.report_text:
    st.divider()
    st.markdown(st.session_state.report_text)
    st.download_button("💾 レポートを保存", data=st.session_state.report_text, file_name=f"report_{datetime.date.today()}.md")
