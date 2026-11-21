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
st.title("Мой личный ChatGPT")

# Инициализация состояний (для кнопок редактирования)
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
        with st.chat_message(message["role"]):
            # Если это сообщение пользователя и мы его не редактируем
            if message["role"] == "user" and st.session_state.edit_message_id != message["id"]:
                st.markdown(message["content"])
                col1, col2 = st.columns([1, 10])
                with col1:
                    if st.button("✏️", key=f"edit_{message['id']}", help="Редактировать"):
                        st.session_state.edit_message_id = message["id"]
                        st.rerun()
           
            # Если мы редактируем это сообщение
            elif message["role"] == "user" and st.session_state.edit_message_id == message["id"]:
                new_text = st.text_area("Редактировать", value=message["content"], key=f"text_{message['id']}")
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("Сохранить", key=f"save_{message['id']}"):
                        # Обновляем текст в базе
                        supabase.table("messages").update({"content": new_text}).eq("id", message["id"]).execute()
                       
                        # Удаляем все сообщения, которые были ПОСЛЕ этого (чтобы бот заново ответил)
                        for msg_to_delete in history[i+1:]:
                            supabase.table("messages").delete().eq("id", msg_to_delete["id"]).execute()
                       
                        st.session_state.edit_message_id = None
                        st.session_state.rerun_prompt = new_text # Отправляем на генерацию
                        st.rerun()
                with col2:
                    if st.button("Отмена", key=f"cancel_{message['id']}"):
                        st.session_state.edit_message_id = None
                        st.rerun()
           
            # Ответ ассистента
            elif message["role"] == "assistant":
                st.markdown(message["content"])
                # Кнопка перегенерации (только для последнего сообщения ассистента)
                if i == len(history) - 1:
                    if st.button("🔄 Сгенерировать заново", key=f"regen_{message['id']}"):
                        # Берем текст предыдущего сообщения пользователя
                        prev_user_msg = history[-2]["content"]
                        # Удаляем последний ответ бота
                        supabase.table("messages").delete().eq("id", message["id"]).execute()
                        st.session_state.rerun_prompt = prev_user_msg
                        st.rerun()

# --- ЛОГИКА ОТПРАВКИ И ГЕНЕРАЦИИ ---
# Если есть текст из поля ввода ИЛИ из кнопки "Сгенерировать заново"
prompt = st.chat_input("Напишите сообщение...") or st.session_state.rerun_prompt

if prompt:
    # Очищаем сохраненный промпт для перегенерации
    st.session_state.rerun_prompt = None
   
    # Если это новое сообщение (не перегенерация)
    if not st.session_state.current_chat_id or (history and history[-1]["role"] == "assistant"):
        if not st.session_state.current_chat_id:
            st.session_state.current_chat_id = str(uuid.uuid4())
            new_title = prompt[:30] + "..." if len(prompt) > 30 else prompt
            supabase.table("chats").insert({"id": st.session_state.current_chat_id, "title": new_title}).execute()
       
        # Сохраняем новое сообщение пользователя
        supabase.table("messages").insert({
            "session_id": st.session_state.current_chat_id,
            "role": "user",
            "content": prompt
        }).execute()
        with st.chat_message("user"):
            st.markdown(prompt)

    # Загружаем всю историю заново для контекста
    try:
        history = supabase.table("messages").select("*").eq("session_id", st.session_state.current_chat_id).order("created_at").execute().data
    except: history = []

    messages_for_api = [{"role": m["role"], "content": m["content"]} for m in history]

    # Запрос к API
    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages_for_api,
            stream=True,
        )
        response = st.write_stream(stream)
   
    # Сохраняем ответ
    supabase.table("messages").insert({
        "session_id": st.session_state.current_chat_id,
        "role": "assistant",
        "content": response
    }).execute()
   
    st.rerun()
