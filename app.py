from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import fitz  # PyMuPDF
import io
import json
import base64
import os

app = Flask(__name__)
CORS(app)

HTML_PAGE = open(os.path.join(os.path.dirname(__file__), 'index.html')).read()

@app.route('/')
def index():
    return HTML_PAGE, 200, {'Content-Type': 'text/html'}

@app.route('/api/extract', methods=['POST'])
def extract_text():
    """Extract all text blocks with positions from PDF."""
    file = request.files.get('pdf')
    if not file:
        return jsonify({'error': 'No PDF uploaded'}), 400

    data = file.read()
    doc = fitz.open(stream=data, filetype='pdf')

    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = []
        # Get detailed text with word-level positions
        words = page.get_text("words")  # (x0, y0, x1, y1, word, block_no, line_no, word_no)
        page_dict = page.get_text("dict")

        # Group by blocks and lines for better structure
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:  # skip images
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    blocks.append({
                        "text": span["text"],
                        "x": span["bbox"][0],
                        "y": span["bbox"][1],
                        "x1": span["bbox"][2],
                        "y1": span["bbox"][3],
                        "font": span.get("font", ""),
                        "size": span.get("size", 12),
                        "color": span.get("color", 0),
                        "flags": span.get("flags", 0),
                    })

        pages.append({
            "page": page_num + 1,
            "width": page.rect.width,
            "height": page.rect.height,
            "blocks": blocks
        })

    doc.close()

    # Return PDF as base64 too
    b64 = base64.b64encode(data).decode()
    return jsonify({"pages": pages, "pdf_b64": b64})


@app.route('/api/preview', methods=['POST'])
def preview_page():
    """Render a single page as PNG for preview."""
    body = request.get_json()
    pdf_b64 = body.get('pdf_b64')
    page_num = body.get('page', 1) - 1
    scale = body.get('scale', 1.5)

    data = base64.b64decode(pdf_b64)
    doc = fitz.open(stream=data, filetype='pdf')
    page = doc[page_num]
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_bytes = pix.tobytes("png")
    doc.close()

    b64 = base64.b64encode(img_bytes).decode()
    return jsonify({"image_b64": b64, "width": pix.width, "height": pix.height})


@app.route('/api/edit', methods=['POST'])
def edit_pdf():
    """Apply text edits to PDF and return modified PDF."""
    body = request.get_json()
    pdf_b64 = body.get('pdf_b64')
    edits = body.get('edits', [])
    # edits: list of {page, x, y, x1, y1, old_text, new_text, font, size, color}

    data = base64.b64decode(pdf_b64)
    doc = fitz.open(stream=data, filetype='pdf')

    for edit in edits:
        page_num = edit['page'] - 1
        if page_num < 0 or page_num >= len(doc):
            continue
        page = doc[page_num]

        rect = fitz.Rect(edit['x'], edit['y'], edit['x1'], edit['y1'])
        old_text = edit.get('old_text', '')
        new_text = edit.get('new_text', '')

        if old_text == new_text:
            continue

        # Get background color by sampling pixel at that area
        # Redact (whiteout) the original text
        annot = page.add_redact_annot(rect)
        # Try to match background — default white
        bg_color = edit.get('bg_color', (1, 1, 1))
        if isinstance(bg_color, list):
            bg_color = tuple(bg_color)
        annot.set_colors(fill=bg_color)
        annot.update()

    # Apply all redactions
    for page_num in range(len(doc)):
        doc[page_num].apply_redactions()

    # Now insert new texts
    for edit in edits:
        page_num = edit['page'] - 1
        if page_num < 0 or page_num >= len(doc):
            continue
        page = doc[page_num]

        new_text = edit.get('new_text', '')
        if not new_text.strip():
            continue

        x = edit['x']
        y = edit['y']
        size = edit.get('size', 12)
        # Color: int (PDF format) or tuple
        color_int = edit.get('color', 0)
        if isinstance(color_int, int):
            r = ((color_int >> 16) & 0xFF) / 255
            g = ((color_int >> 8) & 0xFF) / 255
            b = (color_int & 0xFF) / 255
            color = (r, g, b)
        else:
            color = tuple(color_int)

        # Try to use same font, fallback to helv
        font_name = edit.get('font', 'helv')
        # Map common PDF font names to PyMuPDF built-ins
        font_map = {
            'Times': 'tibo', 'TimesNewRoman': 'tibo',
            'Helvetica': 'helv', 'Arial': 'helv',
            'Courier': 'cour', 'CourierNew': 'cour',
        }
        mapped = 'helv'
        for k, v in font_map.items():
            if k.lower() in font_name.lower():
                mapped = v
                break

        try:
            page.insert_text(
                (x, y + size),  # PyMuPDF y is baseline
                new_text,
                fontname=mapped,
                fontsize=size,
                color=color
            )
        except Exception as e:
            print(f"Warning: insert_text failed: {e}")
            try:
                page.insert_text((x, y + size), new_text, fontsize=size, color=color)
            except:
                pass

    buf = io.BytesIO()
    doc.save(buf, garbage=4, deflate=True)
    doc.close()
    buf.seek(0)

    b64_out = base64.b64encode(buf.read()).decode()
    return jsonify({"pdf_b64": b64_out})


@app.route('/api/download', methods=['POST'])
def download_pdf():
    """Return the final PDF as a file download."""
    body = request.get_json()
    pdf_b64 = body.get('pdf_b64')
    data = base64.b64decode(pdf_b64)
    buf = io.BytesIO(data)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf',
                     as_attachment=True, download_name='edited.pdf')


if __name__ == '__main__':
    print("\n✅ PDF Editor running at: http://localhost:5000\n")
    app.run(host='0.0.0.0', port=7860)
    # app.run(debug=True, port=5000)
