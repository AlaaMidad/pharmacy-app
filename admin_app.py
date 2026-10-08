import streamlit as st
import sqlite3
import pandas as pd
import os
from PIL import Image
try:
    from pyzbar.pyzbar import decode
except ImportError:
    decode = None

def scan_barcode_from_image(image_file):
    """قراءة الباركود من صورة الكاميرا"""
    if decode is None or image_file is None:
        return None
    try:
        img = Image.open(image_file)
        decoded_objs = decode(img)
        for obj in decoded_objs:
            return obj.data.decode('utf-8')
    except Exception as e:
        return None
    return None

# ---- تبويب إضافة مواد / توريد للمخزن ----
st.subheader("📦 إضافة أدوية ومواد جديدة للمخزن")

# اختيار طريقة إدخال الباركود
input_method = st.radio(
    "اختر طريقة قراءة الباركود:",
    ["📷 قراءة عبر كاميرا التابلت", "📟 قارئ الباركود (Scanner)", "✏️ إدخال يدوي"],
    horizontal=True
)

scanned_barcode = ""

if input_method == "📷 قراءة عبر كاميرا التابلت":
    st.info("وجه كاميرا التابلت نحو باركود المنتج لقراءته تلقائياً:")
    img_buffer = st.camera_input("التقط صورة الباركود")
    if img_buffer is not None:
        detected_code = scan_barcode_from_image(img_buffer)
        if detected_code:
            scanned_barcode = detected_code
            st.success(f"✅ تم التقاط الباركود بنجاح: **{scanned_barcode}**")
        else:
            st.error("لم يتم العثور على باركود واضح في الصورة، يرجى المحاولة مجدداً.")

elif input_method == "📟 قارئ الباركود (Scanner)":
    scanned_barcode = st.text_input("امسح الباركود باستخدام الجهاز:", key="scanner_input")

else: # إدخال يدوي
    scanned_barcode = st.text_input("اكتب رقم الباركود يدوياً:", key="manual_input")

# نموذج إدخال تفاصيل المادة إلى المخزن
with st.form("add_product_to_stock"):
    final_barcode = st.text_input("رقم الباركود المعتمد", value=scanned_barcode)
    product_name = st.text_input("اسم الدواء / المادة")
    buy_price = st.number_input("سعر الشراء (التكلفة $)", min_value=0.0, format="%.2f")
    sell_price = st.number_input("سعر البيع للمستهلك ($)", min_value=0.0, format="%.2f")
    quantity = st.number_input("الكمية المدخلة للمخزن", min_value=1, value=10)
    
    submit_btn = st.form_submit_button("📥 إدخال مباشر إلى المخزن", type="primary")

    if submit_btn:
        if not final_barcode or not product_name:
            st.error("يرجى التأكد من كتابة الباركود واسم المادة.")
        else:
            try:
                conn = sqlite3.connect('pharmacy_system.db')
                c = conn.cursor()
                
                # التحقق إذا كان المنتج موجوداً مسبقاً في المخزن لمضاعفة الكمية أو إضافته من جديد
                c.execute("SELECT stock_quantity FROM products WHERE barcode = ?", (final_barcode,))
                existing = c.fetchone()
                
                if existing:
                    c.execute("""
                        UPDATE products 
                        SET stock_quantity = stock_quantity + ?, buy_price = ?, sell_price = ? 
                        WHERE barcode = ?
                    """, (quantity, buy_price, sell_price, final_barcode))
                    st.success(f"🎉 تم زيادة كمية المادة ({product_name}) بمقدار {quantity} قطعة بنجاح!")
                else:
                    c.execute("""
                        INSERT INTO products (barcode, name, buy_price, sell_price, stock_quantity)
                        VALUES (?, ?, ?, ?, ?)
                    """, (final_barcode, product_name, buy_price, sell_price, quantity))
                    st.success(f"🎉 تم تسجيل المادة الجديدة ({product_name}) في المخزن بنجاح!")
                
                # تسجيل الحركة في السجل المالي والمخزني
                c.execute("""
                    INSERT INTO transactions (pharmacy_name, type, barcode, product_name, quantity, amount, cost_amount)
                    VALUES ('المركز الرئيسي', 'شراء/إدخال', ?, ?, ?, ?, ?)
                """, (final_barcode, product_name, quantity, quantity * buy_price, quantity * buy_price))
                
                conn.commit()
                conn.close()
            except Exception as e:
                st.error(f"حدث خطأ أثناء الحفظ: {e}")
