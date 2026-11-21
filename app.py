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
    base_url="https://api.groq.com/openai/v1",  # FIX: был "https://groq.com"
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

    /* 6. Строгие компактные кнопки действий и стрелок */
    [data-testid="stChatMessage"] .stButton > button {
        padding: 2px 8px !important;
        font-size: 13px !important;
        border-radius: 8px !important;
        min-height: 28px !important;
        background-color: rgba(255, 255, 255, 0.08) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
    }
    [data-testid="stChatMessage"] .stButton > button:hover {
        background-color: rgba(255, 255, 255, 0.18) !important;
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
if "variant_indices" not in st.session_state:
    st.session_state.variant_indices = {}


def group_messages(raw_history):
    """Группирует подряд идущие ответы бота в варианты (версии) одного ответа."""
    grouped = []
    for msg in raw_history:
        if msg["role"] == "assistant" and grouped and grouped[-1]["role"] == "assistant":
            grouped[-1]["variants"].append(msg)
        else:
            grouped.append(
                {
                    "role": msg["role"],
                    "variants": [msg],
                }
            )
    return grouped


def load_history(chat_id):
    try:
        return (
            supabase.table("messages")
            .select("*")
            .eq("session_id", chat_id)
            .order("created_at")
            .order("id")
            .execute()
            .data
        )
    except Exception as e:
        st.error(f"Ошибка при загрузке истории: {e}")
        return []


def create_chat_and_save_user(prompt_text):
    """Создаёт новый чат (если нужно) и сохраняет сообщение пользователя."""
    if st.session_state.current_chat_id is None:
        new_id = str(uuid.uuid4())
        supabase.table("chats").insert({"id": new_id, "title": prompt_text[:50]}).execute()
        st.session_state.current_chat_id = new_id

    supabase.table("messages").insert(
        {
            "session_id": st.session_state.current_chat_id,
            "role": "user",
            "content": prompt_text,
        }
    ).execute()


def stream_assistant_reply(messages_for_api):
    """Обращается к модели, показывает ответ потоком и сохраняет его в базу."""
    with st.chat_message("assistant"):
        try:
            stream = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages_for_api,
                stream=True,
            )
            response = st.write_stream(stream)
        except Exception as e:
            st.error(f"Ошибка при обращении к Groq: {e}")
            st.stop()

    supabase.table("messages").insert(
        {
            "session_id": st.session_state.current_chat_id,
            "role": "assistant",
            "content": response,
        }
    ).execute()

    st.rerun()


# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.header("Мои чаты")

    if st.button("Новый чат", icon=":material/add:", use_container_width=True):
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
    except Exception as e:
        st.error(f"Ошибка при загрузке чатов: {e}")
        chats = []

    if not chats:
        st.write("История пуста.")
    else:
        for chat in chats:
            if st.button(
                chat["title"],
                icon=":material/chat_bubble_outline:",
                key=f"chat_{chat['id']}",  # FIX: префикс, чтобы не пересекаться с другими key
                use_container_width=True,
            ):
                st.session_state.current_chat_id = chat["id"]
                st.session_state.edit_message_id = None
                st.rerun()

# --- ОСНОВНОЙ ЧАТ ---
raw_history = []
grouped_history = []

if st.session_state.current_chat_id:
    raw_history = load_history(st.session_state.current_chat_id)
    grouped_history = group_messages(raw_history)

    for i, item in enumerate(grouped_history):
        role = item["role"]
        variants = item["variants"]

        # --- Сообщение пользователя ---
        if role == "user":
            message = variants[0]
            with st.chat_message("user"):
                if st.session_state.edit_message_id != message["id"]:
                    st.write(message["content"])
                    if st.button(
                        "",
                        icon=":material/edit:",
                        key=f"edit_{message['id']}",
                        help="Редактировать сообщение",
                    ):
                        st.session_state.edit_message_id = message["id"]
                        st.rerun()
                else:
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
                            supabase.table("messages").update(
                                {"content": new_text}
                            ).eq("id", message["id"]).execute()

                            # Удаляем все последующие сообщения и варианты в ветке
                            for next_item in grouped_history[i + 1 :]:
                                for v in next_item["variants"]:
                                    supabase.table("messages").delete().eq(
                                        "id", v["id"]
                                    ).execute()

                            st.session_state.edit_message_id = None
                            st.session_state.rerun_prompt = new_text
                            st.rerun()
                    with col2:
                        if st.button("Отмена", key=f"cancel_{message['id']}"):
                            st.session_state.edit_message_id = None
                            st.rerun()

        # --- Сообщение ассистента (с переключением вариантов) ---
        elif role == "assistant":
            group_key = str(variants[0]["id"])
            total_variants = len(variants)

            # По умолчанию показываем самый последний сгенерированный вариант
            if group_key not in st.session_state.variant_indices:
                st.session_state.variant_indices[group_key] = total_variants - 1

            current_idx = st.session_state.variant_indices[group_key]
            if current_idx >= total_variants:
                current_idx = total_variants - 1
                st.session_state.variant_indices[group_key] = current_idx

            active_message = variants[current_idx]

            with st.chat_message("assistant"):
                st.write(active_message["content"])

                # Панель управления под ответом
                is_last_block = i == len(grouped_history) - 1
                has_multiple = total_variants > 1

                if has_multiple or is_last_block:
                    cols = st.columns([1, 1.3, 1, 1])

                    # Стрелка влево — предыдущий вариант
                    if has_multiple:
                        with cols[0]:
                            if st.button(
                                "◀",
                                key=f"prev_{group_key}",
                                disabled=(current_idx == 0),
                            ):
                                st.session_state.variant_indices[group_key] = (
                                    current_idx - 1
                                )
                                st.rerun()

                    # Счётчик вариантов (или подпись для одиночного ответа)
                    if has_multiple:
                        cols[1].write(f"Вариант {current_idx + 1} из {total_variants}")

                    # Стрелка вправо — следующий вариант
                    if has_multiple:
                        with cols[2]:
                            if st.button(
                                "▶",
                                key=f"next_{group_key}",
                                disabled=(current_idx == total_variants - 1),
                            ):
                                st.session_state.variant_indices[group_key] = (
                                    current_idx + 1
                                )
                                st.rerun()

                    # Кнопка перегенерации — только на последнем блоке
                    if is_last_block:
                        with cols[3]:
                            if st.button(
                                "🔄",
                                key=f"regen_{group_key}",
                                help="Сгенерировать новый вариант",
                            ):
                                # Собираем контекст для API
                                grouped_for_api = group_messages(raw_history)
                                messages_for_api = []
                                for api_item in grouped_for_api:
                                    api_variants = api_item["variants"]
                                    api_key = str(api_variants[0]["id"])
                                    default_idx = (
                                        len(api_variants) - 1
                                        if api_item["role"] == "assistant"
                                        else 0
                                    )
                                    idx = min(
                                        st.session_state.variant_indices.get(
                                            api_key, default_idx
                                        ),
                                        len(api_variants) - 1,
                                    )
                                    if content := api_variants[idx].get("content"):
                                        messages_for_api.append(
                                            {
                                                "role": api_item["role"],
                                                "content": content,
                                            }
                                        )

                                # Убираем с конца прошлые ответы бота,
                                # чтобы последним был запрос пользователя
                                while messages_for_api and messages_for_api[-1]["role"] != "user":
                                    messages_for_api.pop()

                                if not messages_for_api:
                                    st.error("Нет запроса пользователя для перегенерации.")
                                    st.stop()

                                stream_assistant_reply(messages_for_api)

# --- ВВОД НОВОГО СООБЩЕНИЯ ---
prompt = st.chat_input("Введите сообщение...")

if prompt:
    create_chat_and_save_user(prompt)

    raw_history = load_history(st.session_state.current_chat_id)
    grouped_for_api = group_messages(raw_history)
    messages_for_api = []
    for item in grouped_for_api:
        idx = 0 if item["role"] == "user" else len(item["variants"]) - 1
        if content := item["variants"][idx].get("content"):
            messages_for_api.append({"role": item["role"], "content": content})

    stream_assistant_reply(messages_for_api)

# --- ПОВТОРНАЯ ГЕНЕРАЦИЯ ПОСЛЕ РЕДАКТИРОВАНИЯ ---
if st.session_state.rerun_prompt:
    text = st.session_state.rerun_prompt
    st.session_state.rerun_prompt = None
    create_chat_and_save_user(text)

    raw_history = load_history(st.session_state.current_chat_id)
    grouped_for_api = group_messages(raw_history)
    messages_for_api = []
    for item in grouped_for_api:
        idx = 0 if item["role"] == "user" else len(item["variants"]) - 1
        if content := item["variants"][idx].get("content"):
            messages_for_api.append({"role": item["role"], "content": content})

    stream_assistant_reply(messages_for_api)
