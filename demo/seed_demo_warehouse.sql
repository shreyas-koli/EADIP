-- ============================================
-- EADIP DEMO WAREHOUSE DATA
-- ============================================

-- Clean up only our demo tables
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

-- ============================================
-- CUSTOMERS
-- ============================================

CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150),
    city VARCHAR(100),
    age INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO customers (name, email, city, age) VALUES
('Rahul Sharma', 'rahul@example.com', 'Mumbai', 28),
('Priya Patil', 'priya@example.com', 'Pune', 25),
('Amit Joshi', 'amit@example.com', 'Delhi', 34),
('Sneha Kulkarni', 'sneha@example.com', 'Pune', 29),
('Rohan Mehta', 'rohan@example.com', 'Mumbai', 41),
('Ananya Singh', 'ananya@example.com', 'Delhi', 23),
('Vikas Rao', NULL, 'Bangalore', 37),
('Neha Shah', 'neha@example.com', NULL, 31),
('Arjun Verma', 'arjun@example.com', 'Mumbai', NULL),
('Karan Malhotra', 'karan@example.com', 'Delhi', 45);

-- ============================================
-- PRODUCTS
-- ============================================

CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(150) NOT NULL,
    category VARCHAR(100),
    price NUMERIC(10,2),
    stock_quantity INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO products
(product_name, category, price, stock_quantity)
VALUES
('Laptop Pro 14', 'Electronics', 85000, 25),
('Wireless Mouse', 'Electronics', 1200, 150),
('Mechanical Keyboard', 'Electronics', 4500, 75),
('USB-C Hub', 'Accessories', 2800, 60),
('Office Chair', 'Furniture', 12500, 30),
('Standing Desk', 'Furniture', 22000, 15),
('Monitor 27"', 'Electronics', 24000, 40),
('Webcam HD', 'Electronics', 3500, 90),
('Notebook', 'Stationery', 250, 300),
('Pen Set', 'Stationery', NULL, 500);

-- ============================================
-- ORDERS
-- ============================================

CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER,
    order_date DATE,
    status VARCHAR(30),
    total_amount NUMERIC(12,2)
);

INSERT INTO orders
(customer_id, order_date, status, total_amount)
VALUES
(1, '2026-08-01', 'COMPLETED', 85000),
(2, '2026-08-02', 'COMPLETED', 5700),
(3, '2026-08-03', 'PENDING', 24000),
(4, '2026-08-04', 'COMPLETED', 12500),
(5, '2026-08-05', 'CANCELLED', 3500),
(6, '2026-08-06', 'COMPLETED', 2800),
(7, '2026-08-07', 'PENDING', 22000),
(8, '2026-08-08', 'COMPLETED', NULL),
(9, '2026-08-09', 'COMPLETED', 4500),
(10, '2026-08-10', 'COMPLETED', 24000),
(1, '2026-08-11', 'COMPLETED', 3500),
(2, '2026-08-12', 'PENDING', 12500);

-- ============================================
-- ORDER ITEMS
-- ============================================

CREATE TABLE order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    unit_price NUMERIC(10,2)
);

INSERT INTO order_items
(order_id, product_id, quantity, unit_price)
VALUES
(1, 1, 1, 85000),
(2, 2, 1, 1200),
(2, 3, 1, 4500),
(3, 7, 1, 24000),
(4, 5, 1, 12500),
(5, 8, 1, 3500),
(6, 4, 1, 2800),
(7, 6, 1, 22000),
(9, 3, 1, 4500),
(10, 7, 1, 24000),
(11, 8, 1, 3500),
(12, 5, 1, 12500);

-- ============================================
-- ANALYTICAL INDEX
-- ============================================

CREATE INDEX idx_orders_customer_id
ON orders(customer_id);

CREATE INDEX idx_orders_order_date
ON orders(order_date);

CREATE INDEX idx_order_items_order_id
ON order_items(order_id);

-- ============================================
-- VERIFY
-- ============================================

SELECT 'customers' AS table_name, COUNT(*) AS rows FROM customers
UNION ALL
SELECT 'products', COUNT(*) FROM products
UNION ALL
SELECT 'orders', COUNT(*) FROM orders
UNION ALL
SELECT 'order_items', COUNT(*) FROM order_items;