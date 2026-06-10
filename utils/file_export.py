from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from xml.sax.saxutils import escape as xml_escape
from utils.timezone import format_samarkand

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


def export_referral_chats_to_txt(link_name, public_url, chats, filename="referral_chats.txt"):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Giper ssilka: {link_name}\n")
        f.write(f"Ssilka: {public_url}\n")
        f.write(f"Bot admin bo‘lgan guruh/kanallar soni: {len(chats)}\n")
        f.write("=" * 60 + "\n\n")

        if not chats:
            f.write("Bu ssilka orqali bot admin qilingan guruh/kanal topilmadi.\n")
            return filename

        for i, row in enumerate(chats, start=1):
            chat_id, title, chat_type, is_admin, bot_status, added_at, added_by = row
            f.write(f"{i}. {title or chat_id}\n")
            f.write(f"   ID: {chat_id}\n")
            f.write(f"   Turi: {chat_type}\n")
            f.write(f"   Status: {bot_status} | Admin: {bool(is_admin)}\n")
            f.write(f"   Qo‘shilgan: {format_samarkand(added_at)}\n")
            if added_by:
                f.write(f"   Kim qo‘shgan: {added_by}\n")
            f.write("\n")
    return filename


def export_referral_chats_to_pdf(link_name, public_url, chats, filename="referral_chats.pdf"):
    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>Giper ssilka:</b> {xml_escape(str(link_name))}", styles["Title"]))
    story.append(Paragraph(f"<b>Ssilka:</b> {xml_escape(str(public_url))}", styles["Normal"]))
    story.append(Paragraph(f"<b>Bot admin bo‘lgan guruh/kanallar soni:</b> {len(chats)}", styles["Normal"]))
    story.append(Paragraph("<br/>", styles["Normal"]))

    if not chats:
        story.append(Paragraph("Bu ssilka orqali bot admin qilingan guruh/kanal topilmadi.", styles["Normal"]))
    else:
        for i, row in enumerate(chats, start=1):
            chat_id, title, chat_type, is_admin, bot_status, added_at, added_by = row
            added_by_text = f" | Kim qo‘shgan: {added_by}" if added_by else ""
            text = (
                f"<b>{i}. {xml_escape(str(title or chat_id))}</b><br/>"
                f"ID: {chat_id} | Turi: {xml_escape(str(chat_type))} | Status: {xml_escape(str(bot_status))} | Admin: {bool(is_admin)}<br/>"
                f"Qo‘shilgan: {xml_escape(format_samarkand(added_at))}{xml_escape(str(added_by_text))}"
            )
            story.append(Paragraph(text, styles["Normal"]))
            story.append(Paragraph("<br/>", styles["Normal"]))

    doc.build(story)
    return filename
