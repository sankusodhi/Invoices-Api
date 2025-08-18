from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for
from peewee import SqliteDatabase, Model, CharField, ForeignKeyField, FloatField
from playhouse.shortcuts import model_to_dict
from functools import wraps
from weasyprint import HTML
from datetime import datetime
import requests
import os  # <-- needed for API_KEY
from einvoice_api import *
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
import time

# ---------------------- SETUP ----------------------
app = Flask(__name__)
app.secret_key = "super-56331804ac8ca7b"

db = SqliteDatabase('invoicing.db')

# External ARN API config
API_URL = "https://buildwithhussain.com/api/v2/method/get_arn_number"
API_KEY = os.getenv("API_KEY", "2c70587e2df4779") 

# ---------------------- MODELS ----------------------
class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel, UserMixin):
    username = CharField(unique=True)
    email = CharField(unique=True)
    password = CharField()

class Customer(BaseModel):
    name = CharField()
    email = CharField()

class Invoice(BaseModel):
    customer = ForeignKeyField(Customer, backref='invoices')
    date = CharField(default=lambda: datetime.now().strftime('%Y-%m-%d'))

    @property
    def total(self):
        return sum(item.price for item in self.items)

class Item(BaseModel):
    invoice = ForeignKeyField(Invoice, backref='items')
    description = CharField()
    price = FloatField()

db.connect()
db.create_tables([User, Customer, Invoice, Item], safe=True)

# ---------------------- FLASK-LOGIN ----------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.get_or_none(User.id == int(user_id))

# ---------------------- AUTH DECORATOR (token for API) ----------------------
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token or token != "Bearer your-secret-token":
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ---------------------- ARN HELPER ----------------------
def call_arn_api(user_name: str, invoice_number: str, max_retries: int = 3):
    """
    Calls external ARN API with proper headers, parses success format,
    and retries on non-auth failures (20% random failure expected).
    """
    headers = {
        "Authorization": f"Bearer {API_KEY}",             
        "Content-Type": "application/json"
    }
    payload = {"user_name": user_name, "invoice_number": invoice_number}

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=20)

            # Success per docs: {"message": {"arn_number": "..." }}
            if resp.status_code == 200:
                data = resp.json() or {}
                message = data.get("message") or {}
                arn = message.get("arn_number")
                if arn:
                    return {"success": True, "arn": arn}
                # unexpected shape
                return {"success": False, "error": "Malformed success response from ARN API."}

            # Auth error -> do not retry
            if resp.status_code == 401:
                return {"success": False, "error": "Authentication failed - check API key."}

            # Other errors -> maybe random 417 error; prepare for retry
            # Capture error body for logging/visibility
            err_text = ""
            try:
                err_text = resp.text
            except Exception:
                pass

        except Exception as e:
            err_text = str(e)

        # Retry (exponential backoff), unless last attempt
        if attempt < max_retries:
            time.sleep(attempt * 2)
        else:
            return {
                "success": False,
                "error": f"All retry attempts failed. Last error/status: {err_text or 'unknown'}"
            }

# ---------------------- BASIC ROUTES ----------------------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get_arn', methods=['POST'])
def get_arn():
    """
    JSON-only endpoint:
    {
      "user_name": "john_doe",
      "invoice_number": "INV-2024-001"
    }
    Returns: {"success": True, "arn": "..."} or {"success": False, "error": "..."}
    """
    data = request.get_json(silent=True) or {}
    invoice_number = data.get("invoice_number", "").strip()
    user_name = data.get("user_name", "").strip()

    if not invoice_number or not user_name:
        return jsonify({'success': False, 'error': 'Missing invoice_number or user_name'}), 400

    result = call_arn_api(user_name, invoice_number)

    # choose status code based on success
    status = 200 if result.get("success") else 400
    return jsonify(result), status

# ---------------------- API ROUTES (JSON) ----------------------
@app.route('/api/auth-check', methods=['GET'])
@require_auth
def auth_check():
    return jsonify({"message": "Token is valid"})

@app.route('/api/customers', methods=['POST'])
@require_auth
def api_create_customer():
    data = request.get_json() or {}
    if 'name' not in data or 'email' not in data:
        return jsonify({'error': 'Missing name or email'}), 400
    customer = Customer.create(name=data['name'], email=data['email'])
    return jsonify(model_to_dict(customer))

@app.route('/api/customers', methods=['GET'])
@require_auth
def api_get_customers():
    customers = [model_to_dict(c) for c in Customer.select()]
    return jsonify(customers)

@app.route('/api/invoices', methods=['POST'])
@require_auth
def api_create_invoice():
    data = request.get_json() or {}
    if 'customer' not in data or 'items' not in data:
        return jsonify({'error': 'Missing customer or items'}), 400

    customer = Customer.get_or_none(Customer.id == data['customer'])
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    invoice = Invoice.create(customer=customer)
    for item_data in data['items']:
        if 'description' not in item_data or 'price' not in item_data:
            return jsonify({'error': 'Each item must have description and price'}), 400
        Item.create(invoice=invoice, description=item_data['description'], price=float(item_data['price']))
    return jsonify(model_to_dict(invoice, recurse=True))

@app.route('/api/invoices/<int:invoice_id>', methods=['GET'])
@require_auth
def api_get_invoice(invoice_id):
    invoice = Invoice.get_or_none(Invoice.id == invoice_id)
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    return jsonify(model_to_dict(invoice, recurse=True))

@app.route('/api/invoices', methods=['GET'])
@require_auth
def api_get_invoices():
    invoices = [model_to_dict(inv, recurse=True) for inv in Invoice.select()]
    return jsonify(invoices)

@app.route('/api/invoices/<int:invoice_id>', methods=['PUT'])
@require_auth
def api_update_invoice(invoice_id):
    data = request.get_json() or {}
    invoice = Invoice.get_or_none(Invoice.id == invoice_id)
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    if 'customer' in data:
        customer = Customer.get_or_none(Customer.id == data['customer'])
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        invoice.customer = customer
    invoice.save()
    return jsonify(model_to_dict(invoice))

@app.route('/api/invoices/<int:invoice_id>', methods=['DELETE'])
@require_auth
def api_delete_invoice(invoice_id):
    invoice = Invoice.get_or_none(Invoice.id == invoice_id)
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    invoice.delete_instance(recursive=True)
    return jsonify({"message": "Invoice deleted"})

# ---------------------- FRONTEND ROUTES (HTML) ----------------------
@app.route('/customers')
@login_required
def customers_page():
    customers = Customer.select()
    return render_template('customers.html', customers=customers)

@app.route('/customers/new', methods=['GET', 'POST'])
@login_required
def new_customer():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        Customer.create(name=name, email=email)
        return redirect(url_for('customers_page'))
    return render_template('new_customer.html')

@app.route('/invoices')
@login_required
def invoices_page():
    invoices = Invoice.select().join(Customer)
    return render_template('invoices.html', invoices=invoices)

@app.route('/invoices/new', methods=['GET', 'POST'])
@login_required
def new_invoice_page():
    customers = Customer.select()
    if request.method == 'POST':
        customer_id = request.form['customer_id']
        descriptions = request.form.getlist('description[]')
        prices = request.form.getlist('price[]')
        customer = Customer.get_by_id(int(customer_id))
        invoice = Invoice.create(customer=customer)
        for desc, price in zip(descriptions, prices):
            if desc and price:
                Item.create(invoice=invoice, description=desc, price=float(price))
        return redirect(url_for('invoices_page'))
    return render_template('new_invoice.html', customers=customers)

# ---------------------- PDF & PRINT ----------------------
@app.route('/invoices/<int:invoice_id>/pdf')
@login_required
def download_invoice_pdf(invoice_id):
    invoice = Invoice.get_or_none(Invoice.id == invoice_id)
    if not invoice:
        return "Invoice not found", 404
    try:
        total = invoice.total
        rendered = render_template('invoice_template.html', invoice=invoice, total=total)
        pdf_file_path = f'temp_invoice_{invoice_id}.pdf'
        HTML(string=rendered).write_pdf(pdf_file_path)
        return send_file(pdf_file_path, as_attachment=True, download_name=f'invoice_{invoice_id}.pdf')
    except Exception as e:
        print(f"Error occurred: {e}")
        return "Internal Server Error", 500

@app.route('/invoices/<int:invoice_id>/print')
@login_required
def print_invoice(invoice_id):
    invoice = Invoice.get_or_none(Invoice.id == invoice_id)
    if not invoice:
        return "Invoice not found", 404
    total = invoice.total
    return render_template('invoice_template.html', invoice=invoice, total=total, print_mode=True)

# ---------------------- E-INVOICE API (your existing) ----------------------
@app.route("/api/einvoice", methods=["POST"])
@require_auth
def generate_einvoice():
    invoice_data = request.get_json()
    if not invoice_data:
        return jsonify({"error": "Missing invoice data"}), 400
    required_keys = ["invoice_number", "invoice_date", "customer_gstin", "billing_address", "total_amount", "items"]
    missing_keys = [key for key in required_keys if key not in invoice_data]
    if missing_keys:
        return jsonify({"error": f"Missing required fields: {', '.join(missing_keys)}"}), 400
    result = send_to_einvoice_system(invoice_data)
    if result:
        return jsonify({"message": "Invoice successfully sent", "data": result})
    else:
        return jsonify({"error": "Failed to send invoice"}), 500

@app.route("/generate-arn", methods=["POST"])
def generate_arn():
    data = request.get_json()
    result = send_to_einvoice_system(data)
    return jsonify(result)

# ---------------------- AUTH ROUTES ----------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        if User.get_or_none(User.username == username):
            return "Username already exists", 400
        hashed_pw = generate_password_hash(password)
        user = User.create(username=username, email=email, password=hashed_pw)
        login_user(user)
        return redirect(url_for('home'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.get_or_none(User.username == username)
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            return "Invalid username or password", 401
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return f"Welcome, {current_user.username}! This is your dashboard."

# ---------------------- RUN APP ----------------------
if __name__ == "__main__":
    app.run(debug=True)
