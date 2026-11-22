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

    .thin-divider {
        border: none;
        border-top: 1px solid #2a2f3d;
        margin: 8px 0;
    }

    [data-testid="chatAvatarIcon-user"],
    [data-testid="chatAvatarIcon-assistant"],
    [data-testid="stChatMessageAvatarUser"],
    [data-testid="stChatMessageAvatarAssistant"],
    .stChatMessageAvatar {
        display: none !important;
    }

    [data-testid="stChatMessage"] {
        padding: 12px 18px !important;
        border-radius: 16px !important;
        margin-bottom: 10px !important;
        max-width: 75% !important;
        width: fit-content !important;
        border: none !important;
    }

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

    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]),
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
        background-color: #262934 !important;
        color: #f0f2f6 !important;
        margin-right: auto !important;
        margin-left: 0 !important;
    }
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) *,
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) * {
        color: #f0f2f6 !important;
    }

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

    .variant-counter {
        color: #9aa0b0;
        font-size: 13px;
        text-align: center;
        user-select: none;
        padding-top: 3px;
    }

    /* Блок с текстом ошибки базы */
    .db-error {
        background-color: #3d1f24;
        border: 1px solid #a63d4a;
        border-radius: 8px;
        padding: 10px 14px;
        color: #ffd7dc;
        font-size: 13px;
        white-space: pre-wrap;
        word-break: break-word;
        margin: 6px 0;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title("Мой личный ChatGPT")


# =====================================================
# АВТОРИЗАЦИЯ (Supabase Auth)
# =====================================================
def _clear_auth():
    for key in ("sb_access_token", "sb_refresh_token", "user_id", "user_email"):
        st.session_state.pop(key, None)


def restore_session() -> bool:
    """Восстанавливает сессию по сохранённым токенам и обновляет их."""
    if "sb_access_token" not in st.session_state:
        return False
    try:
        resp = supabase.auth.set_session(
            st.session_state["sb_access_token"],
            st.session_state["sb_refresh_token"],
        )
    except Exception:
        _clear_auth()
        return False

    if resp.session is None:
        _clear_auth()
        return False

    # Токены могли обновиться — сохраняем свежие
    st.session_state["sb_access_token"] = resp.session.access_token
    st.session_state["sb_refresh_token"] = resp.session.refresh_token
    st.session_state["user_id"] = resp.user.id
    st.session_state["user_email"] = resp.user.email
    return True


def auth_screen():
    st.subheader("Вход")
    mode = st.radio("Действие", ["Войти", "Зарегистрироваться"], horizontal=True)

    email = st.text_input("Email")
    password = st.text_input("Пароль", type="password")

    if st.button(mode, type="primary", use_container_width=True):
        if not email or not password:
            st.error("Заполните email и пароль")
            return
        try:
            if mode == "Войти":
                resp = supabase.auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
            else:
                resp = supabase.auth.sign_up({"email": email, "password": password})
                if resp.session is None:
                    st.warning(
                        "Аккаунт создан, но требуется подтверждение по email. "
                        "Проверьте почту или попросите владельца проекта отключить "
                        "подтверждение в настройках Supabase."
                    )
                    return
        except Exception as e:
            msg = str(getattr(e, "message", "") or e)
            if "already registered" in msg.lower() or "already exists" in msg.lower():
                st.error("Такой email уже зарегистрирован — попробуйте войти")
            elif "invalid login" in msg.lower():
                st.error("Неверный email или пароль")
            else:
                st.error(f"Ошибка авторизации: {msg}")
            return

        session = resp.session
        st.session_state["sb_access_token"] = session.access_token
        st.session_state["sb_refresh_token"] = session.refresh_token
        st.session_state["user_id"] = resp.user.id
        st.session_state["user_email"] = resp.user.email
        st.rerun()

    st.stop()


# --- СОСТОЯНИЕ ---
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None
if "edit_message_id" not in st.session_state:
    st.session_state.edit_message_id = None
if "regenerate" not in st.session_state:
    st.session_state.regenerate = False
if "variant_indices" not in st.session_state:
    st.session_state.variant_indices = {}
if "variant_seen" not in st.session_state:
    st.session_state.variant_seen = {}
if "confirm_delete_id" not in st.session_state:
    st.session_state.confirm_delete_id = None

if not restore_session():
    auth_screen()

OWNER = st.session_state["user_id"]


def show_db_error(where: str, e: Exception):
    """Показывает настоящий текст ошибки Postgres, который Streamlit прячет."""
    msg = getattr(e, "message", None) or getattr(e, "args", [""]) or str(e)
    try:
        msg = msg[0] if isinstance(msg, tuple) else msg
    except Exception:
        pass
    st.markdown(
        f'<div class="db-error">Ошибка базы ({where}):<br>{msg}</div>',
        unsafe_allow_html=True,
    )
    st.stop()


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
        show_db_error("load_history", e)


def build_api_context(raw_history):
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


def create_chat(title: str) -> str:
    """Создаёт чат, привязанный к вошедшему пользователю."""
    new_id = str(uuid.uuid4())
    try:
        supabase.table("chats").insert(
            {"id": new_id, "title": title[:50], "pinned": False, "owner": OWNER}
        ).execute()
    except Exception as e:
        err_text = str(getattr(e, "message", "") or e)
        if "pinned" in err_text.lower() or "owner" in err_text.lower():
            # Колонки нет в базе — вставляем без неё
            try:
                supabase.table("chats").insert(
                    {"id": new_id, "title": title[:50]}
                ).execute()
            except Exception as e2:
                show_db_error("create_chat", e2)
        else:
            show_db_error("create_chat", e)
    return new_id


def save_user_message(prompt_text: str):
    if st.session_state.current_chat_id is None:
        st.session_state.current_chat_id = create_chat(prompt_text)

    try:
        supabase.table("messages").insert(
            {
                "session_id": st.session_state.current_chat_id,
                "role": "user",
                "content": prompt_text,
            }
        ).execute()
    except Exception as e:
        show_db_error("save_user_message", e)


def save_assistant_message(content: str):
    try:
        supabase.table("messages").insert(
            {
                "session_id": st.session_state.current_chat_id,
                "role": "assistant",
                "content": content,
            }
        ).execute()
    except Exception as e:
        show_db_error("save_assistant_message", e)


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

    save_assistant_message(response)
    st.rerun()


def run_regeneration():
    raw_history = load_history(st.session_state.current_chat_id)
    messages_for_api = build_api_context(raw_history)

    while messages_for_api and messages_for_api[-1]["role"] != "user":
        messages_for_api.pop()

    if messages_for_api:
        generate_reply(messages_for_api)
    else:
        st.warning("Нечего перегенерировать: нет сообщения пользователя.")


def reset_chat_view():
    st.session_state.edit_message_id = None
    st.session_state.variant_indices = {}
    st.session_state.variant_seen = {}


def delete_chat(chat_id):
    try:
        supabase.table("messages").delete().eq("session_id", chat_id).execute()
        supabase.table("chats").delete().eq("id", chat_id).execute()
    except Exception as e:
        show_db_error("delete_chat", e)

    if st.session_state.current_chat_id == chat_id:
        st.session_state.current_chat_id = None
    reset_chat_view()
    st.rerun()


def toggle_pin(chat_id, is_pinned: bool):
    try:
        supabase.table("chats").update({"pinned": not is_pinned}).eq("id", chat_id).execute()
    except Exception as e:
        err_text = str(getattr(e, "message", "") or e)
        if "pinned" in err_text.lower():
            st.warning("Колонка pinned не найдена в таблице chats. Выполните в SQL Editor:\n"
                       "alter table chats add column pinned boolean not null default false;")
        else:
            show_db_error("toggle_pin", e)
        return
    st.rerun()


def render_chat_row(chat):
    """Строка чата. Действия (закрепить/удалить) видны только у выбранного чата."""
    chat_id = chat["id"]
    is_pinned = bool(chat.get("pinned"))
    is_active = st.session_state.current_chat_id == chat_id

    label = f"📌 {chat['title']}" if is_pinned else chat["title"]

    if st.button(label, key=f"chat_{chat_id}", use_container_width=True):
        st.session_state.current_chat_id = chat_id
        st.session_state.confirm_delete_id = None
        reset_chat_view()
        st.rerun()

    if is_active:
        col1, col2 = st.columns([1, 1], gap="small")
        with col1:
            if st.button(
                ("🔓 Открепить" if is_pinned else "📌 Закрепить"),
                key=f"pin_{chat_id}",
                use_container_width=True,
            ):
                toggle_pin(chat_id, is_pinned)
        with col2:
            if st.session_state.confirm_delete_id == chat_id:
                if st.button(
                    "Точно удалить?", key=f"confirm_{chat_id}", use_container_width=True
                ):
                    delete_chat(chat_id)
            else:
                if st.button("✕ Удалить", key=f"del_{chat_id}", use_container_width=True):
                    st.session_state.confirm_delete_id = chat_id
                    st.rerun()


# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.header("Мои чаты")
    st.caption(f"Вы вошли как {st.session_state['user_email']}")

    if st.button("Новый чат", use_container_width=True):
        st.session_state.current_chat_id = None
        st.session_state.confirm_delete_id = None
        reset_chat_view()
        st.rerun()

    if st.button("Выйти", use_container_width=True):
        _clear_auth()
        st.session_state.current_chat_id = None
        reset_chat_view()
        st.rerun()

    st.divider()

    try:
        chats = (
            supabase.table("chats")
            .select("*")
            .eq("owner", OWNER)  # только чаты вошедшего пользователя
            .order("created_at", desc=True)
            .execute()
            .data
        )
    except Exception as e:
        show_db_error("load_chats", e)

    if not chats:
        st.write("История пуста.")
    else:
        pinned_chats = [c for c in chats if c.get("pinned")]
        regular_chats = [c for c in chats if not c.get("pinned")]

        for chat in pinned_chats:
            render_chat_row(chat)

        if pinned_chats and regular_chats:
            st.markdown('<hr class="thin-divider">', unsafe_allow_html=True)

        for chat in regular_chats:
            render_chat_row(chat)

# --- ОТРИСОВКА ИСТОРИИ ---
if st.session_state.current_chat_id:
    raw_history = load_history(st.session_state.current_chat_id)
    grouped_history = group_messages(raw_history)

    for i, item in enumerate(grouped_history):
        variants = item["variants"]

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
                            try:
                                supabase.table("messages").update(
                                    {"content": new_text}
                                ).eq("id", message["id"]).execute()

                                for next_item in grouped_history[i + 1 :]:
                                    for v in next_item["variants"]:
                                        supabase.table("messages").delete().eq(
                                            "id", v["id"]
                                        ).execute()
                            except Exception as e:
                                show_db_error("edit_message", e)

                            st.session_state.edit_message_id = None
                            st.session_state.regenerate = True
                            st.rerun()
                    with col2:
                        if st.button("Отмена", key=f"cancel_{message['id']}"):
                            st.session_state.edit_message_id = None
                            st.rerun()

        else:
            group_key = str(variants[0]["id"])
            total = len(variants)

            seen = st.session_state.variant_seen.get(group_key)
            if seen is None or total > seen:
                idx = total - 1
            else:
                idx = min(
                    st.session_state.variant_indices.get(group_key, total - 1),
                    total - 1,
                )

            st.session_state.variant_seen[group_key] = total
            st.session_state.variant_indices[group_key] = idx

            active = variants[idx]
            is_last_block = i == len(grouped_history) - 1

            with st.chat_message("assistant"):
                st.write(active["content"])

                if total > 1 or is_last_block:
                    cols = (
                        st.columns([0.4, 0.9, 0.4, 1.0])
                        if total > 1
                        else st.columns([1.0])
                    )
                    c = 0

                    if total > 1:
                        if cols[0].button(
                            "‹",
                            key=f"prev_{group_key}",
                            disabled=(idx == 0),
                            help="Предыдущий вариант",
                        ):
                            st.session_state.variant_indices[group_key] = idx - 1
                            st.rerun()

                        cols[1].markdown(
                            f'<div class="variant-counter">{idx + 1} / {total}</div>',
                            unsafe_allow_html=True,
                        )

                        if cols[2].button(
                            "›",
                            key=f"next_{group_key}",
                            disabled=(idx == total - 1),
                            help="Следующий вариант",
                        ):
                            st.session_state.variant_indices[group_key] = idx + 1
                            st.rerun()
                        c = 3

                    if is_last_block:
                        if cols[c].button(
                            "⟳",
                            key=f"regen_{group_key}",
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
