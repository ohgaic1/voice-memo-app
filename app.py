import streamlit as st
import os
import tempfile
import datetime
import re
from openai import OpenAI
import google.generativeai as genai

# ページ設定
st.set_page_config(page_title="AI議事録Pro", page_icon="📝")

st.title("📝 AI統合レポート作成ツール")
st.caption("時系列順に結合して1つのレポートを作成します")

# --- サイドバー：設定 ---
with st.sidebar:
    st.header("🔑 設定")
    openai_key = st.text_input("OpenAI API Key (sk-...)", type="password")
    gemini_key = st.text_input("Gemini API Key (AIza...)", type="password")
    
    st.divider()
    
    # レポート種類の選択
    report_type = st.radio(
        "📄 レポートの種類",
        ["会議・打ち合わせ", "講演会・セミナー", "相談会・ヒアリング"],
        index=0
    )
    
    st.divider()
    
    # モデル選択 (自動取得ロジック)
    available_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
    if gemini_key:
        try:
            genai.configure(api_key=gemini_key)
            models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            if models: available_models = models
        except: pass
        
    # Flashを優先
    default_idx = next((i for i, m in enumerate(available_models) if "flash" in m), 0)
    selected_model = st.selectbox("使用モデル", available_models, index=default_idx)

# --- プロンプトのテンプレート定義 ---
prompts = {
    "会議・打ち合わせ": """
    あなたは優秀な書記です。以下のテキストは「会議」の録音です。
    複数の録音ファイルを時系列に結合しています。内容を統合し、以下のフォーマットでMarkdownレポートを作成してください。
    
    # {date} 会議議事録
    
    ## 1. 会議の概要
    （3行程度で要約）
    
    ## 2. 決定事項
    - 
    
    ## 3. 議論の内容（詳細）
    - 
    
    ## 4. ネクストアクション（ToDo）
    - [担当] 期限: タスク内容
    """,
    
    "講演会・セミナー": """
    あなたは優秀なライターです。以下のテキストは「講演会」の録音です。
    聞き手が内容を深く理解できるよう、以下のフォーマットで講義録を作成してください。
    
    # {date} 講演レポート
    
    ## 1. 講演のテーマと要旨
    
    ## 2. キーポイント（学び）
    - **ポイント1**: 詳細...
    - **ポイント2**: 詳細...
    
    ## 3. 講義の詳細構成（マインドマップ風）
    
    ## 4. 質疑応答の要点
    """,
    
    "相談会・ヒアリング": """
    あなたは行政書士などの専門家のアシスタントです。以下のテキストは「相談会」の録音です。
    相談者の悩みと、それに対する回答を整理してください。
    
    # {date} 相談記録
    
    ## 1. 相談者の属性・状況
    
    ## 2. 相談内容（悩み・課題）
    
    ## 3. 専門家からの回答・アドバイス
    
    ## 4. 今後の対応方針・手続き
    """
}

# --- メイン処理 ---
uploaded_files = st.file_uploader(
    "音声ファイルをアップロード（自動でファイル名順に並び替えます）", 
    type=["mp3", "m4a", "wav"], 
    accept_multiple_files=True
)

if uploaded_files and openai_key and gemini_key:
    # 【重要】ファイル名でソートすることで「時系列順」を担保する
    # 例: 2026-02-03 13_00.mp3 -> 2026-02-03 13_30.mp3 の順になる
    uploaded_files.sort(key=lambda x: x.name)
    
    st.success(f"📂 以下の順序で結合して処理します（全 {len(uploaded_files)} ファイル）")
    
    # 処理順序をユーザーに確認させる表示
    order_text = ""
    for i, f in enumerate(uploaded_files):
        order_text += f"{i+1}. {f.name}\n"
    st.code(order_text, language=None)
    
    if st.button("🚀 レポート作成を開始"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        client = OpenAI(api_key=openai_key)
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(selected_model)
        
        full_transcript = ""
        
        # 1. すべてのファイルを文字起こしして結合
        for i, uploaded_file in enumerate(uploaded_files):
            try:
                status_text.text(f"文字起こし中 ({i+1}/{len(uploaded_files)}): {uploaded_file.name}")
                
                # 一時ファイル処理
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = tmp_file.name
                
                # 文字起こし
                with open(tmp_file_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file,
                        response_format="text"
                    )
                
                os.remove(tmp_file_path)
                
                # テキスト結合（ファイル名の見出しをつける）
                full_transcript += f"\n\n--- 録音データ: {uploaded_file.name} ---\n\n"
                full_transcript += transcript
                
                progress_bar.progress((i + 1) / (len(uploaded_files) + 1))
                
            except Exception as e:
                st.error(f"エラー ({uploaded_file.name}): {e}")
                st.stop()

        # 2. まとめてレポート作成
        status_text.text("🧠 AIがレポートを執筆中...")
        
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        prompt_template = prompts[report_type].format(date=today_str)
        
        final_prompt = f"""
        {prompt_template}
        
        【以下の結合テキストをもとに作成してください】
        {full_transcript}
        """
        
        try:
            response = model.generate_content(final_prompt)
            report_text = response.text
            
            progress_bar.progress(100)
            status_text.success("完了しました！")
            
            # 結果表示
            st.divider()
            st.subheader(f"📊 {report_type} レポート")
            st.markdown(report_text)
            
            # ダウンロードボタン用ファイル名生成
            # レポートの1行目（タイトル）を取得してみる
            file_name_candidate = "report"
            for line in report_text.split('\n'):
                if line.startswith("# "):
                    # # 2026-02-04 会議... -> 2026-02-04_会議...
                    file_name_candidate = line.replace("# ", "").strip().replace(" ", "_").replace("/", "-")
                    break
            
            if not file_name_candidate:
                file_name_candidate = f"{today_str}_report"
            
            save_name = f"{file_name_candidate}.md"
            
            st.download_button(
                label="💾 レポートを保存 (mdファイル)",
                data=report_text,
                file_name=save_name,
                mime="text/markdown"
            )
            
            with st.expander("文字起こし原文（結合版）を確認する"):
                st.text_area("原文", full_transcript, height=200)
                
        except Exception as e:
            st.error(f"レポート生成エラー: {e}")

elif not (openai_key and gemini_key):
    st.warning("👈 左のサイドバーにAPIキーを入力してください。")
