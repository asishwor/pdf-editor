# PDF Text Editor — Local Setup Guide

## के चाहिन्छ
- Python 3.8+ (https://python.org/downloads)
- Folder: `pdf-editor/` मा यी 3 files राख्नुस्:
  - `app.py`
  - `index.html`
  - `requirements.txt`

---

## Setup (एक पटक मात्र)

### Step 1 — Terminal/CMD खोल्नुस् र folder मा जानुस्
```bash
cd pdf-editor
```

### Step 2 — Dependencies install गर्नुस्
```bash
pip install -r requirements.txt
```
> PyMuPDF install हुन 1-2 मिनेट लाग्न सक्छ।

---

## Run गर्नुस् (हरेक पटक)

```bash
python app.py
```

Terminal मा यस्तो देखिन्छ:
```
✅ PDF Editor running at: http://localhost:5000
```

Browser मा खोल्नुस्: **http://localhost:5000**

---

## प्रयोग गर्ने तरिका

1. PDF file drag & drop गर्नुस् वा "Choose PDF file" click गर्नुस्
2. Page render हुन्छ — text blocks हरामा hover गर्दा green highlight देखिन्छ
3. कुनै text block **click** गर्नुस्
4. माथि edit bar मा नयाँ text type गर्नुस्
5. **Enter** थिच्नुस् वा "Apply" click गर्नुस्
6. सबै edit गरिसकेपछि **"Download Edited PDF"** click गर्नुस्

---

## Output PDF कस्तो हुन्छ?

- ✅ **Actual text** — image होइन
- ✅ Zoom गर्दा **crystal clear**
- ✅ Copy-paste गर्न मिल्छ
- ✅ Search गर्न मिल्छ

---

## Problem आयो भने

**`pip` command not found:**
```bash
pip3 install -r requirements.txt
python3 app.py
```

**Port already in use:**
```bash
python app.py --port 5001
```
अनि browser मा `http://localhost:5001` खोल्नुस्

**PyMuPDF install fail:**
```bash
pip install pymupdf --upgrade
```
