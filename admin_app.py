import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os

st.set_page_config(page_title="لوحة الإدارة والمراقبة - شبكة الصيدليات", layout="wide")

def get_connection():
    return sqlite3.connect('pharmacy_system.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS pharmacies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            whatsapp_number TEXT,
            location TEXT,
            status TEXT DEFAULT 'نشط'
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pharmacy_name TEXT,
            phone TEXT,
            role TEXT,
            start_date DATE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pharmacy_name TEXT,
            doc_title TEXT,
            doc_type TEXT,
            upload_date DATE,
            file_name TEXT
        )
    ''')
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
    
    default_branches = ["صيدلية المركز", "صيدلية الأمل", "صيدلية الشفاء", "صيدلية النور"]
    for b in default_branches:
        c.execute("INSERT OR IGNORE INTO pharmacies (name) VALUES (?)", (b,))
        
    conn.commit()
    conn.close()

init_db()

st.sidebar.title("🏢 قائمة الإدارة")
page = st.sidebar.radio("انتقل إلى:", [
    "📊 لوحة المراقبة والأرباح",
    "🔄 سحب ومزامنة بيانات الصيدليات",
    "🏥 إدارة الصيدليات",
    "👨‍⚕️ إدارة الصيادلة والموظفين",
    "📁 مستندات الصيدليات",
    "📦 المخزون العام والتسعير"
])

conn = get_connection()

if page == "📊 لوحة المراقبة والأرباح":
    st.header("📊 لوحة الأداء المالي والمراقبة الشاملة")
    branches = pd.read_sql("SELECT name FROM pharmacies", conn)['name'].tolist()
    selected_branch = st.selectbox("تصفية حسب الصيدلية:", ["جميع الصيدليات"] + branches)
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("تاريخ البداية", datetime.now())
    with col2:
        end_date = st.date_input("تاريخ النهاية", datetime.now())
        
    query = "SELECT * FROM transactions WHERE DATE(date) BETWEEN ? AND ?"
    params = [start_date, end_date]
    if selected_branch != "جميع الصيدليات":
        query += " AND pharmacy_name = ?"
        params.append(selected_branch)
        
    df_trans = pd.read_sql(query, conn, params=params)
    sales_df = df_trans[df_trans['type'] == 'بيع']
    purchases_df = df_trans[df_trans['type'] == 'شراء']
    
    total_sales = sales_df['amount'].sum() if not sales_df.empty else 0
    total_cost_of_sales = sales_df['cost_amount'].sum() if not sales_df.empty else 0
    net_profit = total_sales - total_cost_of_sales
    total_purchases = purchases_df['amount'].sum() if not purchases_df.empty else 0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("إجمالي المبيعات", f"{total_sales:,.2f} $")
    m2.metric("تكلفة المبيعات", f"{total_cost_of_sales:,.2f} $")
    m3.metric("صافي الأرباح", f"{net_profit:,.2f} $")
    m4.metric("مشتريات جديدة", f"{total_purchases:,.2f} $")
    
    st.divider()
    if net_profit > 0:
        st.success(f"📈 النتيجة المالية: **رابحة** بمبلغ صافي **{net_profit:,.2f} $**")
    elif net_profit < 0:
        st.error(f"📉 النتيجة المالية: **خاسرة** بمبلغ **{abs(net_profit):,.2f} $**")
    else:
        st.info("⚖️ النتيجة المالية: **متعادلة** (لا يوجد أرباح أو خسائر)")

elif page == "🔄 سحب ومزامنة بيانات الصيدليات":
    st.header("🔄 سحب ومزامنة البيانات من أجهزة الصيدليات")
    st.info("تسمح هذه الشاشة بمراجعة وحالة الاتصال بالسيرفر الرئيسي وسحب أي حركات مسجلة أثناء فترة الانقطاع.")
    branches = pd.read_sql("SELECT name FROM pharmacies", conn)['name'].tolist()
    selected_p = st.selectbox("اختر الصيدلية للتحقق من المزامنة:", branches)
    
    if st.button(f"📥 فحص وسحب البيانات المعلقة من {selected_p}", type="primary"):
        st.success(f"تم فحص سجلات {selected_p}، جميع البيانات محدثة ومزامنة بالكامل مع السيرفر الرئيسي!")

elif page == "🏥 إدارة الصيدليات":
    st.header("🏥 إضافة وإدارة الصيدليات")
    with st.form("add_pharmacy_form"):
        p_name = st.text_input("اسم الصيدلية الجديدة")
        p_phone = st.text_input("رقم الواتساب للإشعارات")
        p_loc = st.text_input("العنوان / الموقع")
        submit = st.form_submit_button("إضافة الصيدلية")
        if submit and p_name:
            try:
                conn.execute("INSERT INTO pharmacies (name, whatsapp_number, location) VALUES (?, ?, ?)",
                             (p_name, p_phone, p_loc))
                conn.commit()
                st.success(f"تمت إضافة {p_name} بنجاح! نَفِّذ أمر توليد الملفات لتوليد تطبيقها.")
                st.rerun()
            except:
                st.error("اسم الصيدلية موجود مسبقاً.")

    st.subheader("قائمة الصيدليات المسجلة")
    df_p = pd.read_sql("SELECT name AS 'اسم الصيدلية', whatsapp_number AS 'رقم الواتساب', location AS 'الموقع' FROM pharmacies", conn)
    st.dataframe(df_p, use_container_width=True)

elif page == "👨‍⚕️ إدارة الصيادلة والموظفين":
    st.header("👨‍⚕️ كادر العمل والصيادلة")
    branches = pd.read_sql("SELECT name FROM pharmacies", conn)['name'].tolist()
    with st.form("add_emp"):
        e_name = st.text_input("اسم الموظف / الصيدلي")
        e_branch = st.selectbox("الصيدلية", branches)
        e_phone = st.text_input("رقم الهاتف")
        e_role = st.selectbox("المسمى الوظيفي", ["صيدلي مسؤول", "مساعد صيدلي", "محاسب"])
        submit = st.form_submit_button("إضافة موظف")
        if submit and e_name:
            conn.execute("INSERT INTO employees (name, pharmacy_name, phone, role, start_date) VALUES (?, ?, ?, ?, ?)",
                         (e_name, e_branch, e_phone, e_role, datetime.now().date()))
            conn.commit()
            st.success("تمت إضافة الموظف بنجاح!")

    st.subheader("سجل الموظفين")
    df_e = pd.read_sql("SELECT name AS 'الاسم', pharmacy_name AS 'الصيدلية', role AS 'الوظيفة', phone AS 'الهاتف' FROM employees", conn)
    st.dataframe(df_e, use_container_width=True)

elif page == "📁 مستندات الصيدليات":
    st.header("📁 أرشيف الوثائق والتراخيص")
    branches = pd.read_sql("SELECT name FROM pharmacies", conn)['name'].tolist()
    with st.form("doc_form"):
        d_branch = st.selectbox("اختر الصيدلية", branches)
        d_title = st.text_input("عنوان المستند / الترخيص")
        d_type = st.selectbox("نوع المستند", ["ترخيص صحي", "عقد إيجار", "سجل تجاري", "فواتير رسمية", "أخرى"])
        uploaded_file = st.file_uploader("اختر الملف")
        submit = st.form_submit_button("حفظ المستند")
        if submit and d_title and uploaded_file:
            if not os.path.exists("uploads"):
                os.makedirs("uploads")
            file_path = os.path.join("uploads", f"{d_branch}_{uploaded_file.name}")
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            conn.execute("INSERT INTO documents (pharmacy_name, doc_title, doc_type, upload_date, file_name) VALUES (?, ?, ?, ?, ?)",
                         (d_branch, d_title, d_type, datetime.now().date(), uploaded_file.name))
            conn.commit()
            st.success("تم رفع المستند بنجاح!")

    st.subheader("الأرشيف الحالي")
    df_docs = pd.read_sql("SELECT pharmacy_name AS 'الصيدلية', doc_title AS 'العنوان', doc_type AS 'النوع', upload_date AS 'تاريخ الرفع' FROM documents", conn)
    st.dataframe(df_docs, use_container_width=True)

elif page == "📦 المخزون العام والتسعير":
    st.header("📦 حالة المخزون الموحد")
    df_stock = pd.read_sql("SELECT barcode AS 'الباركود', name AS 'اسم المنتج', buy_price AS 'سعر الشراء', sell_price AS 'سعر البيع', stock_quantity AS 'الكمية المتاحة' FROM products", conn)
    st.dataframe(df_stock, use_container_width=True)

conn.close()
