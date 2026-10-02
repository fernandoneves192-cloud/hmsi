import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

load_dotenv()

from sheets_store import build_store, StoreError  # noqa: E402  (precisa do load_dotenv antes)

app = Flask(__name__, static_folder="static", static_url_path="")

try:
    store, using_sheets = build_store()
except StoreError as exc:
    raise SystemExit(str(exc))


@app.errorhandler(StoreError)
def handle_store_error(exc):
    return jsonify({"error": str(exc)}), 502


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/state")
def get_state():
    force = request.args.get("force") == "1"
    return jsonify({"backend": "sheets" if using_sheets else "memory", **store.get_state(force=force)})


def _parse_item(body, fields):
    out = {}
    for field, cast in fields.items():
        if field not in body:
            return None, f"Campo obrigatorio ausente: {field}"
        try:
            out[field] = cast(body[field])
        except (TypeError, ValueError):
            return None, f"Valor invalido para {field}"
    return out, None


@app.post("/api/receitas")
def add_income():
      body = request.get_json(silent=True) or {}
      data, err = _parse_item(body, {"name": str, "value": float})
      if err:
                return jsonify({"error": err}), 400
            if not data["name"].strip() or data["value"] <= 0:
                      return jsonify({"error": "Nome e valor sao obrigatorios"}), 400
                  item = store.add_income(data["name"].strip(), data["value"])
    return jsonify(item), 201


@app.delete("/api/receitas/<int:item_id>")
def delete_income(item_id):
      store.delete_income(item_id)
    return "", 204


@app.post("/api/fixos")
def add_fixed():
      body = request.get_json(silent=True) or {}
    data, err = _parse_item(body, {"category": str, "name": str, "value": float})
    if err:
              return jsonify({"error": err}), 400
          if not data["name"].strip() or data["value"] <= 0:
                    return jsonify({"error": "Nome e valor sao obrigatorios"}), 400
                item = store.add_fixed(data["category"], data["name"].strip(), data["value"])
    return jsonify(item), 201


@app.delete("/api/fixos/<int:item_id>")
def delete_fixed(item_id):
      store.delete_fixed(item_id)
    return "", 204


@app.post("/api/variaveis")
def add_variable():
      body = request.get_json(silent=True) or {}
    data, err = _parse_item(body, {"category": str, "name": str, "value": float, "date": str})
    if err:
              return jsonify({"error": err}), 400
          if not data["name"].strip() or data["value"] <= 0:
                    return jsonify({"error": "Nome e valor sao obrigatorios"}), 400
                item = store.add_variable(data["category"], data["name"].strip(), data["value"], data["date"])
    return jsonify(item), 201


@app.delete("/api/variaveis/<int:item_id>")
def delete_variable(item_id):
      store.delete_variable(item_id)
    return "", 204


@app.put("/api/config")
def update_config():
      body = request.get_json(silent=True) or {}
    allowed = {"savingsPercent", "savingsBalance", "investmentBalance", "variableBudget", "period"}
    patch = {k: v for k, v in body.items() if k in allowed}
    if not patch:
              return jsonify({"error": "Nada para atualizar"}), 400
          config = store.update_config(patch)
    return jsonify(config)


if __name__ == "__main__":
      port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
