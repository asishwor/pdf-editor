from flask import Flask, request, send_file
from flask_cors import CORS
import fitz
import io, base64, os, re, html

app = Flask(__name__)
CORS(app)

HTML_PAGE = open(os.path.join(os.path.dirname(__file__), 'index.html'), encoding='utf-8').read()

@app.route('/')
def index():
    return HTML_PAGE, 200, {'Content-Type': 'text/html; charset=utf-8'}


def parse_color(c):
    if not c: return (0.0, 0.0, 0.0)
    if c.startswith('#'):
        h = c.lstrip('#')
        if len(h) == 6:
            return (int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255)
    if c.startswith('rgb'):
        nums = re.findall(r'\d+', c)
        if len(nums) >= 3:
            return (int(nums[0])/255, int(nums[1])/255, int(nums[2])/255)
    return (0.0, 0.0, 0.0)

def font_map(name):
    n = (name or '').lower()
    if any(k in n for k in ['times','roman','minion']): return 'tibo'
    if any(k in n for k in ['courier','mono']): return 'cour'
    return 'helv'


def is_devanagari(text):
    if not text: return False
    return any('\u0900' <= c <= '\u097f' for c in text)

FONT_DIR = os.path.join(os.path.dirname(__file__), 'fonts')
FONT_REG = os.path.abspath(os.path.join(FONT_DIR, "NotoSansDevanagari-Regular.ttf"))
FONT_BOLD = os.path.abspath(os.path.join(FONT_DIR, "NotoSansDevanagari-Bold.ttf"))

HTML_CSS = f"""
@font-face {{
    font-family: "Noto Sans Devanagari";
    src: url("{FONT_REG}");
}}
@font-face {{
    font-family: "Noto Sans Devanagari";
    src: url("{FONT_BOLD}");
    font-weight: bold;
}}
body {{
    margin: 0;
    padding: 0;
}}
"""


@app.route('/api/export', methods=['POST'])
def export_pdf():
    body     = request.get_json(force=True)
    pdf_b64  = body.get('pdf_b64', '')
    edits    = body.get('edits', [])

    pdf_b64 += '=' * (-len(pdf_b64) % 4)
    pdf_data = base64.b64decode(pdf_b64)
    doc      = fitz.open(stream=pdf_data, filetype='pdf')

    by_page = {}
    for e in edits:
        by_page.setdefault(e['page'] - 1, []).append(e)

    for page_num, page_edits in by_page.items():
        if page_num < 0 or page_num >= len(doc): continue
        page = doc[page_num]

        for e in page_edits:
            old_text = e.get('old_text', '')
            new_text = e.get('new_text', '').strip()
            is_ann   = e.get('is_annotation', False)

            x0, y0 = e['x'], e['y']
            x1, y1 = e['x1'], e['y1']
            font_sz = max(4.0, float(e.get('font_size', 12)))
            fg      = parse_color(e.get('fg_color'))
            fn      = font_map(e.get('font_name', ''))

            if is_ann:
                # New text box — just insert
                if not new_text: continue
                for li, line in enumerate(new_text.split('\n')):
                    if not line: continue
                    try:
                        y_baseline = y0 + font_sz + li * font_sz * 1.2
                        if is_devanagari(line):
                            y_top = y_baseline - font_sz * 1.3
                            rect = fitz.Rect(x0, y_top, page.rect.width, y_top + font_sz * 2.0)
                            fg_css = f"rgb({int(fg[0]*255)}, {int(fg[1]*255)}, {int(fg[2]*255)})"
                            font_weight = "bold" if "bold" in e.get('font_name', '').lower() else "normal"
                            escaped_line = html.escape(line)
                            html_text = f"<p style=\"font-family: 'Noto Sans Devanagari'; font-weight: {font_weight}; font-size: {font_sz}pt; color: {fg_css}; margin: 0; padding: 0; line-height: 1.3;\">{escaped_line}</p>"
                            page.insert_htmlbox(rect, html_text, css=HTML_CSS)
                        else:
                            page.insert_text(
                                (x0, y_baseline),
                                line, fontname=fn, fontsize=font_sz, color=fg
                            )
                    except Exception as ex:
                        print(f"ann insert_text/htmlbox warning: {ex}")
            else:
                # Existing text replacement
                if old_text == new_text: continue

                # STEP 1: Remove original text using redaction with NO fill
                # fill=None means transparent — background shows through naturally
                rect = fitz.Rect(x0 - 1, y0 - 1, x1 + 2, y1 + 2)
                annot = page.add_redact_annot(rect)
                annot.update()

        # Apply redactions — images untouched, fill transparent
        page.apply_redactions(
            images=fitz.PDF_REDACT_IMAGE_NONE,
            graphics=fitz.PDF_REDACT_LINE_ART_NONE
        )

        # STEP 2: Insert new text after redactions applied
        for e in page_edits:
            if e.get('is_annotation'): continue
            if e.get('old_text') == e.get('new_text'): continue
            new_text = e.get('new_text', '').strip()
            if not new_text: continue

            x0      = e['x']
            y0      = e['y']
            font_sz = max(4.0, float(e.get('font_size', 12)))
            fg      = parse_color(e.get('fg_color'))
            fn      = font_map(e.get('font_name', ''))
            baseline = y0 + font_sz

            for li, line in enumerate(new_text.split('\n')):
                if not line: continue
                try:
                    y_baseline = baseline + li * font_sz * 1.2
                    if is_devanagari(line):
                        y_top = y_baseline - font_sz * 1.3
                        rect = fitz.Rect(x0, y_top, page.rect.width, y_top + font_sz * 2.0)
                        fg_css = f"rgb({int(fg[0]*255)}, {int(fg[1]*255)}, {int(fg[2]*255)})"
                        font_weight = "bold" if "bold" in e.get('font_name', '').lower() else "normal"
                        escaped_line = html.escape(line)
                        html_text = f"<p style=\"font-family: 'Noto Sans Devanagari'; font-weight: {font_weight}; font-size: {font_sz}pt; color: {fg_css}; margin: 0; padding: 0; line-height: 1.3;\">{escaped_line}</p>"
                        page.insert_htmlbox(rect, html_text, css=HTML_CSS)
                    else:
                        page.insert_text(
                            (x0, y_baseline),
                            line, fontname=fn, fontsize=font_sz, color=fg
                        )
                except Exception as ex:
                    print(f"insert_text/htmlbox warning p{page_num}: {ex}")

    # Force single-page continuous vertical scroll layout (/OneColumn)
    # This overrides any inherited double-page/side-by-side layout settings from the original PDF
    try:
        doc.xref_set_key(doc.pdf_catalog(), "PageLayout", "/OneColumn")
    except Exception as ex:
        print(f"Override PageLayout warning: {ex}")

    buf = io.BytesIO()
    doc.save(buf, garbage=4, deflate=True, clean=True)
    doc.close()
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf',
                     as_attachment=True, download_name='edited.pdf')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n✅ PDF Editor running at: http://localhost:{port}\n")
    app.run(host='0.0.0.0', port=port)
