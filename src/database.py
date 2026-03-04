"""
نظام قاعدة البيانات - Database System
SQLite مع فهرسة متقدمة لسرعة البحث
"""

import sqlite3
import json
import os
from typing import List, Dict, Optional, Tuple
from functools import lru_cache
import time


class QuranDatabase:
    """قاعدة بيانات القرآن الكريم مع SQLite"""
    
    def __init__(self, db_path: str = "data/quran.db"):
        """
        تهيئة قاعدة البيانات
        
        Args:
            db_path: مسار ملف قاعدة البيانات
        """
        self.db_path = db_path
        self.conn = None
        self.initialized = False
        
        # إنشاء الاتصال
        self._connect()
    
    def _connect(self):
        """إنشاء اتصال بقاعدة البيانات"""
        try:
            self.conn = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=10.0
            )
            self.conn.row_factory = sqlite3.Row  # للحصول على النتائج كقواميس
            print(f"[DB] ✅ Connected to database: {self.db_path}")
        except Exception as e:
            print(f"[DB] ❌ Connection error: {e}")
            raise
    
    def create_tables(self):
        """إنشاء جداول قاعدة البيانات"""
        cursor = self.conn.cursor()
        
        # جدول الآيات الرئيسي
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                surah INTEGER NOT NULL,
                ayah INTEGER NOT NULL,
                ar TEXT NOT NULL,
                ar_simple TEXT NOT NULL,
                en TEXT,
                fr TEXT,
                nl TEXT,
                normalized TEXT NOT NULL,
                length INTEGER NOT NULL,
                word_count INTEGER NOT NULL,
                UNIQUE(surah, ayah)
            )
        ''')
        
        # جدول السور
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS surahs (
                number INTEGER PRIMARY KEY,
                name_ar TEXT NOT NULL,
                name_en TEXT NOT NULL,
                revelation_type TEXT,
                total_verses INTEGER NOT NULL
            )
        ''')
        
        # جدول آيات سجود التلاوة
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sajdah_verses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                surah INTEGER NOT NULL,
                ayah INTEGER NOT NULL,
                type TEXT DEFAULT 'tilawah',
                UNIQUE(surah, ayah)
            )
        ''')
        
        self.conn.commit()
        print("[DB] ✅ Tables created successfully")
    
    def create_indexes(self):
        """إنشاء فهارس لتسريع البحث"""
        cursor = self.conn.cursor()
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_surah ON verses(surah)",
            "CREATE INDEX IF NOT EXISTS idx_ayah ON verses(ayah)",
            "CREATE INDEX IF NOT EXISTS idx_normalized ON verses(normalized)",
            "CREATE INDEX IF NOT EXISTS idx_length ON verses(length)",
            "CREATE INDEX IF NOT EXISTS idx_surah_ayah ON verses(surah, ayah)",
            "CREATE INDEX IF NOT EXISTS idx_sajdah ON sajdah_verses(surah, ayah)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        self.conn.commit()
        print("[DB] ✅ Indexes created successfully")
    
    def import_from_json(self, json_path: str):
        """
        استيراد البيانات من ملف JSON
        
        Args:
            json_path: مسار ملف quran.json
        """
        print(f"[DB] 📥 Importing data from {json_path}...")
        start_time = time.time()
        
        # تحميل البيانات
        with open(json_path, 'r', encoding='utf-8') as f:
            quran_data = json.load(f)
        
        cursor = self.conn.cursor()
        
        # استيراد الآيات
        from arabic_normalizer import ArabicNormalizer
        normalizer = ArabicNormalizer()
        
        verses_count = 0
        for surah_num, surah_data in quran_data.items():
            surah_num = int(surah_num)
            
            # إدراج معلومات السورة
            surah_name_ar = surah_data.get('name_ar', f'السورة {surah_num}')
            surah_name_en = surah_data.get('name', f'Surah {surah_num}')
            total_verses = len(surah_data.get('ayahs', []))
            
            cursor.execute('''
                INSERT OR REPLACE INTO surahs (number, name_ar, name_en, total_verses)
                VALUES (?, ?, ?, ?)
            ''', (surah_num, surah_name_ar, surah_name_en, total_verses))
            
            # إدراج الآيات
            for ayah_data in surah_data.get('ayahs', []):
                ayah_num = ayah_data.get('number', 0)
                ar = ayah_data.get('ar', '')
                
                # إزالة التشكيل للنسخة البسيطة
                ar_simple = normalizer.remove_diacritics(ar)
                
                # التطبيع الكامل
                normalized = normalizer.full_normalize(ar)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO verses 
                    (surah, ayah, ar, ar_simple, en, fr, nl, normalized, length, word_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    surah_num,
                    ayah_num,
                    ar,
                    ar_simple,
                    ayah_data.get('en', ''),
                    ayah_data.get('fr', ''),
                    ayah_data.get('nl', ''),
                    normalized,
                    len(normalized),
                    len(normalized.split())
                ))
                
                verses_count += 1
        
        # إدراج آيات سجود التلاوة
        sajdah_verses = [
            (7, 206), (13, 15), (16, 50), (17, 109), (19, 58),
            (22, 18), (22, 77), (25, 60), (27, 26), (32, 15),
            (38, 24), (41, 38), (53, 62), (84, 21), (96, 19)
        ]
        
        for surah, ayah in sajdah_verses:
            cursor.execute('''
                INSERT OR IGNORE INTO sajdah_verses (surah, ayah)
                VALUES (?, ?)
            ''', (surah, ayah))
        
        self.conn.commit()
        
        elapsed = time.time() - start_time
        print(f"[DB] ✅ Imported {verses_count} verses in {elapsed:.2f}s")
        
        self.initialized = True
    
    @lru_cache(maxsize=1000)
    def get_verse(self, surah: int, ayah: int) -> Optional[Dict]:
        """
        جلب آية محددة (مع كاش)
        
        Args:
            surah: رقم السورة
            ayah: رقم الآية
        
        Returns:
            بيانات الآية أو None
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM verses WHERE surah = ? AND ayah = ?
        ''', (surah, ayah))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def search_by_normalized(self, normalized_text: str, 
                            surah: Optional[int] = None,
                            limit: int = 10) -> List[Dict]:
        """
        البحث بالنص المطبّع
        
        Args:
            normalized_text: النص المطبّع
            surah: رقم السورة (اختياري)
            limit: عدد النتائج الأقصى
        
        Returns:
            قائمة بالآيات المطابقة
        """
        cursor = self.conn.cursor()
        
        # حساب نطاق الطول
        text_len = len(normalized_text)
        tolerance = max(int(text_len * 0.3), 5)
        min_len = max(1, text_len - tolerance)
        max_len = text_len + tolerance
        
        if surah:
            cursor.execute('''
                SELECT * FROM verses 
                WHERE surah = ? 
                AND length BETWEEN ? AND ?
                AND normalized LIKE ?
                LIMIT ?
            ''', (surah, min_len, max_len, f'%{normalized_text}%', limit))
        else:
            cursor.execute('''
                SELECT * FROM verses 
                WHERE length BETWEEN ? AND ?
                AND normalized LIKE ?
                LIMIT ?
            ''', (min_len, max_len, f'%{normalized_text}%', limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_surah_verses(self, surah: int) -> List[Dict]:
        """
        جلب جميع آيات السورة
        
        Args:
            surah: رقم السورة
        
        Returns:
            قائمة بآيات السورة
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM verses WHERE surah = ? ORDER BY ayah
        ''', (surah,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_surah_info(self, surah: int) -> Optional[Dict]:
        """
        جلب معلومات السورة
        
        Args:
            surah: رقم السورة
        
        Returns:
            معلومات السورة
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM surahs WHERE number = ?
        ''', (surah,))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def is_sajdah_verse(self, surah: int, ayah: int) -> bool:
        """
        التحقق من آية سجدة
        
        Args:
            surah: رقم السورة
            ayah: رقم الآية
        
        Returns:
            True إذا كانت آية سجدة
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM sajdah_verses 
            WHERE surah = ? AND ayah = ?
        ''', (surah, ayah))
        
        return cursor.fetchone()[0] > 0
    
    def get_all_sajdah_verses(self) -> List[Dict]:
        """جلب جميع آيات السجدة"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT s.surah, s.ayah, v.ar, su.name_ar
            FROM sajdah_verses s
            JOIN verses v ON s.surah = v.surah AND s.ayah = v.ayah
            JOIN surahs su ON s.surah = su.number
            ORDER BY s.surah, s.ayah
        ''')
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_stats(self) -> Dict:
        """احصائيات قاعدة البيانات"""
        cursor = self.conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM verses')
        total_verses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM surahs')
        total_surahs = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM sajdah_verses')
        total_sajdah = cursor.fetchone()[0]
        
        # حجم قاعدة البيانات
        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        
        return {
            'total_verses': total_verses,
            'total_surahs': total_surahs,
            'total_sajdah': total_sajdah,
            'db_size_mb': round(db_size / (1024 * 1024), 2),
            'initialized': self.initialized
        }
    
    def close(self):
        """إغلاق الاتصال بقاعدة البيانات"""
        if self.conn:
            self.conn.close()
            print("[DB] 🔒 Database connection closed")


def initialize_database(json_path: str = "data/quran.json", 
                       db_path: str = "data/quran.db",
                       force: bool = False) -> QuranDatabase:
    """
    تهيئة قاعدة البيانات
    
    Args:
        json_path: مسار ملف JSON
        db_path: مسار ملف قاعدة البيانات
        force: إعادة البناء حتى لو كانت موجودة
    
    Returns:
        كائن قاعدة البيانات
    """
    # حذف قاعدة البيانات القديمة إذا كان force=True
    if force and os.path.exists(db_path):
        os.remove(db_path)
        print(f"[DB] 🗑️ Removed old database: {db_path}")
    
    # إنشاء قاعدة البيانات
    db = QuranDatabase(db_path)
    
    # التحقق من وجود الجداول
    needs_init = False
    try:
        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='verses'")
        if not cursor.fetchone():
            needs_init = True
    except:
        needs_init = True
    
    # إذا لم تكن قاعدة البيانات موجودة أو الجداول مفقودة، إنشائها
    if not os.path.exists(db_path) or force or needs_init:
        print("[DB] 🔨 Creating new database...")
        db.create_tables()
        db.create_indexes()
        
        if os.path.exists(json_path):
            db.import_from_json(json_path)
        else:
            print(f"[DB] ⚠️ JSON file not found: {json_path}")
            print(f"[DB] Looking for: {os.path.abspath(json_path)}")
    else:
        print("[DB] ✅ Using existing database")
        db.initialized = True
    
    # طباعة الإحصائيات
    try:
        stats = db.get_stats()
        print(f"[DB] 📊 Database stats:")
        print(f"     • Total verses: {stats['total_verses']}")
        print(f"     • Total surahs: {stats['total_surahs']}")
        print(f"     • Sajdah verses: {stats['total_sajdah']}")
        print(f"     • Database size: {stats['db_size_mb']} MB")
    except Exception as e:
        print(f"[DB] ⚠️ Could not get stats: {e}")
    
    return db


# ==========================================
# اختبار
# ==========================================

if __name__ == "__main__":
    print("="*70)
    print("🗄️ نظام قاعدة البيانات - اختبارات")
    print("="*70)
    
    # تهيئة قاعدة البيانات
    db = initialize_database(
        json_path="data/quran.json",
        db_path="data/quran.db",
        force=False  # غيّر إلى True لإعادة البناء
    )
    
    # اختبار 1: جلب آية
    print("\n📝 اختبار 1: جلب آية محددة")
    print("-" * 70)
    verse = db.get_verse(1, 1)
    if verse:
        print(f"السورة {verse['surah']} - الآية {verse['ayah']}")
        print(f"النص: {verse['ar']}")
        print(f"الترجمة: {verse['en']}")
    
    # اختبار 2: البحث
    print("\n📝 اختبار 2: البحث بالنص")
    print("-" * 70)
    results = db.search_by_normalized("بسم الله", limit=3)
    print(f"عدد النتائج: {len(results)}")
    for r in results:
        print(f"  - سورة {r['surah']}, آية {r['ayah']}: {r['ar'][:50]}...")
    
    # اختبار 3: آيات السجدة
    print("\n📝 اختبار 3: آيات السجدة")
    print("-" * 70)
    sajdah_verses = db.get_all_sajdah_verses()
    print(f"عدد آيات السجدة: {len(sajdah_verses)}")
    for v in sajdah_verses[:5]:
        print(f"  - {v['name_ar']} ({v['surah']}:{v['ayah']})")
    
    # إغلاق
    db.close()
    
    print("\n✅ جميع الاختبارات اكتملت بنجاح!")
