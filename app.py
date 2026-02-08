import streamlit as st
import os
import tempfile
import datetime
import time
import google.generativeai as genai

# ページ設定
st.set_page_config(page_title="AI議事録Pro", page_icon="📝")

st.title("📝 AI統合レポート作成ツール")
st.caption("時系列順に結合して1つのレポートを作成します（大容量ファイル対応版）")

# --- セッションステート初期化 ---
if "report_text" not in st.session_state:
    st.session_state.report_text = None
if "file_names" not in st.session_state:
    st.session_state.file_names = []

# --- サイドバー：設定 ---
with st.sidebar:
    st.header("🔑 設定")
    # File API利用のため、OpenAIキーは不要になりました（Geminiのみで完結）
    gemini_key = st.text_input("Gemini API Key (AIza...)", type="password")
    
    st.divider()
    
    report_type = st.radio(
        "📄 レポートの種類",
        ["会議・打ち合わせ", "講演会・セミナー", "相談会・ヒアリング"],
        index=0
    )
    
    st.divider()
    
    # モデル選択（File API対応モデルに限定）
    available_models = ["gemini-1.5-flash", "gemini-1.5-pro"]
    selected_model = st.selectbox("使用モデル", available_models, index=0)
    
    st.divider()
    if st.button("🗑️ 履歴をクリアしてリセット"):
        st.session_state.report_text = None
        st.session_state.file_names = []
        st.rerun()

# --- プロンプト定義 ---
prompts = {
    "会議・打ち合わせ": "# {date} 会議議事録\n\n## 1. 会議の概要\n## 2. 決定事項\n## 3. 議論の内容\n## 4.ToDo",
    "講演会・セミナー": "# {date} 講演レポート\n\n## 1. テーマ\n## 2. キーポイント\n## 3. 詳細構成\n## 4. 質疑応答",
    "相談会・ヒアリング": "# {date} 相談記録\n\n## 1. 相談者の状況\n## 2. 相談内容\n## 3. 回答・アドバイス\n## 4. 今後の対応"
}

# --- メイン処理 ---
uploaded_files = st.file_uploader(
    "音声ファイルをアップロード（最大1GB対応）", 
    type=["mp3", "m4a", "wav"], 
    accept_multiple_files=True
)

if uploaded_files and gemini_key:
    uploaded_files.sort(key=lambda x: x.name)
    
    if st.button("🚀 レポート作成を開始"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(selected_model)
        
        # Geminiに送るコンテンツのリストを作成（プロンプトを最初に入れる）
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        content_to_send = [f"あなたは優秀な専門家です。以下の音声ファイルを時系列順に統合し、レポートを作成してください。\n\n【出力フォーマット】\n{prompts[report_type].format(date=today_str)}"]
        
        temp_files = [] # 削除用リスト
        g_files = []    # Googleサーバー上の削除用

        try:
            # 1. 各ファイルをGoogle File APIにアップロード
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"ファイルを転送中 ({i+1}/{len(uploaded_files)}): {uploaded_file.name}")
                
                # 一時ファイルとして保存
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                    temp_files.append(tmp_path)
                
                # Google File APIへアップロード
                g_file = genai.upload_file(path=tmp_path)
                
                # 処理待ち
                while g_file.state.name == "PROCESSING":
                    time.sleep(2)
                    g_file = genai.get_file(g_file.name)
                
                content_to_send.append(g_file)
                g_files.append(g_file)
                progress_bar.progress(((i + 1) / len(uploaded_files)) * 0.5)

            # 2. レポート生成
            status_text.text("🧠 AIが音声を直接解析してレポートを執筆中...")
            response = model.generate_content(content_to_send)
            
            st.session_state.report_text = response.text
            progress_bar.progress(100)
            status_text.success("完了しました！")
            
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
        
        finally:
            # 3. 【重要】後片付け：Googleサーバーとローカルから削除
            for gf in g_files:
                genai.delete_file(gf.name)
            for tf in temp_files:
                if os.path.exists(tf):
                    os.remove(tf)

# --- 結果表示 ---
if st.session_state.report_text:
    st.divider()
    st.markdown(st.session_state.report_text)
    st.download_button(
        label="💾 レポートを保存",
        data=st.session_state.report_text,
        file_name=f"report_{datetime.date.today()}.md",
        mime="text/markdown"
    )
