#!/usr/bin/env python3
"""
سكريبت التشغيل السريع
Quick Start Script
"""

import os
import sys
import subprocess
import webbrowser
import time

def print_banner():
    """طباعة شعار التطبيق"""
    banner = """
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║            🌙 نظام الترجمة الفورية للقرآن الكريم 🌙              ║
║                     Quran Live Translation System                 ║
║                         Enhanced Version 2.0                      ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
"""
    print(banner)

def check_setup():
    """التحقق من اكتمال التهيئة"""
    print("📋 التحقق من التهيئة...")
    
    # التحقق من قاعدة البيانات
    db_path = os.path.join('data', 'quran.db')
    if not os.path.exists(db_path):
        print("❌ قاعدة البيانات غير موجودة!")
        print("   يرجى تشغيل: python setup.py")
        return False
    
    print("✅ قاعدة البيانات موجودة")
    
    # التحقق من الملفات الأساسية
    required_files = [
        'src/app.py',
        'src/database.py',
        'src/cache.py',
        'src/enhanced_matcher.py',
        'templates/index.html'
    ]
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            print(f"❌ الملف المطلوب غير موجود: {file_path}")
            return False
    
    print("✅ جميع الملفات الأساسية موجودة")
    return True

def start_server():
    """تشغيل الخادم"""
    print("\n🚀 بدء تشغيل الخادم...")
    print("="*70)
    
    try:
        os.chdir('src')
        
        # تشغيل التطبيق
        process = subprocess.Popen(
            [sys.executable, 'app.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # انتظار حتى يبدأ الخادم
        print("⏳ انتظار بدء الخادم...")
        time.sleep(3)
        
        # فتح المتصفح
        print("🌐 فتح المتصفح...")
        webbrowser.open('http://localhost:5000')
        
        print("\n✅ التطبيق يعمل الآن!")
        print("="*70)
        print("\n📍 الروابط المهمة:")
        print("   الواجهة الرئيسية: http://localhost:5000")
        print("   الإحصائيات:       http://localhost:5000/stats")
        print("   فحص الصحة:        http://localhost:5000/api/health")
        print("\n💡 للإيقاف: اضغط Ctrl+C")
        print("="*70 + "\n")
        
        # طباعة مخرجات الخادم
        for line in process.stdout:
            print(line, end='')
        
    except KeyboardInterrupt:
        print("\n\n⚠️  إيقاف الخادم...")
        process.terminate()
        process.wait()
        print("✅ تم إيقاف الخادم")
    except Exception as e:
        print(f"\n❌ خطأ: {e}")
        return False
    finally:
        os.chdir('..')
    
    return True

def show_menu():
    """عرض القائمة"""
    print("\n📋 الخيارات المتاحة:")
    print("  1. تشغيل التطبيق")
    print("  2. إعادة بناء قاعدة البيانات")
    print("  3. اختبار المكونات")
    print("  4. عرض المعلومات")
    print("  5. خروج")
    
    choice = input("\nاختر رقماً (1-5): ").strip()
    return choice

def rebuild_database():
    """إعادة بناء قاعدة البيانات"""
    print("\n🔨 إعادة بناء قاعدة البيانات...")
    
    try:
        os.chdir('src')
        result = subprocess.run(
            [sys.executable, 'database.py'],
            check=True
        )
        os.chdir('..')
        
        if result.returncode == 0:
            print("✅ تمت إعادة بناء قاعدة البيانات بنجاح")
            return True
        else:
            print("❌ فشلت إعادة بناء قاعدة البيانات")
            return False
    except Exception as e:
        print(f"❌ خطأ: {e}")
        os.chdir('..')
        return False

def test_components():
    """اختبار المكونات"""
    print("\n🧪 اختبار المكونات...")
    print("="*70)
    
    tests = [
        ('معالج النص العربي', 'src/arabic_normalizer.py'),
        ('كاشف حركات الصلاة', 'src/prayer_movement_detector.py'),
        ('نظام الكاش', 'src/cache.py'),
        ('قاعدة البيانات', 'src/database.py')
    ]
    
    results = []
    for name, script in tests:
        print(f"\n📌 اختبار {name}...")
        try:
            result = subprocess.run(
                [sys.executable, script],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print(f"✅ {name} - يعمل بشكل صحيح")
                results.append(True)
            else:
                print(f"❌ {name} - يوجد خطأ")
                results.append(False)
        except Exception as e:
            print(f"❌ {name} - فشل: {e}")
            results.append(False)
    
    print("\n" + "="*70)
    if all(results):
        print("✅ جميع المكونات تعمل بشكل صحيح")
    else:
        print("⚠️  بعض المكونات بها مشاكل")

def show_info():
    """عرض المعلومات"""
    print("\n📊 معلومات النظام")
    print("="*70)
    
    print(f"Python: {sys.version}")
    print(f"نظام التشغيل: {os.name}")
    print(f"المسار الحالي: {os.getcwd()}")
    
    # حجم قاعدة البيانات
    db_path = os.path.join('data', 'quran.db')
    if os.path.exists(db_path):
        size_mb = os.path.getsize(db_path) / (1024 * 1024)
        print(f"حجم قاعدة البيانات: {size_mb:.2f} MB")
    
    print("="*70)

def main():
    """الدالة الرئيسية"""
    print_banner()
    
    # التحقق من التهيئة
    if not check_setup():
        print("\n⚠️  يجب إكمال التهيئة أولاً")
        print("تشغيل: python setup.py")
        return
    
    print("✅ النظام جاهز للتشغيل!")
    
    while True:
        choice = show_menu()
        
        if choice == '1':
            start_server()
        elif choice == '2':
            rebuild_database()
        elif choice == '3':
            test_components()
        elif choice == '4':
            show_info()
        elif choice == '5':
            print("\n👋 إلى اللقاء!")
            break
        else:
            print("❌ خيار غير صحيح")
        
        if choice != '1':  # إلا إذا كان تشغيل الخادم
            input("\n⏎ اضغط Enter للمتابعة...")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 إلى اللقاء!")
    except Exception as e:
        print(f"\n❌ خطأ: {e}")
