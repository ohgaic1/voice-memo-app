import streamlit as st
import os
import tempfile
import datetime
import pdfplumber
from openai import OpenAI

# ページ設定
st.set_page_config(page_title="AI議事録Pro", page_icon="📝", layout="wide")

st.title("📝 AI統合レポート作成ツール (自動分岐モード)")
st.caption("資料があれば「高精度統合モード」、なければ「音声解析モード」で自動実行します")

# --- セッションステート初期化 ---
if "report_text" not in st.session_state:
    st.session_state.report_text = None
if "full_transcript" not in st.session_state:
    st.session_state.full_transcript = None

# --- サイドバー設定 ---
with st.sidebar:
    st.header("🔑 設定")
    openai_key = st.text_input("OpenAI API Key (sk-...)", type="password")
    
    st.divider()
    
    report_type = st.radio(
        "📄 レポートの種類",
        ["講演会・セミナー", "会議・打ち合わせ", "ヒアリング・相談会"],
        index=0
    )
    
    st.divider()
    if st.button("🗑️ 履歴をクリア"):
        st.session_state.clear()
        st.rerun()

# --- ファイルアップロードエリア ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. 音声 (必須)")
    uploaded_audio = st.file_uploader(
        "mp3, m4a, wav (複数可)", 
        type=["mp3", "m4a", "wav"], 
        accept_multiple_files=True
    )

with col2:
    st.subheader("2. 資料 (任意)")
    uploaded_ref = st.file_uploader(
        "レジュメ・資料 (PDFのみ)", 
        type=["pdf"],
        accept_multiple_files=False 
    )

# --- 準備状況の診断と実行ボタン ---
st.divider()

# 1. 必須項目のチェック
is_ready = True
error_messages = []

if not openai_key:
    error_messages.append("❌ OpenAI APIキーが入力されていません")
    is_ready = False

if not uploaded_audio:
    st.info("👈 まずは音声ファイルをアップロードしてください")
    is_ready = False
else:
    # 25MB制限チェック
    oversized = [f.name for f in uploaded_audio if f.size > 25 * 1024 * 1024]
    if oversized:
        error_messages.append(f"⚠️ サイズオーバー (25MB超): {', '.join(oversized)}")
        is_ready = False

# エラー表示
if error_messages:
    for msg in error_messages:
        st.error(msg)

# 実行ボタン表示
if is_ready:
    # 資料の有無でメッセージを変える
    mode_text = "📚 資料参照モード" if uploaded_ref else "🎙️ 音声のみモード"
    st.success(f"準備完了！ **【{mode_text}】** で作成します。")

    if st.button("🚀 レポート作成を開始"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        client = OpenAI(api_key=openai_key)
        
        # --- A. 資料読み込み (分岐処理) ---
        ref_text = ""
        if uploaded_ref:
            status_text.text("📄 資料(PDF)を読み取っています...")
            try:
                with pdfplumber.open(uploaded_ref) as pdf:
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted: ref_text += extracted + "\n"
                # 文字数制限 (トークン節約のため冒頭3万文字)
                ref_text = ref_text[:30000]
            except Exception as e:
                st.error(f"PDF読み込みエラー: {e}")
                st.stop()
        else:
            ref_text = "（資料なし。音声のみで構成してください）"

        # --- B. 音声文字起こし ---
        full_transcript = ""
        # ファイル名順にソート
        uploaded_audio.sort(key=lambda x: x.name)
        
        for i, audio_file in enumerate(uploaded_audio):
            status_text.text(f"🎙️ 文字起こし中 ({i+1}/{len(uploaded_audio)}): {audio_file.name}")
            try:
                # 一時ファイル保存
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_file.name.split('.')[-1]}") as tmp_file:
                    tmp_file.write(audio_file.getvalue())
                    tmp_file_path = tmp_file.name
                
                # Whisper実行
                with open(tmp_file_path, "rb") as af:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=af, 
                        response_format="text"
                    )
                os.remove(tmp_file_path)
                full_transcript += f"\n\n--- Audio Part {i+1}: {audio_file.name} ---\n{transcript}"
                
            except Exception as e:
                st.error(f"文字起こしエラー: {e}")
                st.stop()
            
            progress_bar.progress((i + 1) / (len(uploaded_audio) + 2))

        # --- C. レポート生成 (プロンプト分岐) ---
        status_text.text("🧠 レポート執筆中...")
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        
        # 共通の出力フォーマット
        base_format = f"""
        # [タイトル]

        ## 1. 概要 (Executive Summary)
        （{today_str} 実施。全体の要点を簡潔にまとめ）

        ## 2. 詳細内容
        （章立てて記述。重要な数字、用語、固有名詞は漏らさず記載）
        
        ## 3. 質疑応答 / 重要な議論
        
        ## 4. ネクストアクション / 課題
        """

        # 指示の分岐
        if uploaded_ref:
            # 資料あり用の強力な指示
            instruction = f"""
            【資料ありモード】
            提供された「配布資料テキスト」の目次構造と専門用語を正として、音声内容を整理してください。
            音声が聞き取りにくい箇所も、資料の文脈から補完してください。
            """
        else:
            # 音声のみ用の指示
            instruction = """
            【音声のみモード】
            資料はありません。音声テキストの流れを解析し、論理的な章立て（見出し）を自分で構築してください。
            話の区切りを見つけ、適切なタイトルを付けて整理してください。
            """

        user_message = f"""
        あなたはプロのライターです。以下の指示と素材に従ってレポートを作成してください。

        {instruction}

        【出力フォーマット】
        {base_format}

        ========================================
        【配布資料テキスト】
        {ref_text}
        ========================================

        【音声テキスト】
        {full_transcript}
        ========================================
        """
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "あなたは優秀な編集者です。"},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3
            )
            
            st.session_state.report_text = response.choices[0].message.content
            progress_bar.progress(100)
            status_text.success("✅ 作成完了！")
            
        except Exception as e:
            st.error(f"生成エラー: {e}")

# --- 結果表示とダウンロード ---
if st.session_state.report_text:
    st.divider()
    st.subheader(f"📊 {report_type} レポート")
    st.markdown(st.session_state.report_text)
    
    # ファイル名生成
    file_name = f"{datetime.date.today()}_report.md"
    
    st.download_button(
        label="💾 レポートを保存 (mdファイル)",
        data=st.session_state.report_text,
        file_name=file_name,
        mime="text/markdown"
    )
    
    with st.expander("文字起こし原文を見る"):
        st.text_area("Transcript", st.session_state.full_transcript, height=200)
