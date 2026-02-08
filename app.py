import streamlit as st
import os
import tempfile
import datetime
from openai import OpenAI
import google.generativeai as genai

# ページ設定
st.set_page_config(page_title="AI議事録Pro", page_icon="📝")

st.title("📝 AI統合レポート作成ツール")
st.caption("OpenAI Whisperを使用して文字起こしを行います（25MB制限あり）")

# --- セッションステート初期化 ---
if "report_text" not in st.session_state:
    st.session_state.report_text = None
if "full_transcript" not in st.session_state:
    st.session_state.full_transcript = None

# --- サイドバー：設定 ---
with st.sidebar:
    st.header("🔑 設定")
    openai_key = st.text_input("OpenAI API Key", type="password")
    gemini_key = st.text_input("Gemini API Key", type="password")
    
    report_type = st.radio("📄 レポートの種類", ["会議・打ち合わせ", "講演会・セミナー", "相談会・ヒアリング"])
    selected_model = st.selectbox("使用モデル", ["gemini-1.5-flash", "gemini-1.5-pro"])

# --- メイン処理 ---
uploaded_files = st.file_uploader("音声ファイルをアップロード", type=["mp3", "m4a", "wav"], accept_multiple_files=True)

if uploaded_files and openai_key and gemini_key:
    uploaded_files.sort(key=lambda x: x.name)
    
    if st.button("🚀 レポート作成を開始"):
        progress_bar = st.progress(0)
        client = OpenAI(api_key=openai_key)
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(selected_model)
        
        full_transcript = ""
        
        try:
            for i, uploaded_file in enumerate(uploaded_files):
                st.info(f"文字起こし中: {uploaded_file.name}")
                
                # 一時保存してWhisperに投げる
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                
                with open(tmp_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file,
                        response_format="text"
                    )
                
                os.remove(tmp_path)
                full_transcript += f"\n\n--- {uploaded_file.name} ---\n{transcript}"
                progress_bar.progress((i + 1) / (len(uploaded_files) + 1))

            # レポート生成
            st.info("レポート執筆中...")
            today = datetime.date.today().strftime('%Y-%m-%d')
            response = model.generate_content(f"日付:{today}\n内容:\n{full_transcript}")
            
            st.session_state.report_text = response.text
            st.session_state.full_transcript = full_transcript
            progress_bar.progress(100)
            
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

# --- 結果表示 ---
if st.session_state.report_text:
    st.markdown(st.session_state.report_text)
    with st.expander("文字起こし原文を確認"):
        st.text_area("原文", st.session_state.full_transcript, height=200)
