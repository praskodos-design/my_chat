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

# --- CSS: ТЁМНАЯ ТЕМА ---
st.markdown(
    """
<style>
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div {
        background-color: #0e1117 !important;
        color: #fafafa !important;
    }

    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div {
        background-color: #161a24 !important;
        color: #fafafa !important;
    }
    [data-testid="stSidebar"] * {
        color: #fafafa !important;
    }

    h1, h2, h3, p, span, label, div {
        color: #fafafa;
    }

    [data-testid="stChatInput"] {
        background-color: #1e222d !important;
        border-color: #313646 !important;
    }
    [data-testid="stChatInput"] textarea {
        color: #ffffff !important;
        background-color: #1e222d !important;
    }

    [data-testid="stSidebar"] .stButton > button {
        background-color: #262b38 !important;
        color: #ffffff !important;
        border: 1px solid #363d4f !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: #32394a !important;
        border-color: #4b556e !important;
    }

    /* Скрываем аватары пользователя и бота */
    [data-testid="chatAvatarIcon-user"],
    [data-testid="chatAvatarIcon-assistant"],
    [data-testid="stChatMessageAvatarUser"],
    [data-testid="stChatMessageAvatarAssistant"],
    .stChatMessageAvatar {
        display: none !important;
    }

    /* Пузыри сообщений */
    [data-testid="stChatMessage"] {
        padding: 12px 18px !important;
        border-radius: 16px !important;
        margin-bottom: 10px !important;
        max-width: 75% !important;
        width: fit-content !important;
        border: none !important;
    }

    /* Пользователь: справа, синий */
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

    /* Бот: слева, тёмно-серый */
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

    /* Маленькие невидимые кнопки-иконки под сообщениями */
    [data-testid="stChatMessage"] .stButton > button {
        padding: 2px 6px !important;
        min-height: 26px !important;
        min-width: 30px !important;
        background: transparent !important;
        color: #9aa0b0 !important;
        border: none !important;
        box-shadow: none !important;
        font-size: 15px !important;
    }
    [data-testid="stChatMessage"] .stButton > button:hover {
        background-color: rgba(255, 255, 255, 0.08) !important;
        color: #ffffff !important;
    }
    [data-testid="stChatMessage"] .stButton > button:disabled {
        opacity: 0.3 !important;
    }

    /* Счётчик вариантов */
    .variant-counter {
        color: #9aa0b0;
        font-size: 13px;
        text-align: center;
        user-select: none;
        padding-top: 3px;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title("Мой личный ChatGPT")

# --- СОСТОЯНИЕ ---
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None
if "edit_message_id" not in st.session_state:
    st.session_state.edit_message_id = None
if "regenerate" not in st.session_state:
    st.session_state.regenerate = False
if "variant_indices" not in st.session_state:
    st.session_state.variant_indices = {}  # какой вариант выбрал пользователь стрелками
if "variant_seen" not in st.session_state:
    st.session_state.variant_seen = {}     # сколько вариантов группы видели в прошлый раз


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def group_messages(raw_history):
    """Группирует подряд идущие ответы бота в варианты одного ответа."""
    grouped = []
    for msg in raw_history:
        if msg["role"] == "assistant" and grouped and grouped[-1]["role"] == "assistant":
            grouped[-1]["variants"].append(msg)
        else:
            grouped.append({"role": msg["role"], "variants": [msg]})
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


def build_api_context(raw_history):
    """Собирает контекст для API из выбранных вариантов ответов."""
    messages = []
    for item in group_messages(raw_history):
        variants = item["variants"]
        group_key = str(variants[0]["id"])
        default_idx = len(variants) - 1 if item["role"] == "assistant" else 0
        idx = min(
            st.session_state.variant_indices.get(group_key, default_idx),
            len(variants) - 1,
        )
        if content := variants[idx].get("content"):
            messages.append({"role": item["role"], "content": content})
    return messages


def save_user_message(prompt_text):
    if st.session_state.current_chat_id is None:
        new_id = str(uuid.uuid4())
        supabase.table("chats").insert(
            {"id": new_id, "title": prompt_text[:50]}
        ).execute()
        st.session_state.current_chat_id = new_id

    supabase.table("messages").insert(
        {
            "session_id": st.session_state.current_chat_id,
            "role": "user",
            "content": prompt_text,
        }
    ).execute()


def generate_reply(messages_for_api):
    """Запрашивает ответ у модели, показывает его потоком и сохраняет в базу."""
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


def run_regeneration():
    """Убирает из контекста прошлые ответы бота и генерирует новый вариант."""
    raw_history = load_history(st.session_state.current_chat_id)
    messages_for_api = build_api_context(raw_history)

    # Последним в контексте должен быть запрос пользователя
    while messages_for_api and messages_for_api[-1]["role"] != "user":
        messages_for_api.pop()

    if messages_for_api:
        generate_reply(messages_for_api)


# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.header("Мои чаты")

    if st.button("Новый чат", use_container_width=True):
        st.session_state.current_chat_id = None
        st.session_state.edit_message_id = None
        st.session_state.variant_indices = {}
        st.session_state.variant_seen = {}
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
                key=f"chat_{chat['id']}",
                use_container_width=True,
            ):
                st.session_state.current_chat_id = chat["id"]
                st.session_state.edit_message_id = None
                st.session_state.variant_indices = {}
                st.session_state.variant_seen = {}
                st.rerun()

# --- ОТРИСОВКА ИСТОРИИ ---
if st.session_state.current_chat_id:
    raw_history = load_history(st.session_state.current_chat_id)
    grouped_history = group_messages(raw_history)

    for i, item in enumerate(grouped_history):
        variants = item["variants"]

        # --- Сообщение пользователя ---
        if item["role"] == "user":
            message = variants[0]
            with st.chat_message("user"):
                if st.session_state.edit_message_id != message["id"]:
                    st.write(message["content"])
                    if st.button(
                        "✎",
                        key=f"edit_{message['id']}",
                        help="Редактировать сообщение",
                    ):
                        st.session_state.edit_message_id = message["id"]
                        st.rerun()
                else:
                    new_text = st.text_area(
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

                            # Удаляем всё, что шло после этого сообщения
                            for next_item in grouped_history[i + 1 :]:
                                for v in next_item["variants"]:
                                    supabase.table("messages").delete().eq(
                                        "id", v["id"]
                                    ).execute()

                            st.session_state.edit_message_id = None
                            st.session_state.regenerate = True
                            st.rerun()
                    with col2:
                        if st.button("Отмена", key=f"cancel_{message['id']}"):
                            st.session_state.edit_message_id = None
                            st.rerun()

        # --- Ответ бота с переключением вариантов ---
        else:
            group_key = str(variants[0]["id"])
            total = len(variants)

            # Если вариантов стало больше — показываем самый свежий,
            # иначе оставляем выбор пользователя (или тоже самый свежий)
            seen = st.session_state.variant_seen.get(group_key)
            if seen is None or total > seen:
                idx = total - 1
            else:
                idx = min(st.session_state.variant_indices.get(group_key, total - 1), total - 1)

            st.session_state.variant_seen[group_key] = total
            st.session_state.variant_indices[group_key] = idx

            active = variants[idx]
            is_last_block = i == len(grouped_history) - 1

            with st.chat_message("assistant"):
                st.write(active["content"])

                if total > 1 or is_last_block:
                    cols = st.columns([0.4, 0.9, 0.4, 1.0]) if total > 1 else st.columns([1.0])
                    c = 0

                    if total > 1:
                        if cols[0].button(
                            "‹", key=f"prev_{group_key}",
                            disabled=(idx == 0), help="Предыдущий вариант",
                        ):
                            st.session_state.variant_indices[group_key] = idx - 1
                            st.rerun()

                        cols[1].markdown(
                            f'<div class="variant-counter">{idx + 1} / {total}</div>',
                            unsafe_allow_html=True,
                        )

                        if cols[2].button(
                            "›", key=f"next_{group_key}",
                            disabled=(idx == total - 1), help="Следующий вариант",
                        ):
                            st.session_state.variant_indices[group_key] = idx + 1
                            st.rerun()
                        c = 3

                    if is_last_block:
                        if cols[c].button(
                            "⟳", key=f"regen_{group_key}",
                            help="Сгенерировать ещё раз",
                        ):
                            st.session_state.regenerate = True
                            st.rerun()

# --- ВВОД НОВОГО СООБЩЕНИЯ ---
prompt = st.chat_input("Введите сообщение...")

if prompt:
    save_user_message(prompt)
    raw_history = load_history(st.session_state.current_chat_id)
    generate_reply(build_api_context(raw_history))

# --- ПОВТОРНАЯ ГЕНЕРАЦИЯ ---
if st.session_state.regenerate:
    st.session_state.regenerate = False
    run_regeneration()
