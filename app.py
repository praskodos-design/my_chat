import streamlit as st
from openai import OpenAI
from supabase import create_client
import uuid

# --- НАСТРОЙКИ ---
API_KEY = st.secrets["API_KEY"]
MODEL_NAME = "openai/gpt-oss-120b"
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

st.set_page_config(page_title="Мой ChatGPT", layout="wide")

# --- CSS СТИЛИ (Делаем красиво) ---
st.markdown("""
<style>
    /* Убираем аватарки */
    [data-testid="chatAvatarIcon-user"] { display: none !important; }
    [data-testid="chatAvatarIcon-assistant"] { display: none !important; }
   
    /* Стили для пузырей сообщений */
    [data-testid="stChatMessage"] {
        padding: 15px;
        border-radius: 15px;
        margin-bottom: 10px;
        max-width: 80%;
    }
   
    /* Сообщения пользователя (справа, синие) */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background-color: #0078FF; /* Синий цвет */
        color: white !important;
        margin-left: auto;
        margin-right: 0;
    }
   
    /* Текст внутри сообщений пользователя тоже белый */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) * {
        color: white !important;
    }

    /* Сообщения ассистента (слева, серые) */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
        background-color: #F0F2F6; /* Серый цвет */
        color: black;
        margin-right: auto;
        margin-left: 0;
    }

    /* Делаем маленькие аккуратные кнопки */
    .stButton > button {
        border-radius: 20px;
        padding: 5px 10px;
        font-size: 14px;
        border: 1px solid #ccc;
        background-color: transparent;
        color: #555;
    }
    .stButton > button:hover {
        background-color: #e0e0e0;
        color: black;
    }
</style>
""", unsafe_allow_html=True)

st.title("Мой личный ChatGPT")

# Инициализация состояний
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
        chats = supabase.table("chats").select("*").order("created_at", desc=True).execute().data
    except: chats = []
       
    if not chats:
        st.write("История пуста.")
    else:
        for chat in chats:
            if st.button(f"💬 {chat['title']}", key=chat['id'], use_container_width=True):
                st.session_state.current_chat_id = chat['id']
                st.session_state.edit_message_id = None
                st.rerun()

# --- ОСНОВНОЙ ЧАТ ---
if st.session_state.current_chat_id:
    try:
        history = supabase.table("messages").select("*").eq("session_id", st.session_state.current_chat_id).order("created_at").execute().data
    except: history = []
   
    for i, message in enumerate(history):
        # Обертка для правильного позиционирования
        with st.chat_message(message["role"]):
            if message["role"] == "user" and st.session_state.edit_message_id != message["id"]:
                st.write(message["content"])
                col1, col2 = st.columns([1, 15])
                with col1:
                    if st.button("✏️", key=f"edit_{message['id']}", help="Редактировать"):
                        st.session_state.edit_message_id = message["id"]
                        st.rerun()
           
            elif message["role"] == "user" and st.session_state.edit_message_id == message["id"]:
                new_text = st.text_area("Редактировать", value=message["content"], key=f"text_{message['id']}")
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("Сохранить", key=f"save_{message['id']}"):
                        supabase.table("messages").update({"content": new_text}).eq("id", message["id"]).execute()
                        for msg_to_delete in history[i+1:]:
                            supabase.table("messages").delete().eq("id", msg_to_delete["id"]).execute()
                        st.session_state.edit_message_id = None
                        st.session_state.rerun_prompt = new_text
                        st.rerun()
                with col2:
                    if st.button("Отмена", key=f"cancel_{message['id']}"):
                        st.session_state.edit_message_id = None
                        st.rerun()
           
            elif message["role"] == "assistant":
                st.write(message["content"])
                if i == len(history) - 1:
                    col1, col2 = st.columns([1, 15])
                    with col1:
                        # Кнопка в виде иконки перезагрузки
                        if st.button("🔄 Сгенерировать заново", key=f"regen_{message['id']}", use_container_width=True):
                            prev_user_msg = history[-2]["content"]
                            supabase.table("messages").delete().eq("id", message["id"]).execute()
                            st.session_state.rerun_prompt = prev_user_msg
                            st.rerun()

# --- ЛОГИКА ОТПРАВКИ ---
prompt = st.chat_input("Напишите сообщение...") or st.session_state.rerun_prompt

if prompt:
    st.session_state.rerun_prompt = None
   
    if not st.session_state.current_chat_id or (history and history[-1]["role"] == "assistant"):
        if not st.session_state.current_chat_id:
            st.session_state.current_chat_id = str(uuid.uuid4())
            new_title = prompt[:30] + "..." if len(prompt) > 30 else prompt
            supabase.table("chats").insert({"id": st.session_state.current_chat_id, "title": new_title}).execute()
       
        supabase.table("messages").insert({
            "session_id": st.session_state.current_chat_id,
            "role": "user",
            "content": prompt
        }).execute()
       
        with st.chat_message("user"):
            st.write(prompt)

    try:
        history = supabase.table("messages").select("*").eq("session_id", st.session_state.current_chat_id).order("created_at").execute().data
    except: history = []

    messages_for_api = [{"role": m["role"], "content": m["content"]} for m in history]

    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages_for_api,
            stream=True,
        )
        response = st.write_stream(stream)
   
    supabase.table("messages").insert({
        "session_id": st.session_state.current_chat_id,
        "role": "assistant",
        "content": response
    }).execute()
   
    st.rerun()
