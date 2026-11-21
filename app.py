import streamlit as st
from openai import OpenAI
from supabase import create_client
import uuid

# --- НАСТРОЙКИ ---
API_KEY = st.secrets["API_KEY"]
MODEL_NAME = "openai/gpt-oss-120b"

# Подключение к базе данных Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

st.title("Мой личный ChatGPT")

# Генерируем уникальный ID сессии для каждого пользователя, чтобы истории не смешивались
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Загружаем историю из базы данных
def load_history():
    response = supabase.table("messages").select("*").eq("session_id", st.session_state.session_id).order("created_at").execute()
    return response.data

history = load_history()

# Отображаем историю
for message in history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Поле ввода
if prompt := st.chat_input("Напишите сообщение..."):
    # Сохраняем сообщение пользователя в базу
    supabase.table("messages").insert({
        "session_id": st.session_state.session_id,
        "role": "user",
        "content": prompt
    }).execute()
   
    with st.chat_message("user"):
        st.markdown(prompt)

    # Формируем историю для отправки нейросети
    messages_for_api = [{"role": m["role"], "content": m["content"]} for m in history]
    messages_for_api.append({"role": "user", "content": prompt})

    # Отправка запроса к API
    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages_for_api,
            stream=True,
        )
        response = st.write_stream(stream)
   
    # Сохраняем ответ ассистента в базу
    supabase.table("messages").insert({
        "session_id": st.session_state.session_id,
        "role": "assistant",
        "content": response
    }).execute()
