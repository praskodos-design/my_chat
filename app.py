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

client = OpenAI(
    api_key=API_KEY,
    base_url="https://groq.com",
)

st.set_page_config(page_title="Мой ChatGPT", layout="wide")

# --- CSS СТИЛИ (ПРИНУДИТЕЛЬНАЯ ТЁМНАЯ ТЕМА) ---
st.markdown(
    """
<style>
    /* 1. Принудительная тёмная тема для всего приложения */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div {
        background-color: #0e1117 !important;
        color: #fafafa !important;
    }

    /* Тёмная боковая панель и текст в ней */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div {
        background-color: #161a24 !important;
        color: #fafafa !important;
    }
    [data-testid="stSidebar"] * {
        color: #fafafa !important;
    }

    /* Заголовки и обычный текст */
    h1, h2, h3, p, span, label, div {
        color: #fafafa;
    }

    /* Поле ввода сообщения снизу */
    [data-testid="stChatInput"] {
        background-color: #1e222d !important;
        border-color: #313646 !important;
    }
    [data-testid="stChatInput"] textarea {
        color: #ffffff !important;
        background-color: #1e222d !important;
    }

    /* Кнопки в боковой панели */
    [data-testid="stSidebar"] .stButton > button {
        background-color: #262b38 !important;
        color: #ffffff !important;
        border: 1px solid #363d4f !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: #32394a !important;
        border-color: #4b556e !important;
    }

    /* 2. Полностью скрываем иконки человека и робота */
    [data-testid="chatAvatarIcon-user"],
    [data-testid="chatAvatarIcon-assistant"],
    [data-testid="stChatMessageAvatarUser"],
    [data-testid="stChatMessageAvatarAssistant"],
    .stChatMessageAvatar {
        display: none !important;
    }

    /* 3. Общий вид пузырей сообщений */
    [data-testid="stChatMessage"] {
        padding: 12px 18px !important;
        border-radius: 16px !important;
        margin-bottom: 10px !important;
        max-width: 75% !important;
        width: fit-content !important;
        border: none !important;
    }

    /* 4. Сообщения пользователя: справа, синий фон, белые буквы */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]),
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background-color: #2b7fff !important;
        color: #ffffff !important;
        margin-left: auto !important;
        margin-right: 0 !important;
    }
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) *,
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) * {
        color: #ffffff !important;
    }

    /* 5. Сообщения бота: слева, насыщенный тёмно-серый фон, светлые буквы */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]),
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        background-color: #262934 !important;
        color: #f0f2f6 !important;
        margin-right: auto !important;
        margin-left: 0 !important;
    }
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) *,
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) * {
        color: #f0f2f6 !important;
    }

    /* 6. Кнопки редактирования и перегенерации внутри сообщений */
    [data-testid="stChatMessage"] .stButton > button {
        padding: 2px 8px !important;
        font-size: 14px !important;
        border-radius: 8px !important;
        min-height: 28px !important;
        background-color: rgba(255, 255, 255, 0.12) !important;
        color: #ffffff !important;
        border: none !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title("Мой личный ChatGPT")

# --- ИНИЦИАЛИЗАЦИЯ ПЕРЕМЕННЫХ ---
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None
if "edit_message_id" not in st.session_state:
    st.session_state.edit_message_id = None
if "rerun_prompt" not in st.session_state:
    st.session_state.rerun_prompt = None

# --- БОКОВАЯ ПАНЕЛЬ ---
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

# --- ОСНОВНОЙ ЧАТ ---
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
            # Сообщение пользователя
            if message["role"] == "user":
                if st.session_state.edit_message_id != message["id"]:
                    st.write(message["content"])
                    if st.button("✏️", key=f"edit_{message['id']}"):
                        st.session_state.edit_message_id = message["id"]
                        st.rerun()
                else:
                    new_text = st.text_area(
                        "Редактировать",
                        value=message["content"],
                        key=f"text_{message['id']}",
                        label_visibility="collapsed",
                    )
                    col1, col2 = st.columns()
                    with col1:
                        if st.button(
                            "Сохранить", key=f"save_{message['id']}", type="primary"
                        ):
                            supabase.table("messages").update(
                                {"content": new_text}
                            ).eq("id", message["id"]).execute()
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

            # Сообщение ассистента
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

# --- ЛОГИКА ОТПРАВКИ И ГЕНЕРАЦИИ ---
prompt = st.chat_input("Напишите сообщение...")
is_rerun = False

if not prompt and st.session_state.rerun_prompt:
    prompt = st.session_state.rerun_prompt
    is_rerun = True

if prompt:
    st.session_state.rerun_prompt = None

    if not st.session_state.current_chat_id:
        st.session_state.current_chat_id = str(uuid.uuid4())
        new_title = prompt[:30] + "..." if len(prompt) > 30 else prompt
        supabase.table("chats").insert(
            {"id": st.session_state.current_chat_id, "title": new_title}
        ).execute()

    if not is_rerun:
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
        {"role": m["role"], "content": m["content"]}
        for m in history
        if m.get("content")
    ]

    # Убираем висящие в конце ответы бота, если база не успела обновиться
    while messages_for_api and messages_for_api[-1]["role"] != "user":
        messages_for_api.pop()

    if not messages_for_api:
        messages_for_api = [{"role": "user", "content": prompt}]

    with st.chat_message("assistant"):
        try:
            stream = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages_for_api,
