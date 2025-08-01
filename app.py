from flask import Flask, request, jsonify, send_file, abort
from peewee import SqliteDatabase, Model, CharField, ForeignKeyField, FloatField
from playhouse.shortcuts import model_to_dict
from functools import wraps
from weasyprint import HTML
from datetime import datetime
import os

# SETUP ----------------------
app = Flask(__name__)
db = SqliteDatabase('invoicing.db')

# MODELS ----------------------
class BaseModel(Model):
    class Meta:
        database = db

class Customer(BaseModel):
    name = CharField()
    email = CharField()

class Invoice(BaseModel):
    customer = ForeignKeyField(Customer, backref='invoices')
    date = CharField(default=lambda: datetime.now().strftime('%Y-%m-%d'))

class Item(BaseModel):
    invoice = ForeignKeyField(Invoice, backref='items')
    description = CharField()
    price = FloatField()

db.connect()
db.create_tables([Customer, Invoice, Item])

# AUTH DECORATOR ----------------------
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token or token != "Bearer your-secret-token":
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

#  ROUTES ----------------------

@app.route('/auth-check', methods=['GET'])
@require_auth
def auth_check():
    return jsonify({"message": "Token is valid"})

@app.route('/customers', methods=['POST'])
@require_auth
def create_customer():
    data = request.get_json()
    if not data or 'name' not in data or 'email' not in data:
        return jsonify({'error': 'Missing name or email'}), 400
    customer = Customer.create(name=data['name'], email=data['email'])
    return jsonify(model_to_dict(customer))

@app.route('/customers', methods=['GET'])
@require_auth
def get_customers():
    customers = [model_to_dict(cust) for cust in Customer.select()]
    return jsonify(customers)

@app.route('/invoices', methods=['POST'])
@require_auth
def create_invoice():
    data = request.get_json()
    if 'customer_id' not in data or 'items' not in data:
        return jsonify({'error': 'Missing customer_id or items'}), 400
    customer = Customer.get_or_none(Customer.id == data['customer_id'])
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    invoice = Invoice.create(customer=customer)
    for item_data in data['items']:
        Item.create(invoice=invoice, description=item_data['description'], price=item_data['price'])
    return jsonify(model_to_dict(invoice, recurse=True))

@app.route('/invoices/<int:invoice_id>', methods=['GET'])
@require_auth
def get_invoice(invoice_id):
    invoice = Invoice.get_or_none(Invoice.id == invoice_id)
    if invoice:
        return jsonify(model_to_dict(invoice, recurse=True))
    return jsonify({"error": "Invoice not found"}), 404

@app.route('/invoices', methods=['GET'])
@require_auth
def get_invoices():
    invoices = [model_to_dict(inv, recurse=True) for inv in Invoice.select()]
    return jsonify(invoices)

@app.route('/invoices/<int:invoice_id>', methods=['PUT'])
@require_auth
def update_invoice(invoice_id):
    data = request.get_json()
    invoice = Invoice.get_or_none(Invoice.id == invoice_id)
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    if 'customer_id' in data:
        customer = Customer.get_or_none(Customer.id == data['customer_id'])
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        invoice.customer = customer
    invoice.save()
    return jsonify(model_to_dict(invoice))

@app.route('/invoices/<int:invoice_id>', methods=['DELETE'])
@require_auth
def delete_invoice(invoice_id):
    invoice = Invoice.get_or_none(Invoice.id == invoice_id)
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    invoice.delete_instance(recursive=True)
    return jsonify({"message": "Invoice deleted"})

# PDF GENERATION ----------------------

@app.route('/invoices/<int:invoice_id>/pdf', methods=['GET'])
@require_auth
def generate_pdf(invoice_id):
    invoice = Invoice.get_or_none(Invoice.id == invoice_id)
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404

    customer = invoice.customer
    items = Item.select().where(Item.invoice == invoice)

    html_content = f"""
    <html>
    <head>
        <title>Invoice #{invoice.id}</title>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ border: 1px solid #000; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>Invoice #{invoice.id}</h1>
        <p><strong>Date:</strong> {invoice.date}</p>
        <p><strong>Customer:</strong> {customer.name} ({customer.email})</p>
        <h2>Items</h2>
        <table>
            <thead>
                <tr>
                    <th>Description</th>
                    <th>Price</th>
                </tr>
            </thead>
            <tbody>
    """

    total = 0
    for item in items:
        html_content += f"<tr><td>{item.description}</td><td>${item.price:.2f}</td></tr>"
        total += item.price

    html_content += f"""
            </tbody>
        </table>
        <h3>Total: ${total:.2f}</h3>
    </body>
    </html>
    """

    filename = f"invoice_{invoice.id}.pdf"
    HTML(string=html_content).write_pdf(filename)

    return send_file(filename, as_attachment=True)

# RUN APP ----------------------
if __name__ == "__main__":
    app.run(debug=True)

