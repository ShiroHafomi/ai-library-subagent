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
    print("Lệnh:")
    print("  /new = hội thoại mới")
    print("  /borrow = yêu cầu mượn sách")
    print("  /exit = thoát")
    print()
    print("Bạn cũng có thể nhập trực tiếp:")
    print('  "Tôi muốn mượn sách Clean Code"')

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

        # Shortcut để bắt đầu yêu cầu mượn sách.
        # Main Agent vẫn quyết định delegation.
        if command == "/borrow":
            user_input = (
                "Tôi muốn mượn sách. "
                "Hãy giúp tôi kiểm tra điều kiện mượn, "
                "thu thập thông tin cần thiết và yêu cầu "
                "xác nhận trước khi thực hiện."
            )

        elif command.startswith("/borrow "):
            book_title = user_input[len("/borrow "):].strip()

            if not book_title:
                print("AI: Vui lòng nhập tên sách.")
                continue

            user_input = (
                f"Tôi muốn mượn sách '{book_title}'. "
                "Hãy kiểm tra điều kiện mượn và hướng dẫn "
                "tôi xác nhận trước khi thực hiện."
            )

        try:
            result = agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": user_input,
                        }
                    ]
                },
                config=config,
            )

            final_message = result["messages"][-1]

            print(f"AI: {extract_text(final_message)}")

        except Exception as exc:
            print(f"AI: Có lỗi xảy ra: {exc}")


if __name__ == "__main__":
    main()