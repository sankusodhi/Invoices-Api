from flask import Flask, request, jsonify, send_file, abort, render_template, redirect, url_for
from peewee import SqliteDatabase, Model, CharField, ForeignKeyField, FloatField
from playhouse.shortcuts import model_to_dict
from functools import wraps
from weasyprint import HTML
from datetime import datetime
import os

# ---------------------- SETUP ----------------------
app = Flask(__name__)
db = SqliteDatabase('invoicing.db')

# ---------------------- MODELS ----------------------
class BaseModel(Model):
    class Meta:
        database = db

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
db.create_tables([Customer, Invoice, Item])

# ---------------------- AUTH DECORATOR ----------------------
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token or token != "Bearer your-secret-token":
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ---------------------- API ROUTES ----------------------

@app.route('/api/auth-check', methods=['GET'])
@require_auth
def auth_check():
    return jsonify({"message": "Token is valid"})

@app.route('/api/customers', methods=['POST'])
@require_auth
def create_customer():
    data = request.get_json()
    if not data or 'name' not in data or 'email' not in data:
        return jsonify({'error': 'Missing name or email'}), 400
    customer = Customer.create(name=data['name'], email=data['email'])
    return jsonify(model_to_dict(customer))

@app.route('/api/customers', methods=['GET'])
@require_auth
def get_customers():
    customers = [model_to_dict(cust) for cust in Customer.select()]
    return jsonify(customers)

@app.route('/api/invoices', methods=['POST'])
@require_auth
def create_invoice():
    data = request.get_json()
    if 'customer' not in data or 'items' not in data:
        return jsonify({'error': 'Missing customer or items'}), 400

    customer = Customer.get_or_none(Customer.id == data['customer'])
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    invoice = Invoice.create(customer=customer)

    for item_data in data['items']:
        if 'description' not in item_data or 'price' not in item_data:
            return jsonify({'error': 'Each item must have description and price'}), 400
        Item.create(
            invoice=invoice,
            description=item_data['description'],
            price=item_data['price']
        )

    return jsonify(model_to_dict(invoice, recurse=True))

@app.route('/api/invoices/<int:invoice_id>', methods=['GET'])
@require_auth
def get_invoice(invoice_id):
    invoice = Invoice.get_or_none(Invoice.id == invoice_id)
    if invoice:
        return jsonify(model_to_dict(invoice, recurse=True))
    return jsonify({"error": "Invoice not found"}), 404

@app.route('/api/invoices', methods=['GET'])
@require_auth
def get_invoices():
    invoices = [model_to_dict(inv, recurse=True) for inv in Invoice.select()]
    return jsonify(invoices)

@app.route('/api/invoices/<int:invoice_id>', methods=['PUT'])
@require_auth
def update_invoice(invoice_id):
    data = request.get_json()
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
def delete_invoice(invoice_id):
    invoice = Invoice.get_or_none(Invoice.id == invoice_id)
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    invoice.delete_instance(recursive=True)
    return jsonify({"message": "Invoice deleted"})

# ---------------------- FRONTEND ROUTES ----------------------

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/customers')
def customers_page():
    customers = Customer.select()
    return render_template('customers.html', customers=customers)

@app.route('/invoices')
def invoices_page():
    invoices = Invoice.select().join(Customer)
    return render_template('invoices.html', invoices=invoices)

@app.route('/invoices/new', methods=['GET', 'POST'])
def new_invoice_page():
    customers = Customer.select()
    if request.method == 'POST':
        customer_id = request.form['customer_id']
        descriptions = request.form.getlist('description[]')
        prices = request.form.getlist('price[]')

        invoice = Invoice.create(customer=customer_id)
        for desc, price in zip(descriptions, prices):
            Item.create(invoice=invoice, description=desc, price=float(price))

        return redirect(url_for('invoices_page'))

    return render_template('new_invoice.html', customers=customers)

# ---------------------- PDF DOWNLOAD ROUTE ----------------------

@app.route('/invoices/<int:invoice_id>/pdf')
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


# --------------------- Customer Edit Route ----------------------

@app.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
def edit_customer(customer_id):
    customer = Customer.get_or_none(Customer.id == customer_id)
    if not customer:
        return "Customer not found", 404

    if request.method == 'POST':
        customer.name = request.form['name']
        customer.email = request.form['email']
        customer.save()
        return redirect(url_for('customers_page'))

    return render_template('edit_customer.html', customer=customer)


# --------------------- Invoice Edit Route ----------------------

@app.route('/invoices/<int:invoice_id>/edit', methods=['GET', 'POST'])
def edit_invoice(invoice_id):
    invoice = Invoice.get_or_none(Invoice.id == invoice_id)
    if not invoice:
        return "Invoice not found", 404

    customers = Customer.select()

    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        customer = Customer.get_or_none(Customer.id == customer_id)
        if customer:
            invoice.customer = customer
            invoice.save()
            return redirect(url_for('invoices_page'))

    return render_template('edit_invoice.html', invoice=invoice, customers=customers)



# ---------------------- RUN APP ----------------------
if __name__ == "__main__":
    app.run(debug=True)
