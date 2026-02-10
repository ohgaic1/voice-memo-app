import streamlit as st
import os
import tempfile
import datetime
from openai import OpenAI

# ページ設定
st.set_page_config(page_title="AI議事録Pro", page_icon="📝", layout="wide")

st.title("📝 AI統合レポート作成ツール (Pro版)")
st.caption("詳細な講義録や会議録を、プロ並みの構成で作成します")

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
    openai_key = st.text_input("OpenAI API Key (sk-...)", type="password")
    
    st.divider()
    
    # レポート種類の選択
    report_type = st.radio(
        "📄 レポートの種類",
        ["講演会・セミナー", "会議・打ち合わせ", "相談会・ヒアリング"],
        index=0
    )
    
    st.divider()
    # リセットボタン
    if st.button("🗑️ 履歴をクリアしてリセット"):
        st.session_state.report_text = None
        st.session_state.full_transcript = None
        st.session_state.file_names = []
        st.rerun()
        
    st.info("※GPT-4o-miniを使用。長時間の録音でも安価に処理可能です。")

# --- プロンプト定義 (詳細版) ---
prompts = {
    "講演会・セミナー": """
    あなたはプロの「講義録作成ライター」です。提供された音声テキスト（講演・セミナー）をもとに、
    詳細かつ網羅的なレポートを作成してください。単なる要約ではなく、後から読み返して学習できるレベルの「教材」を作成することが目標です。

    【重要なお願い】
    - 情報量を減らさないでください。具体的な数字、固有名詞、事例はすべて記載してください。
    - 階層構造（### 1. -> #### 1.1 -> 箇条書き）を必ず維持してください。
    - 講師が話した「重要なノウハウ」や「ロジック」を漏らさないでください。

    【出力フォーマット】
    # Summary

    日時: {date}
    場所: [音声から推測、不明なら空欄]
    講師: [音声から推測される講師名]

    ## 概要
    （講義全体の要旨を、400〜600文字程度の文章でまとめてください。どのような背景があり、結論として何が語られたかを記述します。）

    ## 知識点
    （ここがメインです。講義の流れに沿って、章立てて詳細に記述してください）

    ### 1. [大項目タイトル]
    #### 1.1. [中項目タイトル]
    * **[キーワード]**: [詳細な説明]
    * [具体的な数字や統計データがあれば必ず記載]
    * [講師が挙げた具体例やエピソード]

    ### 2. [次の大項目タイトル]
    #### 2.1. [中項目タイトル]
    * ...

    ## 質問
    * [質疑応答があれば、その内容を記載。なければ「特になし」]

    ## 課題
    （講義内容から導き出される、聴講者がやるべきアクションリストを作成してください）
    - [ ] 1. [具体的なアクション]
    - [ ] 2. [具体的なアクション]
    - [ ] 3. ...
    """,

    "会議・打ち合わせ": """
    あなたはプロの「議事録作成書記」です。会議の音声を、詳細な公式議事録としてまとめてください。
    発言の意図を汲み取り、決定事項と未決定事項を明確に区別してください。

    【出力フォーマット】
    # {date} 会議議事録

    ## 1. 会議の概要
    （会議の目的と、最終的な結論を300文字程度で要約）

    ## 2. 決定事項
    （確定した事項を箇条書きで。曖昧さを排除して記載すること）
    - **[決定項目]**: [詳細内容]
    - 

    ## 3. 議論の詳細（時系列・トピック別）
    ### [トピック名]
    * **[発言者名]**: [発言の要旨と主張]
    * **議論の流れ**: [どのように議論が進み、なぜその結論に至ったかの経緯]

    ## 4. ネクストアクション（ToDo）
    （「誰が」「いつまでに」「何をするか」を明確に）
    - [ ] [担当者名] 期限:[日付]: [タスク内容]
    """,
    
    "相談会・ヒアリング": """
    あなたは専門家の「相談記録アシスタント」です。相談会やインタビューの音声を記録します。
    相談者の「現状」「悩み」「専門家のアドバイス」を構造化して出力してください。

    【出力フォーマット】
    # {date} 相談・ヒアリング記録

    ## 1. 相談者の属性・状況
    * [音声からわかる範囲で記述]

    ## 2. 相談内容（現状の課題）
    ### [課題カテゴリ]
    * [具体的な悩みや、困っている事象の詳細]
    * [その課題が発生している背景]

    ## 3. 専門家からの回答・アドバイス
    ### [アドバイスの要点]
    * **回答**: [専門家の具体的な回答]
    * **根拠**: [法令や知識に基づく根拠]
    * **提案**: [具体的な解決策の提示]

    ## 4. 今後の対応方針・手続き
    - [ ] [次にやるべき手続きやアクション]
    """
}

# --- メイン処理 ---
uploaded_files = st.file_uploader(
    "音声ファイルをアップロード（ファイル名順に結合されます）", 
    type=["mp3", "m4a", "wav"], 
    accept_multiple_files=True
)

if uploaded_files and openai_key:
    # ファイル名でソート（時系列順序の担保）
    uploaded_files.sort(key=lambda x: x.name)
    current_file_names = [f.name for f in uploaded_files]
    
    # ファイル変更検知
    if st.session_state.file_names and st.session_state.file_names != current_file_names:
        st.warning("⚠️ ファイルリストが変更されました。「履歴をクリア」してリセットすることをお勧めします。")

    # 処理順序の表示
    st.write("📂 以下の順序で結合して処理します:")
    order_text = "\n".join([f"{i+1}. {f.name}" for i, f in enumerate(uploaded_files)])
    st.code(order_text)

    # 実行ボタン
    if st.button("🚀 詳細レポート作成を開始"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        client = OpenAI(api_key=openai_key)
        full_transcript = ""
        
        # 1. 音声文字起こし (Whisper)
        # ※ここでのプロンプトはWhisper用ではなく、後半のGPT用です
        
        for i, uploaded_file in enumerate(uploaded_files):
            try:
                status_text.text(f"文字起こし中 ({i+1}/{len(uploaded_files)})...")
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = tmp_file.name
                
                with open(tmp_file_path, "rb") as audio_file:
                    # Whisper API呼び出し
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file,
                        response_format="text"
                    )
                
                os.remove(tmp_file_path)
                
                # 結合時にファイル名の区切りを入れる
                full_transcript += f"\n\n--- Source: {uploaded_file.name} ---\n\n"
                full_transcript += transcript
                
                progress_bar.progress((i + 1) / (len(uploaded_files) + 1))
                
            except Exception as e:
                st.error(f"文字起こしエラー ({uploaded_file.name}): {e}")
                st.stop()

        # 2. レポート作成 (GPT-4o-mini)
        status_text.text("🧠 AIが詳細レポートを執筆中...（長文のため時間がかかります）")
        
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        prompt_template = prompts[report_type].format(date=today_str)
        
        # システムプロンプトの設定
        system_prompt = """
        あなたは熟練のライター兼アナリストです。
        提供されたテキストから、具体的かつ構造化されたMarkdownレポートを作成してください。
        重要な情報は「省略せず」に詳しく記述することが求められます。
        """
        
        user_message = f"""
        {prompt_template}

        【対象テキスト】
        {full_transcript}
        """
        
        try:
            # トークン数を節約せず、最大化するために max_tokens は指定しない（または大きく取る）
            response = client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3 # 事実に基づいた記述にするため、温度は低め
            )
            
            report_content = response.choices[0].message.content
            
            # 結果保存
            st.session_state.report_text = report_content
            st.session_state.full_transcript = full_transcript
            st.session_state.file_names = current_file_names
            
            progress_bar.progress(100)
            status_text.success("完了しました！")
            
        except Exception as e:
            st.error(f"レポート生成エラー: {e}")

# --- 結果表示とダウンロード ---
if st.session_state.report_text:
    st.divider()
    st.subheader(f"📊 {report_type}")
    
    st.markdown(st.session_state.report_text)
    
    # ファイル名生成ロジック
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    file_name_candidate = f"{today_str}_report"
    
    # タイトル行があればそれをファイル名にする
    for line in st.session_state.report_text.split('\n'):
        if line.startswith("# Summary") or line.startswith("# "):
             # "Summary"だけだと味気ないので日付をつける、あるいは内容から推測
             pass 
        if "日時" not in line and "場所" not in line and line.strip().startswith("#") and len(line) > 5:
             # 見出しっぽいものを取得
             cleaned_line = line.replace("#", "").strip().replace(" ", "_").replace("/", "-")
             if cleaned_line != "Summary":
                 file_name_candidate = f"{today_str}_{cleaned_line}"
                 break
    
    save_name = f"{file_name_candidate}.md"
    
    st.download_button(
        label="💾 レポートを保存 (mdファイル)",
        data=st.session_state.report_text,
        file_name=save_name,
        mime="text/markdown"
    )
    
    with st.expander("文字起こし原文（結合版）を確認する"):
        st.text_area("原文", st.session_state.full_transcript, height=300)

elif not openai_key:
    st.warning("👈 左のサイドバーにOpenAI APIキーを入力してください。")
