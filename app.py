import uuid

import streamlit as st
from openai import OpenAI
from supabase import create_client

# --- НАСТРОЙКИ ---
API_KEY = st.secrets["API_KEY"]
MODEL_NAME = "openai/gpt-oss-120b"
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

client = OpenAI(api_key=API_KEY, base_url="https://api.groq.com/openai/v1")

st.set_page_config(page_title="Мой ChatGPT", layout="wide")

# --- CSS СТИЛИ ---
st.markdown(
    """
<style>
    [data-testid="chatAvatarIcon-user"],
    [data-testid="chatAvatarIcon-assistant"],
    .stChatMessageAvatar {
        display: none !important;
    }

    [data-testid="stChatMessage"] {
        padding: 15px 20px;
        border-radius: 15px;
        margin-bottom: 10px;
        max-width: 85%;
        border: none !important;
    }

    [data-testid="stChatMessage"]:has(> div > [data-testid="chatAvatarIcon-user"]) {
        background-color: #2b7fff !important;
        color: white !important;
        margin-left: auto !important;
        margin-right: 0 !important;
    }
    [data-testid="stChatMessage"]:has(> div > [data-testid="chatAvatarIcon-user"]) * {
        color: white !important;
    }

    [data-testid="stChatMessage"]:has(> div > [data-testid="chatAvatarIcon-assistant"]) {
        background-color: #f0f2f6 !important;
        color: black !important;
        margin-right: auto !important;
        margin-left: 0 !important;
    }
    [data-testid="stChatMessage"]:has(> div > [data-testid="chatAvatarIcon-assistant"]) * {
        color: black !important;
    }

    .stButton > button {
        padding: 2px 8px !important;
        font-size: 14px !important;
        border-radius: 8px !important;
        min-height: 30px !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title("Мой личный ChatGPT")

if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None
if "edit_message_id" not in st.session_state:
    st.session_state.edit_message_id = None
if "rerun_prompt" not in st.session_state:
    st.session_state.rerun_prompt = None

with st.sidebar:
    st.header("Мои чаты")
    if st.button("➕ Новый чат", use_container_width=True):
        st.session_state.current_chat_id = None
        st.session_state.edit_message_id = None
        st.rerun()
    st.divider()

    try:
        chats = (
            supabase.table("chats")
            .select("*")
            .order("created_at", desc=True)
            .execute()
            .data
        )
    except Exception:
        chats = []

    if not chats:
        st.write("История пуста.")
    else:
        for chat in chats:
            if st.button(
                f"💬 {chat['title']}", key=chat["id"], use_container_width=True
            ):
                st.session_state.current_chat_id = chat["id"]
                st.session_state.edit_message_id = None
                st.rerun()

history = []

if st.session_state.current_chat_id:
    try:
        history = (
            supabase.table("messages")
            .select("*")
            .eq("session_id", st.session_state.current_chat_id)
            .order("created_at")
            .execute()
            .data
        )
    except Exception:
        history = []

    for i, message in enumerate(history):
        with st.chat_message(message["role"]):
            if (
                message["role"] == "user"
                and st.session_state.edit_message_id != message["id"]
            ):
                st.write(message["content"])
                if st.button("✏️", key=f"edit_{message['id']}"):
                    st.session_state.edit_message_id = message["id"]
                    st.rerun()

            elif (
                message["role"] == "user"
                and st.session_state.edit_message_id == message["id"]
            ):
                new_text = st.text_area(
                    "Редактировать",
                    value=message["content"],
                    key=f"text_{message['id']}",
                    label_visibility="collapsed",
                )
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button(
                        "Сохранить", key=f"save_{message['id']}", type="primary"
                    ):
                        supabase.table("messages").update({"content": new_text}).eq(
                            "id", message["id"]
                        ).execute()
                        for msg_to_delete in history[i + 1 :]:
                            supabase.table("messages").delete().eq(
                                "id", msg_to_delete["id"]
                            ).execute()
                        st.session_state.edit_message_id = None
                        st.session_state.rerun_prompt = new_text
                        st.rerun()
                with col2:
                    if st.button("Отмена", key=f"cancel_{message['id']}"):
                        st.session_state.edit_message_id = None
                        st.rerun()

            elif message["role"] == "assistant":
                st.write(message["content"])
                if i == len(history) - 1 and len(history) >= 2:
                    if st.button(
                        "🔄",
                        key=f"regen_{message['id']}",
                        help="Сгенерировать заново",
                    ):
                        prev_user_msg = history[-2]["content"]
                        supabase.table("messages").delete().eq(
                            "id", message["id"]
                        ).execute()
                        st.session_state.rerun_prompt = prev_user_msg
                        st.rerun()

prompt = st.chat_input("Напишите сообщение...") or st.session_state.rerun_prompt

if prompt:
    st.session_state.rerun_prompt = None

    if not st.session_state.current_chat_id or (
        history and history[-1]["role"] == "assistant"
    ):
        if not st.session_state.current_chat_id:
            st.session_state.current_chat_id = str(uuid.uuid4())
            new_title = prompt[:30] + "..." if len(prompt) > 30 else prompt
            supabase.table("chats").insert(
                {"id": st.session_state.current_chat_id, "title": new_title}
            ).execute()

        supabase.table("messages").insert(
            {
                "session_id": st.session_state.current_chat_id,
                "role": "user",
                "content": prompt,
            }
        ).execute()

        with st.chat_message("user"):
            st.write(prompt)

    try:
        history = (
            supabase.table("messages")
            .select("*")
            .eq("session_id", st.session_state.current_chat_id)
            .order("created_at")
            .execute()
            .data
        )
    except Exception:
        history = []

    messages_for_api = [
        {"role": m["role"], "content": m["content"]} for m in history
    ]

    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages_for_api,
            stream=True,
        )
        response = st.write_stream(stream)

    supabase.table("messages").insert(
        {
            "session_id": st.session_state.current_chat_id,
            "role": "assistant",
            "content": response,
        }
    ).execute()

    st.rerun()
