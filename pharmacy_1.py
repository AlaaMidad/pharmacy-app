import streamlit as st
import sqlite3
import pandas as pd
import os

CURRENT_PHARMACY = "صيدلية الأمل"
REMOTE_DB_PATH = 'pharmacy_system.db'
LOCAL_DB_PATH = 'local_p1.db'

st.set_page_config(page_title=f"نظام البيع - {CURRENT_PHARMACY}", layout="centered")

def get_active_connection():
    try:
        conn = sqlite3.connect(REMOTE_DB_PATH, timeout=2)
        conn.execute("SELECT 1")
        return conn, "online"
    except:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        return conn, "offline"

def init_local_db():
    conn = sqlite3.connect(LOCAL_DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS pending_transactions (
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

st.sidebar.title("📶 حالة الاتصال")
conn_test, mode = get_active_connection()
conn_test.close()

if mode == "online":
    st.sidebar.success("🌐 الاتصال بالشبكة: **متصل (أونلاين)**")
else:
    st.sidebar.warning("📡 الاتصال بالشبكة: **مقطوع (يعمل أوفلاين)**")

if st.sidebar.button("🔄 سحب وتزامن البيانات المجهزة"):
    try:
        remote_conn = sqlite3.connect(REMOTE_DB_PATH, timeout=5)
        local_conn = sqlite3.connect(LOCAL_DB_PATH)
        
        pending_df = pd.read_sql("SELECT * FROM pending_transactions", local_conn)
        if not pending_df.empty:
            for _, row in pending_df.iterrows():
                remote_conn.execute("""
                    INSERT INTO transactions (pharmacy_name, type, barcode, product_name, quantity, amount, cost_amount, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (row['pharmacy_name'], row['type'], row['barcode'], row['product_name'], row['quantity'], row['amount'], row['cost_amount'], row['date']))
            
            remote_conn.commit()
            local_conn.execute("DELETE FROM pending_transactions")
            local_conn.commit()
            st.sidebar.success(f"✅ تم سحب وتزامن {len(pending_df)} عملية بنجاح!")
        else:
            st.sidebar.info("لا توجد بيانات معلقة للسحب.")
            
        remote_conn.close()
        local_conn.close()
    except Exception as e:
        st.sidebar.error(f"فشلت المزامنة. تأكد من عودة الاتصال بالأجهزة. ({e})")

st.title(f"🏥 {CURRENT_PHARMACY}")
st.caption("نظام نقاط البيع والمخزون الداخلي المستقل")

if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "sale"

col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("🛍️ عملية بيع جديدة", use_container_width=True):
        st.session_state.active_tab = "sale"
with col2:
    if st.button("📦 إدخال منتج جديد", use_container_width=True):
        st.session_state.active_tab = "add"
with col3:
    if st.button("📊 الجرد الحالي", use_container_width=True):
        st.session_state.active_tab = "inventory"
with col4:
    if st.button("💵 حركة الصندوق", use_container_width=True):
        st.session_state.active_tab = "cash"

st.divider()
conn, conn_mode = get_active_connection()

if st.session_state.active_tab == "sale":
    st.subheader("🛍️ تسجيل عملية بيع")
    try:
        products = pd.read_sql("SELECT barcode, name, sell_price, buy_price, stock_quantity FROM products", conn)
    except:
        products = pd.DataFrame(columns=['barcode', 'name', 'sell_price', 'buy_price', 'stock_quantity'])
    
    if products.empty:
        st.warning("لا يوجد أدوية مسجلة في المخزون حالياً.")
    else:
        search_type = st.radio("طريقة الاختيار:", ["قارئ الباركود", "البحث بالاسم"], horizontal=True)
        selected_prod = None
        
        if search_type == "قارئ الباركود":
            barcode_input = st.text_input("امسح الباركود هنا:", key="barcode_key")
            if barcode_input:
                match = products[products['barcode'] == barcode_input]
                if not match.empty:
                    selected_prod = match.iloc[0]
                else:
                    st.error("المنتج غير موجود.")
        else:
            p_name = st.selectbox("اختر اسم الدواء:", products['name'].tolist())
            selected_prod = products[products['name'] == p_name].iloc[0]

        if selected_prod is not None:
            st.info(f"المنتج: **{selected_prod['name']}** | السعر: **{selected_prod['sell_price']} $** | المتاح: **{selected_prod['stock_quantity']}**")
            qty = st.number_input("الكمية المباعة:", min_value=1, max_value=max(1, int(selected_prod['stock_quantity'])), value=1)
            total_amount = qty * selected_prod['sell_price']
            total_cost = qty * selected_prod['buy_price']
            
            st.write(f"### المبلغ الإجمالي: **{total_amount:,.2f} $**")
            
            if st.button("✅ تأكيد البيع وإصدار الفاتورة", type="primary"):
                if conn_mode == "online":
                    conn.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE barcode = ?", (qty, selected_prod['barcode']))
                    conn.execute("""
                        INSERT INTO transactions (pharmacy_name, type, barcode, product_name, quantity, amount, cost_amount)
                        VALUES (?, 'بيع', ?, ?, ?, ?, ?)
                    """, (CURRENT_PHARMACY, selected_prod['barcode'], selected_prod['name'], qty, total_amount, total_cost))
                    conn.commit()
                    st.success("تم تسجيل البيع مباشرة في السيرفر الرئيسي!")
                else:
                    conn.execute("""
                        INSERT INTO pending_transactions (pharmacy_name, type, barcode, product_name, quantity, amount, cost_amount)
                        VALUES (?, 'بيع', ?, ?, ?, ?, ?)
                    """, (CURRENT_PHARMACY, selected_prod['barcode'], selected_prod['name'], qty, total_amount, total_cost))
                    conn.commit()
                    st.warning("تم حفظ عملية البيع محلياً (أوفلاين)، انقر زر المزامنة عند عودة الإنترنت.")
                
                msg = f"عملية بيع في {CURRENT_PHARMACY}%0Aالمنتج: {selected_prod['name']}%0Aالكمية: {qty}%0Aالمبلغ: {total_amount:,.2f} $"
                whatsapp_url = f"https://wa.me/?text={msg}"
                st.markdown(f"[📲 إرسال إشعار عبر WhatsApp]({whatsapp_url})", unsafe_allow_html=True)

elif st.session_state.active_tab == "add":
    st.subheader("📦 إضافة أدوية / توريد جديد")
    with st.form("new_product"):
        b_code = st.text_input("الباركود")
        p_name = st.text_input("اسم الدواء / المنتج")
        b_price = st.number_input("سعر الشراء (التكلفة)", min_value=0.0, format="%.2f")
        s_price = st.number_input("سعر البيع للمستهلك", min_value=0.0, format="%.2f")
        qty = st.number_input("الكمية المدخلة", min_value=1, value=10)
        submit = st.form_submit_button("حفظ وإضافة للمخزون")
        
        if submit and b_code and p_name:
            if conn_mode == "online":
                c = conn.cursor()
                c.execute("SELECT stock_quantity FROM products WHERE barcode = ?", (b_code,))
                existing = c.fetchone()
                if existing:
                    conn.execute("UPDATE products SET stock_quantity = stock_quantity + ?, buy_price = ?, sell_price = ? WHERE barcode = ?", 
                                 (qty, b_price, s_price, b_code))
                else:
                    conn.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?)", (b_code, p_name, b_price, s_price, qty))
                
                conn.execute("""
                    INSERT INTO transactions (pharmacy_name, type, barcode, product_name, quantity, amount, cost_amount)
                    VALUES (?, 'شراء', ?, ?, ?, ?, ?)
                """, (CURRENT_PHARMACY, b_code, p_name, qty, qty * b_price, qty * b_price))
                conn.commit()
                st.success("تم إضافة المنتج في السيرفر الرئيسي!")
            else:
                st.error("إضافة أدوية جديدة يتطلب الاتصال بالسيرفر الرئيسي (أونلاين).")

elif st.session_state.active_tab == "inventory":
    st.subheader("📊 الجرد الحالي للمخزون")
    try:
        df_inv = pd.read_sql("SELECT barcode AS 'الباركود', name AS 'اسم الدواء', sell_price AS 'سعر البيع', stock_quantity AS 'الكمية المتاحة' FROM products", conn)
        st.dataframe(df_inv, use_container_width=True)
    except:
        st.info("الجرد الحالي يتطلب الاتصال بالمخزون الرئيسي.")

elif st.session_state.active_tab == "cash":
    st.subheader(f"💵 حركة الصندوق الخاص بـ ({CURRENT_PHARMACY})")
    if conn_mode == "online":
        df_c = pd.read_sql("""
            SELECT type AS 'نوع الحركة', product_name AS 'الصنف', quantity AS 'الكمية', amount AS 'المبلغ', date AS 'التاريخ'
            FROM transactions WHERE pharmacy_name = ? ORDER BY date DESC
        """, conn, params=[CURRENT_PHARMACY])
    else:
        df_c = pd.read_sql("""
            SELECT type AS 'نوع الحركة', product_name AS 'الصنف', quantity AS 'الكمية', amount AS 'المبلغ', date AS 'التاريخ'
            FROM pending_transactions ORDER BY date DESC
        """, conn)
        st.warning("⚠️ هذه الحركة المسجلة أوفلاين فقط والتي لم تُرفع للسيرفر الرئيسي بعد.")
    
    st.dataframe(df_c, use_container_width=True)

conn.close()
