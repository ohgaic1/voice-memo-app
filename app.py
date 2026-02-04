import streamlit as st
import os
import tempfile
from openai import OpenAI
import google.generativeai as genai

# ページ設定
st.set_page_config(page_title="AI議事録アプリ", page_icon="🎙️")

st.title("🎙️ AI議事録 & レポート作成")
st.caption("最新のAIモデルを自動検出して使用します")

# --- サイドバー：設定 ---
with st.sidebar:
    st.header("🔑 APIキー設定")
    openai_key = st.text_input("OpenAI API Key (sk-...)", type="password")
    gemini_key = st.text_input("Gemini API Key (AIza...)", type="password")
    
    st.divider()
    
    # モデル選択機能（キーがある場合のみリストを取得）
    available_models = []
    if gemini_key:
        try:
            genai.configure(api_key=gemini_key)
            # 使えるモデル一覧を取得
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    # モデル名から 'models/' を取り除く
                    name = m.name.replace('models/', '')
                    available_models.append(name)
        except Exception as e:
            st.error(f"Geminiキーのエラー: {e}")

    # リストが空ならデフォルト値を表示
    if not available_models:
        available_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
    
    st.header("⚙️ モデル選択")
    # デフォルトで gemini-1.5-flash を優先的に選ぶ
    default_index = 0
    for i, m in enumerate(available_models):
        if "flash" in m:
            default_index = i
            break
            
    selected_model = st.selectbox("使用するモデル", available_models, index=default_index)
    st.caption(f"選択中: {selected_model}")

# --- メイン処理 ---
uploaded_files = st.file_uploader(
    "音声ファイルをアップロード", 
    type=["mp3", "m4a", "wav"], 
    accept_multiple_files=True
)

if uploaded_files and openai_key and gemini_key:
    st.success(f"準備完了！ 使用モデル: {selected_model}")
    
    if st.button("🚀 一括処理を開始"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # APIクライアント準備
        client = OpenAI(api_key=openai_key)
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(selected_model) # 選択したモデルを使用

        for i, uploaded_file in enumerate(uploaded_files):
            try:
                current_name = uploaded_file.name
                status_text.text(f"▶ 処理中: {current_name}")
                
                # 1. 音声処理 (Whisper)
                # 一時ファイル作成
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{current_name.split('.')[-1]}") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = tmp_file.name
                
                # 25MBチェック
                if os.path.getsize(tmp_file_path) > 25 * 1024 * 1024:
                    st.error(f"❌ {current_name} はサイズが大きすぎます(25MB超)。")
                    os.remove(tmp_file_path)
                    continue

                # 文字起こし実行
                with open(tmp_file_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file,
                        response_format="text"
                    )
                os.remove(tmp_file_path)

                # 2. 要約処理 (Gemini)
                prompt = f"""
                以下のテキストは会議の録音です。
                内容を整理し、ビジネスレポート形式（タイトル、要約、ToDo）で出力してください。
                
                テキスト:
                {transcript}
                """
                
                response = model.generate_content(prompt)

                # 結果表示
                with st.expander(f"✅ レポート: {current_name}", expanded=True):
                    st.markdown(response.text)
                    st.divider()
                    st.text_area("文字起こし原文", transcript, height=100)

            except Exception as e:
                st.error(f"⚠️ エラー ({current_name}): {e}")
            
            progress_bar.progress((i + 1) / len(uploaded_files))
        
        status_text.success("すべての処理が完了しました！")

elif not (openai_key and gemini_key):
    st.warning("👈 左のサイドバーにAPIキーを入力してください。")
