import io
import re
import markdown
from xhtml2pdf import pisa

def export_chat_pdf_buffer(chat_title, msgs):
    html_content = f"<h1 style='text-align:center; color:#0f172a;'>{chat_title}</h1><hr style='border:1px solid #e2e8f0;'>"
    
    for role, content in msgs:
        clean_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        clean_content = re.sub(r'!\[.*?\]\(.*?\)', '<i>[System: Image Attachment]</i>', clean_content)
        parsed_html = markdown.markdown(clean_content, extensions=['tables', 'fenced_code'])
        
        if role == 'user':
            html_content += f"<div style='background-color:#e0f2fe; padding:15px; border-radius:10px; margin-bottom:15px; border-left: 4px solid #38bdf8;'><b>User:</b><br>{parsed_html}</div>"
        else:
            html_content += f"<div style='background-color:#f8fafc; padding:15px; border-radius:10px; margin-bottom:15px; border:1px solid #cbd5e1;'><b>Assistant:</b><br>{parsed_html}</div>"

    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8">
    <style>
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; }}
        pre {{ background: #1e293b; color: #f8fafc; padding: 12px; border-radius: 8px; white-space: pre-wrap; word-wrap: break-word; }}
        code {{ font-family: monospace; background: #f1f5f9; color:#ef4444; padding:2px 4px; border-radius:4px; }}
        pre code {{ background: transparent; color: inherit; }}
    </style>
    </head>
    <body>{html_content}</body></html>
    """
    
    pdf_buffer = io.BytesIO()
    pisa.CreatePDF(io.StringIO(styled_html), dest=pdf_buffer)
    return pdf_buffer.getvalue()

def create_document_pdf(markdown_content, output_filepath):
    html_body = markdown.markdown(markdown_content, extensions=['tables', 'fenced_code'])
    
    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 20mm;
            }}
            body {{
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                line-height: 1.6;
                color: #333333;
            }}
            h1 {{ color: #0284c7; border-bottom: 2px solid #e2e8f0; padding-bottom: 5px; }}
            h2 {{ color: #0f172a; margin-top: 20px; }}
            h3 {{ color: #334155; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 15px; }}
            th, td {{ border: 1px solid #cbd5e1; padding: 10px; text-align: left; }}
            th {{ background-color: #f1f5f9; font-weight: bold; }}
            code {{ background-color: #f8fafc; padding: 2px 4px; border-radius: 4px; font-family: monospace; }}
            pre {{ background-color: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; overflow-x: auto; }}
            pre code {{ background-color: transparent; padding: 0; }}
            blockquote {{ border-left: 4px solid #cbd5e1; padding-left: 15px; color: #64748b; margin-left: 0; }}
        </style>
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """
    
    with open(output_filepath, "wb") as pdf_file:
        pisa.CreatePDF(styled_html, dest=pdf_file)