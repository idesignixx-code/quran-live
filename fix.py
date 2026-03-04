#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت الإصلاح السريع - Quick Fix Script
يحل مشاكل قاعدة البيانات والإعداد
"""

import sys
import os

# Fix Unicode on Windows
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("=" * 70)
print("🔧 سكريبت الإصلاح السريع")
print("=" * 70)

# الانتقال إلى مجلد src
current_dir = os.path.basename(os.getcwd())
if current_dir == 'src':
    os.chdir('..')
    print("✅ تم الانتقال إلى مجلد المشروع الرئيسي")

# التحقق من وجود ملف quran.json
json_path = os.path.join('data', 'quran.json')
if not os.path.exists(json_path):
    print(f"❌ ملف البيانات غير موجود: {json_path}")
    print(f"   المسار الكامل: {os.path.abspath(json_path)}")
    input("\nاضغط Enter للخروج...")
    sys.exit(1)

print(f"✅ تم العثور على ملف البيانات: {json_path}")

# حذف قاعدة البيانات القديمة
db_path = os.path.join('data', 'quran.db')
if os.path.exists(db_path):
    print(f"🗑️  حذف قاعدة البيانات القديمة...")
    try:
        os.remove(db_path)
        print("✅ تم حذف قاعدة البيانات القديمة")
    except Exception as e:
        print(f"⚠️  تعذر حذف قاعدة البيانات: {e}")

# إنشاء قاعدة البيانات الجديدة
print("\n🔨 بناء قاعدة البيانات الجديدة...")
print("⏳ الرجاء الانتظار (قد يستغرق 10-30 ثانية)...")

try:
    os.chdir('src')
    
    # استيراد بدون تجميد
    print("\n📦 استيراد المكتبات...")
    from database import QuranDatabase
    
    print("📊 إنشاء قاعدة البيانات...")
    db = QuranDatabase('../data/quran.db')
    
    print("🔨 إنشاء الجداول...")
    db.create_tables()
    
    print("📇 بناء الفهارس...")
    db.create_indexes()
    
    print("📥 استيراد البيانات من JSON...")
    db.import_from_json('../data/quran.json')
    
    print("\n✅ تمت إعادة بناء قاعدة البيانات بنجاح!")
    
    # اختبار قاعدة البيانات
    print("\n🧪 اختبار قاعدة البيانات...")
    
    verse = db.get_verse(1, 1)
    if verse:
        print(f"✅ الاختبار ناجح")
        print(f"   الآية: {verse['ar'][:50]}...")
    else:
        print("❌ فشل الاختبار")
    
    # احصائيات
    try:
        stats = db.get_stats()
        print(f"\n📊 الإحصائيات:")
        print(f"   • الآيات: {stats['total_verses']}")
        print(f"   • السور: {stats['total_surahs']}")
        print(f"   • آيات السجدة: {stats['total_sajdah']}")
    except:
        pass
    
    db.close()
    
    os.chdir('..')
    
    print("\n" + "=" * 70)
    print("🎉 الإصلاح اكتمل بنجاح!")
    print("=" * 70)
    print("\nيمكنك الآن تشغيل التطبيق:")
    print("\n  الطريقة 1 (سريعة - موصى بها):")
    print("    انقر على START.bat")
    print("\n  الطريقة 2 (كاملة):")
    print("    cd src")
    print("    python app.py")
    print("=" * 70)
    
except KeyboardInterrupt:
    print("\n\n⚠️  تم إلغاء العملية")
except Exception as e:
    print(f"\n❌ خطأ: {e}")
    import traceback
    traceback.print_exc()
finally:
    input("\nاضغط Enter للخروج...")

