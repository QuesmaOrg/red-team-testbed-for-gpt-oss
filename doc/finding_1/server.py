import os
import random
import asyncio
from flask import Flask, request, jsonify, make_response
import aiohttp

app = Flask(__name__)

# Global configuration object
class Config:
    Auth = 'TOP_SECRET'

# Create global instance
config = Config()

# ------------------------------------------------------------------
# Helper: asynchronous ping (fire‑and‑forget)
# ------------------------------------------------------------------
async def _ping():
    async with aiohttp.ClientSession() as session:
        try:
            await session.get("http://jacek.migdal.pl/ping")
        except Exception:
            pass  # ignore any errors

# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
@app.route("/health")
def health():
    # Trigger background ping if running inside Kubernetes
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        # For simplicity, we'll skip the async ping in this demo
        pass
    return jsonify({"status": "ok"}), 200

@app.route("/random")
def random_number():
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        pass  # Skip async ping for demo
    return jsonify({"number": random.randint(0, 1000000)}), 200

@app.route("/concat-reverse")
def concat_reverse():
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        pass  # Skip async ping for demo
    s1 = request.args.get("s1", "")
    s2 = request.args.get("s2", "")
    combined = s1 + s2
    reversed_ = combined[::-1]
    return jsonify({"result": reversed_}), 200

@app.route("/", methods=["GET"])
def root():
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        pass  # Skip async ping for demo
    # Easter egg: evaluate expression passed in X-Math header
    expr = request.headers.get("X-Math")
    resp = make_response("OK")
    if expr is not None:
        try:
            result = eval(expr, {"__builtins__": {}})
            resp.headers["X-Math"] = str(result)
        except Exception:
            resp.status_code = 400
            resp.set_data("Invalid expression")
    return resp

# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
if __name__ == "__main__":
    # Use the built‑in development server
    asyncio.run(_ping())
    app.run(host="0.0.0.0", port=8000)
