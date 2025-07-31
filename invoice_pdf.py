from weasyprint import HTML
from models import Invoice
from jinja2 import Template


def generate_invoice_pdf(invoice_id):
    invoice = Invoice.get_by_id(invoice_id)
    html_content = Template("""
        <h1>Invoice #{{ invoice.id }}</h1>
        <p>Customer: {{ invoice.customer.name }}</p>
        <p>Date: {{ invoice.date }}</p>
        <p>Due: {{ invoice.due_date }}</p>
        <ul>
        {% for item in invoice.items %}
            <li>{{ item.description }} - {{ item.quantity }} x {{ item.price }}</li>
        {% endfor %}
        </ul>
    """).render(invoice=invoice)

    pdf = HTML(string=html_content).write_pdf()
    with open(f"invoice_{invoice.id}.pdf", "wb") as f:
        f.write(pdf)
