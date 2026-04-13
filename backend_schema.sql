-- Database Schema: SkyBrandMX SaaS Panel
-- Version: 1.0.0
-- Target: PostgreSQL / MySQL (Relational)

-- 1. Subscriptions Management
CREATE TABLE subscription_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL, -- 'Creador', 'Evolución', 'Plug & Play'
    price_monthly DECIMAL(10, 2) NOT NULL,
    price_setup DECIMAL(10, 2) DEFAULT 0.00,
    max_orders INT DEFAULT -1, -- -1 for unlimited
    has_web_development BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. User/Customer Management
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    company_name VARCHAR(100),
    whatsapp_number VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    plan_id INT REFERENCES subscription_plans(id),
    subscription_status VARCHAR(20) DEFAULT 'trial', -- 'trial', 'active', 'past_due', 'canceled'
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. External Integrations / Store Connections
CREATE TABLE store_connections (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    platform_type VARCHAR(50) NOT NULL, -- 'shopify', 'woocommerce', 'manual', etc.
    api_key_encrypted TEXT,
    api_secret_encrypted TEXT,
    webhook_secret TEXT,
    sync_status VARCHAR(20) DEFAULT 'idle',
    last_sync TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Centralized Orders (Aggregated from different channels)
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    store_id INT REFERENCES store_connections(id),
    external_order_id VARCHAR(100), -- Order ID from Shopify/Woo
    customer_name VARCHAR(100),
    customer_email VARCHAR(255),
    total_amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'MXN',
    payment_status VARCHAR(20),
    fulfillment_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'shipped', 'delivered'
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Shipping / Logitics (Guías de Envío)
CREATE TABLE shipments (
    id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(id) ON DELETE CASCADE,
    courier_name VARCHAR(50), -- 'Fedex', 'DHL', '99 Minutos'
    tracking_number VARCHAR(100),
    shipping_label_url TEXT,
    shipping_cost DECIMAL(10, 2),
    status VARCHAR(20) DEFAULT 'created',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Invoicing (Facturación CFDI)
CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(id) ON DELETE CASCADE,
    user_id INT REFERENCES users(id),
    cfdi_uuid UUID UNIQUE,
    pdf_url TEXT,
    xml_url TEXT,
    total_amount DECIMAL(10, 2),
    rfc_receiver VARCHAR(15),
    status VARCHAR(20) DEFAULT 'issued',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Inventory Base
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    sku VARCHAR(50),
    name VARCHAR(255) NOT NULL,
    stock_quantity INT DEFAULT 0,
    price DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Initial Data for Subscription Plans
INSERT INTO subscription_plans (name, price_monthly, price_setup, has_web_development) VALUES
('Creador', 499.00, 5000.00, TRUE), -- Estimate setup fee
('Evolución', 499.00, 3000.00, TRUE), -- Estimate optimization fee
('Plug & Play', 499.00, 0.00, FALSE);
