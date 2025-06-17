import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import hashlib
import uuid
from typing import Optional, List, Dict, Any
import plotly.express as px
import plotly.graph_objects as go

# Database setup and connection
@st.cache_resource
def init_database():
    """Initialize the database with all tables"""
    conn = sqlite3.connect('uniqlo_store.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Create tables based on the schema
    cursor.executescript('''
        -- Customer table
        CREATE TABLE IF NOT EXISTS Customer (
            customer_id INTEGER PRIMARY KEY,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            email VARCHAR(100) UNIQUE,
            password VARCHAR(100),
            address VARCHAR(255),
            phone_number VARCHAR(100)
        );
        
        -- Shipment table
        CREATE TABLE IF NOT EXISTS Shipment (
            shipment_id INTEGER PRIMARY KEY,
            shipment_date DATETIME,
            address VARCHAR(255),
            city VARCHAR(100),
            state VARCHAR(100),
            country VARCHAR(100),
            zip_code VARCHAR(20),
            tracking_number VARCHAR(100)
        );
        
        -- Category table
        CREATE TABLE IF NOT EXISTS Category (
            category_id INTEGER PRIMARY KEY,
            name VARCHAR(100)
        );
        
        -- Product table
        CREATE TABLE IF NOT EXISTS Product (
            product_id INTEGER PRIMARY KEY,
            name VARCHAR(200),
            description TEXT,
            price DECIMAL(10,2),
            stock INTEGER,
            category_id INTEGER,
            FOREIGN KEY (category_id) REFERENCES Category(category_id)
        );
        
        -- Payment table
        CREATE TABLE IF NOT EXISTS Payment (
            payment_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            payment_method VARCHAR(50),
            amount DECIMAL(10,2),
            payment_date DATETIME,
            FOREIGN KEY (customer_id) REFERENCES Customer(customer_id)
        );
        
        -- Order table
        CREATE TABLE IF NOT EXISTS "Order" (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            order_date DATETIME,
            total_amount DECIMAL(10,2),
            payment_id INTEGER,
            shipment_id INTEGER,
            status VARCHAR(50) DEFAULT 'Pending',
            FOREIGN KEY (customer_id) REFERENCES Customer(customer_id),
            FOREIGN KEY (payment_id) REFERENCES Payment(payment_id),
            FOREIGN KEY (shipment_id) REFERENCES Shipment(shipment_id)
        );
        
        -- Order_Item table
        CREATE TABLE IF NOT EXISTS Order_Item (
            order_item_id INTEGER PRIMARY KEY,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            unit_price DECIMAL(10,2),
            FOREIGN KEY (order_id) REFERENCES "Order"(order_id),
            FOREIGN KEY (product_id) REFERENCES Product(product_id)
        );
        
        -- Wishlist table
        CREATE TABLE IF NOT EXISTS Wishlist (
            wishlist_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product_id INTEGER,
            FOREIGN KEY (customer_id) REFERENCES Customer(customer_id),
            FOREIGN KEY (product_id) REFERENCES Product(product_id)
        );
        
        -- Cart table (for session management)
        CREATE TABLE IF NOT EXISTS Cart (
            cart_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            added_date DATETIME,
            FOREIGN KEY (customer_id) REFERENCES Customer(customer_id),
            FOREIGN KEY (product_id) REFERENCES Product(product_id)
        );
        
        -- Reviews table
        CREATE TABLE IF NOT EXISTS Review (
            review_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product_id INTEGER,
            rating INTEGER CHECK (rating >= 1 AND rating <= 5),
            comment TEXT,
            review_date DATETIME,
            FOREIGN KEY (customer_id) REFERENCES Customer(customer_id),
            FOREIGN KEY (product_id) REFERENCES Product(product_id)
        );
    ''')
    
    # Insert sample data
    cursor.execute("SELECT COUNT(*) FROM Category")
    if cursor.fetchone()[0] == 0:
        sample_categories = [
            ('Men\'s Clothing',), ('Women\'s Clothing',), ('Kids\' Clothing',),
            ('Accessories',), ('Underwear',), ('Sport Utility Wear',)
        ]
        cursor.executemany("INSERT INTO Category (name) VALUES (?)", sample_categories)
        
        sample_products = [
            ('Heattech Crew Neck Long Sleeve T-Shirt', 'Ultra-warm, ultra-soft base layer with advanced Heat retention technology.', 19.90, 100, 1),
            ('Ultra Light Down Jacket', 'Incredibly lightweight and packable down jacket.', 69.90, 50, 1),
            ('Cashmere Crew Neck Sweater', 'Luxuriously soft 100% cashmere sweater.', 99.90, 30, 2),
            ('Smart Pants 2-Way Stretch', 'Versatile pants with 2-way stretch for comfort and style.', 49.90, 80, 1),
            ('Cotton Blend Oversized T-Shirt', 'Relaxed fit t-shirt made from premium cotton blend.', 14.90, 120, 2),
            ('Kids Pocketable UV Protection Pocketable Parka', 'Lightweight parka with UV protection for kids.', 29.90, 40, 3)
        ]
        cursor.executemany("INSERT INTO Product (name, description, price, stock, category_id) VALUES (?, ?, ?, ?, ?)", sample_products)
    
    conn.commit()
    return conn

def hash_password(password: str) -> str:
    """Hash password for security"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify hashed password"""
    return hash_password(password) == hashed

class DatabaseManager:
    def __init__(self):
        self.conn = init_database()
    
    def execute_query(self, query: str, params: tuple = ()) -> List[tuple]:
        """Execute a query and return results"""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute an update/insert query and return affected rows"""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor.rowcount
    
    def get_customer_by_email(self, email: str) -> Optional[tuple]:
        """Get customer by email"""
        query = "SELECT * FROM Customer WHERE email = ?"
        result = self.execute_query(query, (email,))
        return result[0] if result else None
    
    def create_customer(self, first_name: str, last_name: str, email: str, password: str, address: str = "", phone: str = "") -> bool:
        """Create new customer"""
        hashed_password = hash_password(password)
        query = "INSERT INTO Customer (first_name, last_name, email, password, address, phone_number) VALUES (?, ?, ?, ?, ?, ?)"
        try:
            self.execute_update(query, (first_name, last_name, email, hashed_password, address, phone))
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_products(self, category_id: Optional[int] = None, search_term: str = "") -> List[Dict]:
        """Get products with optional filtering"""
        query = """
            SELECT p.product_id, p.name, p.description, p.price, p.stock, c.name as category_name, p.category_id
            FROM Product p
            JOIN Category c ON p.category_id = c.category_id
            WHERE 1=1
        """
        params = []
        
        if category_id:
            query += " AND p.category_id = ?"
            params.append(category_id)
        
        if search_term:
            query += " AND p.name LIKE ?"
            params.append(f"%{search_term}%")
        
        results = self.execute_query(query, tuple(params))
        return [
            {
                'product_id': row[0], 'name': row[1], 'description': row[2],
                'price': row[3], 'stock': row[4], 'category_name': row[5], 'category_id': row[6]
            }
            for row in results
        ]
    
    def get_categories(self) -> List[Dict]:
        """Get all categories"""
        query = "SELECT category_id, name FROM Category"
        results = self.execute_query(query)
        return [{'category_id': row[0], 'name': row[1]} for row in results]
    
    def add_to_cart(self, customer_id: int, product_id: int, quantity: int) -> bool:
        """Add item to cart"""
        # Check if item already in cart
        query = "SELECT cart_id, quantity FROM Cart WHERE customer_id = ? AND product_id = ?"
        existing = self.execute_query(query, (customer_id, product_id))
        
        if existing:
            # Update quantity
            new_quantity = existing[0][1] + quantity
            query = "UPDATE Cart SET quantity = ? WHERE cart_id = ?"
            self.execute_update(query, (new_quantity, existing[0][0]))
        else:
            # Add new item
            query = "INSERT INTO Cart (customer_id, product_id, quantity, added_date) VALUES (?, ?, ?, ?)"
            self.execute_update(query, (customer_id, product_id, quantity, datetime.now()))
        return True
    
    def get_cart_items(self, customer_id: int) -> List[Dict]:
        """Get cart items for customer"""
        query = """
            SELECT c.cart_id, c.product_id, p.name, p.price, c.quantity, 
                   (p.price * c.quantity) as total_price
            FROM Cart c
            JOIN Product p ON c.product_id = p.product_id
            WHERE c.customer_id = ?
        """
        results = self.execute_query(query, (customer_id,))
        return [
            {
                'cart_id': row[0], 'product_id': row[1], 'name': row[2],
                'price': row[3], 'quantity': row[4], 'total_price': row[5]
            }
            for row in results
        ]
    
    def remove_from_cart(self, cart_id: int) -> bool:
        """Remove item from cart"""
        query = "DELETE FROM Cart WHERE cart_id = ?"
        return self.execute_update(query, (cart_id,)) > 0
    
    def create_order(self, customer_id: int, payment_method: str, shipping_address: str) -> Optional[int]:
        """Create new order from cart"""
        try:
            # Get cart items
            cart_items = self.get_cart_items(customer_id)
            if not cart_items:
                return None
            
            total_amount = sum(item['total_price'] for item in cart_items)
            
            # Create payment record
            payment_query = "INSERT INTO Payment (customer_id, payment_method, amount, payment_date) VALUES (?, ?, ?, ?)"
            cursor = self.conn.cursor()
            cursor.execute(payment_query, (customer_id, payment_method, total_amount, datetime.now()))
            payment_id = cursor.lastrowid
            
            # Create shipment record
            shipment_query = "INSERT INTO Shipment (shipment_date, address, tracking_number) VALUES (?, ?, ?)"
            tracking_number = f"UNIQLO{uuid.uuid4().hex[:8].upper()}"
            cursor.execute(shipment_query, (datetime.now(), shipping_address, tracking_number))
            shipment_id = cursor.lastrowid
            
            # Create order
            order_query = "INSERT INTO \"Order\" (customer_id, order_date, total_amount, payment_id, shipment_id, status) VALUES (?, ?, ?, ?, ?, ?)"
            cursor.execute(order_query, (customer_id, datetime.now(), total_amount, payment_id, shipment_id, 'Processing'))
            order_id = cursor.lastrowid
            
            # Create order items
            for item in cart_items:
                item_query = "INSERT INTO Order_Item (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)"
                cursor.execute(item_query, (order_id, item['product_id'], item['quantity'], item['price']))
                
                # Update product stock
                stock_query = "UPDATE Product SET stock = stock - ? WHERE product_id = ?"
                cursor.execute(stock_query, (item['quantity'], item['product_id']))
            
            # Clear cart
            clear_cart_query = "DELETE FROM Cart WHERE customer_id = ?"
            cursor.execute(clear_cart_query, (customer_id,))
            
            self.conn.commit()
            return order_id
            
        except Exception as e:
            self.conn.rollback()
            st.error(f"Error creating order: {e}")
            return None
    
    def get_customer_orders(self, customer_id: int) -> List[Dict]:
        """Get orders for customer"""
        query = """
            SELECT o.order_id, o.order_date, o.total_amount, o.status, s.tracking_number
            FROM "Order" o
            LEFT JOIN Shipment s ON o.shipment_id = s.shipment_id
            WHERE o.customer_id = ?
            ORDER BY o.order_date DESC
        """
        results = self.execute_query(query, (customer_id,))
        return [
            {
                'order_id': row[0], 'order_date': row[1], 'total_amount': row[2],
                'status': row[3], 'tracking_number': row[4]
            }
            for row in results
        ]

# Initialize database manager
@st.cache_resource
def get_db_manager():
    return DatabaseManager()

def customer_login_page():
    """Customer login/signup page"""
    st.title("🛍️ Uniqlo - Customer Portal")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.subheader("Login to Your Account")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", key="login_btn"):
            if email and password:
                db = get_db_manager()
                customer = db.get_customer_by_email(email)
                if customer and verify_password(password, customer[4]):
                    st.session_state.user_type = "customer"
                    st.session_state.customer_id = customer[0]
                    st.session_state.customer_name = f"{customer[1]} {customer[2]}"
                    st.session_state.customer_email = customer[3]
                    st.rerun()
                else:
                    st.error("Invalid email or password")
            else:
                st.error("Please fill in all fields")
    
    with tab2:
        st.subheader("Create New Account")
        first_name = st.text_input("First Name", key="signup_fname")
        last_name = st.text_input("Last Name", key="signup_lname")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm")
        address = st.text_area("Address (Optional)", key="signup_address")
        phone = st.text_input("Phone Number (Optional)", key="signup_phone")
        
        if st.button("Create Account", key="signup_btn"):
            if first_name and last_name and email and password and confirm_password:
                if password == confirm_password:
                    db = get_db_manager()
                    if db.create_customer(first_name, last_name, email, password, address, phone):
                        st.success("Account created successfully! Please login.")
                    else:
                        st.error("Email already exists")
                else:
                    st.error("Passwords do not match")
            else:
                st.error("Please fill in all required fields")

def customer_dashboard():
    """Customer dashboard"""
    st.title(f"Welcome back, {st.session_state.customer_name}! 👋")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", [
        "🏠 Home", "🛍️ Shop", "🛒 Cart", "📦 Orders", 
        "👤 Profile", "⭐ Reviews", "❤️ Wishlist"
    ])
    
    if st.sidebar.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    db = get_db_manager()
    
    if page == "🏠 Home":
        customer_home_page(db)
    elif page == "🛍️ Shop":
        customer_shop_page(db)
    elif page == "🛒 Cart":
        customer_cart_page(db)
    elif page == "📦 Orders":
        customer_orders_page(db)
    elif page == "👤 Profile":
        customer_profile_page(db)
    elif page == "⭐ Reviews":
        customer_reviews_page(db)
    elif page == "❤️ Wishlist":
        customer_wishlist_page(db)

def customer_home_page(db):
    """Customer home page with recommendations"""
    st.subheader("🌟 Featured Products")
    
    # Get featured products (top 6 products)
    products = db.get_products()[:6]
    
    cols = st.columns(3)
    for i, product in enumerate(products):
        with cols[i % 3]:
            st.image("https://via.placeholder.com/200x250?text=Product+Image", use_column_width=True)
            st.write(f"**{product['name']}**")
            st.write(f"${product['price']:.2f}")
            st.write(f"Category: {product['category_name']}")
            if st.button(f"Add to Cart", key=f"home_add_{product['product_id']}"):
                db.add_to_cart(st.session_state.customer_id, product['product_id'], 1)
                st.success("Added to cart!")
                st.rerun()

def customer_shop_page(db):
    """Customer shopping page"""
    st.subheader("🛍️ Shop Products")
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        categories = db.get_categories()
        category_options = {0: "All Categories"}
        category_options.update({cat['category_id']: cat['name'] for cat in categories})
        selected_category = st.selectbox("Category", options=list(category_options.keys()), 
                                       format_func=lambda x: category_options[x])
    
    with col2:
        search_term = st.text_input("Search products", placeholder="Enter product name...")
    
    # Get filtered products
    category_filter = selected_category if selected_category != 0 else None
    products = db.get_products(category_filter, search_term)
    
    if not products:
        st.info("No products found matching your criteria.")
        return
    
    # Display products
    cols = st.columns(3)
    for i, product in enumerate(products):
        with cols[i % 3]:
            st.image("https://via.placeholder.com/200x250?text=Product+Image", use_column_width=True)
            st.write(f"**{product['name']}**")
            st.write(f"${product['price']:.2f}")
            st.write(f"Stock: {product['stock']}")
            st.write(f"Category: {product['category_name']}")
            
            quantity = st.number_input(f"Quantity", min_value=1, max_value=product['stock'], 
                                     value=1, key=f"qty_{product['product_id']}")
            
            if st.button(f"Add to Cart", key=f"shop_add_{product['product_id']}", 
                        disabled=product['stock'] == 0):
                if product['stock'] >= quantity:
                    db.add_to_cart(st.session_state.customer_id, product['product_id'], quantity)
                    st.success("Added to cart!")
                    st.rerun()
                else:
                    st.error("Not enough stock available")

def customer_cart_page(db):
    """Customer cart page"""
    st.subheader("🛒 Shopping Cart")
    
    cart_items = db.get_cart_items(st.session_state.customer_id)
    
    if not cart_items:
        st.info("Your cart is empty. Start shopping!")
        return
    
    # Display cart items
    total_amount = 0
    for item in cart_items:
        col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
        
        with col1:
            st.write(f"**{item['name']}**")
        with col2:
            st.write(f"${item['price']:.2f}")
        with col3:
            st.write(f"Qty: {item['quantity']}")
        with col4:
            st.write(f"${item['total_price']:.2f}")
        with col5:
            if st.button("Remove", key=f"remove_{item['cart_id']}"):
                db.remove_from_cart(item['cart_id'])
                st.rerun()
        
        total_amount += item['total_price']
        st.divider()
    
    # Cart summary
    st.subheader(f"Total: ${total_amount:.2f}")
    
    # Checkout
    st.subheader("Checkout")
    payment_method = st.selectbox("Payment Method", ["Credit Card", "Debit Card", "PayPal", "Cash on Delivery"])
    shipping_address = st.text_area("Shipping Address", placeholder="Enter your shipping address...")
    
    if st.button("Place Order", type="primary"):
        if shipping_address:
            order_id = db.create_order(st.session_state.customer_id, payment_method, shipping_address)
            if order_id:
                st.success(f"Order placed successfully! Order ID: {order_id}")
                st.balloons()
                st.rerun()
            else:
                st.error("Failed to place order. Please try again.")
        else:
            st.error("Please enter shipping address")

def customer_orders_page(db):
    """Customer orders page"""
    st.subheader("📦 Your Orders")
    
    orders = db.get_customer_orders(st.session_state.customer_id)
    
    if not orders:
        st.info("You haven't placed any orders yet.")
        return
    
    for order in orders:
        with st.expander(f"Order #{order['order_id']} - {order['order_date'][:10]}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Status:** {order['status']}")
                st.write(f"**Total:** ${order['total_amount']:.2f}")
            with col2:
                st.write(f"**Tracking Number:** {order['tracking_number']}")
                if order['status'] in ['Shipped', 'Delivered']:
                    st.success("🚚 Track your package with the tracking number above")

def customer_profile_page(db):
    """Customer profile page"""
    st.subheader("👤 Profile Settings")
    
    # Get current customer info
    customer = db.get_customer_by_email(st.session_state.customer_email)
    
    with st.form("profile_form"):
        first_name = st.text_input("First Name", value=customer[1])
        last_name = st.text_input("Last Name", value=customer[2])
        email = st.text_input("Email", value=customer[3], disabled=True)
        address = st.text_area("Address", value=customer[5] or "")
        phone = st.text_input("Phone Number", value=customer[6] or "")
        
        new_password = st.text_input("New Password (leave blank to keep current)", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        
        if st.form_submit_button("Update Profile"):
            update_query = "UPDATE Customer SET first_name = ?, last_name = ?, address = ?, phone_number = ?"
            params = [first_name, last_name, address, phone]
            
            if new_password:
                if new_password == confirm_password:
                    update_query += ", password = ?"
                    params.append(hash_password(new_password))
                else:
                    st.error("Passwords do not match")
                    return
            
            update_query += " WHERE customer_id = ?"
            params.append(st.session_state.customer_id)
            
            if db.execute_update(update_query, tuple(params)):
                st.success("Profile updated successfully!")
                st.session_state.customer_name = f"{first_name} {last_name}"
            else:
                st.error("Failed to update profile")

def customer_reviews_page(db):
    """Customer reviews page"""
    st.subheader("⭐ Product Reviews")
    st.info("Review system coming soon!")

def customer_wishlist_page(db):
    """Customer wishlist page"""
    st.subheader("❤️ Your Wishlist")
    st.info("Wishlist feature coming soon!")

def staff_login_page():
    """Staff login page"""
    st.title("👨‍💼 Uniqlo - Staff Portal")
    
    # Simple staff login (in production, implement proper authentication)
    staff_id = st.text_input("Staff ID")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        # Simple authentication (replace with proper system)
        if staff_id == "admin" and password == "admin123":
            st.session_state.user_type = "staff"
            st.session_state.staff_id = staff_id
            st.rerun()
        else:
            st.error("Invalid credentials")

def staff_dashboard():
    """Staff dashboard"""
    st.title("👨‍💼 Staff Dashboard")
    
    # Sidebar navigation
    st.sidebar.title("Staff Navigation")
    page = st.sidebar.radio("Go to", [
        "📊 Dashboard", "📦 Manage Products", "🛍️ Manage Orders", 
        "👥 Manage Customers", "📈 Reports", "📢 Notifications"
    ])
    
    if st.sidebar.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    db = get_db_manager()
    
    if page == "📊 Dashboard":
        staff_home_page(db)
    elif page == "📦 Manage Products":
        staff_products_page(db)
    elif page == "🛍️ Manage Orders":
        staff_orders_page(db)
    elif page == "👥 Manage Customers":
        staff_customers_page(db)
    elif page == "📈 Reports":
        staff_reports_page(db)
    elif page == "📢 Notifications":
        staff_notifications_page(db)

def staff_home_page(db):
    """Staff home page with overview"""
    st.subheader("📊 Business Overview")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_products = db.execute_query("SELECT COUNT(*) FROM Product")[0][0]
        st.metric("Total Products", total_products)
    
    with col2:
        total_customers = db.execute_query("SELECT COUNT(*) FROM Customer")[0][0]
        st.metric("Total Customers", total_customers)
    
    with col3:
        total_orders = db.execute_query("SELECT COUNT(*) FROM \"Order\"")[0][0]
        st.metric("Total Orders", total_orders)
    
    with col4:
        total_revenue = db.execute_query("SELECT COALESCE(SUM(total_amount), 0) FROM \"Order\"")[0][0]
        st.metric("Total Revenue", f"${total_revenue:.2f}")
    
    # Recent orders
    st.subheader("Recent Orders")
    recent_orders = db.execute_query("""
        SELECT o.order_id, c.first_name, c.last_name, o.order_date, o.total_amount, o.status
        FROM "Order" o
        JOIN Customer c ON o.customer_id = c.customer_id
        ORDER BY o.order_date DESC
        LIMIT 10
    """)
    
    if recent_orders:
        df = pd.DataFrame(recent_orders, columns=['Order ID', 'First Name', 'Last Name', 'Date', 'Amount', 'Status'])
        st.dataframe(df, use_container_width=True)

def staff_products_page(db):
    """Staff product management page"""
    st.subheader("📦 Product Management")
    
    tab1, tab2 = st.tabs(["View Products", "Add Product"])
    
    with tab1:
        # Display products
        products = db.get_products()
        if products:
            df = pd.DataFrame(products)
            st.dataframe(df, use_container_width=True)
            
            # Update stock form
            st.subheader("Update Product Stock")
            product_names = {p['product_id']: p['name'] for p in products}
            selected_product = st.selectbox("Select Product", options=list(product_names.keys()),
                                          format_func=lambda x: product_names[x])
            new_stock = st.number_input("New Stock Quantity", min_value=0, value=0)
            
            if st.button("Update Stock"):
                db.execute_update("UPDATE Product SET stock = ? WHERE product_id = ?", 
                                (new_stock, selected_product))
                st.success("Stock updated successfully!")
                st.rerun()
    
    with tab2:
        # Add new product
        with st.form("add_product_form"):
            name = st.text_input("Product Name")
            description = st.text_area("Description")
            price = st.number_input("Price", min_value=0.0, step=0.01)
            stock = st.number_input("Initial Stock", min_value=0, value=0)
            
            categories = db.get_categories()
            category_options = {cat['category_id']: cat['name'] for cat in categories}
            category_id = st.selectbox("Category", options=list(category_options.keys()),
                                     format_func=lambda x: category_options[x])
            
            if st.form_submit_button("Add Product"):
                if name and description and price > 0:
                    query = "INSERT INTO Product (name, description, price, stock, category_id) VALUES (?, ?, ?, ?, ?)"
                    db.execute_update(query, (name, description, price, stock, category_id))
                    st.success("Product added successfully!")
                    st.rerun()
                else:
                    st.error("Please fill in all required fields")

def staff_orders_page(db):
    """Staff order management page"""
    st.subheader("🛍️ Order Management")
    
    # Get all orders
    orders = db.execute_query("""
        SELECT o.order_id, c.first_name, c.last_name, o.order_date, 
               o.total_amount, o.status, s.tracking_number
        FROM "Order" o
        JOIN Customer c ON o.customer_id = c.customer_id
        LEFT JOIN Shipment s ON o.shipment_id = s.shipment_id
        ORDER BY o.order_date DESC
    """)
    
    if not orders:
        st.info("No orders found.")
        return
    
    # Display orders in expandable format
    for order in orders:
        order_id, first_name, last_name, order_date, total_amount, status, tracking_number = order
        
        with st.expander(f"Order #{order_id} - {first_name} {last_name} - ${total_amount:.2f}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Customer:** {first_name} {last_name}")
                st.write(f"**Date:** {order_date}")
                st.write(f"**Total:** ${total_amount:.2f}")
                st.write(f"**Tracking:** {tracking_number}")
            
            with col2:
                # Update order status
                new_status = st.selectbox(
                    "Update Status",
                    ["Pending", "Processing", "Shipped", "Delivered", "Cancelled"],
                    index=["Pending", "Processing", "Shipped", "Delivered", "Cancelled"].index(status),
                    key=f"status_{order_id}"
                )
                
                if st.button("Update Status", key=f"update_{order_id}"):
                    db.execute_update("UPDATE \"Order\" SET status = ? WHERE order_id = ?", 
                                    (new_status, order_id))
                    st.success("Status updated!")
                    st.rerun()
            
            # Show order items
            st.subheader("Order Items")
            order_items = db.execute_query("""
                SELECT p.name, oi.quantity, oi.unit_price, (oi.quantity * oi.unit_price) as total
                FROM Order_Item oi
                JOIN Product p ON oi.product_id = p.product_id
                WHERE oi.order_id = ?
            """, (order_id,))
            
            if order_items:
                df = pd.DataFrame(order_items, columns=['Product', 'Quantity', 'Unit Price', 'Total'])
                st.dataframe(df, use_container_width=True)

def staff_customers_page(db):
    """Staff customer management page"""
    st.subheader("👥 Customer Management")
    
    # Get all customers
    customers = db.execute_query("""
        SELECT customer_id, first_name, last_name, email, phone_number, address
        FROM Customer
        ORDER BY first_name, last_name
    """)
    
    if customers:
        df = pd.DataFrame(customers, columns=['ID', 'First Name', 'Last Name', 'Email', 'Phone', 'Address'])
        st.dataframe(df, use_container_width=True)
        
        # Customer analytics
        st.subheader("Customer Analytics")
        
        # Customer order history
        selected_customer_id = st.selectbox(
            "Select Customer for Order History",
            options=[c[0] for c in customers],
            format_func=lambda x: f"{next(c[1] + ' ' + c[2] for c in customers if c[0] == x)} (ID: {x})"
        )
        
        if selected_customer_id:
            customer_orders = db.execute_query("""
                SELECT order_id, order_date, total_amount, status
                FROM "Order"
                WHERE customer_id = ?
                ORDER BY order_date DESC
            """, (selected_customer_id,))
            
            if customer_orders:
                df_orders = pd.DataFrame(customer_orders, columns=['Order ID', 'Date', 'Amount', 'Status'])
                st.dataframe(df_orders, use_container_width=True)
                
                total_spent = sum(order[2] for order in customer_orders)
                st.metric("Total Customer Value", f"${total_spent:.2f}")
            else:
                st.info("This customer hasn't placed any orders yet.")

def staff_reports_page(db):
    """Staff reports and analytics page"""
    st.subheader("📈 Reports & Analytics")
    
    # Date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("End Date", value=datetime.now())
    
    # Sales report
    st.subheader("Sales Report")
    sales_data = db.execute_query("""
        SELECT DATE(order_date) as date, SUM(total_amount) as daily_sales, COUNT(*) as orders
        FROM "Order"
        WHERE DATE(order_date) BETWEEN ? AND ?
        GROUP BY DATE(order_date)
        ORDER BY date
    """, (start_date, end_date))
    
    if sales_data:
        df_sales = pd.DataFrame(sales_data, columns=['Date', 'Sales', 'Orders'])
        
        # Sales chart
        fig = px.line(df_sales, x='Date', y='Sales', title='Daily Sales')
        st.plotly_chart(fig, use_container_width=True)
        
        # Orders chart
        fig2 = px.bar(df_sales, x='Date', y='Orders', title='Daily Orders')
        st.plotly_chart(fig2, use_container_width=True)
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            total_sales = df_sales['Sales'].sum()
            st.metric("Total Sales", f"${total_sales:.2f}")
        with col2:
            total_orders = df_sales['Orders'].sum()
            st.metric("Total Orders", total_orders)
        with col3:
            avg_order_value = total_sales / total_orders if total_orders > 0 else 0
            st.metric("Average Order Value", f"${avg_order_value:.2f}")
    
    # Product performance
    st.subheader("Product Performance")
    product_sales = db.execute_query("""
        SELECT p.name, SUM(oi.quantity) as total_sold, SUM(oi.quantity * oi.unit_price) as revenue
        FROM Order_Item oi
        JOIN Product p ON oi.product_id = p.product_id
        JOIN "Order" o ON oi.order_id = o.order_id
        WHERE DATE(o.order_date) BETWEEN ? AND ?
        GROUP BY p.product_id, p.name
        ORDER BY revenue DESC
        LIMIT 10
    """, (start_date, end_date))
    
    if product_sales:
        df_products = pd.DataFrame(product_sales, columns=['Product', 'Quantity Sold', 'Revenue'])
        st.dataframe(df_products, use_container_width=True)
        
        # Top products chart
        fig3 = px.bar(df_products, x='Product', y='Revenue', title='Top 10 Products by Revenue')
        fig3.update_xaxes(tickangle=45)
        st.plotly_chart(fig3, use_container_width=True)
    
    # Category performance
    st.subheader("Category Performance")
    category_sales = db.execute_query("""
        SELECT c.name, COUNT(oi.order_item_id) as items_sold, SUM(oi.quantity * oi.unit_price) as revenue
        FROM Order_Item oi
        JOIN Product p ON oi.product_id = p.product_id
        JOIN Category c ON p.category_id = c.category_id
        JOIN "Order" o ON oi.order_id = o.order_id
        WHERE DATE(o.order_date) BETWEEN ? AND ?
        GROUP BY c.category_id, c.name
        ORDER BY revenue DESC
    """, (start_date, end_date))
    
    if category_sales:
        df_categories = pd.DataFrame(category_sales, columns=['Category', 'Items Sold', 'Revenue'])
        
        # Category pie chart
        fig4 = px.pie(df_categories, values='Revenue', names='Category', title='Revenue by Category')
        st.plotly_chart(fig4, use_container_width=True)
        
        st.dataframe(df_categories, use_container_width=True)

def staff_notifications_page(db):
    """Staff notifications page"""
    st.subheader("📢 Customer Notifications")
    
    # Low stock alerts
    st.subheader("⚠️ Low Stock Alerts")
    low_stock = db.execute_query("""
        SELECT name, stock
        FROM Product
        WHERE stock < 10
        ORDER BY stock ASC
    """)
    
    if low_stock:
        df_low_stock = pd.DataFrame(low_stock, columns=['Product', 'Stock'])
        st.dataframe(df_low_stock, use_container_width=True)
    else:
        st.success("All products have sufficient stock!")
    
    # Send notifications
    st.subheader("Send Customer Notifications")
    
    with st.form("notification_form"):
        notification_type = st.selectbox("Notification Type", [
            "Promotional Offer", "New Product Launch", "Order Update", "General Announcement"
        ])
        
        subject = st.text_input("Subject")
        message = st.text_area("Message", height=150)
        
        # Customer selection
        customers = db.execute_query("SELECT customer_id, first_name, last_name, email FROM Customer")
        customer_options = ["All Customers"] + [f"{c[1]} {c[2]} ({c[3]})" for c in customers]
        selected_customers = st.multiselect("Recipients", customer_options, default=["All Customers"])
        
        if st.form_submit_button("Send Notification"):
            if subject and message:
                # In a real application, this would send actual emails/SMS
                recipient_count = len(customers) if "All Customers" in selected_customers else len(selected_customers) - 1
                st.success(f"Notification sent to {recipient_count} customers!")
                
                # Log notification (you could create a notifications table)
                st.info("Notification logged in system.")
            else:
                st.error("Please fill in subject and message")
    
    # Recent notifications log
    st.subheader("Recent Notifications")
    st.info("Notification history feature would be implemented here with a proper notifications table.")

# Main application
def main():
    st.set_page_config(
        page_title="Uniqlo Management System",
        page_icon="🛍️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        color: #FF6B6B;
        font-size: 2.5rem;
        margin-bottom: 2rem;
    }
    .stButton > button {
        background-color: #FF6B6B;
        color: white;
        border-radius: 20px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #FF5252;
        color: white;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #FF6B6B;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'user_type' not in st.session_state:
        st.session_state.user_type = None
    
    # Route to appropriate interface
    if st.session_state.user_type == "customer":
        customer_dashboard()
    elif st.session_state.user_type == "staff":
        staff_dashboard()
    else:
        # Main login page
        st.markdown('<h1 class="main-header">🛍️ UNIQLO Management System</h1>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🛍️ Customer Portal")
            st.write("Shop products, manage orders, and track deliveries")
            if st.button("Customer Login", key="customer_portal", use_container_width=True):
                st.session_state.login_type = "customer"
        
        with col2:
            st.markdown("### 👨‍💼 Staff Portal")
            st.write("Manage products, orders, and customer relationships")
            if st.button("Staff Login", key="staff_portal", use_container_width=True):
                st.session_state.login_type = "staff"
        
        # Show appropriate login form
        if 'login_type' in st.session_state:
            st.divider()
            if st.session_state.login_type == "customer":
                customer_login_page()
            elif st.session_state.login_type == "staff":
                staff_login_page()

if __name__ == "__main__":
    main()