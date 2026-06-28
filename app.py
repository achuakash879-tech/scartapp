import os
import shutil
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scatbys.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'payment_screenshots')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB max upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
G_PAY_UPI_ID = os.environ.get('G_PAY_UPI_ID', 'your-upi-id@okaxis')
G_PAY_QR_IMAGE = os.environ.get('G_PAY_QR_IMAGE', '/static/payments/gpay-qr.png')

db = SQLAlchemy()
db.init_app(app)

def allowed_payment_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =========================================================================
# DATABASE MODELS
# =========================================================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    orders = db.relationship('Order', backref='user', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(200), nullable=False)
    stock_quantity = db.Column(db.Integer, default=0)
    category = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    orders = db.relationship('Order', backref='product', lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Payment Pending')  # Payment Pending, Processing, Shipped, Delivered
    payment_method = db.Column(db.String(50), nullable=False, default='GPay / UPI')
    payment_status = db.Column(db.String(50), nullable=False, default='Pending Verification')  # Pending Verification, Approved, Rejected
    payment_screenshot = db.Column(db.String(255), nullable=True)
    ordered_at = db.Column(db.DateTime, default=datetime.utcnow)

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

# =========================================================================
# LOGIN DECORATORS & SESSION UTILITIES
# =========================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session or not session['admin_logged_in']:
            flash('Admin authentication required.', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# =========================================================================
# INLINE HTML/CSS TEMPLATES
# =========================================================================

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}{% endblock %} - Scatbys</title>
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;600;700;800&display=swap" rel="stylesheet">
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary: #4f46e5;
            --primary-light: #818cf8;
            --secondary: #06b6d4;
            --dark: #0f172a;
            --dark-light: #1e293b;
            --light: #f8fafc;
            --white: #ffffff;
            --accent: #ec4899;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --font-main: 'Inter', sans-serif;
            --font-heading: 'Outfit', sans-serif;
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
            --shadow-premium: 0 20px 40px -15px rgba(79, 70, 229, 0.15);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: var(--font-main);
            background-color: #fafbfd;
            color: var(--dark-light);
            line-height: 1.6;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: var(--font-heading);
            font-weight: 700;
            color: var(--dark);
        }

        a {
            color: inherit;
            text-decoration: none;
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }
        ::-webkit-scrollbar-track {
            background: var(--light);
        }
        ::-webkit-scrollbar-thumb {
            background: #cbd5e1;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #94a3b8;
        }

        /* Animations */
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(25px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        .fade-in-up {
            animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        .fade-in {
            animation: fadeIn 0.4s ease-out forwards;
        }

        /* Promo Banner Sub-nav */
        .promo-banner {
            background: linear-gradient(90deg, #1e1b4b, #312e81);
            color: rgba(255, 255, 255, 0.9);
            font-size: 0.8rem;
            padding: 8px 5%;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .promo-text i {
            color: var(--secondary);
            margin-right: 5px;
        }
        .promo-links a {
            margin-left: 15px;
            transition: color 0.2s;
        }
        .promo-links a:hover {
            color: var(--secondary);
        }

        /* Main Header */
        .main-header {
            background: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid rgba(226, 232, 240, 0.8);
            position: sticky;
            top: 0;
            z-index: 999;
        }
        .nav-container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 12px 5%;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .brand-logo {
            font-family: var(--font-heading);
            font-weight: 800;
            font-size: 1.8rem;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -1px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .nav-menu {
            display: flex;
            list-style: none;
            align-items: center;
            gap: 25px;
        }
        .nav-link {
            font-weight: 600;
            font-size: 0.95rem;
            color: var(--dark-light);
            position: relative;
            padding: 5px 0;
            transition: color 0.2s;
        }
        .nav-link:hover {
            color: var(--primary);
        }
        .nav-link::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            width: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            transition: width 0.3s ease;
        }
        .nav-link:hover::after {
            width: 100%;
        }
        .nav-link.active::after {
            width: 100%;
        }

        .search-form-container {
            flex-grow: 1;
            max-width: 350px;
            margin: 0 20px;
            position: relative;
        }
        .search-input {
            width: 100%;
            padding: 8px 16px 8px 40px;
            border-radius: 99px;
            border: 1px solid #e2e8f0;
            background: #f1f5f9;
            font-size: 0.85rem;
            transition: all 0.3s;
        }
        .search-input:focus {
            outline: none;
            border-color: var(--primary-light);
            background: var(--white);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
        }
        .search-icon {
            position: absolute;
            left: 14px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--dark-light);
            opacity: 0.6;
        }

        .nav-actions {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .btn-nav-outline {
            border: 1.5px solid var(--primary);
            color: var(--primary);
            border-radius: 99px;
            padding: 6px 16px;
            font-size: 0.85rem;
            font-weight: 600;
            transition: all 0.2s;
        }
        .btn-nav-outline:hover {
            background: var(--primary);
            color: white;
        }
        .btn-nav-solid {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
            border-radius: 99px;
            padding: 7px 18px;
            font-size: 0.85rem;
            font-weight: 600;
            transition: all 0.2s;
            box-shadow: 0 4px 10px rgba(79, 70, 229, 0.25);
        }
        .btn-nav-solid:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 14px rgba(79, 70, 229, 0.35);
        }

        /* Secondary Navigation Categories Bar */
        .categories-nav {
            background: var(--white);
            border-bottom: 1px solid #e2e8f0;
            padding: 8px 5%;
        }
        .categories-container {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            gap: 15px;
            overflow-x: auto;
            scrollbar-width: none;
        }
        .categories-container::-webkit-scrollbar {
            display: none;
        }
        .category-tab {
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--dark-light);
            opacity: 0.8;
            padding: 6px 14px;
            border-radius: 99px;
            white-space: nowrap;
            transition: all 0.2s;
            background: #f1f5f9;
        }
        .category-tab:hover {
            color: var(--primary);
            background: #eef2ff;
            opacity: 1;
        }
        .category-tab.active {
            background: var(--primary);
            color: white;
            opacity: 1;
        }

        /* Admin Navigation Bar */
        .admin-navbar {
            background: #0b0f19;
            border-bottom: 2px solid var(--primary);
            padding: 10px 5%;
            font-size: 0.85rem;
        }
        .admin-nav-container {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .admin-title-badge {
            background: linear-gradient(135deg, #f59e0b, #ef4444);
            color: white;
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 800;
            text-transform: uppercase;
            font-size: 0.7rem;
            letter-spacing: 0.5px;
        }
        .admin-menu {
            display: flex;
            list-style: none;
            gap: 20px;
            margin: 0;
        }
        .admin-link {
            color: #94a3b8;
            font-weight: 600;
            transition: color 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .admin-link:hover, .admin-link.active {
            color: var(--white);
        }
        .admin-link.active {
            border-bottom: 2px solid var(--secondary);
            padding-bottom: 2px;
        }

        /* Alert Notification Banner */
        .alerts-container {
            max-width: 1400px;
            margin: 20px auto 0 auto;
            padding: 0 5%;
        }
        .custom-alert {
            padding: 14px 20px;
            border-radius: 12px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: var(--shadow-md);
            font-weight: 500;
        }
        .custom-alert.success {
            background-color: #ecfdf5;
            border-left: 5px solid var(--success);
            color: #065f46;
        }
        .custom-alert.danger {
            background-color: #fef2f2;
            border-left: 5px solid var(--danger);
            color: #991b1b;
        }
        .custom-alert.warning {
            background-color: #fffbeb;
            border-left: 5px solid var(--warning);
            color: #92400e;
        }
        .alert-close {
            cursor: pointer;
            background: none;
            border: none;
            font-size: 1.2rem;
            color: inherit;
            opacity: 0.6;
            transition: opacity 0.2s;
        }
        .alert-close:hover {
            opacity: 1;
        }

        /* Main Content wrapper */
        .content-wrapper {
            flex-grow: 1;
            max-width: 1400px;
            width: 100%;
            margin: 0 auto;
            padding: 30px 5%;
        }

        /* Footer styling */
        .main-footer {
            background: #090d16;
            color: #94a3b8;
            padding: 50px 5% 25px 5%;
            border-top: 1px solid #1e293b;
            margin-top: auto;
        }
        .footer-container {
            max-width: 1400px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 40px;
            margin-bottom: 30px;
        }
        .footer-col h4 {
            color: var(--white);
            font-size: 1.1rem;
            margin-bottom: 18px;
            position: relative;
            padding-bottom: 6px;
        }
        .footer-col h4::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            width: 35px;
            height: 2px;
            background: var(--primary);
        }
        .footer-col p {
            font-size: 0.85rem;
            line-height: 1.8;
        }
        .footer-links {
            list-style: none;
        }
        .footer-links li {
            margin-bottom: 10px;
        }
        .footer-links a {
            font-size: 0.85rem;
            transition: all 0.2s;
            display: inline-block;
        }
        .footer-links a:hover {
            color: var(--secondary);
            transform: translateX(4px);
        }
        .social-icons {
            display: flex;
            gap: 12px;
            margin-top: 15px;
        }
        .social-icon {
            width: 34px;
            height: 34px;
            border-radius: 50%;
            background: #1e293b;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--white);
            transition: all 0.2s;
        }
        .social-icon:hover {
            background: var(--primary);
            transform: translateY(-3px);
        }
        .footer-bottom {
            max-width: 1400px;
            margin: 0 auto;
            padding-top: 20px;
            border-top: 1px solid #1e293b;
            text-align: center;
            font-size: 0.8rem;
        }

        /* Forms Layout & Styling */
        .auth-card {
            max-width: 440px;
            margin: 40px auto;
            padding: 35px;
            background: var(--white);
            border-radius: 18px;
            box-shadow: var(--shadow-lg);
            border: 1px solid #e2e8f0;
        }
        .auth-card h2 {
            text-align: center;
            margin-bottom: 25px;
            font-size: 1.7rem;
            background: linear-gradient(135deg, var(--dark), var(--primary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .form-group {
            margin-bottom: 18px;
        }
        .form-label {
            display: block;
            margin-bottom: 6px;
            font-weight: 600;
            font-size: 0.85rem;
            color: var(--dark-light);
        }
        .form-control-custom {
            width: 100%;
            padding: 10px 14px;
            border-radius: 8px;
            border: 1.5px solid #cbd5e1;
            font-size: 0.9rem;
            transition: all 0.2s;
            font-family: var(--font-main);
        }
        .form-control-custom:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.15);
        }
        .btn-submit {
            width: 100%;
            padding: 11px;
            border-radius: 8px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
            border: none;
            font-weight: 700;
            font-size: 0.95rem;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.2);
            transition: all 0.2s;
        }
        .btn-submit:hover {
            transform: translateY(-1.5px);
            box-shadow: 0 6px 16px rgba(79, 70, 229, 0.3);
        }
        .auth-footer {
            text-align: center;
            margin-top: 20px;
            font-size: 0.85rem;
            color: var(--dark-light);
            opacity: 0.8;
        }
        .auth-footer a {
            color: var(--primary);
            font-weight: 600;
        }
        .auth-footer a:hover {
            text-decoration: underline;
        }

        /* Generic table styles */
        .table-container {
            background: var(--white);
            border-radius: 16px;
            border: 1px solid #e2e8f0;
            box-shadow: var(--shadow-md);
            overflow-x: auto;
            margin-top: 20px;
        }
        .custom-table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.9rem;
        }
        .custom-table th {
            background: #f8fafc;
            padding: 16px 20px;
            font-weight: 700;
            color: var(--dark);
            border-bottom: 2px solid #e2e8f0;
        }
        .custom-table td {
            padding: 16px 20px;
            border-bottom: 1px solid #e2e8f0;
            color: var(--dark-light);
        }
        .custom-table tr:last-child td {
            border-bottom: none;
        }
        .custom-table tr:hover td {
            background: #f8fafc;
        }

        /* Grid layouts for Admin Stats */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: var(--white);
            border-radius: 16px;
            border: 1px solid #e2e8f0;
            padding: 24px;
            box-shadow: var(--shadow-md);
            display: flex;
            align-items: center;
            gap: 20px;
            transition: transform 0.3s;
        }
        .stat-card:hover {
            transform: translateY(-3px);
        }
        .stat-icon {
            width: 50px;
            height: 50px;
            border-radius: 12px;
            background: #eef2ff;
            color: var(--primary);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.4rem;
        }
        .stat-card:nth-child(2) .stat-icon { background: #ecfeff; color: var(--secondary); }
        .stat-card:nth-child(3) .stat-icon { background: #ecfdf5; color: var(--success); }
        .stat-card:nth-child(4) .stat-icon { background: #fffbeb; color: var(--warning); }
        
        .stat-value {
            font-size: 1.8rem;
            font-weight: 800;
            color: var(--dark);
        }
        .stat-label {
            font-size: 0.8rem;
            color: var(--dark-light);
            opacity: 0.7;
            font-weight: 600;
            text-transform: uppercase;
        }

        @media (max-width: 992px) {
            .nav-container {
                flex-direction: column;
                gap: 15px;
                padding: 15px 5%;
            }
            .search-form-container {
                margin: 10px 0;
                width: 100%;
                max-width: 100%;
            }
            .nav-menu {
                width: 100%;
                justify-content: center;
                flex-wrap: wrap;
                gap: 15px;
            }
            .admin-nav-container {
                flex-direction: column;
                gap: 10px;
                align-items: flex-start;
            }
            .admin-menu {
                flex-wrap: wrap;
                gap: 15px;
            }
        }
    </style>
    {% block extra_css %}{% endblock %}
</head>
<body>
    <!-- Top Promo Banner -->
    <div class="promo-banner">
        <div class="promo-text">
            <i class="fa-solid fa-fire"></i> Premium products. Location-based delivery charges apply.
        </div>
        <div class="promo-links">
            <a href="/"><i class="fa-solid fa-store"></i> Scatbys Prime</a>
            <a href="/admin/login"><i class="fa-solid fa-user-shield"></i> Admin Portal</a>
            <a href="/#contact"><i class="fa-solid fa-headset"></i> Support</a>
        </div>
    </div>

    <!-- Admin Sub-navbar -->
    {% if session.get('admin_logged_in') %}
    <div class="admin-navbar">
        <div class="admin-nav-container">
            <div>
                <span class="admin-title-badge">ADMIN CONTROL</span>
            </div>
            <ul class="admin-menu">
                <li><a href="/admin/dashboard" class="admin-link {% if request.path == '/admin/dashboard' %}active{% endif %}"><i class="fa-solid fa-chart-line"></i> Dashboard</a></li>
                <li><a href="/admin/products" class="admin-link {% if request.path == '/admin/products' %}active{% endif %}"><i class="fa-solid fa-boxes-stacked"></i> Products</a></li>
                <li><a href="/admin/orders" class="admin-link {% if request.path == '/admin/orders' %}active{% endif %}"><i class="fa-solid fa-receipt"></i> Orders</a></li>
                <li><a href="/admin/add-product" class="admin-link {% if request.path == '/admin/add-product' %}active{% endif %}"><i class="fa-solid fa-plus"></i> Add Product</a></li>
                <li><a href="/admin/users" class="admin-link {% if request.path == '/admin/users' %}active{% endif %}"><i class="fa-solid fa-users"></i> Users</a></li>
                <li><a href="/admin/logout" class="admin-link" style="color: var(--danger);"><i class="fa-solid fa-right-from-bracket"></i> Logout</a></li>
            </ul>
        </div>
    </div>
    {% endif %}

    <!-- Main Navigation Header -->
    <header class="main-header">
        <div class="nav-container">
            <a href="/" class="brand-logo">
                <i class="fa-solid fa-bolt-lightning"></i> Scatbys
            </a>

            <!-- Search Bar -->
            <div class="search-form-container">
                <form action="/products" method="GET">
                    <i class="fa-solid fa-magnifying-glass search-icon"></i>
                    <input type="text" name="q" class="search-input" placeholder="Search catalog..." value="{{ request.args.get('q', '') }}">
                </form>
            </div>

            <!-- Main Menu Links -->
            <ul class="nav-menu">
                <li><a href="/" class="nav-link {% if request.path == '/' %}active{% endif %}">Home</a></li>
                <li><a href="/products" class="nav-link {% if request.path == '/products' %}active{% endif %}">Products</a></li>
                <li><a href="/#about" class="nav-link">About</a></li>
                <li><a href="/#contact" class="nav-link">Contact</a></li>
                {% if session.get('user_id') %}
                    <li><a href="/dashboard" class="nav-link {% if request.path == '/dashboard' %}active{% endif %}">Dashboard</a></li>
                {% endif %}
            </ul>

            <!-- User Auth Buttons -->
            <div class="nav-actions">
                {% if session.get('user_id') %}
                    <span style="font-size:0.85rem; font-weight:600; color:var(--dark-light);"><i class="fa-regular fa-circle-user"></i> {{ session.get('username') }}</span>
                    <a href="/logout" class="btn-nav-outline"><i class="fa-solid fa-sign-out-alt"></i> Logout</a>
                {% else %}
                    <a href="/login" class="btn-nav-outline">Login</a>
                    <a href="/register" class="btn-nav-solid">Register</a>
                {% endif %}
            </div>
        </div>
    </header>

    <!-- Categories / Sub navigation -->
    <nav class="categories-nav">
        <div class="categories-container">
            <a href="/products" class="category-tab {% if not request.args.get('category') %}active{% endif %}">All Categories</a>
            <a href="/products?category=Electronics" class="category-tab {% if request.args.get('category') == 'Electronics' %}active{% endif %}"><i class="fa-solid fa-laptop"></i> Electronics</a>
            <a href="/products?category=Fashion" class="category-tab {% if request.args.get('category') == 'Fashion' %}active{% endif %}"><i class="fa-solid fa-shirt"></i> Fashion</a>
            <a href="/products?category=Home" class="category-tab {% if request.args.get('category') == 'Home' %}active{% endif %}"><i class="fa-solid fa-couch"></i> Home</a>
            <a href="/products?category=Sports" class="category-tab {% if request.args.get('category') == 'Sports' %}active{% endif %}"><i class="fa-solid fa-basketball"></i> Sports</a>
        </div>
    </nav>

    <!-- Flashed Alert Messages -->
    <div class="alerts-container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="custom-alert {{ category }}">
                        <div>
                            {% if category == 'success' %}
                                <i class="fa-solid fa-circle-check"></i>
                            {% elif category == 'danger' %}
                                <i class="fa-solid fa-circle-xmark"></i>
                            {% elif category == 'warning' %}
                                <i class="fa-solid fa-triangle-exclamation"></i>
                            {% else %}
                                <i class="fa-solid fa-circle-info"></i>
                            {% endif %}
                            <span style="margin-left: 8px;">{{ message }}</span>
                        </div>
                        <button class="alert-close" onclick="this.parentElement.remove()">&times;</button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
    </div>

    <!-- Main Content Container -->
    <main class="content-wrapper fade-in">
        {% block content %}{% endblock %}
    </main>

    <!-- Footer Section -->
    <footer class="main-footer">
        <div class="footer-container">
            <div class="footer-col">
                <a href="/" class="brand-logo" style="margin-bottom:15px; font-size:1.6rem;">
                    <i class="fa-solid fa-bolt-lightning"></i> Scatbys
                </a>
                <p>Welcome to Scatbys, the leading high-end online shop offering top quality electronics, designer clothing, and elite home decor. Shop in confidence with our premium guarantees.</p>
                <div class="social-icons">
                    <a href="#" class="social-icon"><i class="fa-brands fa-facebook-f"></i></a>
                    <a href="#" class="social-icon"><i class="fa-brands fa-twitter"></i></a>
                    <a href="https://www.instagram.com/_scartbys_/" target="_blank" class="social-icon"><i class="fa-brands fa-instagram"></i></a>
                    <a href="#" class="social-icon"><i class="fa-brands fa-linkedin-in"></i></a>
                </div>
            </div>
            <div class="footer-col">
                <h4>Categories</h4>
                <ul class="footer-links">
                    <li><a href="/products?category=Electronics">Electronics & Gadgets</a></li>
                    <li><a href="/products?category=Fashion">Fashion & Clothing</a></li>
                    <li><a href="/products?category=Home">Home & Office Furniture</a></li>
                    <li><a href="/products?category=Sports">Sports & Outdoors</a></li>
                </ul>
            </div>
            <div class="footer-col">
                <h4>Quick Links</h4>
                <ul class="footer-links">
                    <li><a href="/products">Shop Catalog</a></li>
                    <li><a href="/#about">About Scatbys</a></li>
                    <li><a href="/#contact">Contact Support</a></li>
                    <li><a href="/admin/login">Admin Dashboard</a></li>
                </ul>
            </div>
            <div class="footer-col">
                <h4>Support Center</h4>
                <p style="margin-bottom:10px;"><i class="fa-solid fa-envelope" style="color:var(--primary-light);"></i> achuakash879@gmail.com</p>
                <p style="margin-bottom:10px;"><i class="fa-solid fa-phone" style="color:var(--primary-light);"></i> +91 9061222794</p>
                <p><i class="fa-solid fa-location-dot" style="color:var(--primary-light);"></i> Moongalar, Vandiperiyar, Idukki, Kerala, India</p>
            </div>
        </div>
        <div class="footer-bottom">
            <p>&copy; 2026 Scatbys Inc. All rights reserved. Designed to look premium and stunning.</p>
        </div>
    </footer>
</body>
</html>
"""

# =========================================================================
# PAGE TEMPLATES (INLINE HTML JINJA2)
# =========================================================================

HOME_TEMPLATE = """
{% extends "base" %}
{% block title %}Stunning E-commerce Experience{% endblock %}

{% block extra_css %}
<style>
    /* Hero section styling */
    .hero-section {
        background: linear-gradient(135deg, #0b0f19 0%, #1e1b4b 60%, #312e81 100%);
        border-radius: 24px;
        padding: 80px 8%;
        position: relative;
        overflow: hidden;
        margin-bottom: 50px;
        box-shadow: var(--shadow-lg);
        color: white;
        display: flex;
        align-items: center;
        min-height: 480px;
    }
    .hero-glow {
        position: absolute;
        width: 350px;
        height: 350px;
        background: radial-gradient(circle, rgba(79, 70, 229, 0.4) 0%, rgba(79, 70, 229, 0) 70%);
        top: -50px;
        right: -50px;
        pointer-events: none;
    }
    .hero-content {
        max-width: 650px;
        position: relative;
        z-index: 2;
    }
    .hero-content h1 {
        font-size: 3.5rem;
        line-height: 1.1;
        margin-bottom: 20px;
        color: white;
        font-weight: 800;
        letter-spacing: -1.5px;
    }
    .hero-content h1 span {
        background: linear-gradient(135deg, #a5b4fc, var(--secondary));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-content p {
        font-size: 1.1rem;
        opacity: 0.85;
        margin-bottom: 30px;
        line-height: 1.7;
    }
    .hero-btn-container {
        display: flex;
        gap: 15px;
        flex-wrap: wrap;
    }
    .btn-hero-primary {
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        color: white;
        border-radius: 99px;
        padding: 14px 32px;
        font-weight: 700;
        font-size: 1rem;
        display: inline-flex;
        align-items: center;
        gap: 10px;
        box-shadow: 0 10px 20px rgba(79, 70, 229, 0.3);
        transition: all 0.3s;
    }
    .btn-hero-primary:hover {
        transform: translateY(-2px);
        box-shadow: 0 14px 24px rgba(79, 70, 229, 0.45);
    }
    .btn-hero-secondary {
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: white;
        border-radius: 99px;
        padding: 14px 32px;
        font-weight: 700;
        font-size: 1rem;
        transition: all 0.3s;
        backdrop-filter: blur(8px);
    }
    .btn-hero-secondary:hover {
        background: rgba(255, 255, 255, 0.18);
        border-color: rgba(255, 255, 255, 0.3);
    }

    /* Featured Products Headers */
    .section-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        margin-bottom: 30px;
    }
    .section-title {
        font-size: 2rem;
        position: relative;
    }
    .section-title span {
        color: var(--primary);
    }
    .section-view-all {
        font-weight: 700;
        color: var(--primary);
        font-size: 0.95rem;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .section-view-all:hover {
        color: var(--secondary);
    }

    /* Infobar grid */
    .info-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 25px;
        margin: 60px 0;
    }
    .info-card {
        background: var(--white);
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 25px;
        box-shadow: var(--shadow-sm);
        display: flex;
        gap: 15px;
        align-items: flex-start;
        transition: all 0.3s;
    }
    .info-card:hover {
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
    }
    .info-card-icon {
        font-size: 2rem;
        color: var(--primary);
    }
    .info-card-content h4 {
        margin-bottom: 6px;
        font-size: 1.1rem;
    }
    .info-card-content p {
        font-size: 0.85rem;
        color: var(--text-muted);
    }

    /* About Section Home */
    .about-home {
        background: linear-gradient(135deg, #f8fafc, #eff6ff);
        border-radius: 20px;
        padding: 45px;
        margin: 60px 0;
        border: 1px solid #e2e8f0;
    }
    .about-content {
        max-width: 800px;
        margin: 0 auto;
        text-align: center;
    }
    .about-content h3 {
        font-size: 1.8rem;
        margin-bottom: 15px;
    }

    /* Contact Section Home */
    .contact-home {
        background: var(--white);
        border-radius: 20px;
        padding: 45px;
        border: 1px solid #e2e8f0;
        margin: 60px 0 20px 0;
        box-shadow: var(--shadow-sm);
    }
    .contact-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 40px;
        align-items: center;
    }
    .contact-info h3 {
        font-size: 1.8rem;
        margin-bottom: 15px;
    }
    .contact-info p {
        color: var(--text-muted);
        margin-bottom: 25px;
    }
    .contact-methods {
        list-style: none;
    }
    .contact-methods li {
        margin-bottom: 15px;
        display: flex;
        align-items: center;
        gap: 15px;
        font-weight: 500;
    }
    .contact-methods i {
        font-size: 1.2rem;
        color: var(--primary);
    }
</style>
{% endblock %}

{% block content %}
<!-- Hero Section -->
<section class="hero-section fade-in-up">
    <div class="hero-glow"></div>
    <div class="hero-content">
        <h1>Welcome to <br><span>Scatbys Premium</span></h1>
        <p>Step into the future of boutique e-commerce. Discover curated accessories, electronics, and fashion items styled with sleek designs and backed by our elite satisfaction guarantees.</p>
        <div class="hero-btn-container">
            <a href="/products" class="btn-hero-primary">Explore Products <i class="fa-solid fa-arrow-right"></i></a>
            <a href="/register" class="btn-hero-secondary">Create Account</a>
        </div>
    </div>
</section>

<!-- Info Grid -->
<section class="info-grid">
    <div class="info-card">
        <i class="fa-solid fa-truck-fast info-card-icon"></i>
        <div class="info-card-content">
            <h4>Location-Based Delivery</h4>
            <p>Fast, tracked delivery across India. Shipping charges calculated based on your location at checkout.</p>
        </div>
    </div>
    <div class="info-card">
        <i class="fa-solid fa-shield-halved info-card-icon" style="color: var(--secondary);"></i>
        <div class="info-card-content">
            <h4>Secure Encrypted Checkout</h4>
            <p>Your transactions are 100% safeguarded using industry standard SSL and direct payment protocols.</p>
        </div>
    </div>
    <div class="info-card">
        <i class="fa-solid fa-arrows-rotate info-card-icon" style="color: var(--accent);"></i>
        <div class="info-card-content">
            <h4>30-Day Hassle-Free Return</h4>
            <p>If you're not fully satisfied, return your item within 30 days for a swift refund.</p>
        </div>
    </div>
</section>

<!-- Featured Products Header -->
<div class="section-header">
    <h2 class="section-title">Featured <span>Designs</span></h2>
    <a href="/products" class="section-view-all">View All Products <i class="fa-solid fa-chevron-right"></i></a>
</div>

<!-- Products Grid (Featured) -->
<div class="product-grid">
    {% for product in featured_products %}
        <div class="product-card">
            <div class="product-img-wrapper">
                <span class="product-tag">{{ product.category }}</span>
                <img src="{{ product.image_url }}" alt="{{ product.name }}" class="product-img">
            </div>
            <div class="product-info">
                <h3 class="product-title">{{ product.name }}</h3>
                <p class="product-desc">{{ product.description }}</p>
                <div class="product-meta">
                    <span class="product-price">&#8377;{{ "%.2f"|format(product.price) }}</span>
                    <a href="/product/{{ product.id }}" class="btn-card">Details</a>
                </div>
            </div>
        </div>
    {% endfor %}
</div>

<!-- About Section -->
<section class="about-home" id="about">
    <div class="about-content">
        <h3>About <span>Scatbys</span></h3>
        <p style="color: var(--text-muted); line-height: 1.8;">Scatbys was founded in 2026 with a simple mission: to deliver ultra-premium, beautifully designed items straight to your door. We emphasize sleek design aesthetics, rich material selection, and modern digital customer service. We believe shopping is not just about transactions, but an entire journey of elevated design.</p>
    </div>
</section>

<!-- Contact Section -->
<section class="contact-home" id="contact">
    <div class="contact-grid">
        <div class="contact-info">
            <h3>Get In <span>Touch</span></h3>
            <p>Have questions about products, orders, or delivery? Reach out to our support team anytime.</p>
            <ul class="contact-methods">
                <li><i class="fa-solid fa-phone"></i> +91 9061222794</li>
                <li><i class="fa-solid fa-envelope"></i> achuakash879@gmail.com</li>
                <li><i class="fa-solid fa-location-dot"></i> Moongalar, Vandiperiyar, Idukki, Kerala, India</li>
                <li><a href="https://www.instagram.com/_scartbys_/" target="_blank" style="color:var(--primary); display:flex; align-items:center; gap:10px;"><i class="fa-brands fa-instagram" style="font-size:1.2rem;"></i> Follow us on Instagram</a></li>
            </ul>
        </div>
        <div>
            <form action="/contact" method="POST" class="auth-card" style="margin: 0; box-shadow: none; border-color: #e2e8f0; max-width: 100%;">
                <h4 style="margin-bottom: 20px; font-size: 1.3rem;">Send us a message</h4>
                <div class="form-group">
                    <label class="form-label">Full Name</label>
                    <input type="text" name="name" class="form-control-custom" placeholder="Your Name" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Email Address</label>
                    <input type="email" name="email" class="form-control-custom" placeholder="your@email.com" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Your Message</label>
                    <textarea name="message" class="form-control-custom" rows="4" placeholder="How can we help you?" required style="resize: none;"></textarea>
                </div>
                <button type="submit" class="btn-submit">Send Message <i class="fa-solid fa-paper-plane"></i></button>
            </form>
        </div>
    </div>
</section>
{% endblock %}
"""

REGISTER_TEMPLATE = """
{% extends "base" %}
{% block title %}Register Account{% endblock %}

{% block content %}
<div class="auth-card fade-in-up">
    <h2>Register Account</h2>
    <form action="/register" method="POST">
        <div class="form-group">
            <label for="username" class="form-label"><i class="fa-solid fa-user"></i> Username</label>
            <input type="text" id="username" name="username" class="form-control-custom" placeholder="Choose a username" required>
        </div>
        <div class="form-group">
            <label for="email" class="form-label"><i class="fa-solid fa-envelope"></i> Email Address</label>
            <input type="email" id="email" name="email" class="form-control-custom" placeholder="Enter your email" required>
        </div>
        <div class="form-group">
            <label for="password" class="form-label"><i class="fa-solid fa-lock"></i> Password</label>
            <input type="password" id="password" name="password" class="form-control-custom" placeholder="Create a strong password" required>
        </div>
        <div class="form-group">
            <label for="confirm_password" class="form-label"><i class="fa-solid fa-circle-check"></i> Confirm Password</label>
            <input type="password" id="confirm_password" name="confirm_password" class="form-control-custom" placeholder="Repeat your password" required>
        </div>
        <button type="submit" class="btn-submit">Create Account</button>
    </form>
    <div class="auth-footer">
        Already have an account? <a href="/login">Login here</a>
    </div>
</div>
{% endblock %}
"""

LOGIN_TEMPLATE = """
{% extends "base" %}
{% block title %}User Login{% endblock %}

{% block content %}
<div class="auth-card fade-in-up">
    <h2>Welcome Back</h2>
    <form action="/login" method="POST">
        <div class="form-group">
            <label for="username" class="form-label"><i class="fa-solid fa-user"></i> Username</label>
            <input type="text" id="username" name="username" class="form-control-custom" placeholder="Enter username" required>
        </div>
        <div class="form-group">
            <label for="password" class="form-label"><i class="fa-solid fa-lock"></i> Password</label>
            <input type="password" id="password" name="password" class="form-control-custom" placeholder="Enter password" required>
        </div>
        <button type="submit" class="btn-submit">Secure Login</button>
    </form>
    <div class="auth-footer">
        Don't have an account? <a href="/register">Register here</a><br>
        <div style="margin-top: 10px; border-top: 1px solid #cbd5e1; padding-top: 10px; font-size: 0.8rem;">
            Store Manager? <a href="/admin/login" style="color: var(--warning); font-weight: 700;">Admin Login Portal</a>
        </div>
    </div>
</div>
{% endblock %}
"""

PRODUCTS_TEMPLATE = """
{% extends "base" %}
{% block title %}Our Premium Collection{% endblock %}

{% block extra_css %}
<style>
    .catalog-header {
        margin-bottom: 30px;
        text-align: center;
        padding: 30px 0 20px 0;
    }
    .catalog-header h2 {
        font-size: 2.5rem;
        margin-bottom: 10px;
        background: linear-gradient(135deg, var(--dark), var(--primary));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .catalog-header p {
        color: var(--text-muted);
        font-size: 1rem;
        max-width: 600px;
        margin: 0 auto;
    }
    .filter-actions-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 20px;
        margin-bottom: 35px;
        background: var(--white);
        padding: 16px 24px;
        border-radius: 14px;
        border: 1px solid #e2e8f0;
        box-shadow: var(--shadow-sm);
    }
    .filter-count {
        font-size: 0.9rem;
        font-weight: 600;
        color: var(--dark-light);
    }
    .filter-search-box {
        position: relative;
        width: 100%;
        max-width: 320px;
    }
    /* Category cards layout */
    .category-section {
        margin-bottom: 50px;
    }
    .category-section-title {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 20px;
        padding-bottom: 12px;
        border-bottom: 2px solid #e2e8f0;
    }
    .category-section-title h3 {
        font-size: 1.4rem;
        margin: 0;
    }
    .category-icon-badge {
        width: 38px;
        height: 38px;
        border-radius: 10px;
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 1rem;
    }
    .cat-count-badge {
        background: #eef2ff;
        color: var(--primary);
        padding: 3px 10px;
        border-radius: 99px;
        font-size: 0.75rem;
        font-weight: 700;
        margin-left: auto;
    }
    /* Mosaic / Masonry style for products */
    .products-mosaic {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
        gap: 22px;
    }
    .mosaic-card {
        background: var(--white);
        border-radius: 18px;
        border: 1px solid #e8edf5;
        overflow: hidden;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        transition: all 0.3s cubic-bezier(0.16,1,0.3,1);
        display: flex;
        flex-direction: column;
    }
    .mosaic-card:hover {
        transform: translateY(-6px);
        box-shadow: 0 16px 40px rgba(79,70,229,0.14);
        border-color: var(--primary-light);
    }
    .mosaic-img-wrap {
        position: relative;
        background: linear-gradient(135deg, #f0f4ff, #e8f4ff);
        overflow: hidden;
        height: 200px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .mosaic-img-wrap img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        transition: transform 0.4s ease;
    }
    .mosaic-card:hover .mosaic-img-wrap img {
        transform: scale(1.06);
    }
    .mosaic-cat-tag {
        position: absolute;
        top: 12px;
        left: 12px;
        background: rgba(255,255,255,0.92);
        color: var(--primary);
        font-size: 0.7rem;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 99px;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        backdrop-filter: blur(4px);
    }
    .mosaic-stock-tag {
        position: absolute;
        top: 12px;
        right: 12px;
        font-size: 0.7rem;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 99px;
    }
    .mosaic-body {
        padding: 18px;
        flex-grow: 1;
        display: flex;
        flex-direction: column;
    }
    .mosaic-title {
        font-size: 0.98rem;
        font-weight: 700;
        color: var(--dark);
        margin-bottom: 6px;
        line-height: 1.3;
    }
    .mosaic-desc {
        font-size: 0.8rem;
        color: var(--dark-light);
        opacity: 0.75;
        line-height: 1.6;
        flex-grow: 1;
        margin-bottom: 14px;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .mosaic-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        border-top: 1px solid #f1f5f9;
        padding-top: 12px;
    }
    .mosaic-price {
        font-size: 1.2rem;
        font-weight: 800;
        color: var(--primary);
    }
    .mosaic-actions {
        display: flex;
        gap: 8px;
    }
    .btn-mosaic-view {
        width: 34px;
        height: 34px;
        border-radius: 8px;
        background: #f1f5f9;
        color: var(--dark);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.85rem;
        transition: all 0.2s;
    }
    .btn-mosaic-view:hover { background: #e2e8f0; }
    .btn-mosaic-order {
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        color: white;
        border-radius: 8px;
        padding: 6px 14px;
        font-size: 0.78rem;
        font-weight: 700;
        transition: all 0.2s;
        box-shadow: 0 3px 8px rgba(79,70,229,0.25);
    }
    .btn-mosaic-order:hover {
        transform: translateY(-1px);
        box-shadow: 0 5px 14px rgba(79,70,229,0.35);
    }
</style>
{% endblock %}

{% block content %}
<div class="catalog-header fade-in-up">
    <h2>Our Premium Collection</h2>
    <p>Browse our hand-selected line of ultra-premium goods. Filter by category, search keywords, and order securely.</p>
</div>

<!-- Search & Filters Info Bar -->
<div class="filter-actions-bar fade-in-up" style="animation-delay: 0.1s;">
    <div class="filter-count">
        <i class="fa-solid fa-filter"></i> Showing <span style="color: var(--primary);">{{ products|length }}</span> products
        {% if category_filter %}
            in <span class="badge-status processing" style="font-size: 0.75rem; margin-left: 5px;">{{ category_filter }}</span>
        {% endif %}
        {% if search_query %}
            matching <span class="badge-status pending" style="font-size: 0.75rem; margin-left: 5px;">&quot;{{ search_query }}&quot;</span>
        {% endif %}
    </div>
    <div class="filter-search-box">
        <form action="/products" method="GET" style="display: flex; gap: 10px;">
            {% if category_filter %}
                <input type="hidden" name="category" value="{{ category_filter }}">
            {% endif %}
            <input type="text" name="q" class="form-control-custom" placeholder="Search catalog..." value="{{ search_query }}" style="padding: 8px 14px;">
            <button type="submit" class="btn-nav-solid" style="padding: 8px 16px; border: none; cursor: pointer;"><i class="fa-solid fa-search"></i></button>
        </form>
    </div>
</div>

{% if products %}
    {% set categories = products | map(attribute='category') | unique | list %}
    {% for cat in categories %}
        {% set cat_products = products | selectattr('category', 'equalto', cat) | list %}
        <div class="category-section fade-in-up">
            <div class="category-section-title">
                <div class="category-icon-badge">
                    {% if cat == 'Electronics' %}<i class="fa-solid fa-laptop"></i>
                    {% elif cat == 'Fashion' %}<i class="fa-solid fa-shirt"></i>
                    {% elif cat == 'Home' %}<i class="fa-solid fa-couch"></i>
                    {% elif cat == 'Sports' %}<i class="fa-solid fa-basketball"></i>
                    {% else %}<i class="fa-solid fa-box"></i>{% endif %}
                </div>
                <h3>{{ cat }}</h3>
                <span class="cat-count-badge">{{ cat_products | length }} items</span>
            </div>
            <div class="products-mosaic">
                {% for product in cat_products %}
                    <div class="mosaic-card">
                        <div class="mosaic-img-wrap">
                            <span class="mosaic-cat-tag">{{ product.category }}</span>
                            {% if product.stock_quantity <= 5 and product.stock_quantity > 0 %}
                                <span class="mosaic-stock-tag" style="background:#fff7ed; color:var(--warning);">Low Stock</span>
                            {% elif product.stock_quantity == 0 %}
                                <span class="mosaic-stock-tag" style="background:#fef2f2; color:var(--danger);">Sold Out</span>
                            {% else %}
                                <span class="mosaic-stock-tag" style="background:#ecfdf5; color:var(--success);">In Stock</span>
                            {% endif %}
                            <img src="{{ product.image_url }}" alt="{{ product.name }}">
                        </div>
                        <div class="mosaic-body">
                            <div class="mosaic-title">{{ product.name }}</div>
                            <p class="mosaic-desc">{{ product.description }}</p>
                            <div class="mosaic-footer">
                                <span class="mosaic-price">&#8377;{{ "%.2f"|format(product.price) }}</span>
                                <div class="mosaic-actions">
                                    <a href="/product/{{ product.id }}" class="btn-mosaic-view" title="View Details"><i class="fa-solid fa-eye"></i></a>
                                    {% if product.stock_quantity > 0 %}
                                        {% if session.get('user_id') %}
                                            <a href="/order/{{ product.id }}" class="btn-mosaic-order"><i class="fa-solid fa-cart-shopping"></i> Order</a>
                                        {% else %}
                                            <a href="/login" class="btn-mosaic-order" onclick="alert('Please log in first!');"><i class="fa-solid fa-cart-shopping"></i> Order</a>
                                        {% endif %}
                                    {% else %}
                                        <span class="btn-mosaic-order" style="opacity:0.5; cursor:not-allowed;">Sold Out</span>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                    </div>
                {% endfor %}
            </div>
        </div>
    {% endfor %}
{% else %}
    <div class="fade-in-up" style="text-align: center; padding: 50px 0; background: var(--white); border-radius: 16px; border: 1px solid #e2e8f0;">
        <i class="fa-regular fa-folder-open" style="font-size: 3rem; color: var(--text-muted); margin-bottom: 15px;"></i>
        <h3>No Products Found</h3>
        <p style="color: var(--text-muted); margin-top: 5px;">We couldn't find any products fitting your filters. Try clearing your search parameters.</p>
        <a href="/products" class="btn-nav-solid" style="margin-top: 20px; display: inline-block;">Clear Filters</a>
    </div>
{% endif %}
{% endblock %}
"""

PRODUCT_DETAIL_TEMPLATE = """
{% extends "base" %}
{% block title %}{{ product.name }}{% endblock %}

{% block extra_css %}
<style>
    .detail-card {
        background: var(--white);
        border-radius: 20px;
        border: 1px solid #e2e8f0;
        box-shadow: var(--shadow-lg);
        overflow: hidden;
        display: grid;
        grid-template-columns: 1fr 1fr;
        margin-top: 20px;
    }
    .detail-img-section {
        background: #f8fafc;
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 40px;
    }
    .detail-img {
        width: 100%;
        max-height: 450px;
        object-fit: cover;
        border-radius: 14px;
        box-shadow: var(--shadow-md);
    }
    .detail-info-section {
        padding: 50px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .detail-category {
        color: var(--primary);
        font-weight: 700;
        text-transform: uppercase;
        font-size: 0.8rem;
        letter-spacing: 1px;
        margin-bottom: 10px;
    }
    .detail-title {
        font-size: 2.2rem;
        line-height: 1.2;
        margin-bottom: 15px;
    }
    .detail-price-box {
        font-size: 2rem;
        font-weight: 800;
        color: var(--dark);
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 15px;
    }
    .detail-desc {
        color: var(--dark-light);
        opacity: 0.9;
        line-height: 1.8;
        margin-bottom: 25px;
    }
    .detail-meta-box {
        background: #f1f5f9;
        border-radius: 12px;
        padding: 15px 20px;
        margin-bottom: 30px;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .meta-row {
        display: flex;
        justify-content: space-between;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .btn-detail-order {
        width: 100%;
        padding: 14px;
        border-radius: 10px;
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        color: white;
        text-align: center;
        font-weight: 700;
        font-size: 1.05rem;
        box-shadow: 0 4px 15px rgba(79, 70, 229, 0.3);
        transition: all 0.2s;
    }
    .btn-detail-order:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(79, 70, 229, 0.4);
    }
    @media (max-width: 992px) {
        .detail-card {
            grid-template-columns: 1fr;
        }
        .detail-info-section {
            padding: 30px;
        }
    }
</style>
{% endblock %}

{% block content %}
<div style="margin-bottom: 20px;">
    <a href="/products" style="font-weight:600; color:var(--primary);"><i class="fa-solid fa-arrow-left"></i> Back to Shop</a>
</div>

<div class="detail-card fade-in-up">
    <!-- Image Column -->
    <div class="detail-img-section">
        <img src="{{ product.image_url }}" alt="{{ product.name }}" class="detail-img">
    </div>
    <!-- Info Column -->
    <div class="detail-info-section">
        <span class="detail-category"><i class="fa-solid fa-tags"></i> {{ product.category }}</span>
        <h2 class="detail-title">{{ product.name }}</h2>
        
        <div class="detail-price-box">
            <span>&#8377;{{ "%.2f"|format(product.price) }}</span>
            {% if product.stock_quantity > 0 %}
                <span class="badge-status delivered" style="font-size:0.8rem; font-weight:700;"><i class="fa-solid fa-circle-check"></i> In Stock</span>
            {% else %}
                <span class="badge-status danger" style="font-size:0.8rem; font-weight:700;"><i class="fa-solid fa-circle-xmark"></i> Out of Stock</span>
            {% endif %}
        </div>
        
        <p class="detail-desc">{{ product.description }}</p>
        
        <div class="detail-meta-box">
            <div class="meta-row">
                <span style="color: var(--text-muted);">Stock Remaining:</span>
                <span>{{ product.stock_quantity }} units</span>
            </div>
            <div class="meta-row" style="border-top: 1px solid #cbd5e1; padding-top: 8px;">
                <span style="color: var(--text-muted);"><i class="fa-solid fa-users"></i> Client Purchases:</span>
                <span style="color: var(--primary);">{{ order_count }} customer(s) ordered this product!</span>
            </div>
        </div>

        {% if product.stock_quantity > 0 %}
            {% if session.get('user_id') %}
                <a href="/order/{{ product.id }}" class="btn-detail-order">Order Now <i class="fa-solid fa-cart-shopping"></i></a>
            {% else %}
                <a href="/login" class="btn-detail-order" style="opacity: 0.6;" onclick="alert('Please login to place an order!');">Log In to Order</a>
            {% endif %}
        {% else %}
            <button class="btn-detail-order" style="background:#cbd5e1; box-shadow:none; cursor:not-allowed;" disabled>Temporarily Unavailable</button>
        {% endif %}
    </div>
</div>
{% endblock %}
"""

ORDER_TEMPLATE = """
{% extends "base" %}
{% block title %}Checkout Order{% endblock %}

{% block extra_css %}
<style>
    .order-checkout-grid {
        display: grid;
        grid-template-columns: 1.2fr 0.8fr;
        gap: 30px;
        margin-top: 20px;
    }
    .checkout-form-card {
        background: var(--white);
        border-radius: 20px;
        border: 1px solid #e2e8f0;
        padding: 35px;
        box-shadow: var(--shadow-lg);
    }
    .summary-card {
        background: #f8fafc;
        border-radius: 20px;
        border: 1px solid #e2e8f0;
        padding: 30px;
        height: fit-content;
        position: sticky;
        top: 100px;
    }
    .summary-title {
        font-size: 1.3rem;
        margin-bottom: 20px;
        border-bottom: 1.5px solid #cbd5e1;
        padding-bottom: 10px;
    }
    .summary-item-img {
        width: 70px;
        height: 70px;
        object-fit: cover;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
    }
    .summary-product-row {
        display: flex;
        gap: 15px;
        align-items: center;
        margin-bottom: 20px;
    }
    .price-summary-box {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin-top: 20px;
        border-top: 1px solid #cbd5e1;
        padding-top: 15px;
    }
    .price-row {
        display: flex;
        justify-content: space-between;
        font-weight: 500;
    }
    .price-row.total {
        font-size: 1.3rem;
        font-weight: 800;
        color: var(--primary);
        border-top: 1px dashed #cbd5e1;
        padding-top: 10px;
        margin-top: 5px;
    }
    @media (max-width: 992px) {
        .order-checkout-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
{% endblock %}

{% block content %}
<div style="margin-bottom: 20px;">
    <a href="/product/{{ product.id }}" style="font-weight:600; color:var(--primary);"><i class="fa-solid fa-arrow-left"></i> Back to details</a>
</div>

<h2>Secure Checkout</h2>

<div class="order-checkout-grid fade-in-up">
    <!-- Billing details card -->
    <div class="checkout-form-card">
        <h4 style="margin-bottom: 20px; font-size:1.25rem;"><i class="fa-solid fa-truck"></i> Shipping Information</h4>
        <form action="/order/{{ product.id }}" method="POST" id="checkout-form" enctype="multipart/form-data">
            <div class="form-group">
                <label class="form-label">Full Name</label>
                <input type="text" class="form-control-custom" value="{{ session.get('username') }}" required readonly>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;" class="form-group">
                <div>
                    <label class="form-label">Quantity</label>
                    <input type="number" id="order-quantity" name="quantity" class="form-control-custom" value="1" min="1" max="{{ product.stock_quantity }}" required>
                    <small style="color:var(--text-muted);">Stock limit: {{ product.stock_quantity }}</small>
                </div>
                <div>
                    <label class="form-label">Payment Method</label>
                    <select class="form-control-custom">
                        <option>Credit Card (Mock)</option>
                        <option>PayPal (Mock)</option>
                        <option>Scatbys Wallet</option>
                    </select>
                </div>
            </div>

            <h4 style="margin-top: 30px; margin-bottom: 20px; font-size:1.25rem;"><i class="fa-solid fa-credit-card"></i> Payment Details</h4>
            <div class="form-group">
                <label class="form-label">Cardholder Name</label>
                <input type="text" class="form-control-custom" placeholder="John Doe" required>
            </div>
            <div class="form-group">
                <label class="form-label">Card Number</label>
                <input type="text" class="form-control-custom" placeholder="1111 - 2222 - 3333 - 4444" required>
            </div>
            
            <button type="submit" class="btn-submit" style="margin-top: 15px;"><i class="fa-solid fa-circle-check"></i> Place Secure Order</button>
        </form>
    </div>

    <!-- Summary Panel -->
    <div class="summary-card">
        <h3 class="summary-title">Order Summary</h3>
        <div class="summary-product-row">
            <img src="{{ product.image_url }}" alt="{{ product.name }}" class="summary-item-img">
            <div>
                <h4 style="font-size:0.95rem; line-height:1.2; margin-bottom:4px;">{{ product.name }}</h4>
                <p style="font-size:0.8rem; color:var(--text-muted);">Category: {{ product.category }}</p>
            </div>
        </div>

        <div class="price-summary-box">
            <div class="price-row">
                <span>Price per unit:</span>
                <span>&#8377;{{ "%.2f"|format(product.price) }}</span>
            </div>
            <div class="price-row">
                <span>Quantity:</span>
                <span id="summary-quantity">1</span>
            </div>
            <div class="price-row">
                <span>Delivery Location:</span>
                <select id="delivery-state" class="form-control-custom" name="delivery_state" style="padding:5px 10px; font-size:0.82rem; width:auto;">
                    <option value="40">Kerala (&#8377;40)</option>
                    <option value="60">Tamil Nadu (&#8377;60)</option>
                    <option value="60">Karnataka (&#8377;60)</option>
                    <option value="80">Andhra Pradesh (&#8377;80)</option>
                    <option value="80">Telangana (&#8377;80)</option>
                    <option value="100">Maharashtra (&#8377;100)</option>
                    <option value="100">Delhi (&#8377;100)</option>
                    <option value="120">Rajasthan (&#8377;120)</option>
                    <option value="120">Uttar Pradesh (&#8377;120)</option>
                    <option value="150">West Bengal (&#8377;150)</option>
                    <option value="150">Other States (&#8377;150)</option>
                </select>
            </div>
            <div class="price-row">
                <span>Delivery Charge:</span>
                <span id="shipping-fee" style="color:var(--warning); font-weight:700;">&#8377;40</span>
            </div>
            <div class="price-row total">
                <span>Total Amount:</span>
                <span id="summary-total">&#8377;{{ "%.2f"|format(product.price + 40) }}</span>
            </div>
        </div>
    </div>
</div>

<script>
    const price = {{ product.price }};
    const qtyInput = document.getElementById('order-quantity');
    const summaryQty = document.getElementById('summary-quantity');
    const summaryTotal = document.getElementById('summary-total');
    const shippingFeeEl = document.getElementById('shipping-fee');
    const stateSelect = document.getElementById('delivery-state');

    function updateSummary() {
        const qty = parseInt(qtyInput.value) || 1;
        summaryQty.textContent = qty;
        const shipping = parseInt(stateSelect.value) || 40;
        shippingFeeEl.textContent = '\u20B9' + shipping.toFixed(2);
        const total = (price * qty) + shipping;
        summaryTotal.textContent = '\u20B9' + total.toFixed(2);
    }

    qtyInput.addEventListener('input', updateSummary);
    stateSelect.addEventListener('change', updateSummary);
    updateSummary();
</script>
{% endblock %}
"""

DASHBOARD_TEMPLATE = """
{% extends "base" %}
{% block title %}User Dashboard{% endblock %}

{% block content %}
<div style="margin-bottom: 25px;">
    <h2>Client Dashboard</h2>
    <p style="color:var(--text-muted);">View and trace your purchase order history below.</p>
</div>

<!-- User Order List Table -->
{% if orders %}
    <div class="table-container fade-in-up">
        <table class="custom-table">
            <thead>
                <tr>
                    <th>Order ID</th>
                    <th>Product</th>
                    <th>Quantity</th>
                    <th>Total Price</th>
                    <th>Order Date</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {% for order in orders %}
                    <tr>
                        <td style="font-weight: 700; color: var(--primary);">#SCB-{{ order.id }}</td>
                        <td>
                            <div style="display:flex; align-items:center; gap:12px;">
                                <img src="{{ order.product.image_url }}" alt="" style="width: 40px; height: 40px; object-fit: cover; border-radius: 6px;">
                                <span style="font-weight:600;">{{ order.product.name }}</span>
                            </div>
                        </td>
                        <td>{{ order.quantity }}</td>
                        <td style="font-weight: 700;">&#8377;{{ "%.2f"|format(order.total_price) }}</td>
                        <td>{{ order.ordered_at.strftime('%b %d, %Y at %H:%M') }}</td>
                        <td>
                            {% if order.status == 'Pending' %}
                                <span class="badge-status pending"><i class="fa-regular fa-clock"></i> {{ order.status }}</span>
                            {% elif order.status == 'Processing' %}
                                <span class="badge-status processing"><i class="fa-solid fa-gears"></i> {{ order.status }}</span>
                            {% elif order.status == 'Shipped' %}
                                <span class="badge-status shipped"><i class="fa-solid fa-truck-ramp-box"></i> {{ order.status }}</span>
                            {% else %}
                                <span class="badge-status delivered"><i class="fa-solid fa-box-open"></i> {{ order.status }}</span>
                            {% endif %}
                        </td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
{% else %}
    <div class="fade-in-up" style="text-align: center; padding: 60px 0; background: var(--white); border-radius: 16px; border: 1px solid #e2e8f0; margin-top: 20px;">
        <i class="fa-solid fa-receipt" style="font-size: 3.5rem; color: var(--text-muted); opacity: 0.5; margin-bottom: 20px;"></i>
        <h3>No Orders Placed Yet</h3>
        <p style="color:var(--text-muted); margin-top: 5px;">Your dashboard is clean. Place your first order today and track it here!</p>
        <a href="/products" class="btn-nav-solid" style="margin-top: 20px; display:inline-block;">Go to Store</a>
    </div>
{% endif %}
{% endblock %}
"""

# =========================================================================
# ADMIN TEMPLATES (INLINE HTML JINJA2)
# =========================================================================

ADMIN_LOGIN_TEMPLATE = """
{% extends "base" %}
{% block title %}Admin Login{% endblock %}

{% block content %}
<div class="auth-card fade-in-up" style="border-top: 4px solid var(--warning);">
    <h2 style="display:flex; justify-content:center; align-items:center; gap:8px;">
        <i class="fa-solid fa-user-shield" style="color:var(--warning);"></i> Admin Access
    </h2>
    <p style="text-align:center; font-size:0.85rem; color:var(--text-muted); margin-bottom: 20px;">
        Authentication portal for Scatbys store administration.
    </p>
    <form action="/admin/login" method="POST">
        <div class="form-group">
            <label for="username" class="form-label">Admin Username</label>
            <input type="text" id="username" name="username" class="form-control-custom" placeholder="Enter admin username" required>
        </div>
        <div class="form-group">
            <label for="password" class="form-label">Password</label>
            <input type="password" id="password" name="password" class="form-control-custom" placeholder="Enter admin password" required>
        </div>
        <button type="submit" class="btn-submit" style="background:linear-gradient(135deg, var(--dark), #1e293b);"><i class="fa-solid fa-key"></i> Authenticate</button>
    </form>
</div>
{% endblock %}
"""

ADMIN_DASHBOARD_TEMPLATE = """
{% extends "base" %}
{% block title %}Admin Portal Overview{% endblock %}

{% block content %}
<div style="margin-bottom: 25px;">
    <h2>Admin Dashboard Overview</h2>
    <p style="color:var(--text-muted);">Real-time statistics and overview parameters of the Scatbys ecosystem.</p>
</div>

<!-- Stats Grid -->
<div class="stats-grid fade-in-up">
    <div class="stat-card">
        <div class="stat-icon"><i class="fa-solid fa-boxes-stacked"></i></div>
        <div>
            <div class="stat-value">{{ total_products }}</div>
            <div class="stat-label">Total Products</div>
        </div>
    </div>
    <div class="stat-card">
        <div class="stat-icon"><i class="fa-solid fa-receipt"></i></div>
        <div>
            <div class="stat-value">{{ total_orders }}</div>
            <div class="stat-label">Total Orders</div>
        </div>
    </div>
    <div class="stat-card">
        <div class="stat-icon"><i class="fa-solid fa-users"></i></div>
        <div>
            <div class="stat-value">{{ total_users }}</div>
            <div class="stat-label">Registered Users</div>
        </div>
    </div>
    <div class="stat-card">
        <div class="stat-icon"><i class="fa-solid fa-circle-dollar-to-slot"></i></div>
        <div>
            <div class="stat-value">&#8377;{{ "%.2f"|format(total_revenue) }}</div>
            <div class="stat-label">Gross Revenue</div>
        </div>
    </div>
</div>

<div class="stats-grid fade-in-up" style="grid-template-columns: 1fr 1fr; gap: 30px; animation-delay: 0.1s;">
    <!-- Recent Orders Section -->
    <div class="checkout-form-card" style="padding: 25px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 15px;">
            <h4 style="font-size:1.15rem;"><i class="fa-solid fa-clock-rotate-left"></i> Recent Activity</h4>
            <a href="/admin/orders" class="category-tab" style="font-size:0.75rem;">View Orders</a>
        </div>
        {% if recent_orders %}
            <ul style="list-style:none;">
                {% for order in recent_orders %}
                    <li style="display:flex; justify-content:space-between; align-items:center; padding:12px 0; border-bottom: 1px solid #f1f5f9;">
                        <div>
                            <p style="font-weight:600; font-size:0.9rem;">#SCB-{{ order.id }} - {{ order.product.name }}</p>
                            <small style="color:var(--text-muted);">User: {{ order.user.username }} | Qty: {{ order.quantity }}</small>
                        </div>
                        <span style="font-weight:700; font-size:0.9rem;">&#8377;{{ "%.2f"|format(order.total_price) }}</span>
                    </li>
                {% endfor %}
            </ul>
        {% else %}
            <p style="color:var(--text-muted); font-size:0.85rem; padding: 20px 0; text-align:center;">No recent order activity.</p>
        {% endif %}
    </div>

    <!-- Quick action shortcuts -->
    <div class="checkout-form-card" style="padding: 25px;">
        <h4 style="font-size:1.15rem; margin-bottom: 15px;"><i class="fa-solid fa-screwdriver-wrench"></i> Administrative Operations</h4>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 15px;">
            <a href="/admin/add-product" class="btn-submit" style="display:flex; flex-direction:column; justify-content:center; align-items:center; gap:8px; height:100px; padding:0; border-radius:12px;">
                <i class="fa-solid fa-plus-circle" style="font-size:1.6rem;"></i>
                <span style="font-size:0.8rem;">Add Product</span>
            </a>
            <a href="/admin/products" class="btn-submit" style="display:flex; flex-direction:column; justify-content:center; align-items:center; gap:8px; height:100px; padding:0; border-radius:12px; background:linear-gradient(135deg, var(--dark), var(--dark-light));">
                <i class="fa-solid fa-sliders" style="font-size:1.6rem;"></i>
                <span style="font-size:0.8rem;">Manage Catalog</span>
            </a>
        </div>
    </div>
</div>

<!-- Customer Messages Section -->
<div class="stats-grid fade-in-up" style="grid-template-columns: 1fr; animation-delay: 0.2s; margin-top: 0;">
    <div class="checkout-form-card" style="padding: 25px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 18px;">
            <h4 style="font-size:1.15rem;"><i class="fa-solid fa-envelope-open-text" style="color:var(--accent);"></i> Customer Messages</h4>
            <span style="background:#fdf4ff; color:var(--accent); padding: 4px 12px; border-radius:99px; font-size:0.75rem; font-weight:700;">{{ messages|length }} message(s)</span>
        </div>
        {% if messages %}
            <div style="display:flex; flex-direction:column; gap:14px;">
            {% for msg in messages %}
                <div style="background: {% if not msg.is_read %}#fdf4ff{% else %}#f8fafc{% endif %}; border-radius:12px; padding:16px 20px; border-left: 4px solid {% if not msg.is_read %}var(--accent){% else %}#cbd5e1{% endif %};">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <div style="width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,var(--primary),var(--accent));display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:0.9rem;">{{ msg.name[0]|upper }}</div>
                            <div>
                                <p style="font-weight:700; font-size:0.9rem; margin:0;">{{ msg.name }}</p>
                                <small style="color:var(--text-muted);">{{ msg.email }}</small>
                            </div>
                        </div>
                        <div style="display:flex; align-items:center; gap:10px;">
                            <small style="color:var(--text-muted);">{{ msg.sent_at.strftime('%b %d, %Y %H:%M') }}</small>
                            {% if not msg.is_read %}<span style="background:var(--accent);color:white;font-size:0.65rem;padding:2px 8px;border-radius:99px;font-weight:700;">NEW</span>{% endif %}
                            <a href="/admin/mark-message-read/{{ msg.id }}" style="background:#eef2ff;color:var(--primary);border-radius:6px;padding:4px 10px;font-size:0.75rem;font-weight:600;"><i class="fa-solid fa-check"></i> Mark Read</a>
                        </div>
                    </div>
                    <p style="font-size:0.88rem; color:var(--dark-light); line-height:1.7; margin:0; padding-left: 46px;">{{ msg.message }}</p>
                </div>
            {% endfor %}
            </div>
        {% else %}
            <div style="text-align:center; padding: 30px 0; color: var(--text-muted);">
                <i class="fa-solid fa-inbox" style="font-size:2.5rem; opacity:0.4; margin-bottom:10px;"></i>
                <p style="font-size:0.9rem;">No customer messages yet.</p>
            </div>
        {% endif %}
    </div>
</div>
{% endblock %}
"""

ADMIN_ADD_PRODUCT_TEMPLATE = """
{% extends "base" %}
{% block title %}{% if edit_mode %}Modify Product{% else %}Add Product{% endif %}{% endblock %}

{% block content %}
<div class="auth-card fade-in-up" style="max-width: 600px;">
    <h2>{% if edit_mode %}<i class="fa-solid fa-pen-to-square"></i> Modify Product{% else %}<i class="fa-solid fa-square-plus"></i> Add Product{% endif %}</h2>
    <p style="text-align:center; font-size:0.85rem; color:var(--text-muted); margin-bottom: 25px;">
        Define details and attributes below to publish to the public storefront catalog.
    </p>
    
    <form action="{% if edit_mode %}/admin/edit-product/{{ product.id }}{% else %}/admin/add-product{% endif %}" method="POST">
        <div class="form-group">
            <label for="name" class="form-label">Product Name</label>
            <input type="text" id="name" name="name" class="form-control-custom" placeholder="e.g. Mechanical Keyboard" value="{{ product.name if product else '' }}" required>
        </div>
        
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;" class="form-group">
            <div>
                <label for="price" class="form-label">Unit Price (&#8377;)</label>
                <input type="number" id="price" name="price" class="form-control-custom" step="0.01" min="0" placeholder="e.g. 199.99" value="{{ product.price if product else '' }}" required>
            </div>
            <div>
                <label for="stock_quantity" class="form-label">Initial Stock Quantity</label>
                <input type="number" id="stock_quantity" name="stock_quantity" class="form-control-custom" min="0" placeholder="e.g. 25" value="{{ product.stock_quantity if product else '' }}" required>
            </div>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;" class="form-group">
            <div>
                <label for="category" class="form-label">Category</label>
                <select id="category" name="category" class="form-control-custom" required>
                    <option value="Electronics" {% if product and product.category == 'Electronics' %}selected{% endif %}>Electronics</option>
                    <option value="Fashion" {% if product and product.category == 'Fashion' %}selected{% endif %}>Fashion</option>
                    <option value="Home" {% if product and product.category == 'Home' %}selected{% endif %}>Home</option>
                    <option value="Sports" {% if product and product.category == 'Sports' %}selected{% endif %}>Sports</option>
                </select>
            </div>
            <div>
                <label for="image_url" class="form-label">Product Image URL</label>
                <input type="text" id="image_url" name="image_url" class="form-control-custom" placeholder="e.g. /static/images/custom.png" value="{{ product.image_url if product else '' }}" required>
            </div>
        </div>

        <div class="form-group">
            <label for="description" class="form-label">Product Description</label>
            <textarea id="description" name="description" class="form-control-custom" rows="5" placeholder="Provide a premium, comprehensive description of the item..." required style="resize:none;">{{ product.description if product else '' }}</textarea>
        </div>

        <button type="submit" class="btn-submit">
            {% if edit_mode %}<i class="fa-solid fa-save"></i> Save Product{% else %}<i class="fa-solid fa-upload"></i> Publish to Store{% endif %}
        </button>
    </form>
</div>
{% endblock %}
"""

ADMIN_PRODUCTS_TEMPLATE = """
{% extends "base" %}
{% block title %}Manage Catalog{% endblock %}

{% block content %}
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 25px;">
    <div>
        <h2>Storefront Catalog</h2>
        <p style="color:var(--text-muted);">Manage details, check inventory counts, and review purchases.</p>
    </div>
    <a href="/admin/add-product" class="btn-nav-solid"><i class="fa-solid fa-plus"></i> Add Product</a>
</div>

{% if products %}
    <div class="table-container fade-in-up">
        <table class="custom-table">
            <thead>
                <tr>
                    <th>Product Details</th>
                    <th>Category</th>
                    <th>Price</th>
                    <th>Stock Level</th>
                    <th>Total Orders</th>
                    <th style="text-align:right;">Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for item in products %}
                    <tr>
                        <td>
                            <div style="display:flex; align-items:center; gap:12px;">
                                <img src="{{ item.product.image_url }}" alt="" style="width: 45px; height: 45px; object-fit: cover; border-radius: 8px; border:1px solid #e2e8f0;">
                                <div>
                                    <span style="font-weight:700; display:block;">{{ item.product.name }}</span>
                                    <small style="color:var(--text-muted); font-size:0.75rem;">ID: #PROD-{{ item.product.id }}</small>
                                </div>
                            </div>
                        </td>
                        <td><span class="badge-status processing">{{ item.product.category }}</span></td>
                        <td style="font-weight:700; color:var(--primary);">&#8377;{{ "%.2f"|format(item.product.price) }}</td>
                        <td>
                            {% if item.product.stock_quantity <= 5 %}
                                <span style="color:var(--danger); font-weight:700;"><i class="fa-solid fa-triangle-exclamation"></i> {{ item.product.stock_quantity }} (Low)</span>
                            {% else %}
                                <span style="font-weight:600;">{{ item.product.stock_quantity }} units</span>
                            {% endif %}
                        </td>
                        <td style="font-weight:700;">{{ item.order_count }} orders</td>
                        <td style="text-align:right;">
                            <a href="/admin/edit-product/{{ item.product.id }}" class="btn-card" style="background:#f1f5f9; color:var(--dark); font-size:0.8rem; padding: 6px 12px; margin-right:5px;"><i class="fa-solid fa-pen-to-square"></i> Edit</a>
                            <a href="/admin/delete-product/{{ item.product.id }}" class="btn-card" style="background:var(--danger); color:white; font-size:0.8rem; padding: 6px 12px;" onclick="return confirm('Are you sure you want to delete this product? All related order records will be affected.');"><i class="fa-solid fa-trash-can"></i></a>
                        </td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
{% else %}
    <div class="fade-in-up" style="text-align: center; padding: 60px 0; background: var(--white); border-radius: 16px; border: 1px solid #e2e8f0;">
        <i class="fa-solid fa-boxes-packing" style="font-size: 3rem; color: var(--text-muted); margin-bottom: 15px;"></i>
        <h3>No Products in Catalog</h3>
        <p style="color: var(--text-muted); margin-top: 5px;">Your storefront inventory is currently empty.</p>
        <a href="/admin/add-product" class="btn-nav-solid" style="margin-top: 20px; display: inline-block;">Add First Product</a>
    </div>
{% endif %}
{% endblock %}
"""

ADMIN_ORDERS_TEMPLATE = """
{% extends "base" %}
{% block title %}Manage Orders{% endblock %}

{% block content %}
<div style="margin-bottom: 25px;">
    <h2>Store Customer Orders</h2>
    <p style="color:var(--text-muted);">Monitor orders, verify manual GPay payments, and update delivery status.</p>
</div>

{% if orders %}
    <div class="table-container fade-in-up">
        <table class="custom-table">
            <thead>
                <tr>
                    <th>Order ID</th>
                    <th>Customer</th>
                    <th>Product & Qty</th>
                    <th>Total</th>
                    <th>Payment</th>
                    <th>Screenshot</th>
                    <th>Delivery Status</th>
                </tr>
            </thead>
            <tbody>
                {% for order in orders %}
                    <tr>
                        <td style="font-weight: 700; color: var(--primary);">#SCB-{{ order.id }}</td>
                        <td>
                            <div style="display:flex; flex-direction:column;">
                                <span style="font-weight:700;">{{ order.user.username }}</span>
                                <small style="color:var(--text-muted); font-size:0.75rem;">{{ order.user.email }}</small>
                            </div>
                        </td>
                        <td>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <img src="{{ order.product.image_url }}" alt="" style="width: 32px; height: 32px; object-fit: cover; border-radius: 4px; border: 1px solid #e2e8f0;">
                                <div>
                                    <span style="font-weight:600; display:block; font-size:0.85rem;">{{ order.product.name }}</span>
                                    <small style="color:var(--text-muted); font-size:0.8rem;">Quantity: {{ order.quantity }}</small>
                                </div>
                            </div>
                        </td>
                        <td style="font-weight:700;">&#8377;{{ "%.2f"|format(order.total_price) }}</td>
                        <td>
                            <div style="display:flex; flex-direction:column; gap:6px;">
                                <span class="badge-status {% if order.payment_status == 'Approved' %}delivered{% elif order.payment_status == 'Rejected' %}danger{% else %}pending{% endif %}">
                                    {{ order.payment_status }}
                                </span>
                                <form action="/admin/update-payment-status/{{ order.id }}" method="POST" style="display:flex; gap:5px; flex-wrap:wrap;">
                                    <button name="payment_status" value="Approved" class="btn-card" style="border:0; background:var(--success); color:white; padding:5px 8px; font-size:0.75rem; cursor:pointer;">Approve</button>
                                    <button name="payment_status" value="Rejected" class="btn-card" style="border:0; background:var(--danger); color:white; padding:5px 8px; font-size:0.75rem; cursor:pointer;">Reject</button>
                                </form>
                            </div>
                        </td>
                        <td>
                            {% if order.payment_screenshot %}
                                <a href="{{ order.payment_screenshot }}" target="_blank" class="btn-card" style="font-size:0.75rem; padding:5px 8px;">View</a>
                            {% else %}
                                <span style="color:var(--text-muted); font-size:0.8rem;">No file</span>
                            {% endif %}
                        </td>
                        <td>
                            <form action="/admin/update-order-status/{{ order.id }}" method="POST" style="display:flex; align-items:center; gap:8px;">
                                <select name="status" class="form-control-custom" style="padding: 4px 8px; font-size: 0.8rem; width: auto;" onchange="this.form.submit()">
                                    <option value="Payment Pending" {% if order.status == 'Payment Pending' %}selected{% endif %}>Payment Pending</option>
                                    <option value="Pending" {% if order.status == 'Pending' %}selected{% endif %}>Pending</option>
                                    <option value="Processing" {% if order.status == 'Processing' %}selected{% endif %}>Processing</option>
                                    <option value="Shipped" {% if order.status == 'Shipped' %}selected{% endif %}>Shipped</option>
                                    <option value="Delivered" {% if order.status == 'Delivered' %}selected{% endif %}>Delivered</option>
                                </select>
                            </form>
                        </td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
{% else %}
    <div class="fade-in-up" style="text-align: center; padding: 60px 0; background: var(--white); border-radius: 16px; border: 1px solid #e2e8f0;">
        <i class="fa-solid fa-receipt" style="font-size: 3rem; color: var(--text-muted); margin-bottom: 15px;"></i>
        <h3>No Customer Orders</h3>
        <p style="color: var(--text-muted); margin-top: 5px;">No orders have been submitted by customers yet.</p>
    </div>
{% endif %}
{% endblock %}
"""

ADMIN_USERS_TEMPLATE = """
{% extends "base" %}
{% block title %}Manage Users{% endblock %}

{% block content %}
<div style="margin-bottom: 25px;">
    <h2>Registered Scatbys Clients</h2>
    <p style="color:var(--text-muted);">Review list of registered users and trace their purchase actions.</p>
</div>

{% if users_data %}
    <div class="table-container fade-in-up">
        <table class="custom-table">
            <thead>
                <tr>
                    <th>User ID</th>
                    <th>Username</th>
                    <th>Email Address</th>
                    <th>Registration Date</th>
                    <th>Total Placed Orders</th>
                    <th>Total Capital Spent</th>
                </tr>
            </thead>
            <tbody>
                {% for item in users_data %}
                    <tr>
                        <td style="font-weight: 700; color: var(--text-muted);">#USER-{{ item.user.id }}</td>
                        <td><span style="font-weight: 700;"><i class="fa-regular fa-user"></i> {{ item.user.username }}</span></td>
                        <td>{{ item.user.email }}</td>
                        <td>{{ item.user.created_at.strftime('%B %d, %Y') }}</td>
                        <td style="font-weight: 700; color: var(--primary);">{{ item.order_count }} orders</td>
                        <td style="font-weight: 800; color: var(--success);">&#8377;{{ "%.2f"|format(item.total_spent) }}</td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
{% else %}
    <div class="fade-in-up" style="text-align: center; padding: 60px 0; background: var(--white); border-radius: 16px; border: 1px solid #e2e8f0;">
        <i class="fa-solid fa-users-slash" style="font-size: 3rem; color: var(--text-muted); margin-bottom: 15px;"></i>
        <h3>No Clients Registered</h3>
        <p style="color: var(--text-muted); margin-top: 5px;">Apart from the auto-created admin, no clients have registered.</p>
    </div>
{% endif %}
{% endblock %}
"""

# =========================================================================
# JINJA2 DICTLOADER SETUP
# =========================================================================
from jinja2 import DictLoader

templates_dict = {
    'base': BASE_TEMPLATE,
    'home': HOME_TEMPLATE,
    'register': REGISTER_TEMPLATE,
    'login': LOGIN_TEMPLATE,
    'products': PRODUCTS_TEMPLATE,
    'product_detail': PRODUCT_DETAIL_TEMPLATE,
    'order': ORDER_TEMPLATE,
    'dashboard': DASHBOARD_TEMPLATE,
    'admin_login': ADMIN_LOGIN_TEMPLATE,
    'admin_dashboard': ADMIN_DASHBOARD_TEMPLATE,
    'admin_add_product': ADMIN_ADD_PRODUCT_TEMPLATE,
    'admin_products': ADMIN_PRODUCTS_TEMPLATE,
    'admin_orders': ADMIN_ORDERS_TEMPLATE,
    'admin_users': ADMIN_USERS_TEMPLATE
}

# Rebuild after adding admin_dashboard update (messages are passed via route)

app.jinja_loader = DictLoader(templates_dict)

def render_scatbys_template(template_name, **context):
    return render_template(template_name, **context)

# =========================================================================
# APPLICATION ROUTES
# =========================================================================

@app.route('/')
def home():
    featured = Product.query.order_by(Product.id.asc()).limit(3).all()
    return render_scatbys_template('home', featured_products=featured)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('products'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not username or not email or not password:
            flash('All input fields are required.', 'danger')
            return redirect(url_for('register'))
            
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))
            
        # Check if user exists
        existing_username = User.query.filter_by(username=username).first()
        if existing_username:
            flash('Username is already taken.', 'danger')
            return redirect(url_for('register'))
            
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email address is already registered.', 'danger')
            return redirect(url_for('register'))
            
        # Create and save user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_scatbys_template('register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('products'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            # Separate Admin login check (prevent admin login from regular route if required,
            # but allow standard users to login cleanly).
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('products'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))
            
    return render_scatbys_template('login')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Successfully logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/products')
def products():
    search_query = request.args.get('q', '').strip()
    category_filter = request.args.get('category', '').strip()
    
    query = Product.query
    if search_query:
        query = query.filter((Product.name.like(f"%{search_query}%")) | (Product.description.like(f"%{search_query}%")))
    if category_filter:
        query = query.filter_by(category=category_filter)
        
    all_products = query.all()
    return render_scatbys_template('products', products=all_products, search_query=search_query, category_filter=category_filter)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Calculate how many distinct people have ordered this product
    order_count = db.session.query(Order.user_id).filter_by(product_id=product.id).distinct().count()
    return render_scatbys_template('product_detail', product=product, order_count=order_count)

@app.route('/order/<int:product_id>', methods=['GET', 'POST'])
def order(product_id):
    product = Product.query.get_or_404(product_id)

    if 'user_id' not in session:
        flash('Authentication required to purchase.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        quantity = int(request.form.get('quantity', 1))
        shipping = int(request.form.get('delivery_state', 40))

        if quantity <= 0:
            flash('Invalid quantity selected.', 'danger')
            return redirect(url_for('order', product_id=product.id))

        if quantity > product.stock_quantity:
            flash(f'Insufficient stock. Only {product.stock_quantity} available.', 'danger')
            return redirect(url_for('order', product_id=product.id))

        payment_file = request.files.get('payment_screenshot')
        if not payment_file or payment_file.filename == '':
            flash('Please upload your GPay payment screenshot.', 'danger')
            return redirect(url_for('order', product_id=product.id))

        if not allowed_payment_file(payment_file.filename):
            flash('Only PNG, JPG, JPEG, or WEBP screenshots are allowed.', 'danger')
            return redirect(url_for('order', product_id=product.id))

        subtotal = product.price * quantity
        total_price = subtotal + shipping

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        safe_name = secure_filename(payment_file.filename)
        unique_name = f"order_{session['user_id']}_{int(datetime.utcnow().timestamp())}_{safe_name}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        payment_file.save(save_path)
        screenshot_url = f"/static/payment_screenshots/{unique_name}"

        new_order = Order(
            user_id=session['user_id'],
            product_id=product.id,
            quantity=quantity,
            total_price=total_price,
            status='Payment Pending',
            payment_method='GPay / UPI',
            payment_status='Pending Verification',
            payment_screenshot=screenshot_url
        )

        product.stock_quantity -= quantity
        db.session.add(new_order)
        db.session.commit()

        flash('Order placed! Payment screenshot uploaded. Admin will verify your payment soon.', 'success')
        return redirect(url_for('dashboard'))

    return render_scatbys_template('order', product=product, gpay_upi_id=G_PAY_UPI_ID, gpay_qr_image=G_PAY_QR_IMAGE)

@app.route('/dashboard')
@login_required
def dashboard():
    user_orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.ordered_at.desc()).all()
    return render_scatbys_template('dashboard', orders=user_orders)

# =========================================================================
# ADMIN CONTROLLER ROUTES
# =========================================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if username == os.environ.get('ADMIN_USERNAME') and password == os.environ.get('ADMIN_PASSWORD'):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Authenticated successfully to Admin Panel.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials.', 'danger')
            return redirect(url_for('admin_login'))
            
    return render_scatbys_template('admin_login')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('Logged out from admin interface.', 'info')
    return redirect(url_for('home'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_products = Product.query.count()
    total_orders = Order.query.count()
    total_users = User.query.count()
    total_revenue = db.session.query(db.func.sum(Order.total_price)).scalar() or 0.0
    recent_orders = Order.query.order_by(Order.ordered_at.desc()).limit(5).all()
    # Fetch all customer messages newest first
    messages = ContactMessage.query.order_by(ContactMessage.sent_at.desc()).all()
    return render_scatbys_template(
        'admin_dashboard',
        total_products=total_products,
        total_orders=total_orders,
        total_users=total_users,
        total_revenue=total_revenue,
        recent_orders=recent_orders,
        messages=messages
    )

@app.route('/admin/add-product', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price = float(request.form.get('price', 0.0))
        stock_quantity = int(request.form.get('stock_quantity', 0))
        category = request.form.get('category', '').strip()
        image_url = request.form.get('image_url', '').strip()
        description = request.form.get('description', '').strip()
        
        if not name or price < 0 or stock_quantity < 0 or not category or not image_url or not description:
            flash('All product fields must be filled out correctly.', 'danger')
            return redirect(url_for('admin_add_product'))
            
        new_prod = Product(
            name=name,
            price=price,
            stock_quantity=stock_quantity,
            category=category,
            image_url=image_url,
            description=description
        )
        db.session.add(new_prod)
        db.session.commit()
        
        flash('Product published successfully to catalog.', 'success')
        return redirect(url_for('admin_products'))
        
    return render_scatbys_template('admin_add_product', edit_mode=False, product=None)

@app.route('/admin/edit-product/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        product.name = request.form.get('name', '').strip()
        product.price = float(request.form.get('price', 0.0))
        product.stock_quantity = int(request.form.get('stock_quantity', 0))
        product.category = request.form.get('category', '').strip()
        product.image_url = request.form.get('image_url', '').strip()
        product.description = request.form.get('description', '').strip()
        
        db.session.commit()
        flash('Product details saved successfully.', 'success')
        return redirect(url_for('admin_products'))
        
    return render_scatbys_template('admin_add_product', edit_mode=True, product=product)

@app.route('/admin/delete-product/<int:product_id>')
@admin_required
def admin_delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Delete related orders to prevent foreign key issues, or cascade deletion
    Order.query.filter_by(product_id=product.id).delete()
    db.session.delete(product)
    db.session.commit()
    
    flash('Product removed from catalog.', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/products')
@admin_required
def admin_products():
    products_list = Product.query.all()
    # Build list with order count per product
    enhanced_list = []
    for p in products_list:
        order_count = Order.query.filter_by(product_id=p.id).count()
        enhanced_list.append({
            'product': p,
            'order_count': order_count
        })
    return render_scatbys_template('admin_products', products=enhanced_list)

@app.route('/admin/orders')
@admin_required
def admin_orders():
    all_orders = Order.query.order_by(Order.ordered_at.desc()).all()
    return render_scatbys_template('admin_orders', orders=all_orders)

@app.route('/admin/update-order-status/<int:order_id>', methods=['POST'])
@admin_required
def update_order_status(order_id):
    order_record = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    if new_status in ['Payment Pending', 'Pending', 'Processing', 'Shipped', 'Delivered']:
        order_record.status = new_status
        db.session.commit()
        flash(f'Order #SCB-{order_record.id} status updated to {new_status}.', 'success')
    else:
        flash('Invalid status operation.', 'danger')
    return redirect(url_for('admin_orders'))

@app.route('/admin/update-payment-status/<int:order_id>', methods=['POST'])
@admin_required
def update_payment_status(order_id):
    order_record = Order.query.get_or_404(order_id)
    new_status = request.form.get('payment_status')
    if new_status in ['Pending Verification', 'Approved', 'Rejected']:
        order_record.payment_status = new_status
        if new_status == 'Approved' and order_record.status == 'Payment Pending':
            order_record.status = 'Processing'
        elif new_status == 'Rejected':
            order_record.status = 'Payment Pending'
        db.session.commit()
        flash(f'Payment for order #SCB-{order_record.id} marked as {new_status}.', 'success')
    else:
        flash('Invalid payment status.', 'danger')
    return redirect(url_for('admin_orders'))

@app.route('/contact', methods=['POST'])
def contact_submit():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    message = request.form.get('message', '').strip()
    if name and email and message:
        new_msg = ContactMessage(name=name, email=email, message=message)
        db.session.add(new_msg)
        db.session.commit()
        flash('Your message has been sent! We will get back to you soon.', 'success')
    else:
        flash('Please fill in all fields before submitting.', 'danger')
    return redirect(url_for('home') + '#contact')

@app.route('/admin/mark-message-read/<int:msg_id>')
@admin_required
def mark_message_read(msg_id):
    msg = ContactMessage.query.get_or_404(msg_id)
    msg.is_read = True
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/users')
@admin_required
def admin_users():
    all_users = User.query.all()
    users_data = []
    for u in all_users:
        order_count = Order.query.filter_by(user_id=u.id).count()
        # Sum total capital spent
        total_spent = db.session.query(db.func.sum(Order.total_price)).filter_by(user_id=u.id).scalar() or 0.0
        users_data.append({
            'user': u,
            'order_count': order_count,
            'total_spent': total_spent
        })
    return render_scatbys_template('admin_users', users_data=users_data)

# =========================================================================
# APPLICATION SETUP AND DATA SEEDING
# =========================================================================

def initialize_database():
    """Creates database schema and inserts admin user and 5 custom products."""
    with app.app_context():
        db.create_all()

        # Lightweight migration for older SQLite databases
        existing_cols = [row[1] for row in db.session.execute(db.text("PRAGMA table_info('order')")).fetchall()]
        migrations = {
            'payment_method': "ALTER TABLE 'order' ADD COLUMN payment_method VARCHAR(50) DEFAULT 'GPay / UPI'",
            'payment_status': "ALTER TABLE 'order' ADD COLUMN payment_status VARCHAR(50) DEFAULT 'Pending Verification'",
            'payment_screenshot': "ALTER TABLE 'order' ADD COLUMN payment_screenshot VARCHAR(255)"
        }
        for col, sql in migrations.items():
            if col not in existing_cols:
                db.session.execute(db.text(sql))
        db.session.commit()

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(os.path.join(app.root_path, 'static', 'payments'), exist_ok=True)

        # Copy product images from generated paths to app static resources
        static_images_dir = os.path.join(app.root_path, 'static', 'images')
        os.makedirs(static_images_dir, exist_ok=True)
        
        image_sources = {
            'keyboard.png': r"C:\Users\AKASHH\.gemini\antigravity-ide\brain\824f36cf-b352-4549-8aa7-728b063d3383\keyboard_1782446345450.png",
            'headphones.png': r"C:\Users\AKASHH\.gemini\antigravity-ide\brain\824f36cf-b352-4549-8aa7-728b063d3383\headphones_1782446366621.png",
            'smartwatch.png': r"C:\Users\AKASHH\.gemini\antigravity-ide\brain\824f36cf-b352-4549-8aa7-728b063d3383\smartwatch_1782446383409.png",
            'backpack.png': r"C:\Users\AKASHH\.gemini\antigravity-ide\brain\824f36cf-b352-4549-8aa7-728b063d3383\backpack_1782446409167.png",
            'chair.png': r"C:\Users\AKASHH\.gemini\antigravity-ide\brain\824f36cf-b352-4549-8aa7-728b063d3383\chair_1782446427168.png",
        }
        
        for filename, src_path in image_sources.items():
            dest_path = os.path.join(static_images_dir, filename)
            if not os.path.exists(dest_path) and os.path.exists(src_path):
                try:
                    shutil.copy2(src_path, dest_path)
                    print(f"Copied {filename} successfully to {dest_path}")
                except Exception as e:
                    print(f"Error copying {filename}: {e}")

        # Seed the admin user if not present
        admin_user = User.query.filter_by(username='aksin').first()
        if not admin_user:
            admin_user = User(
                username='aksin',
                email='achuakash879@gmail.com',
                password_hash=generate_password_hash('aksin@123')
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user aksin registered.")
            
        # Seed 5 sample products if storefront catalog is empty
        if Product.query.count() == 0:
            sample_products = [
                Product(
                    name="AeroType Mechanical Keyboard",
                    description="Experience premium typing with custom hot-swappable yellow switches, RGB backlighting, and a solid aluminum design.",
                    price=129.99,
                    image_url="/static/images/keyboard.png",
                    stock_quantity=15,
                    category="Electronics"
                ),
                Product(
                    name="Scatbys PureSound Headphones",
                    description="Industry-leading hybrid active noise canceling with 40-hour battery life and high-fidelity signature sound profile.",
                    price=249.99,
                    image_url="/static/images/headphones.png",
                    stock_quantity=22,
                    category="Electronics"
                ),
                Product(
                    name="Scatbys ChronoSync Smartwatch",
                    description="Track health stats, receive notifications, and enjoy a vibrant AMOLED always-on screen with 10 days of battery life.",
                    price=179.99,
                    image_url="/static/images/smartwatch.png",
                    stock_quantity=30,
                    category="Electronics"
                ),
                Product(
                    name="Nomad Horizon Leather Backpack",
                    description="Handcrafted full-grain leather pack with dedicated padded laptop sleeve, secret travel pockets, and weather-resistant lining.",
                    price=199.99,
                    image_url="/static/images/backpack.png",
                    stock_quantity=8,
                    category="Fashion"
                ),
                Product(
                    name="ErgoMotion Premium Office Chair",
                    description="Designed with adaptive lumbar support, 3D armrests, and premium mesh for full-day workplace comfort.",
                    price=349.99,
                    image_url="/static/images/chair.png",
                    stock_quantity=12,
                    category="Home"
                )
            ]
            db.session.bulk_save_objects(sample_products)
            db.session.commit()
            print("Successfully seeded 5 initial premium products.")

if __name__ == '__main__':
    initialize_database()
    app.run(host='0.0.0.0', port=5000, debug=True)
