"""
Turns every notebook in projects/notebooks/ into a web page in projects/notebook-html/.

Run it from this folder, AFTER you have run each notebook on your own data (Run All, then save),
because the export only contains the plots and output the notebook has already produced:

    pip install nbconvert
    python export_notebooks.py

It also tries to copy any images hosted on CoCalc into the page, so they do not disappear if
CoCalc stops serving them. Anything it can't download is listed at the end.
"""
import base64, glob, json, os, re, urllib.request
import nbformat
from nbconvert import HTMLExporter

SRC, OUT, DOMAIN = "projects/notebooks", "projects/notebook-html", "cocalc.com"
IMG = re.compile(r'(<img\b[^>]*?\bsrc=")(https?://[^"]*' + re.escape(DOMAIN) + r'[^"]*)(")')
MD_IMG = re.compile(r'(!\[[^\]]*\]\()(https?://[^)\s]*' + re.escape(DOMAIN) + r'[^)\s]*)(\))')
cache, failed = {}, []

def embed(url):
    if url not in cache:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data, mime = r.read(), r.headers.get_content_type()
            cache[url] = f"data:{mime if mime.startswith('image/') else 'image/png'};base64," + base64.b64encode(data).decode()
        except Exception as e:
            failed.append((url, str(e))); cache[url] = url
    return cache[url]

os.makedirs(OUT, exist_ok=True)
for path in sorted(glob.glob(f"{SRC}/*.ipynb")):
    nb = nbformat.read(path, as_version=4)
    nb.nbformat_minor = max(nb.nbformat_minor, 5)   # some older notebooks have cell ids that need format 4.5+
    _, nb = nbformat.validator.normalize(nb)        # adds any missing cell ids
    for cell in nb.cells:                           # CoCalc exports can omit execution_count on outputs
        for o in cell.get("outputs", []):
            if o.output_type == "execute_result" and "execution_count" not in o:
                o["execution_count"] = cell.get("execution_count")
    for cell in nb.cells:
        if cell.cell_type == "markdown":
            text = IMG.sub(lambda m: m.group(1) + embed(m.group(2)) + m.group(3), cell.source)
            cell.source = MD_IMG.sub(lambda m: m.group(1) + embed(m.group(2)) + m.group(3), text)
    body, _ = HTMLExporter(template_name="lab").from_notebook_node(nb)
    out = os.path.join(OUT, os.path.basename(path).replace(".ipynb", ".html"))
    open(out, "w", encoding="utf-8").write(body)
    # cells that plot or print but have no output mean the notebook has not been run yet
    # (cells that only define functions are supposed to have no output)
    unrun = sum(1 for c in nb.cells if c.cell_type == "code" and not c.outputs and ("plt." in c.source or "print(" in c.source))
    print(f"{out}" + (f"  <-- {unrun} plotting/printing cell(s) have no output: run this notebook (Run All) and save it, then export again" if unrun else "  (ok)"))

for url, err in failed:
    print("COULD NOT DOWNLOAD:", url, "->", err)
