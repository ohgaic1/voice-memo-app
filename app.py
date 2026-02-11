import streamlit as st
import os
import tempfile
import datetime
import pdfplumber
from openai import OpenAI

# ページ設定
st.set_page_config(page_title="AI議事録Pro", page_icon="📚", layout="wide")

st.title("📚 AI統合レポート作成ツール (資料参照モード)")
st.caption("「音声」と「配布資料」を組み合わせて、完璧な講義録を作成します")

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
        ["講演会・研究会", "社内会議・打ち合わせ", "専門家ヒアリング"],
        index=0
    )
    
    st.divider()
    if st.button("🗑️ 履歴をクリアしてリセット"):
        st.session_state.report_text = None
        st.session_state.full_transcript = None
        st.rerun()

    st.info("💡 PDF資料をアップロードすると、AIが専門用語や構成を学習して精度が向上します。")

# --- プロンプト定義（資料参照用） ---
prompts = {
    "講演会・研究会": """
    あなたはアカデミックなライティングに長けたプロの編集者です。
    「講演の音声テキスト」と「配布資料の内容」の2つを使って、詳細な講義録を作成してください。

    【最重要指示: 資料と音声の統合】
    1. **用語の統一**: 音声認識で誤変換されやすい専門用語や人名は、必ず「資料」の表記を正として修正してください。
    2. **構造の再現**: 講義の章立ては、「資料」の目次や見出し構成（Chapter 1, 2...）に沿って整理してください。
    3. **数字の補完**: 音声で「この数字」「約○割」と曖昧に言及された箇所は、資料にある正確な数値を補足してください。

    【出力フォーマット】
    # [資料に基づく正確なタイトル]

    ## 1. 講義の要旨（エグゼクティブサマリー）
    （音声と資料を合わせ、この講義で何が語られたかを400文字で要約）

    ## 2. 詳細講義録（資料の構成に準拠）
    ### [資料の章タイトル]
    * **[キーワード]**: [音声での解説内容 + 資料の定義]
    * **重要なポイント**: [講師が強調した点]
    * （図表の解説があれば、「資料の図Xでは〜と示されている」のように記述）

    ### [次の章タイトル]
    ...

    ## 3. 質疑応答とディスカッション
    * Q: ...
    * A: ...

    ## 4. 今後の研究・実践課題
    - [ ] ...
    """,

    "社内会議・打ち合わせ": """
    あなたは優秀なプロジェクトマネージャーです。「会議音声」と「会議資料（アジェンダ等）」を統合し、議事録を作成してください。
    資料にあるアジェンダに沿って、実際の議論がどう進んだかを記録します。

    【重要指示】
    資料にある「議題」に対し、音声で「どのような結論が出たか」を紐づけて記述してください。

    【出力フォーマット】
    # [会議名] 議事録

    ## 概要
    * 日時: {date}
    * 参照資料: [アップロードされた資料の内容から推測]

    ## 議題ごとの議論・決定事項
    ### 1. [資料にある議題名]
    * **議論内容**: ...
    * **決定事項**: ...
    * **ToDo**: ...

    ### 2. [次の議題名]
    ...
    """,

    "専門家ヒアリング": """
    あなたは専門家の知見を整理するライターです。「ヒアリング音声」と「事前資料」をもとに記録を作成します。
    資料の図解やデータを参照しながら、口頭での解説を補足してください。

    【出力フォーマット】
    # ヒアリング調査レポート

    ## ヒアリング対象・テーマ
    
    ## 主要なトピックと回答
    ### [トピック]
    * **現状の課題**: ...
    * **専門家の見解**: ...
        * (資料参照): 資料データの裏付け: ...
    """
}

# --- 関数: PDFからテキスト抽出 ---
def extract_text_from_pdf(pdf_file):
    text = ""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        return f"Error reading PDF: {e}"
    return text

# --- メイン処理 ---
col1, col2 = st.columns(2)

with col1:
    uploaded_audio = st.file_uploader(
        "1. 音声ファイルをアップロード (mp3, m4a, wav)", 
        type=["mp3", "m4a", "wav"], 
        accept_multiple_files=True
    )

with col2:
    uploaded_ref = st.file_uploader(
        "2. 配布資料・レジュメ (PDFのみ)", 
        type=["pdf"],
        accept_multiple_files=False # 資料は今のところ1つに限定（複雑化回避）
    )

if uploaded_audio and openai_key:
    # 音声ファイルのソート
    uploaded_audio.sort(key=lambda x: x.name)
    
    # 実行ボタン
    if st.button("🚀 資料を参照してレポート作成"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        client = OpenAI(api_key=openai_key)
        
        # --- A. 資料のテキスト化 ---
        ref_text = "（資料なし）"
        if uploaded_ref:
            status_text.text("📄 資料(PDF)を読み取っています...")
            ref_text = extract_text_from_pdf(uploaded_ref)
            st.success(f"資料読み込み完了: {len(ref_text)} 文字")
        
        # --- B. 音声の文字起こし ---
        full_transcript = ""
        for i, audio_file in enumerate(uploaded_audio):
            try:
                status_text.text(f"🎙️ 文字起こし中 ({i+1}/{len(uploaded_audio)}): {audio_file.name}")
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_file.name.split('.')[-1]}") as tmp_file:
                    tmp_file.write(audio_file.getvalue())
                    tmp_file_path = tmp_file.name
                
                with open(tmp_file_path, "rb") as af:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=af,
                        response_format="text"
                    )
                os.remove(tmp_file_path)
                full_transcript += f"\n\n--- Audio: {audio_file.name} ---\n{transcript}"
                progress_bar.progress((i + 1) / (len(uploaded_audio) + 2))
                
            except Exception as e:
                st.error(f"音声エラー: {e}")
                st.stop()

        # --- C. AIによるレポート作成 ---
        status_text.text("🧠 資料と音声を統合してレポート執筆中...")
        
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        prompt_template = prompts[report_type].format(date=today_str)
        
        system_prompt = "あなたは高度な分析能力を持つライターです。資料と音声を照らし合わせ、正確無比なレポートを作成します。"
        
        # ここが肝心の統合プロンプト
        user_message = f"""
        {prompt_template}

        ========================================
        【参照資料（PDF抽出テキスト）】
        ※ここにある用語や構成を優先してください。
        {ref_text[:30000]} 
        (※文字数が多すぎる場合は冒頭3万文字のみ使用)
        ========================================

        【音声テキスト（文字起こし）】
        ※ここにある内容を、資料の構造に当てはめて記述してください。
        {full_transcript}
        ========================================
        """
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.2 # 資料に忠実にするため温度を下げる
            )
            
            report_content = response.choices[0].message.content
            st.session_state.report_text = report_content
            
            progress_bar.progress(100)
            status_text.success("完了しました！")
            
        except Exception as e:
            st.error(f"生成エラー: {e}")

# --- 結果表示 ---
if st.session_state.report_text:
    st.divider()
    st.subheader(f"📊 作成レポート")
    st.markdown(st.session_state.report_text)
    
    st.download_button(
        label="💾 レポートを保存 (mdファイル)",
        data=st.session_state.report_text,
        file_name=f"{datetime.date.today()}_lecture_report.md",
        mime="text/markdown"
    )
