# admin_app.py
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os

st.set_page_config(
    page_title="لوحة الإدارة والمراقبة - شبكة الصيدليات",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = 'pharmacy_system.db'

def get_connection():
    return sqlite3.connect(DB_PATH)

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

st.sidebar.title("🏢 قائمة الإدارة الموحدة")
page = st.sidebar.radio("انتقل إلى:", [
    "📊 لوحة المراقبة والأرباح",
    "🔄 دمج ومزامنة بيانات الفروع",
    "🏥 إدارة الصيدليات والفروع",
    "👨‍⚕️ إدارة الصيادلة والموظفين",
    "📁 مستندات وأرشيف الصيدليات",
    "📦 المخزون العام والمنتجات"
])

conn = get_connection()

if page == "📊 لوحة المراقبة والأرباح":
    st.header("📊 لوحة الأداء المالي والمراقبة الشاملة")
    
    branches = pd.read_sql("SELECT name FROM pharmacies", conn)['name'].tolist()
    selected_branch = st.selectbox("تصفية حسب الصيدلية:", ["جميع الصيدليات"] + branches)
    
    show_all = st.checkbox("عرض جميع البيانات المسجلة (تجاهل فلتر التاريخ)", value=True)
    
    if not show_all:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("تاريخ البداية", datetime.now() - timedelta(days=30))
        with col2:
            end_date = st.date_input("تاريخ النهاية", datetime.now() + timedelta(days=1))
            
        query = "SELECT * FROM transactions WHERE DATE(date) BETWEEN ? AND ?"
        params = [str(start_date), str(end_date)]
    else:
        query = "SELECT * FROM transactions"
        params = []

    if selected_branch != "جميع الصيدليات":
        if "WHERE" in query:
            query += " AND pharmacy_name = ?"
        else:
            query += " WHERE pharmacy_name = ?"
        params.append(selected_branch)
        
    df_trans = pd.read_sql(query, conn, params=params)
    
    if not df_trans.empty:
        sales_df = df_trans[df_trans['type'] == 'بيع']
        purchases_df = df_trans[df_trans['type'].str.contains('شراء|إدخال', na=False)]
        
        total_sales = sales_df['amount'].sum() if not sales_df.empty else 0.0
        total_cost_of_sales = sales_df['cost_amount'].sum() if not sales_df.empty else 0.0
        net_profit = total_sales - total_cost_of_sales
        total_purchases = purchases_df['amount'].sum() if not purchases_df.empty else 0.0
    else:
        total_sales = total_cost_of_sales = net_profit = total_purchases = 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("إجمالي المبيعات", f"{total_sales:,.2f} $")
    m2.metric("تكلفة المبيعات", f"{total_cost_of_sales:,.2f} $")
    m3.metric("صافي الأرباح", f"{net_profit:,.2f} $")
    m4.metric("مشتريات/توريد جديد", f"{total_purchases:,.2f} $")
    
    st.divider()
    
    if net_profit > 0:
        st.success(f"📈 النتيجة المالية: **رابحة** بمبلغ صافي **{net_profit:,.2f} $**")
    elif net_profit < 0:
        st.error(f"📉 النتيجة المالية: **خاسرة** بمبلغ **{abs(net_profit):,.2f} $**")
    else:
        st.info("⚖️ النتيجة المالية: **متعادلة** (لا يوجد سجل عمليات أرباح/خسائر)")

    st.subheader("📋 تفاصيل الحركات والعمليات المسجلة")
    st.dataframe(df_trans, use_container_width=True)

elif page == "🔄 دمج ومزامنة بيانات الفروع":
    st.header("🔄 استيراد ومزامنة العمليات والمخزون من الفروع")
    st.info("💡 رفع ملف العمليات سيقوم بتحديث **الأرباح والميزانية** وكذلك **المخزون العام والمنتجات المتاحة** تلقائياً.")
    
    uploaded_files = st.file_uploader(
        "اختر ملفات العمليات المصدّرة من الصيدليات:",
        type=["csv", "xlsx"],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        if st.button("📥 دمج البيانات وتحديث المخزون والميزانية", type="primary"):
            added_count = 0
            for uploaded_file in uploaded_files:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df_up = pd.read_csv(uploaded_file)
                    else:
                        df_up = pd.read_excel(uploaded_file)
                        
                    for _, row in df_up.iterrows():
                        p_name = row.get('pharmacy_name', 'فرع غير محدد')
                        p_type = row.get('type', 'بيع')
                        barcode = str(row.get('barcode', ''))
                        prod_name = row.get('product_name', 'منتج')
                        qty = int(row.get('quantity', 1))
                        amt = float(row.get('amount', 0.0))
                        cost_amt = float(row.get('cost_amount', 0.0))
                        trans_date = str(row.get('date', datetime.now()))
                        
                        # 1️⃣ تسجيل الحركة المالية في سجل الحركات
                        conn.execute("""
                            INSERT INTO transactions (pharmacy_name, type, barcode, product_name, quantity, amount, cost_amount, date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (p_name, p_type, barcode, prod_name, qty, amt, cost_amt, trans_date))
                        
                        # 2️⃣ تحديث المخزون العام والمنتجات في الإدارة
                        if barcode and prod_name:
                            # حساب أسعار القطعة الواحدة
                            unit_cost = cost_amt / qty if qty > 0 else 0.0
                            unit_sell = amt / qty if qty > 0 else 0.0
                            
                            c = conn.cursor()
                            c.execute("SELECT stock_quantity FROM products WHERE barcode = ?", (barcode,))
                            existing = c.fetchone()
                            
                            if p_type in ['شراء/إدخال', 'إدخال']:
                                if existing:
                                    conn.execute("""
                                        UPDATE products 
                                        SET stock_quantity = stock_quantity + ?, buy_price = ?, sell_price = ?
                                        WHERE barcode = ?
                                    """, (qty, unit_cost, unit_sell, barcode))
                                else:
                                    conn.execute("""
                                        INSERT INTO products (barcode, name, buy_price, sell_price, stock_quantity)
                                        VALUES (?, ?, ?, ?, ?)
                                    """, (barcode, prod_name, unit_cost, unit_sell, qty))
                                    
                            elif p_type == 'بيع':
                                if existing:
                                    conn.execute("""
                                        UPDATE products 
                                        SET stock_quantity = MAX(0, stock_quantity - ?)
                                        WHERE barcode = ?
                                    """, (qty, barcode))
                                else:
                                    # في حال تم رفع عملية بيع لم تكن أدخلت سابقاً كشراء
                                    conn.execute("""
                                        INSERT INTO products (barcode, name, buy_price, sell_price, stock_quantity)
                                        VALUES (?, ?, ?, ?, 0)
                                    """, (barcode, prod_name, unit_cost, unit_sell))
                                    
                        added_count += 1
                except Exception as e:
                    st.error(f"حدث خطأ أثناء معالجة الملف {uploaded_file.name}: {e}")
            
            conn.commit()
            st.success(f"✅ تم دمج {added_count} حركات وتحديث جدول المخزون العام والميزانية بنجاح!")

elif page == "🏥 إدارة الصيدليات والفروع":
    st.header("🏥 إضافة وإدارة الصيدليات والفروع")
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
                st.success(f"تمت إضافة {p_name} بنجاح!")
                st.rerun()
            except Exception:
                st.error("اسم الصيدلية موجود مسبقاً.")

    st.subheader("قائمة الصيدليات المسجلة")
    df_p = pd.read_sql("SELECT name AS 'اسم الصيدلية', whatsapp_number AS 'رقم الواتساب', location AS 'الموقع' FROM pharmacies", conn)
    st.dataframe(df_p, use_container_width=True)

elif page == "👨‍⚕️ إدارة الصيادلة والموظفين":
    st.header("👨‍⚕️ كادر العمل والصيادلة")
    branches = pd.read_sql("SELECT name FROM pharmacies", conn)['name'].tolist()
    with st.form("add_emp"):
        e_name = st.text_input("اسم الموظف / الصيدلي")
        e_branch = st.selectbox("الصيدلية الفرعية", branches)
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

elif page == "📁 مستندات وأرشيف الصيدليات":
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

elif page == "📦 المخزون العام والمنتجات":
    st.header("📦 حالة المخزون الموحد")
    df_stock = pd.read_sql("SELECT barcode AS 'الباركود', name AS 'اسم المنتج', buy_price AS 'سعر الشراء', sell_price AS 'سعر البيع', stock_quantity AS 'الكمية المتاحة' FROM products", conn)
    st.dataframe(df_stock, use_container_width=True)

conn.close()
