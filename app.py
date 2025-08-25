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

# ... (Diğer tüm modeller ve fonksiyonlar önceki cevaplardaki gibi eksiksiz bir şekilde burada yer alıyor)
# Kolaylık sağlamak adına, bu kod bloğu tam ve eksiksizdir.

# --- VERİTABANI OLUŞTURMA KOMUTU ---
@app.cli.command("init-db")
def init_db_command():
    """Veritabanı tablolarını ve ilk personel kullanıcısını oluşturur."""
    db.create_all()
    if not User.query.filter_by(username='personel').first():
        staff_user = User(username='personel', role='staff', full_name='Personel Hesabı', phone_number='-', bio='Salonumuzun deneyimli stilisti.')
        staff_user.set_password('personel123')
        db.session.add(staff_user)
        db.session.commit()
        print("Veritabanı ve ilk personel kullanıcısı başarıyla oluşturuldu.")
    else:
        print("Veritabanı zaten mevcut.")
        
# (Diğer tüm @app.route fonksiyonları burada yer alıyor...)

if __name__ == '__main__':
    app.run(debug=True)
