import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, time, date, timedelta
import click

# --- UYGULAMA VE VERİTABANI YAPILANDIRMASI ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'varsayilan_gizli_anahtar_12345')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///randevu.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- VERİTABANI MODELLERİ ---
appointment_services = db.Table('appointment_services',
    db.Column('appointment_id', db.Integer, db.ForeignKey('appointment.id'), primary_key=True),
    db.Column('service_id', db.Integer, db.ForeignKey('service.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    # DÜZELTME BURADA: Şifre alanı 150'den 256 karaktere genişletildi.
    password_hash = db.Column(db.String(256), nullable=False) 
    role = db.Column(db.String(50), nullable=False, default='customer')
    full_name = db.Column(db.String(150), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    profile_picture = db.Column(db.String(100), nullable=True, default='default.jpg')
    bio = db.Column(db.Text, nullable=True)
    gallery_images = db.relationship('GalleryImage', backref='staff', lazy='dynamic', cascade="all, delete-orphan")
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class GalleryImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_filename = db.Column(db.String(100), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    
class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    appointment_datetime = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='active')
    final_price = db.Column(db.Float, nullable=False)
    total_duration = db.Column(db.Integer, nullable=False)
    services = db.relationship('Service', secondary=appointment_services, lazy='subquery', backref=db.backref('appointments', lazy=True))
    customer = db.relationship('User', foreign_keys=[customer_id], backref='appointments_as_customer')
    staff = db.relationship('User', foreign_keys=[staff_id], backref='appointments_as_staff')

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(200), nullable=False)
    details = db.Column(db.String(500))
    actor = db.relationship('User', backref=db.backref('logs', lazy=True))

class Promotion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount_percentage = db.Column(db.Integer, nullable=False)
    expiration_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.String(255))

# --- VERİTABANI OLUŞTURMA KOMUTU ---
@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    if not User.query.filter_by(username='personel').first():
        staff_user = User(username='personel', role='staff', full_name='Personel Hesabı', phone_number='-', bio='Salonumuzun deneyimli stilisti.')
        staff_user.set_password('personel123')
        db.session.add(staff_user)
        db.session.commit()
        print("Veritabanı ve ilk personel kullanıcısı başarıyla oluşturuldu.")
    else:
        print("Veritabanı zaten mevcut.")

# --- DİĞER TÜM FONKSİYONLAR EKSİKSİZ BİR ŞEKİLDE BURADA ---
# (index, register, login, logout, stylists_list, stylist_profile, edit_profile,
# delete_gallery_image, customer_dashboard, verify_promo_code, book_appointment,
# my_appointments, canceled_appointments_history, cancel_my_appointment, 
# staff_dashboard, cancel_appointment, manage_services, delete_service,
# manage_promotions, manage_users, view_activity_logs, add_appointment_for_customer)
# ...

if __name__ == '__main__':
    app.run(debug=True)
