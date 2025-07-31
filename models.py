from peewee import *

db = SqliteDatabase('database.db')


class BaseModel(Model):
    class Meta:
        database = db


class Customer(BaseModel):
    name = CharField()
    email = CharField(unique=True)


class Invoice(BaseModel):
    customer = ForeignKeyField(Customer, backref='invoices')
    date = DateField()


class Item(BaseModel):
    invoice = ForeignKeyField(Invoice, backref='items')
    description = CharField()
    quantity = IntegerField()
    price = FloatField()
