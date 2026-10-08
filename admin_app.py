import streamlit as st
import psycopg2
import pandas as pd

st.set_page_config(
    page_title="لوحة الإدارة والمراقبة - شبكة الصيدليات",
    layout="wide",
    initial_sidebar_state="expanded"
)

# دالة الاتصال بقاعدة البيانات السحابية Supabase
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DATABASE_URL"])
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال بقاعدة البيانات السحابية: {e}")
        return None

# إنشاء الجداول تلقائياً إن لم تكن موجودة
def init_db():
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                barcode TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                buy_price NUMERIC,
                sell_price NUMERIC,
                stock_quantity INTEGER
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                pharmacy_name TEXT,
                type TEXT,
                barcode TEXT,
                product_name TEXT,
                quantity INTEGER,
                amount NUMERIC,
                cost_amount NUMERIC,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()

init_db()

st.sidebar.title("🏢 قائمة الإدارة الموحدة")
page = st.sidebar.radio("انتقل إلى:", [
    "📊 لوحة المراقبة والأرباح المباشرة",
    "📦 المخزون العام والمنتجات الموحدة",
    "📋 سجل الحركات والعمليات المالية"
])

conn = get_connection()

if conn:
    if page == "📊 لوحة المراقبة والأرباح المباشرة":
        st.header("📊 لوحة الأداء المالي والمراقبة المباشرة (لحظية)")
        
        df_trans = pd.read_sql("SELECT * FROM transactions", conn)
        
        if not df_trans.empty:
            sales_df = df_trans[df_trans['type'] == 'بيع']
            total_sales = sales_df['amount'].sum() if not sales_df.empty else 0.0
            total_cost = sales_df['cost_amount'].sum() if not sales_df.empty else 0.0
            net_profit = total_sales - total_cost
        else:
            total_sales = total_cost = net_profit = 0.0

        m1, m2, m3 = st.columns(3)
        m1.metric("إجمالي المبيعات الموحدة", f"{total_sales:,.2f} $")
        m2.metric("إجمالي التكلفة", f"{total_cost:,.2f} $")
        m3.metric("صافي الأرباح المباشرة", f"{net_profit:,.2f} $")
        
        st.divider()
        st.subheader("📊 أداء الفروع والصيدليات")
        if not df_trans.empty and 'pharmacy_name' in df_trans.columns:
            pharmacy_summary = df_trans[df_trans['type'] == 'بيع'].groupby('pharmacy_name').agg(
                إجمالي_المبيعات=('amount', 'sum'),
                إجمالي_التكلفة=('cost_amount', 'sum'),
                عدد_العمليات=('id', 'count')
            ).reset_index()
            pharmacy_summary['صافي الربح'] = pharmacy_summary['إجمالي_المبيعات'] - pharmacy_summary['إجمالي_التكلفة']
            st.dataframe(pharmacy_summary, use_container_width=True)

    elif page == "📦 المخزون العام والمنتجات الموحدة":
        st.header("📦 حالة المخزون الموحد والأسعار بجميع الفروع")
        df_stock = pd.read_sql("""
            SELECT 
                barcode AS "الباركود", 
                name AS "اسم المنتج", 
                buy_price AS "سعر الشراء", 
                sell_price AS "سعر البيع", 
                stock_quantity AS "الكمية المتاحة كلياً" 
            FROM products
        """, conn)
        st.dataframe(df_stock, use_container_width=True)

    elif page == "📋 سجل الحركات والعمليات المالية":
        st.header("📋 كافة العمليات المسجلة لحظياً من جميع الفروع")
        df_trans = pd.read_sql("SELECT * FROM transactions ORDER BY date DESC", conn)
        st.dataframe(df_trans, use_container_width=True)

    conn.close()
