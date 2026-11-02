import logging
import re
import sys
import uuid

from agents.main_agent import create_library_agent
from config import create_model, get_demo_member_id
from langchain_core.callbacks import UsageMetadataCallbackHandler
from database.init_db import initialize_database
from tools.transaction_context import (
    TrustedTransactionContext,
    trusted_transaction_context,
)

CONFIRMATION_MARKER = re.compile(r"\[\[CONFIRM_(BORROW|RETURN):([0-9]+)\]\]")

logger = logging.getLogger(__name__)


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

    try:
        demo_member_id = get_demo_member_id()
    except (RuntimeError, ValueError) as exc:
        demo_member_id = None
        demo_member_error = str(exc)
    else:
        demo_member_error = None

    model = create_model()
    agent = create_library_agent(model)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    pending_confirmation: tuple[str, int] | None = None

    print("Trợ lý thư viện đã sẵn sàng.")
    print("Chế độ demo CLI cục bộ; DEMO_MEMBER_ID không phải xác thực nhiều người dùng.")
    if demo_member_id is None:
        print(f"AI: {demo_member_error}")
        print("AI: Đã tắt thao tác mượn/trả cho đến khi DEMO_MEMBER_ID được cấu hình.")
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
            pending_confirmation = None
            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}

            print("AI: Đã bắt đầu một hội thoại mới.")
            continue

        confirmed_action = None
        confirmed_resource_id = None
        if command == "/cancel":
            pending_confirmation = None
            print("AI: Đã hủy xác nhận đang chờ.")
            continue
        if command == "/confirm":
            if pending_confirmation is None:
                print("AI: Không có giao dịch cụ thể nào đang chờ xác nhận.")
                continue
            if demo_member_id is None:
                print("AI: Cần cấu hình DEMO_MEMBER_ID trước khi xác nhận giao dịch.")
                pending_confirmation = None
                continue
            confirmed_action, confirmed_resource_id = pending_confirmation
            pending_confirmation = None
            user_input = (
                f"Người dùng đã nhập /confirm để xác nhận đúng thao tác "
                f"{confirmed_action} cho mã đích {confirmed_resource_id}. "
                "Chỉ thực hiện đúng thao tác và mã đích này."
            )
        else:
            # A new user turn invalidates an older confirmation target.
            pending_confirmation = None

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
            agent_input = {
                "messages": [{"role": "user", "content": user_input}]
            }
            usage_callback = UsageMetadataCallbackHandler()
            invocation_config = {
                **config,
                "callbacks": [usage_callback],
            }
            if demo_member_id is None:
                result = agent.invoke(agent_input, config=invocation_config)
            else:
                trusted_context = TrustedTransactionContext(
                    actor_id="local-demo-cli",
                    member_id=demo_member_id,
                    authorization_granted=True,
                    confirmation_verified=confirmed_action is not None,
                    loan_days=14,
                    max_active_loans=3,
                    confirmed_action=confirmed_action,
                    confirmed_resource_id=confirmed_resource_id,
                )
                with trusted_transaction_context(trusted_context):
                    result = agent.invoke(agent_input, config=invocation_config)

            for model_name, usage in usage_callback.usage_metadata.items():
                print(
                    "[Token usage] "
                    f"model={model_name} "
                    f"input={usage.get('input_tokens')} "
                    f"output={usage.get('output_tokens')}",
                    file=sys.stderr,
                )

            final_message = result["messages"][-1]
            response_text = extract_text(final_message)
            markers = list(CONFIRMATION_MARKER.finditer(response_text))
            response_text = CONFIRMATION_MARKER.sub("", response_text).strip()
            if len(markers) == 1 and demo_member_id is not None:
                action = markers[0].group(1).lower()
                resource_id = int(markers[0].group(2))
                if resource_id > 0:
                    pending_confirmation = (action, resource_id)
                    action_label = "mượn sách" if action == "borrow" else "trả sách"
                    resource_label = "mã sách" if action == "borrow" else "mã phiếu"
                    response_text += (
                        f"\nĐích xác nhận: {action_label}, {resource_label} {resource_id}. "
                        "Hãy kiểm tra đúng sách/phiếu ở trên; nhập /confirm để tiếp tục "
                        "hoặc /cancel để hủy."
                    )
            elif markers and demo_member_id is None:
                response_text += "\nMượn/trả bị tắt: hãy cấu hình DEMO_MEMBER_ID trong .env."

            print(f"AI: {response_text}")

        except Exception:
            logger.exception("Library agent request failed")
            print("AI: Đã xảy ra lỗi khi xử lý yêu cầu. Vui lòng thử lại sau.")


if __name__ == "__main__":
    main()