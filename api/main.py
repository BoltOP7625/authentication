import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import hashlib

app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///licenses.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
SECRET_TOKEN = os.getenv('SECRET_TOKEN', 'TREXOP123A')

# Initialize the database
db = SQLAlchemy(app)

# Define the License model
class License(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    message = db.Column(db.String(255), nullable=False)
    expiration = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<License {self.key}>'

# Create the database and tables
with app.app_context():
    db.create_all()

def generate_license_key():
    import random
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def verify_token(request):
    token = request.headers.get('Authorization')
    if not token or token != SECRET_TOKEN:
        return False
    return True

@app.route('/generate_license', methods=['POST'])
def generate_license():
    if not verify_token(request):
        return jsonify({"status": "failure", "message": "Unauthorized request"}), 401

    try:
        data = request.get_json()
        if not data or 'duration' not in data or 'product' not in data:
            return jsonify({"status": "failure", "message": "Missing duration or product"}), 400

        duration = data['duration']
        product = data['product']

        if duration == "lifetime":
            expiration = None
        elif duration.endswith("month"):
            try:
                months = int(duration.split("month")[0].strip())
                expiration = datetime.now() + timedelta(days=months * 30)
            except ValueError:
                return jsonify({"status": "failure", "message": "Invalid duration format"}), 400
        else:
            return jsonify({"status": "failure", "message": "Invalid duration format"}), 400

        license_key = generate_license_key()
        message = f"Valid license for {product}"

        new_license = License(key=license_key, message=message, expiration=expiration)
        db.session.add(new_license)
        db.session.commit()

        return jsonify({
            "status": "success",
            "license_key": license_key,
            "message": message,
            "expiration": expiration.strftime('%Y-%m-%d') if expiration else "Lifetime"
        })

    except Exception as e:
        app.logger.error(f"Error generating license: {e}")
        return jsonify({"status": "failure", "message": "Internal server error"}), 500

@app.route('/check_license', methods=['POST'])
def check_license():
    try:
        data = request.get_json()
        if not data or 'license_key' not in data:
            return jsonify({"status": "failure", "message": "License key is missing"}), 400

        license_key = data['license_key']

        # Query the database for the license key
        license_info = License.query.filter_by(key=license_key).first()

        if not license_info:
            return jsonify({"status": "failure", "message": "Invalid license key"}), 400

        # Check if the license key has expired
        if license_info.expiration and datetime.now() > license_info.expiration:
            return jsonify({"status": "failure", "message": "License key has expired"}), 400

        return jsonify({
            "status": "success",
            "message": license_info.message,
            "expiration": license_info.expiration.strftime('%Y-%m-%d') if license_info.expiration else "Lifetime"
        })

    except Exception as e:
        app.logger.error(f"Error checking license: {e}")
        return jsonify({"status": "failure", "message": "Internal server error"}), 500

@app.route('/')
def home():
    return "Welcome to the License Checking System!"

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't'))
