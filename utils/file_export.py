from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

def export_chats_to_txt(chats, filename="chats.txt"):
    with open(filename, "w", encoding="utf-8") as f:
        for chat_id, title, chat_type, invite_link, is_admin in chats:
            f.write(f"ID: {chat_id} | {title} | {chat_type} | Admin: {bool(is_admin)} | link: {invite_link}\n")
    return filename


def export_chats_to_pdf(chats, filename="chats.pdf"):
    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    story = []

    for chat_id, title, chat_type, invite_link, is_admin in chats:
        text = f"ID: {chat_id} | {title} | {chat_type} | Admin: {bool(is_admin)} | link: {invite_link}"
        story.append(Paragraph(text, styles["Normal"]))

    doc.build(story)
    return filename
