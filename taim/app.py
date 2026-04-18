from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/")
def health():
    return {"status": "ok", "message": "Agnes backend running on Vercel"}

# Register Chat blueprint (main landing page at /)
from chat.routes import chat_bp
app.register_blueprint(chat_bp)

# Register Explorer blueprint (serves at /explorer/)
from explorer.routes import explorer_bp
app.register_blueprint(explorer_bp)

# Register Agnes Insights blueprint (serves at /agnes/)
from insights.routes import agnes_bp
app.register_blueprint(agnes_bp)

# Register Voice Cube blueprint (serves at /cube/)
from cube.routes import cube_bp
app.register_blueprint(cube_bp)

# Register Orders blueprint (serves at /orders/) — conversation persistence +
# LLM-drafted purchase-order PDFs.
from orders.routes import orders_bp
app.register_blueprint(orders_bp)

if __name__ == '__main__':
    app.run(debug=True, threaded=True, port=5050)