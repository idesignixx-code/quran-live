"""
نظام المطابقة المحسّن - Enhanced Matching System
يستخدم: Database + Cache + Arabic Normalizer + Sequential Prediction
"""

import time
from typing import Optional, Dict, List, Tuple
from difflib import SequenceMatcher

# استيراد المكونات
from arabic_normalizer import ArabicNormalizer, WhisperPostProcessor
from database import QuranDatabase
from cache import CacheManager


class EnhancedMatcher:
    """نظام مطابقة محسّن مع جميع التحسينات"""
    
    def __init__(self, db: QuranDatabase, cache: CacheManager):
        """
        تهيئة النظام
        
        Args:
            db: قاعدة البيانات
            cache: مدير الكاش
        """
        self.db = db
        self.cache = cache
        self.normalizer = ArabicNormalizer()
        self.processor = WhisperPostProcessor()
        
        # حالة التنبؤ التسلسلي
        self.current_surah = None
        self.last_ayah = None
        self.consecutive_matches = 0
        
        # إحصائيات الأداء
        self.stats = {
            'total_matches': 0,
            'cache_hits': 0,
            'db_queries': 0,
            'sequential_predictions': 0,
            'failed_matches': 0,
            'avg_response_time': 0.0,
            'total_time': 0.0
        }
        
        print("[MATCHER] ✅ Enhanced matcher initialized")
    
    def match_verse(self, text: str, surah: Optional[int] = None,
                   use_aggressive: bool = False) -> Dict:
        """
        مطابقة آية من النص
        
        Args:
            text: النص المعترف عليه
            surah: رقم السورة (اختياري للتصفية)
            use_aggressive: استخدام تطبيع عدواني
        
        Returns:
            نتيجة المطابقة
        """
        start_time = time.time()
        
        # معالجة النص
        processed = self.processor.process_transcript(
            text, 
            aggressive=use_aggressive
        )
        normalized_text = processed['normalized']
        
        if not normalized_text or len(normalized_text) < 3:
            return self._no_match_result("text_too_short", start_time)
        
        # المرحلة 1: التنبؤ التسلسلي
        if self.current_surah and self.last_ayah:
            predicted_verse = self._try_sequential_prediction(normalized_text)
            if predicted_verse:
                self.stats['sequential_predictions'] += 1
                return self._success_result(
                    predicted_verse, 
                    1.0, 
                    "sequential_prediction",
                    start_time
                )
        
        # المرحلة 2: البحث في الكاش
        cached_result = self._search_in_cache(normalized_text, surah)
        if cached_result:
            self.stats['cache_hits'] += 1
            return cached_result
        
        # المرحلة 3: البحث في قاعدة البيانات
        db_result = self._search_in_database(normalized_text, surah)
        if db_result:
            self.stats['db_queries'] += 1
            return db_result
        
        # فشل المطابقة
        self.stats['failed_matches'] += 1
        return self._no_match_result("no_match_found", start_time)
    
    def _try_sequential_prediction(self, normalized_text: str) -> Optional[Dict]:
        """
        محاولة التنبؤ التسلسلي (الآية التالية المتوقعة)
        
        Args:
            normalized_text: النص المطبّع
        
        Returns:
            الآية المتنبأ بها أو None
        """
        # الآية المتوقعة
        expected_surah = self.current_surah
        expected_ayah = self.last_ayah + 1
        
        # جلب من الكاش أولاً
        expected_verse = self.cache.get_verse(expected_surah, expected_ayah)
        
        # إذا لم تكن في الكاش، جلب من قاعدة البيانات
        if not expected_verse:
            expected_verse = self.db.get_verse(expected_surah, expected_ayah)
        
        if not expected_verse:
            # انتهت السورة، إعادة تعيين
            self.current_surah = None
            self.last_ayah = None
            self.consecutive_matches = 0
            return None
        
        # مقارنة مع النص
        score, _ = self.normalizer.smart_match(
            normalized_text,
            expected_verse['normalized']
        )
        
        # إذا كانت المطابقة عالية
        if score >= 0.7:
            self.last_ayah = expected_ayah
            self.consecutive_matches += 1
            
            # حفظ في الكاش
            self.cache.set_verse(expected_surah, expected_ayah, expected_verse)
            
            return expected_verse
        
        return None
    
    def _search_in_cache(self, normalized_text: str, 
                        surah: Optional[int]) -> Optional[Dict]:
        """
        البحث في الكاش
        
        Args:
            normalized_text: النص المطبّع
            surah: رقم السورة
        
        Returns:
            نتيجة من الكاش أو None
        """
        # إذا كانت السورة محددة، جلب آياتها من الكاش
        if surah:
            cached_surah = self.cache.get_surah(surah)
            if cached_surah:
                return self._find_in_verses(
                    normalized_text, 
                    cached_surah,
                    "cache_hit"
                )
        
        return None
    
    def _search_in_database(self, normalized_text: str,
                           surah: Optional[int]) -> Optional[Dict]:
        """
        البحث في قاعدة البيانات
        
        Args:
            normalized_text: النص المطبّع
            surah: رقم السورة
        
        Returns:
            نتيجة من قاعدة البيانات أو None
        """
        start_time = time.time()
        
        # البحث بالنص المطبّع
        candidates = self.db.search_by_normalized(
            normalized_text,
            surah=surah,
            limit=20
        )
        
        if not candidates:
            return None
        
        # إيجاد أفضل مطابقة
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            score, _ = self.normalizer.smart_match(
                normalized_text,
                candidate['normalized']
            )
            
            if score > best_score:
                best_score = score
                best_match = candidate
            
            # توقف مبكر عند ثقة عالية جداً
            if score > 0.95:
                break
        
        if best_match and best_score >= 0.6:
            # حفظ في الكاش
            self.cache.set_verse(
                best_match['surah'],
                best_match['ayah'],
                best_match
            )
            
            # تحديث حالة التنبؤ
            self.current_surah = best_match['surah']
            self.last_ayah = best_match['ayah']
            self.consecutive_matches = 1
            
            return self._success_result(
                best_match,
                best_score,
                "database_match",
                start_time
            )
        
        return None
    
    def _find_in_verses(self, normalized_text: str, 
                       verses: List[Dict],
                       source: str) -> Optional[Dict]:
        """
        البحث في قائمة آيات
        
        Args:
            normalized_text: النص المطبّع
            verses: قائمة الآيات
            source: مصدر البيانات
        
        Returns:
            نتيجة أو None
        """
        best_match = None
        best_score = 0.0
        
        for verse in verses:
            score, _ = self.normalizer.smart_match(
                normalized_text,
                verse['normalized']
            )
            
            if score > best_score:
                best_score = score
                best_match = verse
            
            if score > 0.95:
                break
        
        if best_match and best_score >= 0.6:
            return self._success_result(
                best_match,
                best_score,
                source,
                time.time()
            )
        
        return None
    
    def _success_result(self, verse: Dict, confidence: float,
                       source: str, start_time: float) -> Dict:
        """
        تكوين نتيجة ناجحة
        
        Args:
            verse: بيانات الآية
            confidence: مستوى الثقة
            source: مصدر المطابقة
            start_time: وقت البدء
        
        Returns:
            نتيجة المطابقة
        """
        elapsed_ms = (time.time() - start_time) * 1000
        
        # تحديث الإحصائيات
        self.stats['total_matches'] += 1
        self.stats['total_time'] += elapsed_ms
        self.stats['avg_response_time'] = (
            self.stats['total_time'] / self.stats['total_matches']
        )
        
        # التنبؤ بالآيات التالية
        next_verses = self._predict_next_verses(
            verse['surah'],
            verse['ayah'],
            count=3
        )
        
        return {
            'status': 'success',
            'source': source,
            'matched_verse': verse,
            'confidence': round(confidence, 3),
            'next_verses': next_verses,
            'response_time_ms': round(elapsed_ms, 2),
            'consecutive_matches': self.consecutive_matches
        }
    
    def _no_match_result(self, reason: str, start_time: float) -> Dict:
        """نتيجة عدم المطابقة"""
        elapsed_ms = (time.time() - start_time) * 1000
        
        self.stats['total_matches'] += 1
        self.stats['total_time'] += elapsed_ms
        
        return {
            'status': 'no_match',
            'reason': reason,
            'response_time_ms': round(elapsed_ms, 2)
        }
    
    def _predict_next_verses(self, surah: int, ayah: int, 
                           count: int = 3) -> List[Dict]:
        """
        التنبؤ بالآيات التالية
        
        Args:
            surah: رقم السورة
            ayah: رقم الآية
            count: عدد الآيات المطلوبة
        
        Returns:
            قائمة الآيات التالية
        """
        next_verses = []
        
        for i in range(1, count + 1):
            next_ayah = ayah + i
            
            # جلب من الكاش أولاً
            verse = self.cache.get_verse(surah, next_ayah)
            
            # إذا لم تكن في الكاش، جلب من قاعدة البيانات
            if not verse:
                verse = self.db.get_verse(surah, next_ayah)
            
            if verse:
                next_verses.append(verse)
                # حفظ في الكاش للاستخدام المستقبلي
                self.cache.set_verse(surah, next_ayah, verse)
            else:
                # انتهت السورة
                break
        
        return next_verses
    
    def set_surah(self, surah: int):
        """
        تعيين السورة الحالية (للتنبؤ التسلسلي)
        
        Args:
            surah: رقم السورة
        """
        self.current_surah = surah
        self.last_ayah = 0
        self.consecutive_matches = 0
        
        # تحميل السورة مسبقاً في الكاش
        verses = self.db.get_surah_verses(surah)
        if verses:
            count = self.cache.preload_surah(surah, verses)
            print(f"[MATCHER] 📥 Preloaded {count} verses from Surah {surah}")
    
    def reset(self):
        """إعادة تعيين الحالة"""
        self.current_surah = None
        self.last_ayah = None
        self.consecutive_matches = 0
        print("[MATCHER] 🔄 State reset")
    
    def get_stats(self) -> Dict:
        """احصائيات الأداء"""
        total = self.stats['total_matches']
        success_rate = 0.0
        if total > 0:
            success_rate = (
                (total - self.stats['failed_matches']) / total * 100
            )
        
        return {
            'total_matches': total,
            'cache_hits': self.stats['cache_hits'],
            'db_queries': self.stats['db_queries'],
            'sequential_predictions': self.stats['sequential_predictions'],
            'failed_matches': self.stats['failed_matches'],
            'success_rate': round(success_rate, 2),
            'avg_response_time_ms': round(self.stats['avg_response_time'], 2),
            'consecutive_matches': self.consecutive_matches,
            'current_surah': self.current_surah,
            'last_ayah': self.last_ayah
        }
    
    def print_stats(self):
        """طباعة الإحصائيات"""
        stats = self.get_stats()
        
        print("\n" + "="*70)
        print("📊 إحصائيات المطابقة")
        print("="*70)
        print(f"إجمالي المطابقات:        {stats['total_matches']}")
        print(f"من الكاش:                {stats['cache_hits']}")
        print(f"من قاعدة البيانات:       {stats['db_queries']}")
        print(f"تنبؤات تسلسلية:         {stats['sequential_predictions']}")
        print(f"فشل المطابقة:            {stats['failed_matches']}")
        print(f"معدل النجاح:             {stats['success_rate']:.1f}%")
        print(f"متوسط وقت الاستجابة:     {stats['avg_response_time_ms']:.2f}ms")
        print(f"السورة الحالية:          {stats['current_surah'] or 'غير محدد'}")
        print(f"آخر آية:                 {stats['last_ayah'] or 'غير محدد'}")
        print("="*70)


# ==========================================
# اختبار
# ==========================================

if __name__ == "__main__":
    print("="*70)
    print("🎯 نظام المطابقة المحسّن - اختبارات")
    print("="*70)
    
    # تهيئة المكونات
    from database import initialize_database
    
    db = initialize_database(
        json_path="../data/quran.json",
        db_path="../data/quran.db"
    )
    
    cache = CacheManager(use_redis=False, local_max_size=500)
    
    matcher = EnhancedMatcher(db, cache)
    
    # اختبار 1: مطابقة آية
    print("\n📝 اختبار 1: مطابقة آية من سورة الفاتحة")
    print("-" * 70)
    
    text = "بسم الله الرحمن الرحيم"
    result = matcher.match_verse(text)
    
    if result['status'] == 'success':
        verse = result['matched_verse']
        print(f"✅ تم العثور على الآية:")
        print(f"   السورة: {verse['surah']}, الآية: {verse['ayah']}")
        print(f"   النص: {verse['ar']}")
        print(f"   الثقة: {result['confidence']:.1%}")
        print(f"   المصدر: {result['source']}")
        print(f"   الوقت: {result['response_time_ms']:.2f}ms")
    else:
        print(f"❌ فشلت المطابقة: {result['reason']}")
    
    # اختبار 2: تنبؤ تسلسلي
    print("\n📝 اختبار 2: التنبؤ التسلسلي")
    print("-" * 70)
    
    matcher.set_surah(1)  # سورة الفاتحة
    
    verses_to_test = [
        "بسم الله الرحمن الرحيم",
        "الحمد لله رب العالمين",
        "الرحمن الرحيم"
    ]
    
    for text in verses_to_test:
        result = matcher.match_verse(text)
        if result['status'] == 'success':
            v = result['matched_verse']
            print(f"✅ {v['surah']}:{v['ayah']} - {result['source']}")
        time.sleep(0.1)
    
    # اختبار 3: الأداء
    print("\n📝 اختبار 3: اختبار الأداء")
    print("-" * 70)
    
    test_texts = [
        "قل هو الله احد",
        "الله الصمد",
        "لم يلد ولم يولد"
    ]
    
    start = time.time()
    for text in test_texts:
        matcher.match_verse(text)
    total_time = (time.time() - start) * 1000
    
    print(f"⏱️  معالجة 3 آيات: {total_time:.2f}ms")
    print(f"⏱️  متوسط الوقت: {total_time/3:.2f}ms لكل آية")
    
    # طباعة الإحصائيات
    matcher.print_stats()
    
    # إغلاق
    db.close()
    
    print("\n✅ جميع الاختبارات اكتملت بنجاح!")
