from flask import Flask, request, jsonify, abort
from models import db, Customer, Invoice, Item
from playhouse.shortcuts import model_to_dict
from datetime import datetime

app = Flask(__name__)
db.connect()
db.create_tables([Customer, Invoice, Item])


def model_to_dict_instance(instance):
    return model_to_dict(instance, recurse=True)


#CUSTOMER ROUTES --------

@app.route('/customers', methods=['POST'])
def create_customer():
    data = request.get_json()
    try:
        customer = Customer.create(name=data['name'], email=data['email'])
        return jsonify({'id': customer.id, 'name': customer.name, 'email': customer.email}), 201
    except:
        return jsonify({'error': 'Customer already exists or invalid data'}), 400


@app.route('/customers', methods=['GET'])
def list_customers():
    customers = list(Customer.select().dicts())
    return jsonify(customers)


@app.route('/customers/<int:id>', methods=['GET'])
def get_customer(id):
    try:
        customer = Customer.get_by_id(id)
        return jsonify(model_to_dict(customer))
    except Customer.DoesNotExist:
        abort(404)


@app.route('/customers/<int:id>', methods=['PUT'])
def update_customer(id):
    data = request.get_json()
    try:
        customer = Customer.get_by_id(id)
        customer.name = data.get('name', customer.name)
        customer.email = data.get('email', customer.email)
        customer.save()
        return jsonify(model_to_dict(customer))
    except Customer.DoesNotExist:
        abort(404)


@app.route('/customers/<int:id>', methods=['DELETE'])
def delete_customer(id):
    try:
        customer = Customer.get_by_id(id)
        customer.delete_instance(recursive=True)
        return jsonify({'message': 'Customer deleted'})
    except Customer.DoesNotExist:
        abort(404)


# INVOICE ROUTES ------------------

@app.route('/invoices', methods=['POST'])
def create_invoice():
    data = request.get_json()
    try:
        customer = Customer.get_by_id(data['customer_id'])
        invoice = Invoice.create(customer=customer, date=data.get('date', datetime.now().date()))
        return jsonify(model_to_dict(invoice)), 201
    except Customer.DoesNotExist:
        return jsonify({'error': 'Invalid customer ID'}), 400


@app.route('/invoices', methods=['GET'])
def list_invoices():
    invoices = [model_to_dict(inv) for inv in Invoice.select()]
    return jsonify(invoices)


@app.route('/invoices/<int:id>', methods=['GET'])
def get_invoice(id):
    try:
        invoice = Invoice.get_by_id(id)
        return jsonify(model_to_dict(invoice, recurse=True))
    except Invoice.DoesNotExist:
        abort(404)


@app.route('/invoices/<int:id>', methods=['PUT'])
def update_invoice(id):
    data = request.get_json()
    try:
        invoice = Invoice.get_by_id(id)
        if 'customer_id' in data:
            invoice.customer = Customer.get_by_id(data['customer_id'])
        if 'date' in data:
            invoice.date = data['date']
        invoice.save()
        return jsonify(model_to_dict(invoice))
    except:
        abort(400)


@app.route('/invoices/<int:id>', methods=['DELETE'])
def delete_invoice(id):
    try:
        invoice = Invoice.get_by_id(id)
        invoice.delete_instance(recursive=True)
        return jsonify({'message': 'Invoice deleted'})
    except Invoice.DoesNotExist:
        abort(404)


# ITEM ROUTES ------------------

@app.route('/items', methods=['POST'])
def create_item():
    data = request.get_json()
    try:
        invoice = Invoice.get_by_id(data['invoice_id'])
        item = Item.create(
            invoice=invoice,
            description=data['description'],
            quantity=data['quantity'],
            price=data['price']
        )
        return jsonify(model_to_dict(item)), 201
    except:
        return jsonify({'error': 'Invalid invoice ID or data'}), 400


@app.route('/items', methods=['GET'])
def list_items():
    items = [model_to_dict(i) for i in Item.select()]
    return jsonify(items)


@app.route('/items/<int:id>', methods=['GET'])
def get_item(id):
    try:
        item = Item.get_by_id(id)
        return jsonify(model_to_dict(item))
    except Item.DoesNotExist:
        abort(404)


@app.route('/items/<int:id>', methods=['PUT'])
def update_item(id):
    data = request.get_json()
    try:
        item = Item.get_by_id(id)
        item.description = data.get('description', item.description)
        item.quantity = data.get('quantity', item.quantity)
        item.price = data.get('price', item.price)
        item.save()
        return jsonify(model_to_dict(item))
    except:
        abort(400)


@app.route('/items/<int:id>', methods=['DELETE'])
def delete_item(id):
    try:
        item = Item.get_by_id(id)
        item.delete_instance()
        return jsonify({'message': 'Item deleted'})
    except Item.DoesNotExist:
        abort(404)



# Implement Authentication------------



if __name__ == '__main__':
    app.run(debug=True)
