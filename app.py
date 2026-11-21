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

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Мой ChatGPT", layout="wide")
st.title("Мой личный ChatGPT")

# Инициализация ID текущего чата
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.header("Мои чаты")
   
    # Кнопка нового чата
    if st.button("➕ Новый чат", use_container_width=True):
        st.session_state.current_chat_id = None
        st.rerun()
       
    st.divider()
   
    # Загружаем список всех чатов из базы
    try:
        chats_response = supabase.table("chats").select("*").order("created_at", desc=True).execute()
        chats = chats_response.data
    except Exception as e:
        chats = []
       
    if not chats:
        st.write("История пуста.")
    else:
        for chat in chats:
            # Кнопка для выбора чата
            if st.button(f"💬 {chat['title']}", key=chat['id'], use_container_width=True):
                st.session_state.current_chat_id = chat['id']
                st.rerun()

# --- ОСНОВНОЙ ЧАТ ---
if st.session_state.current_chat_id:
    # Загружаем историю для выбранного чата
    try:
        response = supabase.table("messages").select("*").eq("session_id", st.session_state.current_chat_id).order("created_at").execute()
        history = response.data
    except:
        history = []
       
    for message in history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Поле ввода
if prompt := st.chat_input("Напишите сообщение..."):
    # Если чата нет, создаем новый
    if not st.session_state.current_chat_id:
        st.session_state.current_chat_id = str(uuid.uuid4())
        new_title = prompt[:30] + "..." if len(prompt) > 30 else prompt
        try:
            supabase.table("chats").insert({
                "id": st.session_state.current_chat_id,
                "title": new_title
            }).execute()
        except Exception as e:
            st.error(f"Ошибка при создании чата: {e}")
   
    # Сохраняем сообщение пользователя
    try:
        supabase.table("messages").insert({
            "session_id": st.session_state.current_chat_id,
            "role": "user",
            "content": prompt
        }).execute()
    except Exception as e:
        st.error(f"Ошибка БД (user): {e}")
   
    with st.chat_message("user"):
        st.markdown(prompt)

    # Формируем историю для API
    messages_for_api = []
    if 'history' in locals():
        messages_for_api = [{"role": m["role"], "content": m["content"]} for m in history]
    messages_for_api.append({"role": "user", "content": prompt})

    # Запрос к API
    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages_for_api,
            stream=True,
        )
        response = st.write_stream(stream)
   
    # Сохраняем ответ ассистента
    try:
        supabase.table("messages").insert({
            "session_id": st.session_state.current_chat_id,
            "role": "assistant",
            "content": response
        }).execute()
    except Exception as e:
        st.error(f"Ошибка БД (assistant): {e}")
       
    st.rerun()
