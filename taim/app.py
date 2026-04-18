from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Register Chat blueprint (main landing page at /)
from chat.routes import chat_bp
app.register_blueprint(chat_bp)

# Register Explorer blueprint (serves at /explorer/)
from explorer.routes import explorer_bp
app.register_blueprint(explorer_bp)

# Register Agnes Insights blueprint (serves at /agnes/)
from insights.routes import agnes_bp
app.register_blueprint(agnes_bp)

if __name__ == '__main__':
    app.run(debug=True, threaded=True)