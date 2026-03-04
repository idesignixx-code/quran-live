"""
نظام الكاش المتقدم - Advanced Caching System
يدعم Redis وذاكرة محلية كبديل
"""

import json
import time
from typing import Optional, Dict, Any, List
from functools import lru_cache
from collections import OrderedDict
import threading


class LocalCache:
    """كاش محلي بديل عن Redis (LRU Cache)"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """
        تهيئة الكاش المحلي
        
        Args:
            max_size: الحد الأقصى لعدد العناصر
            ttl: مدة الصلاحية بالثواني
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache = OrderedDict()
        self.timestamps = {}
        self.lock = threading.Lock()
        
        # إحصائيات
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        جلب قيمة من الكاش
        
        Args:
            key: المفتاح
        
        Returns:
            القيمة أو None
        """
        with self.lock:
            if key in self.cache:
                # التحقق من انتهاء الصلاحية
                if time.time() - self.timestamps[key] > self.ttl:
                    # منتهي الصلاحية
                    del self.cache[key]
                    del self.timestamps[key]
                    self.misses += 1
                    return None
                
                # نقل إلى النهاية (LRU)
                self.cache.move_to_end(key)
                self.hits += 1
                
                # فك التشفير JSON
                try:
                    return json.loads(self.cache[key])
                except:
                    return self.cache[key]
            
            self.misses += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        حفظ قيمة في الكاش
        
        Args:
            key: المفتاح
            value: القيمة
            ttl: مدة الصلاحية (اختياري)
        
        Returns:
            True إذا نجحت العملية
        """
        with self.lock:
            # تشفير JSON
            try:
                serialized = json.dumps(value)
            except:
                serialized = str(value)
            
            # إضافة/تحديث
            self.cache[key] = serialized
            self.timestamps[key] = time.time()
            self.cache.move_to_end(key)
            
            # حذف الأقدم إذا تجاوز الحد
            while len(self.cache) > self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
                self.evictions += 1
            
            return True
    
    def delete(self, key: str) -> bool:
        """حذف مفتاح"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                del self.timestamps[key]
                return True
            return False
    
    def clear(self):
        """مسح جميع البيانات"""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()
    
    def get_stats(self) -> Dict:
        """احصائيات الكاش"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            'type': 'local',
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'evictions': self.evictions,
            'hit_rate': round(hit_rate, 2)
        }


class RedisCache:
    """كاش Redis (إذا كان متوفراً)"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, 
                 db: int = 0, ttl: int = 3600):
        """
        تهيئة Redis
        
        Args:
            host: عنوان الخادم
            port: المنفذ
            db: رقم قاعدة البيانات
            ttl: مدة الصلاحية الافتراضية
        """
        self.ttl = ttl
        self.redis = None
        
        try:
            import redis
            self.redis = redis.Redis(
                host=host, 
                port=port, 
                db=db,
                decode_responses=True
            )
            # اختبار الاتصال
            self.redis.ping()
            print(f"[CACHE] ✅ Connected to Redis at {host}:{port}")
        except Exception as e:
            print(f"[CACHE] ⚠️ Redis not available: {e}")
            self.redis = None
    
    def is_available(self) -> bool:
        """التحقق من توفر Redis"""
        return self.redis is not None
    
    def get(self, key: str) -> Optional[Any]:
        """جلب قيمة"""
        if not self.redis:
            return None
        
        try:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            print(f"[CACHE] Error getting key {key}: {e}")
        
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """حفظ قيمة"""
        if not self.redis:
            return False
        
        try:
            serialized = json.dumps(value)
            exp_time = ttl if ttl else self.ttl
            self.redis.setex(key, exp_time, serialized)
            return True
        except Exception as e:
            print(f"[CACHE] Error setting key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """حذف مفتاح"""
        if not self.redis:
            return False
        
        try:
            self.redis.delete(key)
            return True
        except:
            return False
    
    def clear(self):
        """مسح جميع المفاتيح"""
        if self.redis:
            self.redis.flushdb()
    
    def get_stats(self) -> Dict:
        """احصائيات Redis"""
        if not self.redis:
            return {'type': 'redis', 'available': False}
        
        try:
            info = self.redis.info('stats')
            return {
                'type': 'redis',
                'available': True,
                'keys': self.redis.dbsize(),
                'hits': info.get('keyspace_hits', 0),
                'misses': info.get('keyspace_misses', 0)
            }
        except:
            return {'type': 'redis', 'available': False}


class CacheManager:
    """مدير الكاش الموحد - يختار تلقائياً بين Redis والكاش المحلي"""
    
    def __init__(self, use_redis: bool = True, 
                 redis_host: str = 'localhost',
                 redis_port: int = 6379,
                 local_max_size: int = 1000,
                 ttl: int = 3600):
        """
        تهيئة مدير الكاش
        
        Args:
            use_redis: محاولة استخدام Redis
            redis_host: عنوان Redis
            redis_port: منفذ Redis
            local_max_size: حجم الكاش المحلي
            ttl: مدة الصلاحية
        """
        self.ttl = ttl
        self.cache = None
        
        # محاولة استخدام Redis أولاً
        if use_redis:
            redis_cache = RedisCache(redis_host, redis_port, ttl=ttl)
            if redis_cache.is_available():
                self.cache = redis_cache
                self.cache_type = 'redis'
                print("[CACHE] 🚀 Using Redis cache")
                return
        
        # استخدام الكاش المحلي كبديل
        self.cache = LocalCache(max_size=local_max_size, ttl=ttl)
        self.cache_type = 'local'
        print(f"[CACHE] 💾 Using local cache (max_size={local_max_size})")
    
    def get(self, key: str) -> Optional[Any]:
        """جلب قيمة"""
        return self.cache.get(key)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """حفظ قيمة"""
        return self.cache.set(key, value, ttl)
    
    def delete(self, key: str) -> bool:
        """حذف مفتاح"""
        return self.cache.delete(key)
    
    def clear(self):
        """مسح الكاش"""
        self.cache.clear()
    
    def get_stats(self) -> Dict:
        """احصائيات الكاش"""
        return self.cache.get_stats()
    
    # ========================================
    # دوال مساعدة خاصة بالقرآن
    # ========================================
    
    def get_verse(self, surah: int, ayah: int, lang: str = 'ar') -> Optional[Dict]:
        """
        جلب آية من الكاش
        
        Args:
            surah: رقم السورة
            ayah: رقم الآية
            lang: اللغة
        
        Returns:
            بيانات الآية
        """
        key = f"verse:{surah}:{ayah}:{lang}"
        return self.get(key)
    
    def set_verse(self, surah: int, ayah: int, verse_data: Dict, 
                  lang: str = 'ar', ttl: Optional[int] = None) -> bool:
        """
        حفظ آية في الكاش
        
        Args:
            surah: رقم السورة
            ayah: رقم الآية
            verse_data: بيانات الآية
            lang: اللغة
            ttl: مدة الصلاحية
        
        Returns:
            True إذا نجحت العملية
        """
        key = f"verse:{surah}:{ayah}:{lang}"
        return self.set(key, verse_data, ttl)
    
    def get_surah(self, surah: int) -> Optional[List[Dict]]:
        """جلب سورة كاملة"""
        key = f"surah:{surah}"
        return self.get(key)
    
    def set_surah(self, surah: int, verses: List[Dict], 
                  ttl: Optional[int] = None) -> bool:
        """حفظ سورة كاملة"""
        key = f"surah:{surah}"
        return self.set(key, verses, ttl)
    
    def preload_surah(self, surah: int, verses: List[Dict]) -> int:
        """
        تحميل سورة كاملة مسبقاً في الكاش
        
        Args:
            surah: رقم السورة
            verses: قائمة الآيات
        
        Returns:
            عدد الآيات المحملة
        """
        count = 0
        
        # حفظ السورة كاملة
        self.set_surah(surah, verses)
        
        # حفظ كل آية على حدة
        for verse in verses:
            ayah = verse.get('ayah', 0)
            self.set_verse(surah, ayah, verse)
            count += 1
        
        return count
    
    def get_translation(self, surah: int, ayah: int, lang: str) -> Optional[str]:
        """
        جلب ترجمة محددة
        
        Args:
            surah: رقم السورة
            ayah: رقم الآية
            lang: اللغة
        
        Returns:
            نص الترجمة
        """
        verse = self.get_verse(surah, ayah)
        if verse:
            return verse.get(lang)
        return None


# ==========================================
# اختبار
# ==========================================

if __name__ == "__main__":
    print("="*70)
    print("💾 نظام الكاش المتقدم - اختبارات")
    print("="*70)
    
    # تهيئة مدير الكاش
    cache = CacheManager(
        use_redis=True,  # سيحاول Redis أولاً
        local_max_size=100,
        ttl=3600
    )
    
    # اختبار 1: حفظ وجلب
    print("\n📝 اختبار 1: حفظ وجلب آية")
    print("-" * 70)
    
    verse_data = {
        'surah': 1,
        'ayah': 1,
        'ar': 'بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ',
        'en': 'In the name of Allah, the Most Gracious, the Most Merciful'
    }
    
    # حفظ
    cache.set_verse(1, 1, verse_data)
    print("✅ تم حفظ الآية")
    
    # جلب
    cached_verse = cache.get_verse(1, 1)
    if cached_verse:
        print(f"✅ تم جلب الآية من الكاش:")
        print(f"   {cached_verse['ar']}")
    
    # اختبار 2: قياس السرعة
    print("\n📝 اختبار 2: قياس السرعة")
    print("-" * 70)
    
    # حفظ 100 آية
    start = time.time()
    for i in range(1, 101):
        cache.set(f"test:{i}", {'number': i, 'text': f'test verse {i}'})
    save_time = (time.time() - start) * 1000
    print(f"⏱️  حفظ 100 آية: {save_time:.2f}ms")
    
    # جلب 100 آية
    start = time.time()
    for i in range(1, 101):
        cache.get(f"test:{i}")
    fetch_time = (time.time() - start) * 1000
    print(f"⏱️  جلب 100 آية: {fetch_time:.2f}ms")
    
    # اختبار 3: الإحصائيات
    print("\n📝 اختبار 3: الإحصائيات")
    print("-" * 70)
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"  • {key}: {value}")
    
    print("\n✅ جميع الاختبارات اكتملت بنجاح!")
