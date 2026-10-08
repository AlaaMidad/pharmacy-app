# pharmacy_app.py
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from PIL import Image

try:
    from pyzbar.pyzbar import decode
except ImportError:
    decode = None

st.set_page_config(
    page_title="نظام نقاط البيع - صيدلية الشفاء",
    layout="wide"
)

LOCAL_DB_PATH = 'local_pharmacy.db'

def get_connection():
    return sqlite3.connect(LOCAL_DB_PATH)

def init_local_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            barcode TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            buy_price REAL,
            sell_price REAL,
            stock_quantity INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pharmacy_name TEXT,
            type TEXT,
            barcode TEXT,
            product_name TEXT,
            quantity INTEGER,
            amount REAL,
            cost_amount REAL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_local_db()

def scan_barcode_from_image(image_file):
    if decode is None or image_file is None:
        return None
    try:
        img = Image.open(image_file)
        decoded_objs = decode(img)
        for obj in decoded_objs:
            return obj.data.decode('utf-8')
    except Exception:
        return None
    return None

CURRENT_PHARMACY = "صيدلية الشفاء"

st.title(f"🏥 {CURRENT_PHARMACY}")
st.caption("نظام المبيعات والمخزون المباشر")

if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "sale"

col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("🛍️ عملية بيع جديدة", use_container_width=True):
        st.session_state.active_tab = "sale"
with col2:
    if st.button("📦 إدخال مواد جديدة", use_container_width=True):
        st.session_state.active_tab = "add"
with col3:
    if st.button("📊 الجرد الحالي", use_container_width=True):
        st.session_state.active_tab = "inventory"
with col4:
    if st.button("📤 تصدير للإدارة", use_container_width=True):
        st.session_state.active_tab = "export"

st.divider()
conn = get_connection()

if st.session_state.active_tab == "sale":
    st.subheader("🛍️ تسجيل عملية بيع")
    products = pd.read_sql("SELECT barcode, name, sell_price, buy_price, stock_quantity FROM products", conn)
    
    if products.empty:
        st.warning("⚠️ لا توجد مواد مسجلة في مخزون هذه الصيدلية. يرجى إضافة مواد من تبويب (📦 إدخال مواد جديدة) أولاً.")
    else:
        search_type = st.radio("طريقة الاختيار:", ["📷 كاميرا التابلت", "📟 قارئ الباركود", "🔎 البحث بالاسم"], horizontal=True)
        selected_prod = None
        scanned_code = ""

        if search_type == "📷 كاميرا التابلت":
            img_buf = st.camera_input("التقط صورة باركود المنتج")
            if img_buf:
                scanned_code = scan_barcode_from_image(img_buf)
                if scanned_code:
                    st.success(f"الباركود الملتقط: {scanned_code}")
                else:
                    st.error("لم يتم التعرف على الباركود.")

        elif search_type == "📟 قارئ الباركود":
            scanned_code = st.text_input("امسح الباركود هنا:", key="sale_barcode_scanner")

        if scanned_code and search_type != "🔎 البحث بالاسم":
            match = products[products['barcode'] == scanned_code]
            if not match.empty:
                selected_prod = match.iloc[0]
            else:
                st.error("المنتج غير موجود بجدول المخزون.")

        if search_type == "🔎 البحث بالاسم":
            p_name = st.selectbox("اختر اسم الدواء:", products['name'].tolist())
            selected_prod = products[products['name'] == p_name].iloc[0]

        if selected_prod is not None:
            st.info(f"المنتج: **{selected_prod['name']}** | السعر: **{selected_prod['sell_price']} $** | المتاح: **{selected_prod['stock_quantity']}**")
            qty = st.number_input("الكمية المباعة:", min_value=1, max_value=max(1, int(selected_prod['stock_quantity'])), value=1)
            total_amount = qty * selected_prod['sell_price']
            total_cost = qty * selected_prod['buy_price']
            
            st.write(f"### المبلغ الإجمالي: **{total_amount:,.2f} $**")
            
            if st.button("✅ تأكيد البيع وتسجيل الفاتورة", type="primary"):
                conn.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE barcode = ?", (qty, selected_prod['barcode']))
                conn.execute("""
                    INSERT INTO transactions (pharmacy_name, type, barcode, product_name, quantity, amount, cost_amount, date)
                    VALUES (?, 'بيع', ?, ?, ?, ?, ?, ?)
                """, (CURRENT_PHARMACY, selected_prod['barcode'], selected_prod['name'], qty, total_amount, total_cost, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                st.success("🎉 تم تسجيل عملية البيع وخصم المادة من المخزون بنجاح!")
                st.rerun()

elif st.session_state.active_tab == "add":
    st.subheader("📦 إضافة أدوية ومواد جديدة للمخزن")
    
    input_method = st.radio(
        "طريقة قراءة الباركود:",
        ["📷 كاميرا التابلت", "📟 قارئ الباركود (Scanner)", "✏️ إدخال يدوي"],
        horizontal=True
    )

    scanned_barcode = ""

    if input_method == "📷 كاميرا التابلت":
        img_buffer = st.camera_input("التقط صورة الباركود")
        if img_buffer is not None:
            detected_code = scan_barcode_from_image(img_buffer)
            if detected_code:
                scanned_barcode = detected_code
                st.success(f"✅ الباركود الملتقط: **{scanned_barcode}**")

    elif input_method == "📟 قارئ الباركود (Scanner)":
        scanned_barcode = st.text_input("امسح الباركود باستخدام الجهاز:", key="scanner_input_add")

    else:
        scanned_barcode = st.text_input("اكتب رقم الباركود يدوياً:", key="manual_input_add")

    with st.form("add_product_to_stock"):
        final_barcode = st.text_input("رقم الباركود المعتمد", value=scanned_barcode)
        product_name = st.text_input("اسم الدواء / المادة")
        buy_price = st.number_input("سعر الشراء (التكلفة $)", min_value=0.0, format="%.2f")
        sell_price = st.number_input("سعر البيع للمستهلك ($)", min_value=0.0, format="%.2f")
        quantity = st.number_input("الكمية المدخلة للمخزن", min_value=1, value=10)
        
        submit_btn = st.form_submit_button("📥 حفظ في مخزون الصيدلية", type="primary")

        if submit_btn:
            if not final_barcode or not product_name:
                st.error("يرجى كتابة الباركود واسم المادة.")
            else:
                c = conn.cursor()
                c.execute("SELECT stock_quantity FROM products WHERE barcode = ?", (final_barcode,))
                existing = c.fetchone()
                
                if existing:
                    conn.execute("""
                        UPDATE products 
                        SET stock_quantity = stock_quantity + ?, buy_price = ?, sell_price = ? 
                        WHERE barcode = ?
                    """, (quantity, buy_price, sell_price, final_barcode))
                else:
                    conn.execute("""
                        INSERT INTO products (barcode, name, buy_price, sell_price, stock_quantity)
                        VALUES (?, ?, ?, ?, ?)
                    """, (final_barcode, product_name, buy_price, sell_price, quantity))
                
                conn.execute("""
                    INSERT INTO transactions (pharmacy_name, type, barcode, product_name, quantity, amount, cost_amount, date)
                    VALUES (?, 'شراء/إدخال', ?, ?, ?, ?, ?, ?)
                """, (CURRENT_PHARMACY, final_barcode, product_name, quantity, quantity * buy_price, quantity * buy_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                
                conn.commit()
                st.success(f"🎉 تم إدخال ({product_name}) للمخزون وتسجيل الحركة!")

elif st.session_state.active_tab == "inventory":
    st.subheader("📊 المخزون الحالي بالفرع")
    df_inv = pd.read_sql("SELECT barcode AS 'الباركود', name AS 'اسم الدواء', buy_price AS 'سعر الشراء', sell_price AS 'سعر البيع', stock_quantity AS 'الكمية المتاحة' FROM products", conn)
    st.dataframe(df_inv, use_container_width=True)

elif st.session_state.active_tab == "export":
    st.subheader("📤 تصدير سجل الحركة المالية إلى برنامج الإدارة")
    st.info("قم بتنزيل ملف العمليات المحدث ثم رفعه في شاشة (دمج ومزامنة بيانات الفروع) لتظهر الأرباح في تطبيق الإدارة.")
    
    df_export = pd.read_sql("SELECT * FROM transactions", conn)
    
    if not df_export.empty:
        st.dataframe(df_export, use_container_width=True)
        csv_data = df_export.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label=f"⬇️ تنزيل سجل المبيعات والمشتريات لـ ({CURRENT_PHARMACY}) - CSV",
            data=csv_data,
            file_name=f"{CURRENT_PHARMACY}_transactions.csv",
            mime="text/csv",
            type="primary"
        )
    else:
        st.warning("لا توجد حركات مسجلة حالياً للتصدير.")

conn.close()
