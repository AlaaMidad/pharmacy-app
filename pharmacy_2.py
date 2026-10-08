import streamlit as st
import psycopg2
import pandas as pd

st.set_page_config(page_title="نظام نقاط البيع - صيدلية الشفاء", layout="wide")

CURRENT_PHARMACY = "صيدلية الشفاء"

def get_connection():
    try:
        return psycopg2.connect(st.secrets["DATABASE_URL"])
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال بقاعدة البيانات السحابية: {e}")
        return None

st.title(f"🏥 {CURRENT_PHARMACY}")

if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "sale"

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🛍️ عملية بيع جديدة", use_container_width=True):
        st.session_state.active_tab = "sale"
with col2:
    if st.button("📦 إدخال مواد جديدة للمخزن", use_container_width=True):
        st.session_state.active_tab = "add"
with col3:
    if st.button("📊 المخزون الحالي الموحد", use_container_width=True):
        st.session_state.active_tab = "inventory"

st.divider()
conn = get_connection()

if conn:
    cursor = conn.cursor()

    # 🛍️ قسم عملية البيع
    if st.session_state.active_tab == "sale":
        st.subheader("🛍️ تسجيل عملية بيع")
        df_prods = pd.read_sql("SELECT barcode, name, sell_price, buy_price, stock_quantity FROM products", conn)
        
        if not df_prods.empty:
            prod_options = {f"{row['name']} (باركد: {row['barcode']}) - السعر: {row['sell_price']}$": row['barcode'] for _, row in df_prods.iterrows()}
            selected_label = st.selectbox("اختر المنتج:", list(prod_options.keys()))
            selected_barcode = prod_options[selected_label]
            
            selected_prod = df_prods[df_prods['barcode'] == selected_barcode].iloc[0]
            
            sell_qty = st.number_input("الكمية المباعة:", min_value=1, max_value=int(selected_prod['stock_quantity']), value=1)
            total_amt = sell_qty * float(selected_prod['sell_price'])
            total_cost = sell_qty * float(selected_prod['buy_price'])
            
            st.info(f"💵 الإجمالي: **{total_amt:,.2f} $**")
            
            if st.button("✅ تأكيد عملية البيع", type="primary"):
                # 1. إدخال الحركة
                cursor.execute("""
                    INSERT INTO transactions (pharmacy_name, type, barcode, product_name, quantity, amount, cost_amount)
                    VALUES (%s, 'بيع', %s, %s, %s, %s, %s)
                """, (CURRENT_PHARMACY, selected_barcode, selected_prod['name'], sell_qty, total_amt, total_cost))
                
                # 2. خصم الكمية من المخزون
                cursor.execute("""
                    UPDATE products SET stock_quantity = stock_quantity - %s WHERE barcode = %s
                """, (sell_qty, selected_barcode))
                
                conn.commit()
                st.success("✅ تمت عملية البيع بنجاح وتحديث قاعدة البيانات الموحدة!")
                st.rerun()
        else:
            st.warning("لا توجد منتجات مسجلة في المخزون حالياً.")

    # 📦 قسم إضافة مواد جديدة
    elif st.session_state.active_tab == "add":
        st.subheader("📦 إضافة أدوية ومواد جديدة للمخزن الموحد")
        with st.form("add_p"):
            final_barcode = st.text_input("رقم الباركود")
            product_name = st.text_input("اسم الدواء / المادة")
            buy_price = st.number_input("سعر الشراء", min_value=0.0, format="%.2f")
            sell_price = st.number_input("سعر البيع للمستهلك", min_value=0.0, format="%.2f")
            quantity = st.number_input("الكمية المدخلة", min_value=1, value=10)
            
            if st.form_submit_button("📥 حفظ وتحديث المخزون الموحد"):
                if final_barcode and product_name:
                    cursor.execute("""
                        INSERT INTO products (barcode, name, buy_price, sell_price, stock_quantity)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (barcode) DO UPDATE SET
                            stock_quantity = products.stock_quantity + EXCLUDED.stock_quantity,
                            buy_price = EXCLUDED.buy_price,
                            sell_price = EXCLUDED.sell_price;
                    """, (final_barcode, product_name, buy_price, sell_price, quantity))
                    
                    cursor.execute("""
                        INSERT INTO transactions (pharmacy_name, type, barcode, product_name, quantity, amount, cost_amount)
                        VALUES (%s, 'شراء/إدخال', %s, %s, %s, %s, %s)
                    """, (CURRENT_PHARMACY, final_barcode, product_name, quantity, quantity * buy_price, quantity * buy_price))
                    
                    conn.commit()
                    st.success("✅ تم حفظ المنتج وتحديث الأسعار والمخزون الموحد بنجاح!")
                    st.rerun()

    # 📊 قسم الجرد والمخزون
    elif st.session_state.active_tab == "inventory":
        st.subheader("📊 المخزون والأسعار المتاحة حالياً")
        df_inv = pd.read_sql("""
            SELECT 
                barcode AS "الباركود", 
                name AS "اسم الدواء", 
                buy_price AS "سعر الشراء", 
                sell_price AS "سعر البيع", 
                stock_quantity AS "الكمية المتاحة" 
            FROM products
        """, conn)
        st.dataframe(df_inv, use_container_width=True)

    conn.close()
