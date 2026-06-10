from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

def export_chats_to_txt(chats, filename="chats.txt"):
    with open(filename, "w", encoding="utf-8") as f:
        for row in chats:
            chat_id, title, chat_type, invite_link, is_admin = row[:5]
            bot_status = row[5] if len(row) > 5 else "unknown"
            f.write(f"ID: {chat_id} | {title} | {chat_type} | Admin: {bool(is_admin)} | Status: {bot_status} | link: {invite_link}\n")
    return filename


def export_chats_to_pdf(chats, filename="chats.pdf"):
    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    story = []

    for row in chats:
        chat_id, title, chat_type, invite_link, is_admin = row[:5]
        bot_status = row[5] if len(row) > 5 else "unknown"
        text = f"ID: {chat_id} | {title} | {chat_type} | Admin: {bool(is_admin)} | Status: {bot_status} | link: {invite_link}"
        story.append(Paragraph(text, styles["Normal"]))

    doc.build(story)
    return filename
