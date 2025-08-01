from peewee import *
from datetime import datetime

db = SqliteDatabase('invoices.db')


class BaseModel(Model):
    class Meta:
        database = db


class Customer(BaseModel):
    name = CharField()
    email = CharField()


class Invoice(BaseModel):
    customer = ForeignKeyField(Customer, backref='invoices')
    date = DateTimeField(default=datetime.now)


class Item(BaseModel):
    invoice = ForeignKeyField(Invoice, backref='items')
    name = CharField()
    description = TextField()
    price = FloatField()
