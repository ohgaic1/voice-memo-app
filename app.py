import streamlit as st
import os
import tempfile
from openai import OpenAI
import google.generativeai as genai

# タイトルと説明
st.title("🎙️ AI議事録 & レポート作成")
st.caption("OpenAI Whisper (耳) と Google Gemini (脳) を組み合わせた最強ツール")

# サイドバーでAPIキー設定
with st.sidebar:
    st.header("🔑 設定")
    openai_key = st.text_input("OpenAI API Key (sk-...)", type="password")
    gemini_key = st.text_input("Gemini API Key (AIza...)", type="password")
    st.info("※キーはブラウザに一時的に保存されるだけで、外部には漏れません。")

# ファイルアップロード
uploaded_file = st.file_uploader("音声ファイルをアップロード (mp3, m4a, wav)", type=["mp3", "m4a", "wav"])

if uploaded_file and openai_key and gemini_key:
    st.success("準備OK！ボタンを押して開始してください。")
    
    if st.button("🚀 文字起こし＆レポート作成を開始"):
        try:
            # プログレスバーの表示
            progress_text = "処理を開始します..."
            my_bar = st.progress(0, text=progress_text)

            # 1. 一時ファイルとして保存 (Whisperはファイルパスが必要なため)
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name

            # 2. OpenAI (Whisper) 設定
            client = OpenAI(api_key=openai_key)
            
            # --- 音声処理 ---
            my_bar.progress(30, text="👂 音声を聞き取っています (Whisper)...")
            
            with open(tmp_file_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    response_format="text"
                )
            
            # 一時ファイルの削除
            os.remove(tmp_file_path)

            st.subheader("📝 文字起こし結果")
            with st.expander("全文を確認する"):
                st.text_area("原文", transcript, height=200)
            
            # --- 要約処理 (Gemini) ---
            my_bar.progress(70, text="🧠 レポートを作成しています (Gemini)...")
            
            genai.configure(api_key=gemini_key)
            # モデルは最新のFlashを使用（高速・高性能）
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
            あなたはプロの書記です。以下のテキストは会議の録音です。
            内容を整理し、以下のフォーマットで議事録を作成してください。

            ## 1. タイトル
            （30文字以内で内容を要約）

            ## 2. エグゼクティブサマリー
            （200文字程度で全体の要点をまとめる）

            ## 3. 議題と決定事項
            - [議題1]
              - 詳細: ...
            - [議題2]
              - 詳細: ...

            ## 4. ネクストアクション（ToDo）
            - [担当者] 期限: タスク内容

            ---
            【音声テキスト】
            {transcript}
            """
            
            response = model.generate_content(prompt)
            
            my_bar.progress(100, text="✅ 完了しました！")
            
            st.divider()
            st.subheader("📊 AIレポート")
            st.markdown(response.text)
            
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

elif not (openai_key and gemini_key):
    st.warning("👈 左のサイドバーに2つのAPIキーを入力してください。")
