import uuid

from agents.main_agent import create_library_agent
from config import create_model
from database.init_db import initialize_database


def extract_text(message) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(part for part in parts if part)
    return str(content)


def main() -> None:
    initialize_database()

    model = create_model()
    agent = create_library_agent(model)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print("Trợ lý thư viện đã sẵn sàng.")
    print("Lệnh: /new = hội thoại mới, /exit = thoát")

    while True:
        user_input = input("\nBạn: ").strip()
        if not user_input:
            continue

        command = user_input.lower()
        if command in {"/exit", "exit", "quit"}:
            print("AI: Tạm biệt!")
            break

        if command == "/new":
            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}
            print("AI: Đã bắt đầu một hội thoại mới.")
            continue

        try:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config=config,
            )
            final_message = result["messages"][-1]
            print(f"AI: {extract_text(final_message)}")
        except Exception as exc:
            print(f"AI: Có lỗi xảy ra: {exc}")


if __name__ == "__main__":
    main()
