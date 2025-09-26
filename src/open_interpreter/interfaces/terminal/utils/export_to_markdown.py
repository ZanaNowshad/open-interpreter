from ..components.ui import icon_for_role, icon_for_status
from .markdown_pipeline import render_markdown_text


def export_to_markdown(messages: list[dict], export_path: str):
    markdown = messages_to_markdown(messages)
    with open(export_path, "w") as f:
        f.write(markdown)
    print(f"Exported current conversation to {export_path}")


def messages_to_markdown(messages: list[dict]) -> str:
    # Convert interpreter.messages to Markdown text
    markdown_content = ""
    previous_role = None
    for chunk in messages:
        current_role = chunk["role"]
        if current_role == previous_role:
            rendered_chunk = ""
        else:
            heading_role = current_role.replace("_", " ").title()
            role_icon = icon_for_role(current_role)
            status_icon = (
                f" {icon_for_status(chunk.get('status'))}"
                if chunk.get("status")
                else ""
            )
            rendered_chunk = f"## {role_icon} {heading_role}{status_icon}\n\n"
            previous_role = current_role

        # User query message
        if chunk["role"] == "user":
            rendered_chunk += render_markdown_text(chunk["content"]) + "\n\n"
            markdown_content += rendered_chunk
            continue

        # Message
        if chunk["type"] == "message":
            rendered_chunk += render_markdown_text(chunk["content"]) + "\n\n"

        # Code
        if chunk["type"] == "code" or chunk["type"] == "console":
            code_format = chunk.get("format", "")
            rendered_chunk += f"```{code_format}\n{chunk['content']}\n```\n\n"

        markdown_content += rendered_chunk

    return markdown_content
