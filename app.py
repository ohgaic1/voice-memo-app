import streamlit as st
import os
import tempfile
from openai import OpenAI
import google.generativeai as genai

# タイトル
st.title("🎙️ AI議事録 & レポート作成 (複数ファイル対応版)")
st.caption("OpenAI Whisper (文字起こし) + Gemini (要約)")

# サイドバー設定
with st.sidebar:
    st.header("🔑 設定")
    openai_key = st.text_input("OpenAI API Key (sk-...)", type="password")
    gemini_key = st.text_input("Gemini API Key (AIza...)", type="password")
    st.divider()
    st.info("※OpenAI APIには「1ファイル25MBまで」の制限があります。長時間の録音は分割するか、圧縮してください。")

# 複数ファイルアップロードを有効化 (accept_multiple_files=True)
uploaded_files = st.file_uploader(
    "音声ファイルをアップロード (mp3, m4a, wav)", 
    type=["mp3", "m4a", "wav"], 
    accept_multiple_files=True
)

if uploaded_files and openai_key and gemini_key:
    st.success(f"{len(uploaded_files)} 件のファイルを確認しました。")
    
    if st.button("🚀 一括処理を開始"):
        # プログレスバーの準備
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # APIクライアントの準備
        client = OpenAI(api_key=openai_key)
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        # 1つずつファイルを処理
        for i, uploaded_file in enumerate(uploaded_files):
            try:
                current_file_name = uploaded_file.name
                status_text.text(f"処理中 ({i+1}/{len(uploaded_files)}): {current_file_name}")
                
                # --- 25MB制限のチェック ---
                file_size_mb = uploaded_file.size / (1024 * 1024)
                if file_size_mb > 25:
                    st.error(f"❌ エラー: {current_file_name} は {file_size_mb:.1f}MB あり、OpenAIの制限(25MB)を超えています。圧縮するか分割してください。")
                    continue

                # 一時ファイル作成
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{current_file_name.split('.')[-1]}") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = tmp_file.name

                # --- 文字起こし (Whisper) ---
                with open(tmp_file_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file,
                        response_format="text"
                    )
                
                # 一時ファイル削除
                os.remove(tmp_file_path)

                # --- 要約 (Gemini) ---
                prompt = f"""
                以下のテキストは「{current_file_name}」の音声文字起こしです。
                ビジネスレポート形式（タイトル、要約、ToDo）でまとめてください。
                
                テキスト:
                {transcript}
                """
                response = model.generate_content(prompt)

                # --- 結果表示 ---
                with st.expander(f"✅ {current_file_name} のレポート", expanded=True):
                    st.markdown(response.text)
                    st.divider()
                    st.caption("文字起こし原文")
                    st.text_area("原文", transcript, height=150, key=f"text_{i}")

            except Exception as e:
                st.error(f"⚠️ {current_file_name} の処理中にエラーが発生しました: {e}")
            
            # 進捗バー更新
            progress_bar.progress((i + 1) / len(uploaded_files))
        
        status_text.text("すべての処理が完了しました！")

elif not (openai_key and gemini_key):
    st.warning("👈 左のサイドバーにAPIキーを入力してください。")

