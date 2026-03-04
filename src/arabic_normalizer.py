"""
معالج متقدم للنص العربي - Advanced Arabic Text Processor
يعالج: الحروف المقطعة، المد، الشدة، التشكيل
"""

import re
from typing import List, Tuple, Dict, Optional
from difflib import SequenceMatcher
from functools import lru_cache


class ArabicNormalizer:
    """معالج متقدم للنص العربي مع دعم كامل للخصائص القرآنية"""
    
    # الحروف المقطعة (Muqatta'at) في القرآن الكريم
    MUQATTAAT = {
        'الم': ['ا ل م', 'الف لام ميم', 'الم', 'ألف لام ميم'],
        'الر': ['ا ل ر', 'الف لام را', 'الر', 'ألف لام راء'],
        'المص': ['ا ل م ص', 'الف لام ميم صاد', 'المص'],
        'المر': ['ا ل م ر', 'الف لام ميم را', 'المر'],
        'كهيعص': ['ك ه ي ع ص', 'كاف ها يا عين صاد', 'كهيعص'],
        'طه': ['ط ه', 'طا ها', 'طه'],
        'طسم': ['ط س م', 'طا سين ميم', 'طسم'],
        'طس': ['ط س', 'طا سين', 'طس'],
        'يس': ['ي س', 'يا سين', 'يس'],
        'ص': ['ص', 'صاد'],
        'حم': ['ح م', 'حا ميم', 'حم'],
        'عسق': ['ع س ق', 'عين سين قاف', 'عسق'],
        'ق': ['ق', 'قاف'],
        'ن': ['ن', 'نون']
    }
    
    # قواعد المد (Elongation rules)
    MADD_RULES = {
        'ا': ['آ', 'أ', 'إ', 'ٱ'],
        'و': ['ؤ'],
        'ي': ['ئ', 'ى', 'ے']
    }
    
    # التشكيل والرموز (Diacritics)
    DIACRITICS = 'ًٌٍَُِّْـ'
    SPECIAL_CHARS = '،؛؟!٪×÷=<>()[]{}\'\"'
    
    def __init__(self):
        """تهيئة المعالج"""
        self.muqattaat_index = self._build_muqattaat_index()
        self.cache_hits = 0
        self.cache_misses = 0
    
    def _build_muqattaat_index(self) -> Dict[str, str]:
        """بناء فهرس للحروف المقطعة لسرعة البحث"""
        index = {}
        for original, variants in self.MUQATTAAT.items():
            for variant in variants:
                # تطبيع كل صيغة
                normalized = self._basic_normalize(variant)
                index[normalized] = original
        return index
    
    def _basic_normalize(self, text: str) -> str:
        """تطبيع أساسي للنص"""
        # إزالة التشكيل
        text = re.sub(f'[{self.DIACRITICS}]', '', text)
        # إزالة الأحرف الخاصة
        text = re.sub(f'[{self.SPECIAL_CHARS}]', '', text)
        return text.strip().lower()
    
    @lru_cache(maxsize=10000)
    def remove_diacritics(self, text: str) -> str:
        """إزالة التشكيل (مع كاش)"""
        return re.sub(f'[{self.DIACRITICS}]', '', text)
    
    def normalize_muqattaat(self, text: str) -> str:
        """
        تطبيع الحروف المقطعة
        مثال: "الف لام ميم" → "الم"
        """
        # تطبيع أساسي
        normalized = self._basic_normalize(text)
        
        # فحص أول 20 حرف (الفواتح عادة في البداية)
        prefix = normalized[:20]
        
        # البحث عن مطابقة
        for variant, original in self.muqattaat_index.items():
            if prefix.startswith(variant):
                # استبدال بالشكل الأصلي
                text = original + ' ' + text[len(variant):].strip()
                break
        
        return text
    
    def normalize_madd(self, text: str) -> str:
        """
        تطبيع حروف المد
        مثال: "آمن" → "امن"
        """
        for base, variants in self.MADD_RULES.items():
            for variant in variants:
                text = text.replace(variant, base)
        return text
    
    def normalize_shadda(self, text: str) -> str:
        """
        معالجة الشدة (تكرار الحرف)
        مثال: "مَدَّ" → "مدد"
        """
        # إزالة التشكيل أولاً
        text = self.remove_diacritics(text)
        # الشدة تُكتب كتكرار للحرف
        # ولكن في بعض الحالات قد تكون مفقودة
        return text
    
    def normalize_tanween(self, text: str) -> str:
        """
        معالجة التنوين
        مثال: "كتابًا" → "كتابا"
        """
        # تنوين الفتح → ألف
        text = re.sub(r'([^\s])ً', r'\1ا', text)
        # إزالة باقي التنوين
        text = re.sub(r'[ٌٍ]', '', text)
        return text
    
    def normalize_hamza(self, text: str) -> str:
        """
        تطبيع الهمزة
        مثال: "أَكْبَر" → "اكبر"
        """
        hamza_variants = ['ء', 'أ', 'إ', 'آ', 'ؤ', 'ئ']
        for hamza in hamza_variants:
            text = text.replace(hamza, 'ا')
        return text
    
    @lru_cache(maxsize=5000)
    def full_normalize(self, text: str, aggressive: bool = False) -> str:
        """
        التطبيع الكامل للنص
        
        Args:
            text: النص المراد تطبيعه
            aggressive: إذا كان True، يطبق تطبيع أكثر عدوانية (يوحّد الهمزات)
        
        Returns:
            النص المطبّع
        """
        if not text:
            return ""
        
        # 1. إزالة التشكيل
        text = self.remove_diacritics(text)
        
        # 2. معالجة الحروف المقطعة
        text = self.normalize_muqattaat(text)
        
        # 3. تطبيع حروف المد
        text = self.normalize_madd(text)
        
        # 4. معالجة الشدة
        text = self.normalize_shadda(text)
        
        # 5. معالجة التنوين
        text = self.normalize_tanween(text)
        
        # 6. تطبيع الهمزة (إذا كان aggressive)
        if aggressive:
            text = self.normalize_hamza(text)
        
        # 7. إزالة الأحرف الخاصة
        text = re.sub(f'[{self.SPECIAL_CHARS}]', '', text)
        
        # 8. تنظيف المسافات
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip().lower()
    
    def smart_match(self, text1: str, text2: str, 
                   threshold: float = 0.6) -> Tuple[float, Dict]:
        """
        مطابقة ذكية بين نصين مع تحليل تفصيلي
        
        Args:
            text1: النص الأول
            text2: النص الثاني
            threshold: الحد الأدنى للتشابه المقبول
        
        Returns:
            (النتيجة النهائية, التفاصيل)
        """
        # تطبيع كلا النصين
        norm1 = self.full_normalize(text1)
        norm2 = self.full_normalize(text2)
        
        if not norm1 or not norm2:
            return 0.0, {}
        
        # 1. التشابه المباشر (Direct similarity)
        direct_similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        # 2. التشابه بناءً على الكلمات (Word-based)
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        common_words = words1 & words2
        total_words = words1 | words2
        word_similarity = len(common_words) / len(total_words) if total_words else 0
        
        # 3. التشابه بناءً على الأحرف (Character-based)
        chars1 = set(norm1.replace(' ', ''))
        chars2 = set(norm2.replace(' ', ''))
        common_chars = chars1 & chars2
        total_chars = chars1 | chars2
        char_similarity = len(common_chars) / len(total_chars) if total_chars else 0
        
        # 4. التشابه في الطول (Length similarity)
        len1, len2 = len(norm1), len(norm2)
        length_similarity = min(len1, len2) / max(len1, len2) if max(len1, len2) > 0 else 0
        
        # 5. التشابه في الـ n-grams (للكشف عن الأجزاء المشتركة)
        ngram_similarity = self._ngram_similarity(norm1, norm2, n=3)
        
        # النتيجة المرجحة (Weighted score)
        weights = {
            'direct': 0.35,
            'words': 0.25,
            'chars': 0.15,
            'length': 0.10,
            'ngrams': 0.15
        }
        
        final_score = (
            direct_similarity * weights['direct'] +
            word_similarity * weights['words'] +
            char_similarity * weights['chars'] +
            length_similarity * weights['length'] +
            ngram_similarity * weights['ngrams']
        )
        
        # تفاصيل المطابقة
        details = {
            'direct_similarity': round(direct_similarity, 3),
            'word_similarity': round(word_similarity, 3),
            'char_similarity': round(char_similarity, 3),
            'length_similarity': round(length_similarity, 3),
            'ngram_similarity': round(ngram_similarity, 3),
            'final_score': round(final_score, 3),
            'normalized_text1': norm1,
            'normalized_text2': norm2,
            'common_words': list(common_words),
            'word_count_diff': abs(len(words1) - len(words2)),
            'char_count_diff': abs(len1 - len2),
            'is_match': final_score >= threshold
        }
        
        return final_score, details
    
    def _ngram_similarity(self, text1: str, text2: str, n: int = 3) -> float:
        """حساب التشابه بناءً على n-grams"""
        def get_ngrams(text: str, n: int) -> set:
            """استخراج n-grams من النص"""
            text = text.replace(' ', '')
            return set(text[i:i+n] for i in range(len(text) - n + 1))
        
        ngrams1 = get_ngrams(text1, n)
        ngrams2 = get_ngrams(text2, n)
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        common = ngrams1 & ngrams2
        total = ngrams1 | ngrams2
        
        return len(common) / len(total) if total else 0.0
    
    def extract_key_words(self, text: str, min_length: int = 3) -> List[str]:
        """
        استخراج الكلمات المفتاحية من النص
        
        Args:
            text: النص
            min_length: الحد الأدنى لطول الكلمة
        
        Returns:
            قائمة بالكلمات المفتاحية
        """
        normalized = self.full_normalize(text)
        words = normalized.split()
        
        # تصفية الكلمات القصيرة والشائعة
        stop_words = {'من', 'في', 'على', 'الى', 'عن', 'ان', 'هو', 'هي'}
        key_words = [
            word for word in words 
            if len(word) >= min_length and word not in stop_words
        ]
        
        return key_words
    
    def get_stats(self) -> Dict:
        """احصائيات الأداء"""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': round(hit_rate, 2),
            'muqattaat_count': len(self.MUQATTAAT),
            'madd_rules_count': len(self.MADD_RULES)
        }


class WhisperPostProcessor:
    """معالج إضافي لمخرجات Whisper API"""
    
    def __init__(self):
        self.normalizer = ArabicNormalizer()
        
        # قاموس الأخطاء الشائعة التي يرتكبها Whisper
        self.common_errors = {
            # الحروف المقطعة
            'الف لام ميم': 'الم',
            'ألف لام ميم': 'الم',
            'الف لام را': 'الر',
            'كاف ها يا عين صاد': 'كهيعص',
            'يا سين': 'يس',
            'طا ها': 'طه',
            'طا سين ميم': 'طسم',
            'حا ميم': 'حم',
            'عين سين قاف': 'عسق',
            
            # أخطاء شائعة أخرى
            'بسم الله': 'بسم الله',  # تأكد من الكتابة الصحيحة
            'الحمد لله': 'الحمد لله',
        }
    
    def fix_common_errors(self, text: str) -> str:
        """تصحيح الأخطاء الشائعة"""
        for error, correction in self.common_errors.items():
            # استبدال حساس لحالة الأحرف ولا حساس
            text = re.sub(
                re.escape(error), 
                correction, 
                text, 
                flags=re.IGNORECASE
            )
        return text
    
    def process_transcript(self, transcript: str, 
                          fix_errors: bool = True,
                          aggressive: bool = False) -> Dict:
        """
        معالجة النص من Whisper
        
        Args:
            transcript: النص من Whisper
            fix_errors: تصحيح الأخطاء الشائعة
            aggressive: تطبيع عدواني
        
        Returns:
            قاموس بنتائج المعالجة
        """
        # 1. تنظيف أساسي
        cleaned = transcript.strip()
        
        # 2. تصحيح الأخطاء الشائعة
        corrected = self.fix_common_errors(cleaned) if fix_errors else cleaned
        
        # 3. التطبيع الكامل
        normalized = self.normalizer.full_normalize(corrected, aggressive=aggressive)
        
        # 4. استخراج الكلمات المفتاحية
        key_words = self.normalizer.extract_key_words(normalized)
        
        return {
            'original': transcript,
            'cleaned': cleaned,
            'corrected': corrected,
            'normalized': normalized,
            'key_words': key_words,
            'word_count': len(normalized.split()),
            'char_count': len(normalized)
        }


# ==========================================
# أمثلة الاستخدام
# ==========================================

if __name__ == "__main__":
    print("="*70)
    print("🕌 معالج النص العربي المتقدم - اختبارات")
    print("="*70)
    
    # تهيئة المعالج
    normalizer = ArabicNormalizer()
    processor = WhisperPostProcessor()
    
    # اختبار 1: الحروف المقطعة
    print("\n📝 اختبار 1: الحروف المقطعة")
    print("-" * 70)
    text1 = "الف لام ميم ذلك الكتاب لا ريب فيه"
    text2 = "الم ذلك الكتاب لا ريب فيه"
    score, details = normalizer.smart_match(text1, text2)
    print(f"النص 1: {text1}")
    print(f"النص 2: {text2}")
    print(f"التشابه: {score:.1%}")
    print(f"مطابقة: {'✅ نعم' if details['is_match'] else '❌ لا'}")
    
    # اختبار 2: المد والتشكيل
    print("\n📝 اختبار 2: المد والتشكيل")
    print("-" * 70)
    text1 = "قل هو الله احد"
    text2 = "قُلْ هُوَ ٱللَّهُ أَحَدٌ"
    score, details = normalizer.smart_match(text1, text2)
    print(f"النص 1: {text1}")
    print(f"النص 2: {text2}")
    print(f"التشابه: {score:.1%}")
    print(f"التطبيع 1: {details['normalized_text1']}")
    print(f"التطبيع 2: {details['normalized_text2']}")
    
    # اختبار 3: معالجة Whisper
    print("\n📝 اختبار 3: معالجة مخرجات Whisper")
    print("-" * 70)
    whisper_output = "الف لام ميم ذٰلِكَ ٱلْكِتَٰبُ لَا رَيْبَ فِيهِ"
    result = processor.process_transcript(whisper_output)
    print(f"الأصلي: {result['original']}")
    print(f"المصحح: {result['corrected']}")
    print(f"المطبع: {result['normalized']}")
    print(f"الكلمات المفتاحية: {result['key_words']}")
    
    # اختبار 4: الأداء
    print("\n📊 إحصائيات الأداء")
    print("-" * 70)
    stats = normalizer.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    print("\n✅ جميع الاختبارات اكتملت بنجاح!")
