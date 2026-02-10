import streamlit as st
import os
import tempfile
import datetime
from openai import OpenAI

# ページ設定
st.set_page_config(page_title="AI議事録Pro", page_icon="📝")

st.title("📝 AI統合レポート作成ツール (OpenAI版)")
st.caption("OpenAI (Whisper + GPT-4o-mini) を使用して、確実・高速にレポートを作成します")

# --- セッションステート初期化 ---
if "report_text" not in st.session_state:
    st.session_state.report_text = None
if "full_transcript" not in st.session_state:
    st.session_state.full_transcript = None
if "file_names" not in st.session_state:
    st.session_state.file_names = []

# --- サイドバー：設定 ---
with st.sidebar:
    st.header("🔑 設定")
    # Geminiのキーは不要になりました
    openai_key = st.text_input("OpenAI API Key (sk-...)", type="password")
    
    st.divider()
    
    # レポート種類の選択
    report_type = st.radio(
        "📄 レポートの種類",
        ["会議・打ち合わせ", "講演会・セミナー", "相談会・ヒアリング"],
        index=0
    )
    
    st.divider()
    # リセットボタン
    if st.button("🗑️ 履歴をクリアしてリセット"):
        st.session_state.report_text = None
        st.session_state.full_transcript = None
        st.session_state.file_names = []
        st.rerun()
        
    st.info("※GPT-4o-miniを使用します。非常に安価で高性能です。")

# --- プロンプト定義 ---
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

if uploaded_files and openai_key:
    # ファイル名でソート
    uploaded_files.sort(key=lambda x: x.name)
    current_file_names = [f.name for f in uploaded_files]
    
    if st.session_state.file_names and st.session_state.file_names != current_file_names:
        st.warning("⚠️ ファイルが変更されました。「履歴をクリア」ボタンを押すことをお勧めします。")

    # 処理実行ボタン
    if st.button("🚀 レポート作成を開始"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        client = OpenAI(api_key=openai_key)
        full_transcript = ""
        
        # 1. 音声文字起こし (Whisper)
        for i, uploaded_file in enumerate(uploaded_files):
            try:
                status_text.text(f"文字起こし中 ({i+1}/{len(uploaded_files)}): {uploaded_file.name}")
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = tmp_file.name
                
                with open(tmp_file_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file,
                        response_format="text"
                    )
                
                os.remove(tmp_file_path)
                
                full_transcript += f"\n\n--- 録音データ: {uploaded_file.name} ---\n\n"
                full_transcript += transcript
                
                progress_bar.progress((i + 1) / (len(uploaded_files) + 1))
                
            except Exception as e:
                st.error(f"文字起こしエラー ({uploaded_file.name}): {e}")
                st.stop()

        # 2. レポート作成 (GPT-4o-mini)
        status_text.text("🧠 AI (GPT-4o-mini) がレポートを執筆中...")
        
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        prompt_template = prompts[report_type].format(date=today_str)
        
        system_prompt = "あなたはプロの議事録作成アシスタントです。ユーザーから提供された音声テキストを元に、指定されたフォーマットでレポートを作成してください。"
        user_message = f"{prompt_template}\n\n【以下の結合テキストをもとに作成してください】\n{full_transcript}"
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini", # ここで最新の軽量モデルを使用
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3
            )
            
            report_content = response.choices[0].message.content
            
            # 結果を保存
            st.session_state.report_text = report_content
            st.session_state.full_transcript = full_transcript
            st.session_state.file_names = current_file_names
            
            progress_bar.progress(100)
            status_text.success("完了しました！")
            
        except Exception as e:
            st.error(f"レポート生成エラー: {e}")

# --- 結果表示 ---
if st.session_state.report_text:
    st.divider()
    st.subheader(f"📊 {report_type} レポート")
    
    st.markdown(st.session_state.report_text)
    
    # ファイル名生成
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    file_name_candidate = f"{today_str}_report"
    for line in st.session_state.report_text.split('\n'):
        if line.startswith("# "):
            file_name_candidate = line.replace("# ", "").strip().replace(" ", "_").replace("/", "-")
            break
            
    st.download_button(
        label="💾 レポートを保存 (mdファイル)",
        data=st.session_state.report_text,
        file_name=f"{file_name_candidate}.md",
        mime="text/markdown"
    )
    
    with st.expander("文字起こし原文（結合版）を確認する"):
        st.text_area("原文", st.session_state.full_transcript, height=200)

elif not openai_key:
    st.warning("👈 左のサイドバーにOpenAI APIキーを入力してください。")
