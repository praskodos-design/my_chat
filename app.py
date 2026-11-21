import streamlit as st
from openai import OpenAI

# --- НАСТРОЙКИ ---
# Вставьте сюда ваш API-ключ от Groq
API_KEY = st.secrets["API_KEY"]
# Модель Groq (например, llama-3.3-70b-versatile)
MODEL_NAME = "openai/gpt-oss-120b"

# Настройка клиента для работы с Groq
client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

st.title("Мой личный ChatGPT")

# Инициализация истории сообщений в сессии
if "messages" not in st.session_state:
    st.session_state.messages = []

# Отображение истории сообщений при перезагрузке страницы
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Поле ввода для пользователя
if prompt := st.chat_input("Напишите сообщение..."):
    # Добавляем сообщение пользователя в историю и отображаем
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Отправка запроса к API и отображение ответа
    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ],
            stream=True,
        )
        response = st.write_stream(stream)
   
    # Сохраняем ответ ассистента в историю
    st.session_state.messages.append({"role": "assistant", "content": response})
