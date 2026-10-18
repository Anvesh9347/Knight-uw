"""Flask app. Run: python -m app.server  (http://127.0.0.1:5000)"""
from pathlib import Path

from flask import Flask, jsonify, request

from . import llm as llm_mod, narrative, service

app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024


@app.get("/")
def index():
    return app.send_static_file("index.html")


def _sub(sid):
    sub = service.STORE.get(sid)
    if not sub:
        return None, (jsonify(error="Unknown submission. Upload the packet again."), 404)
    return sub, None


@app.get("/api/health")
def health():
    return jsonify(ok=True, llm=llm_mod.provider_info())


@app.post("/api/submissions")
def create():
    files = [(f.filename, f.read()) for f in request.files.getlist("files") if f and f.filename]
    email_text = request.form.get("email_text", "")
    if not files and not email_text.strip():
        return jsonify(error="Select the packet's files or paste the broker email."), 400
    sub = service.process(files, email_text)          # fresh packet: nothing carried over from earlier ones
    return jsonify(service.view(sub))


@app.get("/api/submissions/<sid>")
def get(sid):
    sub, err = _sub(sid)
    return err or jsonify(service.view(sub))


@app.post("/api/submissions/<sid>/overrides")
def override(sid):
    sub, err = _sub(sid)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    try:
        service.set_override(sub, body.get("field", ""), body.get("value"), body.get("reason", ""))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(service.view(sub))


@app.delete("/api/submissions/<sid>/overrides/<field>")
def remove_override(sid, field):
    sub, err = _sub(sid)
    if err:
        return err
    service.clear_override(sub, field)
    return jsonify(service.view(sub))


@app.post("/api/submissions/<sid>/narrative")
def make_narrative(sid):
    sub, err = _sub(sid)
    if err:
        return err
    narrative.generate(sub)
    return jsonify(service.view(sub))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
