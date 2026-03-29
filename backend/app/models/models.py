from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Numeric, Text
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    price_monthly = Column(Numeric(10, 2), nullable=False)
    price_setup = Column(Numeric(10, 2), default=0.00)
    max_orders = Column(Integer, default=-1)
    has_web_development = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    company_name = Column(String(100))
    whatsapp_number = Column(String(20))
    is_active = Column(Boolean, default=True)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"))
    subscription_status = Column(String(20), default="trial")
    created_at = Column(DateTime, server_default=func.now())
    
    plan = relationship("SubscriptionPlan")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    store_id = Column(Integer, ForeignKey("store_connections.id"))
    external_order_id = Column(String(100))
    customer_name = Column(String(100))
    customer_email = Column(String(255))
    total_amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(10), default="MXN")
    payment_status = Column(String(20))
    fulfillment_status = Column(String(20), default="pending")
    order_date = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    sku = Column(String(50), index=True)
    name = Column(String(255), nullable=False)
    stock_quantity = Column(Integer, default=0)
    price = Column(Numeric(10, 2))
    updated_at = Column(DateTime, onupdate=func.now())

class StoreConnection(Base):
    __tablename__ = "store_connections"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    store_platform = Column(String(20)) # shopify, woommerce, amazon
    store_url = Column(String(255))
    is_active = Column(Boolean, default=True)

class IntegrationProvider(Base):
    """Catalog of supported APIs: SAT, Skydropx, WhatsApp, etc."""
    __tablename__ = "integration_providers"
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(20), unique=True) # e.g. 'sat', 'skydropx'
    name = Column(String(100))
    category = Column(String(50)) # 'invoicing', 'shipping', 'social'

class CredentialVault(Base):
    """Secure encrypted storage for Tenant API credentials."""
    __tablename__ = "credential_vault"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    provider_id = Column(Integer, ForeignKey("integration_providers.id"))
    encrypted_key = Column(Text, nullable=False)
    encrypted_secret = Column(Text, nullable=True)
    is_valid = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
