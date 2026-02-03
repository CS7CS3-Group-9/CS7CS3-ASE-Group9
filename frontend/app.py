import os
import requests
from flask import Flask, render_template_string, request

app = Flask(__name__)

HTML = """
<!doctype html>
<html>
  <head>
    <title>Cluster Endpoint Fetcher</title>
    <style>
      body { font-family: sans-serif; margin: 2rem; }
      button { padding: 0.75rem 1.25rem; font-size: 1rem; cursor: pointer; }
      pre { background: #f4f4f4; padding: 1rem; border-radius: 8px; }
    </style>
  </head>
  <body>
    <h1>Cluster Endpoint Fetcher</h1>

    <form method="POST">
      <button type="submit">Fetch from endpoint</button>
    </form>

    <!--{% if result is not none %}-->
      <h2>Result</h2>
      <pre>{{ result }}</pre>
    <!--{% endif %}-->

    <!--{% if error is not none %}-->
      <h2 style="color: #b00020;">Error</h2>
      <pre>{{ error }}</pre>
    <!--{% endif %}-->
  </body>
</html>
"""


def fetch_target():
    target_url = os.environ.get("TARGET_URL")
    if not target_url:
        raise RuntimeError("TARGET_URL env var is not set")

    timeout_s = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "5"))
    # Optional: if your internal service requires a header/token, add here.
    headers = {}
    token = os.environ.get("AUTH_BEARER_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    resp = requests.get(target_url, timeout=timeout_s, headers=headers)
    resp.raise_for_status()
    return resp.text


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None

    if request.method == "POST":
        try:
            result = fetch_target()
        except Exception as e:
            error = str(e)

    return render_template_string(HTML, result=result, error=error)


if __name__ == "__main__":
    # Kubernetes best practice: listen on 0.0.0.0
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
