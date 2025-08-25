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
app.config['SECRET_KEY'] = 'nihai_son_anahtar_calisacak_v3'
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

# --- YARDIMCI FONKSİYONLAR ---
@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

def log_activity(actor, action, details=""):
    log = ActivityLog(actor_id=actor.id, action=action, details=details)
    db.session.add(log)
    db.session.commit()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- ANA SAYFALAR VE GİRİŞ/KAYIT ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('staff_dashboard')) if current_user.role == 'staff' else redirect(url_for('customer_dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        existing_user = User.query.filter_by(username=request.form['username']).first()
        if existing_user:
            flash('Bu kullanıcı adı zaten alınmış!', 'danger')
            return redirect(url_for('register'))
        new_user = User(username=request.form['username'], role='customer', full_name=request.form['full_name'], phone_number=request.form['phone_number'])
        new_user.set_password(request.form['password'])
        db.session.add(new_user)
        db.session.commit()
        flash('Hesap başarıyla oluşturuldu! Lütfen giriş yapın.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('index'))
        flash('Giriş başarısız. Lütfen bilgilerinizi kontrol edin.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- STİLİST PROFİL SAYFALARI ---
@app.route('/ekibimiz')
def stylists_list():
    stylists = User.query.filter_by(role='staff').all()
    return render_template('stylists.html', stylists=stylists)

@app.route('/stilist/<int:stylist_id>')
def stylist_profile(stylist_id):
    stylist = User.query.get_or_404(stylist_id)
    if stylist.role != 'staff': return redirect(url_for('stylists_list'))
    return render_template('stylist_profile.html', stylist=stylist)

@app.route('/profilim', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if current_user.role != 'staff': return redirect(url_for('index'))
    if request.method == 'POST':
        current_user.bio = request.form.get('bio')
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"profile_{current_user.id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                current_user.profile_picture = filename
        if 'gallery_images' in request.files:
            files = request.files.getlist('gallery_images')
            for file in files:
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(f"gallery_{current_user.id}_{datetime.now().timestamp()}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    new_image = GalleryImage(image_filename=filename, staff_id=current_user.id)
                    db.session.add(new_image)
        db.session.commit()
        flash('Profiliniz başarıyla güncellendi!', 'success')
        return redirect(url_for('edit_profile'))
    return render_template('edit_profile.html')

@app.route('/resim-sil/<int:image_id>', methods=['POST'])
@login_required
def delete_gallery_image(image_id):
    image = db.session.get(GalleryImage, image_id)
    if image.staff_id != current_user.id:
        flash('Bu resmi silme yetkiniz yok.', 'danger')
        return redirect(url_for('edit_profile'))
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], image.image_filename))
    except OSError as e:
        print(f"Dosya silinirken hata oluştu: {e}")
    db.session.delete(image)
    db.session.commit()
    flash('Resim galeriden silindi.', 'info')
    return redirect(url_for('edit_profile'))

# --- MÜŞTERİ PANELİ ---
@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def customer_dashboard():
    if current_user.role != 'customer': return redirect(url_for('staff_dashboard'))
    services = Service.query.order_by(Service.name).all()
    stylists = User.query.filter_by(role='staff').all()
    selected_date_str = request.form.get('selected_date_display', datetime.today().strftime('%Y-%m-%d'))
    selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    SLOT_DURATION_MINUTES = 30
    booked_slots = set()
    todays_appointments = db.session.query(Appointment).filter(db.func.date(Appointment.appointment_datetime) == selected_date, Appointment.status == 'active').all()
    for appt in todays_appointments:
        start_time = appt.appointment_datetime
        num_slots_to_book = appt.total_duration // SLOT_DURATION_MINUTES
        for i in range(num_slots_to_book):
            slot_time = start_time + timedelta(minutes=i * SLOT_DURATION_MINUTES)
            booked_slots.add(slot_time.time().strftime('%H:%M:%S'))
    working_hours_slots = []
    start_hour, end_hour = 9, 21
    current_time = datetime.combine(selected_date, time(hour=start_hour))
    end_time = datetime.combine(selected_date, time(hour=end_hour))
    while current_time < end_time:
        working_hours_slots.append(current_time.time())
        current_time += timedelta(minutes=SLOT_DURATION_MINUTES)
    return render_template('customer_dashboard.html', services=services, stylists=stylists, all_slots=working_hours_slots, booked_slots=list(booked_slots), slot_duration=SLOT_DURATION_MINUTES, selected_date=selected_date)

@app.route('/book', methods=['POST'])
@login_required
def book_appointment():
    form_data = request.form
    service_ids = form_data.getlist('service_ids')
    if not service_ids:
        flash('Lütfen en az bir hizmet seçin.', 'danger')
        return redirect(url_for('customer_dashboard'))
    selected_services = db.session.query(Service).filter(Service.id.in_(service_ids)).all()
    total_duration = sum(s.duration_minutes for s in selected_services)
    total_price = sum(s.price for s in selected_services)
    final_price = total_price
    appointment_datetime = datetime.strptime(f"{form_data['date']} {form_data['time']}", '%Y-%m-%d %H:%M:%S')
    new_appointment = Appointment(customer_id=current_user.id, staff_id=form_data['staff_id'], appointment_datetime=appointment_datetime, status='active', final_price=final_price, total_duration=total_duration)
    for service in selected_services: new_appointment.services.append(service)
    db.session.add(new_appointment)
    db.session.commit()
    flash(f'Randevunuz başarıyla oluşturuldu! Toplam Tutar: {final_price:.2f} ₺', 'success')
    return redirect(url_for('customer_dashboard'))

@app.route('/randevularim')
@login_required
def my_appointments():
    if current_user.role != 'customer': return redirect(url_for('index'))
    active_appointments = Appointment.query.filter_by(customer_id=current_user.id, status='active').order_by(Appointment.appointment_datetime).all()
    return render_template('my_appointments.html', appointments=active_appointments)

@app.route('/iptal_edilen_randevular')
@login_required
def canceled_appointments_history():
    if current_user.role != 'customer': return redirect(url_for('index'))
    canceled_appointments = Appointment.query.filter(Appointment.customer_id == current_user.id, Appointment.status.like('canceled_%')).order_by(Appointment.appointment_datetime.desc()).all()
    return render_template('canceled_history.html', appointments=canceled_appointments)

@app.route('/randevu_iptal/<int:appointment_id>', methods=['POST'])
@login_required
def cancel_my_appointment(appointment_id):
    appointment_to_cancel = db.session.get(Appointment, appointment_id)
    if appointment_to_cancel.customer_id != current_user.id:
        flash('Sadece kendi randevularınızı iptal edebilirsiniz.', 'danger')
        return redirect(url_for('my_appointments'))
    appointment_to_cancel.status = 'canceled_by_customer'
    db.session.commit()
    log_activity(current_user, "Müşteri Randevusunu İptal Etti", f"Randevu ID: {appointment_id}")
    flash('Randevunuz başarıyla iptal edildi.', 'success')
    return redirect(url_for('my_appointments'))

# --- PERSONEL PANELİ ---
@app.route('/staff', methods=['GET', 'POST'])
@login_required
def staff_dashboard():
    if current_user.role != 'staff': return redirect(url_for('customer_dashboard'))
    selected_date_str = request.form.get('selected_date', datetime.today().strftime('%Y-%m-%d'))
    selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    appointments_today = Appointment.query.filter(db.func.date(Appointment.appointment_datetime) == selected_date, Appointment.status == 'active').order_by(Appointment.appointment_datetime).all()
    return render_template('staff_dashboard.html', appointments=appointments_today, selected_date=selected_date)

@app.route('/cancel/<int:appointment_id>', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    if current_user.role != 'staff': return redirect(url_for('index'))
    appointment_to_delete = db.session.get(Appointment, appointment_id)
    appointment_to_delete.status = 'canceled_by_staff'
    db.session.commit()
    customer = db.session.get(User, appointment_to_delete.customer_id)
    log_activity(current_user, "Personel Randevu İptal Etti", f"Müşteri: {customer.username}, Randevu ID: {appointment_id}")
    flash('Randevu başarıyla iptal edildi.', 'success')
    return redirect(url_for('staff_dashboard'))

@app.route('/staff/hizmetler', methods=['GET', 'POST'])
@login_required
def manage_services():
    if current_user.role != 'staff': return redirect(url_for('index'))
    if request.method == 'POST':
        new_service = Service(name=request.form['name'], duration_minutes=int(request.form['duration']), price=float(request.form['price']))
        db.session.add(new_service)
        db.session.commit()
        flash(f'"{new_service.name}" hizmeti başarıyla eklendi.', 'success')
        return redirect(url_for('manage_services'))
    services = Service.query.order_by(Service.name).all()
    return render_template('manage_services.html', services=services)

@app.route('/staff/hizmet-sil/<int:service_id>', methods=['POST'])
@login_required
def delete_service(service_id):
    if current_user.role != 'staff': return redirect(url_for('index'))
    service_to_delete = db.session.get(Service, service_id)
    if service_to_delete:
        db.session.delete(service_to_delete)
        db.session.commit()
        flash(f'"{service_to_delete.name}" hizmeti silindi.', 'info')
    return redirect(url_for('manage_services'))
    
@app.route('/staff/promosyonlar', methods=['GET', 'POST'])
@login_required
def manage_promotions():
    if current_user.role != 'staff': return redirect(url_for('index'))
    if request.method == 'POST':
        existing_promo = Promotion.query.filter_by(code=request.form.get('code')).first()
        if existing_promo:
            flash('Bu promosyon kodu zaten mevcut!', 'danger')
            return redirect(url_for('manage_promotions'))
        exp_date_str = request.form.get('expiration_date')
        exp_date = datetime.strptime(exp_date_str, '%Y-%m-%d').date() if exp_date_str else None
        new_promo = Promotion(code=request.form.get('code'), discount_percentage=int(request.form.get('discount')), description=request.form.get('description'), expiration_date=exp_date)
        db.session.add(new_promo)
        db.session.commit()
        flash('Yeni promosyon kodu başarıyla eklendi.', 'success')
        return redirect(url_for('manage_promotions'))
    promotions = Promotion.query.order_by(Promotion.is_active.desc(), Promotion.id).all()
    return render_template('manage_promotions.html', promotions=promotions)

@app.route('/staff/kullanicilar')
@login_required
def manage_users():
    if current_user.role != 'staff': return redirect(url_for('index'))
    customers = User.query.filter_by(role='customer').all()
    return render_template('manage_users.html', customers=customers)

@app.route('/staff/hareketler')
@login_required
def view_activity_logs():
    if current_user.role != 'staff': return redirect(url_for('index'))
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).all()
    return render_template('activity_logs.html', logs=logs)

@app.route('/staff/randevu-ekle', methods=['GET', 'POST'])
@login_required
def add_appointment_for_customer():
    if current_user.role != 'staff': return redirect(url_for('index'))
    customers = User.query.filter_by(role='customer').all()
    services = Service.query.order_by(Service.name).all()
    stylists = User.query.filter_by(role='staff').all()
    if request.method == 'POST':
        flash('Personel adına randevu ekleme henüz tamamlanmadı.', 'info')
        return redirect(url_for('staff_dashboard'))
    return render_template('add_appointment.html', customers=customers, services=services, stylists=stylists)

# --- UYGULAMAYI ÇALIŞTIRMA ---
if __name__ == '__main__':

    app.run(debug=True)
